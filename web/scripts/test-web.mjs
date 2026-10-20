import {webcrypto} from 'node:crypto';globalThis.crypto=webcrypto;
import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';
const source=readFileSync('worker/index.js','utf8');const mod=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const store=new Map();
const BUCKET={
 async put(k,v,opt={}){const text=typeof v==='string'?v:String(v);store.set(k,{text,opt,etag:'test'});return {}},
 async get(k,opt){const x=store.get(k);if(!x)return null;return {json:async()=>JSON.parse(x.text),body:x.text,size:x.text.length,writeHttpMetadata(h){h.set('Content-Type',x.opt.httpMetadata?.contentType||'application/json')}}},
 async list({prefix}){return {objects:[...store.keys()].filter(k=>k.startsWith(prefix)).map(key=>({key})),truncated:false}},
 async delete(keys){for(const k of Array.isArray(keys)?keys:[keys])store.delete(k)}
};
const env={BUCKET,WORKER_KEY:'test-only-key'};
async function call(path,method='GET',body,user='owner-a',extra={}){const headers={'Content-Type':'application/json',...extra};if(user)headers['oai-authenticated-user-id']=user;return mod.default.fetch(new Request('https://example.test'+path,{method,headers,body:body?JSON.stringify(body):undefined}),env)}
const home=await call('/');assert.equal(home.status,200);const html=await home.text();assert.ok(html.includes('return_to=%2F'));assert.ok(!html.includes('returnTo='));
assert.equal((await call('/api/jobs','GET',null,null)).status,401);
assert.equal((await call('/api/jobs','POST',{url:'https://www.bilibili.com/video/BV1cHen6EEen/',category:'restaurant'})).status,503);
await call('/internal/heartbeat','POST',{},null,{Authorization:'Bearer test-only-key'});
for(const url of ['http://127.0.0.1/video/BV1cHen6EEen/','https://bilibili.com.evil.test/video/BV1cHen6EEen/','https://user@www.bilibili.com/video/BV1cHen6EEen/'])assert.equal((await call('/api/jobs','POST',{url,category:'restaurant'})).status,400);
assert.equal((await call('/api/jobs','POST',{url:'https://www.bilibili.com/video/BV1cHen6EEen/',category:'lecture'})).status,400);
const r=await call('/api/jobs','POST',{url:'https://www.bilibili.com/video/BV1cHen6EEen/?share=1',category:'restaurant'});assert.equal(r.status,201);const {job}=await r.json();
assert.equal((await (await call('/api/jobs','GET',null,'owner-b')).json()).jobs.length,0);
assert.equal((await call('/api/jobs/'+job.id,'DELETE',null,'owner-b')).status,404);
const reused=await (await call('/api/jobs','POST',{url:job.url,category:'restaurant'})).json();assert.equal(reused.job.id,job.id);
const next=await (await call('/internal/next','POST',{},null,{Authorization:'Bearer test-only-key'})).json();assert.equal(next.job.id,job.id);
assert.equal((await call('/api/jobs/'+job.id,'DELETE')).status,409);
await call('/internal/jobs/'+job.id,'PATCH',{status:'completed',progress:100},null,{Authorization:'Bearer test-only-key'});
store.set('assets/'+job.id+'/notes.html',{text:'hello',opt:{httpMetadata:{contentType:'text/html'}}});
assert.equal((await call('/notes/'+job.id+'/notes.html','GET',null,'owner-b')).status,404);
assert.equal((await call('/notes/'+job.id+'/notes.html')).status,200);
assert.equal((await call('/api/jobs/'+job.id,'DELETE')).status,200);
assert.equal(store.has('assets/'+job.id+'/notes.html'),false);assert.equal(store.has('jobs/'+job.id+'.json'),false);
console.log('Web checks passed: URL validation, offline handling, category limits, ownership, reuse, queue, active-delete guard, assets, deletion');
