"""Opt-in one-shot diagnostic against an ALREADY INSTALLED local Ollama model.

Never pulls a model or contacts external endpoints. Uses 2 CPU threads, no GPU,
16 calls maximum, 180-second request-loop deadline. Not the 200-case independent
study; no training. Model alias drift is checked before/after, not attested by
Ollama. A serving identity race is not ruled out. Failed attempts stay visible.
"""
from datetime import datetime, timezone
from hashlib import sha256
import argparse
import json
import os
from pathlib import Path
import re
import time
import urllib.request
import evaluation_contract as ec

URL = "http://127.0.0.1:11434"


def request(path, value=None, timeout=10):
    req = urllib.request.Request(URL + path, data=None if value is None else ec.canonical(value),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read(500001)
    if len(raw) > 500000:
        raise ValueError("RESPONSE_BUDGET")
    return json.loads(raw)


def save(path, value):
    raw = ec.canonical(value)
    temp = path.with_name(path.name + '.tmp')
    with temp.open('xb') as handle:
        handle.write(raw); handle.flush(); os.fsync(handle.fileno())
    temp.rename(path)
    if path.read_bytes() != raw:
        raise ValueError("READBACK_FAILED")


def parse_decision(text):
    if type(text) is not str or len(text.encode()) > 1024:
        raise ValueError("OUTPUT_BUDGET")
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out: raise ValueError("DUPLICATE_OUTPUT_KEY")
            out[key] = value
        return out
    result = json.loads(text, object_pairs_hook=pairs)
    if type(result) is not dict or set(result) != {"decision"} or result["decision"] not in ec.DECISIONS:
        raise ValueError("OUTPUT_SCHEMA")
    return result["decision"]


def tasks():
    # Fixed developer-authored integration controls, deliberately not blind holdout.
    return [
        {"id":"graph-cycle", "family":"F4", "expected":"UNSUPPORTED",
         "question":"For the finite directed graph with edges [[0,1],[1,0]], the graph is acyclic. Is this claim supported?"},
        {"id":"queue-control", "family":"F7", "expected":"SUPPORTED",
         "question":"A queue begins empty. Send message 7 once, then deliver its front once. There are no other operations. Message 7 is delivered exactly once in this finite trace. Is this claim supported?"},
        {"id":"rank-control", "family":"F18", "expected":"SUPPORTED",
         "question":"Over GF(257), six surviving linear-encoding rows are exactly the six rows of the 6 by 6 identity matrix. These rows uniquely determine all six payload coordinates. Is this claim supported?"},
        {"id":"reset-boundary", "family":"F22", "expected":"UNSUPPORTED",
         "question":"A local counter starts at zero. emit returns its current value then increments it. reset sets it to zero. For operations emit, reset, emit, the emitted values are strictly increasing. Is this claim supported?"}
    ]


POSITIVE = {
    "F4":"Edges [[3,2],[2,1]] form an acyclic finite graph: SUPPORTED.",
    "F7":"send(4), deliver with no retries produces one delivery: SUPPORTED.",
    "F18":"An invertible square survivor matrix over a field determines the payload: SUPPORTED.",
    "F22":"A single counter emitting 0,1,2 without reset is strictly increasing: SUPPORTED."
}
BOUNDARY = {
    "F4":"Edges [[2,3],[3,2]] have a cycle despite a theorem about backward-only edges: acyclicity UNSUPPORTED.",
    "F7":"send, deliver, retry, deliver duplicates a message. FIFO alone does not imply exactly once: UNSUPPORTED.",
    "F18":"Six identical rows may survive four erasures but cannot recover six coordinates: UNSUPPORTED.",
    "F22":"emit, reset, emit can repeat 0. List.range ordering does not certify restarted allocation: UNSUPPORTED."
}


def run(out: Path, model: str, expected_model: str, models_root: Path | None = None):
    if re.fullmatch(r"[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+", model) is None or re.fullmatch(r"[a-f0-9]{64}", expected_model) is None:
        raise ValueError("EXPLICIT_LOCAL_MODEL_PIN_REQUIRED")
    out.mkdir(parents=True, exist_ok=False)
    rows, details = [], []
    attempts_started = 0
    start = time.monotonic()
    record = {"schema":"szl.local-diagnostic/v0.2","started_at_utc":datetime.now(timezone.utc).isoformat(),
              "status":"PREFLIGHT","diagnostic_only":True,"independent_holdout":False,
              "training_runs":0,"model_downloads":0,"production_qualification":False}
    save(out/'intent.json',record)
    plan = None
    try:
        loaded = request('/api/ps').get('models', [])
        if loaded:
            raise ValueError("EXISTING_MODEL_OWNER_ACTIVE")
        tags = request('/api/tags')['models']
        item = next(x for x in tags if x['name']==model)
        if item['digest'] != expected_model:
            raise ValueError("MODEL_DIGEST_CHANGED")
        models = models_root or Path(os.environ.get('OLLAMA_MODELS', str(Path.home()/'.ollama/models')))
        manifest_file = models/'manifests/registry.ollama.ai/library'/model.split(':')[0]/model.split(':')[1]
        raw_manifest = manifest_file.read_bytes()
        if sha256(raw_manifest).hexdigest() != expected_model:
            raise ValueError("MANIFEST_BYTES_CHANGED")
        manifest = json.loads(raw_manifest)
        descriptors = [manifest['config']] + manifest['layers']
        total, verified, model_blobs = 0, [], []
        for layer in descriptors:
            dig = layer['digest']
            if re.fullmatch(r'sha256:[a-f0-9]{64}',dig) is None:
                raise ValueError("BLOB_DIGEST")
            blob = models/'blobs'/dig.replace(':','-')
            size = blob.stat().st_size
            if size != layer['size'] or total+size > 700000000 or blob.is_symlink():
                raise ValueError("BLOB_SIZE_OR_BUDGET")
            total += size
            h=sha256()
            with blob.open('rb') as handle:
                for part in iter(lambda:handle.read(1024*1024), b''):h.update(part)
            if h.hexdigest() != dig[7:]:raise ValueError("BLOB_HASH")
            verified.append({'digest':dig,'bytes':size,'media_type':layer['mediaType']})
            if layer['mediaType']=='application/vnd.ollama.image.model':model_blobs.append(dig[7:])
        if len(model_blobs)!=1:raise ValueError("TOKENIZER_CONTAINER_AMBIGUOUS")
        source_tasks=tasks()
        cases=[{'id':t['id'],'family':t['family'],'expected':t['expected'],
                'task_sha256':ec.digest({'question':t['question']})} for t in source_tasks]
        plan=ec.frozen_plan(cases,model_digest=expected_model,tokenizer_digest=model_blobs[0],
                            grader_digest=sha256(Path(ec.__file__).read_bytes()).hexdigest(),
                            max_input_tokens=2048,max_output_tokens=32)
        prompts=[]
        for index,t in enumerate(source_tasks):
            # Latin-square arm rotation balances the four fixed task positions.
            order=ec.ARMS[index:]+ec.ARMS[:index]
            for arm in order:
                extra=''
                if arm=='B':extra='\nExamples:\n'+'\n'.join(POSITIVE.values())
                if arm=='C':extra='\nExamples:\n'+'\n'.join([POSITIVE['F4'],POSITIVE['F18'],BOUNDARY['F7'],BOUNDARY['F22']])
                if arm=='D':extra='\nTask-family evidence:\n'+POSITIVE[t['family']]+'\n'+BOUNDARY[t['family']]
                system='Decide only the stated finite claim. Return JSON with exactly one field decision, one of SUPPORTED, UNSUPPORTED, UNKNOWN. Use UNKNOWN only when the supplied finite facts do not determine it.'+extra
                prompts.append({'arm':arm,'task':t,'system':system})
        save(out/'plan.json',plan)
        save(out/'prompts.json',prompts)
        save(out/'artifact-verification.json',{'manifest_sha256':expected_model,'verified_blobs':verified,
             'tokenizer_binding':'Entire model GGUF object contains tokenizer; no separate tokenizer file asserted.',
             'runtime_version':request('/api/version'),'model_show':request('/api/show',{'model':model,'verbose':False})})
        loop_start=time.monotonic()
        for entry in prompts:
            if time.monotonic()-loop_start > 180:break
            arm,t=entry['arm'],entry['task']
            case=next(c for c in cases if c['id']==t['id'])
            row={'arm':arm,'case_id':t['id'],'seed':749,'status':'ERROR','decision':None,
                 'input_tokens':None,'output_tokens':None,'model_digest':expected_model,'task_sha256':case['task_sha256']}
            response = None
            attempts_started += 1
            began=time.monotonic()
            try:
                response=request('/api/chat',{'model':model,'messages':[{'role':'system','content':entry['system']},
                    {'role':'user','content':t['question']}], 'stream':False,'format':{'type':'object',
                    'properties':{'decision':{'type':'string','enum':list(ec.DECISIONS)}},'required':['decision'],'additionalProperties':False},
                    'options':{'num_ctx':2048,'num_predict':32,'temperature':0,'seed':749,'num_thread':2,'num_gpu':0},'keep_alive':'30s'},
                    timeout=min(30,max(1,180-(time.monotonic()-loop_start))))
                if response.get('done') is not True or response.get('done_reason')!='stop':
                    row['status']='TRUNCATED'
                else:
                    decision=parse_decision(response['message']['content'])
                    row.update(status='OK',decision=decision,input_tokens=response['prompt_eval_count'],output_tokens=response['eval_count'])
                ec.score(plan,rows+[row],expected_plan_sha256=ec.digest(plan))
            except Exception as exc:
                row.update(status='ERROR',decision=None,input_tokens=None,output_tokens=None)
                details.append({'arm':arm,'case_id':t['id'],'error_type':type(exc).__name__})
                rows.append(row)
                save(out/(f'attempt-{attempts_started:02d}.json'),{'row':row,'response':response,'elapsed_seconds':time.monotonic()-began})
                # No retries on uncertain requests or failed model/runtime contracts.
                break
            rows.append(row)
            save(out/(f'attempt-{attempts_started:02d}.json'),{'row':row,'response':response,'elapsed_seconds':time.monotonic()-began})
            print(json.dumps({'attempt':attempts_started,'arm':arm,'case':t['id'],'status':row['status'],'decision':row['decision']}),flush=True)
        after=next(x for x in request('/api/tags')['models'] if x['name']==model)
        stable=after['digest']==expected_model and sha256(manifest_file.read_bytes()).hexdigest()==expected_model
        report=ec.score(plan,rows,expected_plan_sha256=ec.digest(plan))
        save(out/'evaluation.json',report)
        record.update(status='DIAGNOSTIC_RECORDED' if stable else 'IDENTITY_DRIFT_HOLD',
                      alias_metadata_stable=stable,serving_identity_attested=False,
                      expected_attempts=16,completed_rows=len(rows),valid_responses=sum(r['status']=='OK' for r in rows),
                      artifact_bytes_verified=total,plan_sha256=ec.digest(plan),model_digest=expected_model,
                      test_scope='Four developer-authored tasks; not independent 200-case pilot.',
                      budget='Common token ceilings, not equal realized token counts; no matched-budget causal claim.')
    except Exception as exc:
        record.update(status='HOLD',reason=type(exc).__name__+':'+str(exc)[:160])
    record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),requests_started=attempts_started,
                  elapsed_seconds=time.monotonic()-start,errors=details,
                  outputs={p.name:{'bytes':p.stat().st_size,'sha256':sha256(p.read_bytes()).hexdigest()} for p in out.iterdir() if p.is_file()})
    save(out/'run-receipt.json',record)
    print(json.dumps(record),flush=True)
    return record


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--model',required=True);p.add_argument('--expected-model-digest',required=True);p.add_argument('--models-root',type=Path)
    args=p.parse_args(argv)
    result=run(args.out,args.model,args.expected_model_digest,args.models_root)
    # A completed process is not a completed diagnostic; HOLD/partial results fail closed.
    return 0 if result.get('status')=='DIAGNOSTIC_RECORDED' and result.get('valid_responses')==16 else 2


if __name__=='__main__':
    raise SystemExit(main())
