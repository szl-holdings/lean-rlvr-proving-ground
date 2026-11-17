import test from 'node:test';
import assert from 'node:assert/strict';
import {webcrypto} from 'node:crypto';
import {canonical,validateSnapshot,SnapshotGate,boundedResponseText,impactCounts} from './assurance.mjs';
async function signed(patch={}) {
 const value={schema:'szl.assurance-surface/v0.3',state:'OBSERVED',data_class:'SYNTHETIC_DEMO',tenant:'research',head:'a'.repeat(64),policy_revision:'b'.repeat(40),observed_at:1000,evaluated_at:1001,valid_until:1031,objects:[{id:'A',kind:'source',revision:'c'.repeat(40),content_sha256:'d'.repeat(64),expires_at:2000,state:'SUPPORTED',scenario_state:'SUPPORTED',explanation_redacted:false,supports:[]}],visible_object_count:1,scenario:{hypothetical:true,withdraw:[],persistent_mutations:0,target:null,cut_sets:null},capabilities:{content_hydration:false,execution:false,training:false,promotion:false},qualifications:{truth_verified:false,production_qualified:false,independent_witness:false},...patch};
 value.snapshot_sha256=[...new Uint8Array(await webcrypto.subtle.digest('SHA-256',new TextEncoder().encode(canonical(value)+'\n')))].map(x=>x.toString(16).padStart(2,'0')).join('');return value;
}
test('valid signed snapshot admitted',async()=>assert.equal((await validateSnapshot(await signed(),webcrypto)).visible_object_count,1));
test('tampered payload rejected',async()=>{const v=await signed();v.objects[0].state='WITHDRAWN';await assert.rejects(validateSnapshot(v,webcrypto),/DIGEST/);});
test('rehashed authority escalation rejected',async()=>{const v=await signed();const capabilities={...v.capabilities,execution:true};await assert.rejects(validateSnapshot(await signed({capabilities}),webcrypto),/AUTHORITY/);});
test('missing capability fails closed',async()=>{await assert.rejects(validateSnapshot(await signed({capabilities:{}}),webcrypto),/SCHEMA/);});
test('unavailable is never presented as observed',async()=>assert.rejects(validateSnapshot(await signed({state:'UNAVAILABLE'}),webcrypto),/CONTRACT/));
test('zero TTL rejected',async()=>assert.rejects(validateSnapshot(await signed({valid_until:1001}),webcrypto),/CONTRACT/));
test('nonintegral count rejected',async()=>assert.rejects(validateSnapshot(await signed({visible_object_count:1.5}),webcrypto),/COUNT/));
test('count mismatch rejected',async()=>assert.rejects(validateSnapshot(await signed({visible_object_count:0}),webcrypto),/CONTRACT/));
test('raw content addition rejected',async()=>assert.rejects(validateSnapshot(await signed({raw_content:'private text'}),webcrypto),/SCHEMA/));
test('invalid object identifier rejected',async()=>{const v=await signed();v.objects[0].id='<img>';await assert.rejects(validateSnapshot(v,webcrypto),/CONTRACT/);});
test('forward dependency rejected',async()=>{const v=await signed();v.objects[0].supports=[['missing']];await assert.rejects(validateSnapshot(v,webcrypto),/SUPPORT/);});
test('unknown support state rejected',async()=>{const v=await signed();v.objects[0].state='PRODUCTION_READY';await assert.rejects(validateSnapshot(v,webcrypto),/CONTRACT/);});
test('old response cannot overwrite newer request',()=>{const g=new SnapshotGate(()=>0);const a=g.begin();const b=g.begin();assert.equal(g.accept(a,{evaluated_at:1000,valid_until:1030}),false);assert.equal(g.accept(b,{evaluated_at:1000,valid_until:1030}),true);});
test('expiry uses monotonic clock',()=>{let t=0;const g=new SnapshotGate(()=>t),s=g.begin();g.accept(s,{evaluated_at:1000,valid_until:1030});t=30000;assert.equal(g.fresh(),false);});
test('new request clears previous usable snapshot',()=>{const g=new SnapshotGate(()=>0),s=g.begin();g.accept(s,{evaluated_at:1000,valid_until:1030});assert.equal(g.fresh(),true);g.begin();assert.equal(g.fresh(),false);});
test('network time is charged to validity window',()=>{const g=new SnapshotGate(()=>31000),s=g.begin();assert.equal(g.accept(s,{evaluated_at:1000,valid_until:1030},0),false);});
test('canonical object order deterministic',()=>assert.equal(canonical({b:2,a:1}),'{"a":1,"b":2}'));

test('response byte budget enforced while streaming',async()=>assert.rejects(boundedResponseText(new Response('12345'),new AbortController().signal,4),/BUDGET/));
test('valid UTF8 streamed response retained',async()=>assert.equal(await boundedResponseText(new Response('sample'),new AbortController().signal),'sample'));
test('already aborted response rejected',async()=>{const c=new AbortController();c.abort();await assert.rejects(boundedResponseText(new Response('test'),c.signal),/TIMEOUT/);});
test('stalled body cancelled at deadline',async()=>{const c=new AbortController(),r=new Response(new ReadableStream({start(){}}));const t=setTimeout(()=>c.abort(),10);await assert.rejects(boundedResponseText(r,c.signal),/TIMEOUT/);clearTimeout(t);});
test('invalid UTF8 rejected',async()=>assert.rejects(boundedResponseText(new Response(new Uint8Array([255])),new AbortController().signal),/encoded|encoding|valid/i));

test('impact accounting separates state change from support loss',()=>{
 const rows=[
  {state:'SUPPORTED',scenario_state:'UNSUPPORTED',explanation_redacted:false},
  {state:'SUPPORTED',scenario_state:'SUPPORTED',explanation_redacted:false},
  {state:'EXPIRED',scenario_state:'WITHDRAWN',explanation_redacted:false},
  {state:'SUPPORTED',scenario_state:'UNSUPPORTED',explanation_redacted:true}
 ];
 assert.deepEqual(impactCounts(rows),{transitions:2,supportLosses:1});
});
test('empty hypothetical withdrawal never invents impact',()=>{
 assert.deepEqual(impactCounts([
  {state:'SUPPORTED',scenario_state:'SUPPORTED',explanation_redacted:false}
 ]),{transitions:0,supportLosses:0});
});
test('impact counter rejects malformed object list',()=>{
 assert.throws(()=>impactCounts(null),/OBJECTS_REQUIRED/);
});
