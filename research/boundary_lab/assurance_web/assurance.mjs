/* Read-only, no persistence, no client-provided policy/tenant/clock authority. */
const STATES = new Set(['SUPPORTED','UNSUPPORTED','WITHDRAWN','EXPIRED','RIGHTS_UNAVAILABLE','UNAVAILABLE']);
const HEX = /^[a-f0-9]{64}$/;
const ID = /^[A-Za-z0-9_.:/-]{1,128}$/;
const PIN = /^(?:[a-f0-9]{40}|[a-f0-9]{64})$/;
export function canonical(value) {
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (value && typeof value === 'object') return '{' + Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical(value[k])).join(',') + '}';
  return JSON.stringify(value);
}
export async function validateSnapshot(v, cryptoAPI=globalThis.crypto) {
  function keys(x, allowed) { if (!x || typeof x!=="object" || Array.isArray(x) || Object.keys(x).sort().join('|')!==allowed.slice().sort().join('|')) throw Error('EXACT_SCHEMA_REQUIRED'); }
  keys(v,['schema','state','data_class','tenant','head','policy_revision','observed_at','evaluated_at','valid_until','objects','scenario','capabilities','qualifications','visible_object_count','snapshot_sha256']);
  if (!v || v.schema!=='szl.assurance-surface/v0.3' || v.state!=='OBSERVED' || !HEX.test(v.head) || !HEX.test(v.snapshot_sha256)) throw Error('RESPONSE_CONTRACT');
  if (!['SYNTHETIC_DEMO','CONTROLLER_SUPPLIED_HANDLES'].includes(v.data_class) || !ID.test(v.tenant) || !PIN.test(v.policy_revision)) throw Error('SCOPE_CONTRACT');
  for (const k of ['observed_at','evaluated_at','valid_until','visible_object_count']) if (!Number.isSafeInteger(v[k]) || v[k]<0) throw Error('TIME_OR_COUNT');
  if (v.valid_until<=v.evaluated_at || v.evaluated_at<v.observed_at || !Array.isArray(v.objects) || v.objects.length>128 || v.visible_object_count!==v.objects.length) throw Error('COVERAGE_CONTRACT');
  keys(v.capabilities,['content_hydration','execution','training','promotion']);
  keys(v.qualifications,['truth_verified','production_qualified','independent_witness']);
  keys(v.scenario,['hypothetical','withdraw','persistent_mutations','target','cut_sets']);
  if (!v.capabilities || Object.values(v.capabilities).some(x=>x!==false) || !v.qualifications || Object.values(v.qualifications).some(x=>x!==false)) throw Error('AUTHORITY_ESCALATION');
  if (!v.scenario || v.scenario.hypothetical!==true || v.scenario.persistent_mutations!==0) throw Error('SCENARIO_CONTRACT');
  const ids = new Set();
  for (const x of v.objects) {
    keys(x,['id','kind','revision','content_sha256','expires_at','state','scenario_state','explanation_redacted','supports']);
    if (typeof x.id!=='string' || typeof x.revision!=='string' || typeof x.content_sha256!=='string' || !Number.isSafeInteger(x.expires_at) || typeof x.explanation_redacted!=='boolean') throw Error('OBJECT_TYPES');
    if (!ID.test(x.id) || ids.has(x.id) || !['source','claim'].includes(x.kind) || !STATES.has(x.state) || !STATES.has(x.scenario_state) || !PIN.test(x.revision) || !HEX.test(x.content_sha256)) throw Error('OBJECT_CONTRACT');
    if (!Array.isArray(x.supports) || x.supports.length>8 || x.supports.some(t=>!Array.isArray(t)||t.length>8||t.some(p=>!ids.has(p)))) throw Error('SUPPORT_CONTRACT');
    ids.add(x.id);
  }
  const expected = v.snapshot_sha256, unsigned = {...v}; delete unsigned.snapshot_sha256;
  const bytes = new TextEncoder().encode(canonical(unsigned)+'\n');
  const actual = [...new Uint8Array(await cryptoAPI.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');
  if (actual!==expected) throw Error('RESPONSE_DIGEST_MISMATCH');
  return v;
}
export function impactCounts(objects) {
  if (!Array.isArray(objects)) throw Error('OBJECTS_REQUIRED');
  let transitions=0, supportLosses=0;
  for (const x of objects) {
    if (x.explanation_redacted) continue;
    if (x.state!==x.scenario_state) {
      transitions+=1;
      if (x.state==='SUPPORTED' && x.scenario_state!=='SUPPORTED') supportLosses+=1;
    }
  }
  return {transitions,supportLosses};
}
export class SnapshotGate {
  constructor(clock=()=>performance.now()) { this.clock=clock; this.sequence=0; this.value=null; this.deadline=0; }
  begin() { this.sequence+=1; this.value=null; this.deadline=0; return this.sequence; }
  accept(sequence, value, startedAt=this.clock()) {
    if (sequence!==this.sequence) return false;
    this.deadline=startedAt+(value.valid_until-value.evaluated_at)*1000;
    if (this.clock()>=this.deadline) return false;
    this.value=value;return true;
  }
  fresh() { return this.value!==null && this.clock()<this.deadline; }
}
export async function boundedResponseText(response, signal, byteLimit=262144) {
  if (!response.body || typeof response.body.getReader !== 'function') throw Error('RESPONSE_STREAM_REQUIRED');
  const reader=response.body.getReader(), decoder=new TextDecoder('utf-8',{fatal:true});
  let size=0, text='';
  const abort=()=>{reader.cancel().catch(()=>{});};
  signal.addEventListener('abort',abort,{once:true});
  try {
    while(true) {
      if(signal.aborted) throw Error('REQUEST_TIMEOUT');
      const {done,value}=await reader.read();
      if(signal.aborted) throw Error('REQUEST_TIMEOUT');
      if(done) break;
      size+=value.byteLength;
      if(size>byteLimit) { await reader.cancel();throw Error('RESPONSE_BUDGET'); }
      text+=decoder.decode(value,{stream:true});
    }
    return text+decoder.decode();
  } finally { signal.removeEventListener('abort',abort);reader.releaseLock(); }
}
if (typeof document!=='undefined') {
 const gate=new SnapshotGate(), el=id=>document.getElementById(id); let timer;
 function text(id,s){el(id).textContent=s;}
 function clear(reason){
   clearTimeout(timer);gate.value=null;gate.deadline=0;
   el('status').dataset.state='UNAVAILABLE';text('status','UNAVAILABLE · '+reason);
   text('object-count','—');text('supported-count','—');text('evaluated','—');text('lease','No current snapshot');
   text('classification','No usable evidence');text('head','Unavailable');text('digest','Unavailable');text('policy','Unavailable');
   for(const id of ['graph','objects','sources','target']) el(id).replaceChildren();
   for(const id of ['simulate','cuts','target']) el(id).disabled=true;
   text('cut-result','No current evidence. Refresh before inspecting a scenario.');text('impact-summary','No current hypothetical impact.');
 }
 function svg(tag,attrs={}){const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,String(v));return n;}
 function renderGraph(objects){
   const levels={},rows={}; for(const x of objects){levels[x.id]=x.supports.length?1+Math.max(...x.supports.flat().map(p=>levels[p])):0;(rows[levels[x.id]]??=[]).push(x);}
   const maxLevel=Math.max(0,...Object.values(levels)),maxRows=Math.max(1,...Object.values(rows).map(x=>x.length));
   const width=(maxLevel+1)*205+30,height=maxRows*90+50,scene=svg('svg',{viewBox:`0 0 ${width} ${height}`,role:'img','aria-label':'Version-bound support dependencies'}),pos={};
   for(const[level,list]of Object.entries(rows))list.forEach((x,i)=>{pos[x.id]=[15+Number(level)*205,25+i*90];});
   for(const x of objects)for(const term of x.supports)for(const parent of term){const[a,b]=pos[parent],[c,d]=pos[x.id];scene.append(svg('path',{d:`M${a+165},${b+27} C${a+185},${b+27} ${c-20},${d+27} ${c},${d+27}`,class:x.supports.length>1?'edge alternate':'edge'}));}
   for(const x of objects){const[a,b]=pos[x.id],g=svg('g',{class:'node','data-state':x.scenario_state});g.append(svg('rect',{x:a,y:b,width:165,height:55,rx:7}));
     const label=svg('text',{x:a+12,y:b+22});label.textContent=x.id.length>23?x.id.slice(0,21)+'…':x.id;g.append(label);
     const status=svg('text',{x:a+12,y:b+41,class:'sub'});status.textContent=x.scenario_state;g.append(status);const title=svg('title');title.textContent=x.id+' · '+x.kind+' · '+x.scenario_state;g.append(title);scene.append(g);}
   el('graph').replaceChildren(scene);
 }
 function render(v){
   el('status').dataset.state='OBSERVED';text('status','OBSERVED · support evaluated');text('classification',v.data_class==='SYNTHETIC_DEMO'?'SYNTHETIC DEMO · NOT ESTATE TELEMETRY':'CONTROLLER-SUPPLIED HANDLES');
   text('object-count',String(v.visible_object_count));text('supported-count',String(v.objects.filter(x=>x.scenario_state==='SUPPORTED').length));
   text('evaluated',new Date(v.evaluated_at*1000).toISOString().slice(11,19));text('lease','Snapshot expires; no stale green fallback');
   text('head',v.head);text('digest',v.snapshot_sha256);text('policy',v.policy_revision);
   const tbody=el('objects');tbody.replaceChildren();for(const x of v.objects){const tr=document.createElement('tr');for(const value of [x.id,x.state,x.scenario_state,x.revision]){const td=document.createElement('td');if(STATES.has(value)){const b=document.createElement('span');b.className='badge';b.dataset.state=value;b.textContent=value;td.append(b);}else td.textContent=value;tr.append(td);}tbody.append(tr);}
   const sourceBox=el('sources'),targetBox=el('target');sourceBox.replaceChildren();targetBox.replaceChildren();const legend=document.createElement('legend');legend.textContent='Available sources';sourceBox.append(legend);
   for(const x of v.objects){if(x.kind==='source'){const label=document.createElement('label');label.className='source-option';const box=document.createElement('input');box.type='checkbox';box.name='withdraw';box.value=x.id;box.checked=v.scenario.withdraw.includes(x.id);label.append(box,document.createTextNode(x.id));sourceBox.append(label);}else{const o=document.createElement('option');o.value=x.id;o.textContent=x.id;targetBox.append(o);}}
   if(v.scenario.target)targetBox.value=v.scenario.target;
   for(const id of ['simulate','cuts','target'])el(id).disabled=false;
   const impact=impactCounts(v.objects);
   text('impact-summary',`${impact.supportLosses} visible supported objects lose support; ${impact.transitions} visible state transitions. Hypothetical only; no ledger mutation.`);
   const cuts=v.scenario.cut_sets;
   text('cut-result',cuts?`${cuts.state} · ${cuts.checks} finite checks\n${cuts.sets.map(s=>s.join(' + ')).join('\n')||'No removal set found in the inspected scope.'}\nSearch complete: ${cuts.search_complete?'yes':'no — bounded result only'}`:'No cut-set search in this response. The scenario is read-only.');
   renderGraph(v.objects);clearTimeout(timer);timer=setTimeout(()=>clear('snapshot expired'),Math.max(0,gate.deadline-performance.now()));
 }
 async function load(route,head){
   const seq=gate.begin(),started=performance.now();clear('reading evidence');
   try{
     const headers={};if(head)headers['If-Match']=head;
     const controller=new AbortController(),deadline=setTimeout(()=>controller.abort(),5000);
     let response,raw;try{response=await fetch(new URL(route,location.href),{cache:'no-store',credentials:'same-origin',headers,signal:controller.signal});raw=await boundedResponseText(response,controller.signal);}finally{clearTimeout(deadline);}
     const payload=JSON.parse(raw);if(!response.ok)throw Error(payload.reason||`HTTP_${response.status}`);
     await validateSnapshot(payload);if(seq!==gate.sequence)return;
     if(!gate.accept(seq,payload,started))throw Error('EXPIRED_OR_OUTDATED_RESPONSE');render(payload);
   }catch(e){if(seq===gate.sequence)clear(String(e.message||'request failed'));}
 }
 el('refresh').addEventListener('click',()=>load('./api/snapshot'));
 el('scenario').addEventListener('submit',e=>{e.preventDefault();if(!gate.fresh()){clear('snapshot expired');return;}const q=new URLSearchParams();for(const box of el('sources').querySelectorAll('input:checked'))q.append('withdraw',box.value);load('./api/scenario?'+q,gate.value.head);});
 el('cuts').addEventListener('click',()=>{if(!gate.fresh()){clear('snapshot expired');return;}load('./api/cuts?'+new URLSearchParams({target:el('target').value}),gate.value.head);});
 document.addEventListener('visibilitychange',()=>{if(!document.hidden&&!gate.fresh())clear('snapshot expired');});
 load('./api/snapshot');
}
