const json=(d,s=200)=>new Response(JSON.stringify(d),{status:s,headers:{'Content-Type':'application/json;charset=utf-8','Cache-Control':'no-store'}});
const owner=r=>r.headers.get('oai-authenticated-user-id');
const metaKey=id=>'jobs/'+id+'.json';
async function read(env,key){const x=await env.BUCKET.get(key);return x?await x.json():null}
async function save(env,j){await env.BUCKET.put(metaKey(j.id),JSON.stringify(j))}
function cleanJob(j){const {owner,...rest}=j;return rest}
function validId(id){return /^[a-f0-9-]{36}$/.test(id)}
export function videoUrl(value){let u;try{u=new URL(value)}catch{return null}if(!['http:','https:'].includes(u.protocol)||!['www.bilibili.com','bilibili.com','m.bilibili.com'].includes(u.hostname)||u.username||u.password||u.port)return null;const m=u.pathname.match(/^\/video\/(BV[a-zA-Z0-9]{10})(?:\/|$)/);return m?'https://www.bilibili.com/video/'+m[1]+'/':null}
async function allJobs(env){const list=await env.BUCKET.list({prefix:'jobs/',limit:1000});return (await Promise.all(list.objects.map(o=>read(env,o.key)))).filter(Boolean)}
async function heartbeat(env){await env.BUCKET.put('worker/heartbeat.json',JSON.stringify({time:Date.now()}))}
async function online(env){const h=await read(env,'worker/heartbeat.json');return !!h&&Date.now()-h.time<90000}
export async function handle(request,env){
 const u=new URL(request.url),path=u.pathname,user=owner(request);
 if(path==='/')return new Response(APP,{headers:{'Content-Type':'text/html;charset=utf-8'}});
 if(!env.BUCKET)return json({error:'云存储尚未配置'},503);
 if(path==='/api/session')return json({user:user?{signed_in:true}:null});
 if(path==='/api/health')return json({online:await online(env),storage:true});
 if(path.startsWith('/internal/')){
  if(!env.WORKER_KEY||request.headers.get('Authorization')!=='Bearer '+env.WORKER_KEY)return json({error:'无权访问'},403);
  await heartbeat(env);
  if(path==='/internal/heartbeat')return json({ok:true});
  if(path==='/internal/jobs'&&request.method==='POST'){
   const d=await request.json(),url=videoUrl(d.url);if(!url||!d.owner)return json({error:'Invalid import'},400);
   const j={id:crypto.randomUUID(),owner:d.owner,url,category:'restaurant',title:'正在解析视频标题',status:'queued',stage:'等待处理',progress:0,created_at:new Date().toISOString(),updated_at:Date.now()};await save(env,j);return json({job:j},201)
  }
  if(path==='/internal/next'&&request.method==='POST'){
   const all=await allJobs(env),j=all.sort((a,b)=>a.created_at.localeCompare(b.created_at)).find(x=>x.status==='queued'||(['downloading','processing','uploading'].includes(x.status)&&Date.now()-x.updated_at>3600000));
   if(!j)return json({job:null});j.status='downloading';j.stage='正在获取视频';j.updated_at=Date.now();await save(env,j);return json({job:j});
  }
  const m=path.match(/^\/internal\/jobs\/([a-f0-9-]{36})(?:\/(assets)\/(.+))?$/);
  if(m){const j=await read(env,metaKey(m[1]));if(!j)return json({error:'任务不存在'},404);
   if(m[2]&&request.method==='PUT'){const asset=decodeURIComponent(m[3]);if(asset.includes('..')||asset.includes('\\')||!(/^(notes\.(html|md|json)|video\.mp4|frames\/[a-zA-Z0-9_.-]+\.jpg)$/).test(asset))return json({error:'文件名无效'},400);await env.BUCKET.put('assets/'+j.id+'/'+asset,request.body,{httpMetadata:{contentType:request.headers.get('Content-Type')||'application/octet-stream'}});return json({ok:true})}
   if(request.method==='GET')return json({job:j});
   if(request.method==='PATCH'){const body=await request.json();for(const key of ['status','title','stage','error','progress','shops'])if(key in body)j[key]=body[key];j.updated_at=Date.now();await save(env,j);return json({ok:true})}
  }return json({error:'接口不存在'},404)
 }
 const service=env.WORKER_KEY&&request.headers.get('Authorization')==='Bearer '+env.WORKER_KEY;
 if(!user&&!service)return json({error:'请先登录后生成或管理笔记'},401);
 if(request.method!=='GET'&&request.headers.get('Origin')&&request.headers.get('Origin')!==u.origin)return json({error:'请求来源无效'},403);
 if(path==='/api/jobs'&&request.method==='GET'){const jobs=(await allJobs(env)).filter(j=>j.owner===user).sort((a,b)=>b.created_at.localeCompare(a.created_at));return json({jobs:jobs.map(cleanJob)})}
 if(path==='/api/jobs'&&request.method==='POST'){
  if(!await online(env))return json({error:'处理服务离线，请稍后再试。已有笔记不受影响。'},503);
  const d=await request.json(),url=videoUrl(d.url);if(!url)return json({error:'请输入有效的哔哩哔哩 BV 视频链接'},400);
  if(d.category!=='restaurant')return json({error:'首版仅支持探店攻略'},400);
  const mine=(await allJobs(env)).filter(j=>j.owner===user);
  const duplicate=mine.find(j=>j.url===url&&j.status!=='failed');if(duplicate)return json({job:cleanJob(duplicate),reused:true});
  if(mine.filter(j=>!['completed','failed'].includes(j.status)).length>=2)return json({error:'请等待已有任务完成后再生成'},429);
  const j={id:crypto.randomUUID(),owner:user,url,category:'restaurant',title:'正在解析视频标题',status:'queued',stage:'等待处理',progress:0,created_at:new Date().toISOString(),updated_at:Date.now()};await save(env,j);return json({job:cleanJob(j)},201)
 }
 const idmatch=path.match(/^\/api\/jobs\/([a-f0-9-]{36})$/);
 if(idmatch&&request.method==='DELETE'){
  const j=await read(env,metaKey(idmatch[1]));if(!j||(j.owner!==user&&!service))return json({error:'笔记不存在'},404);
  if(!['completed','failed','queued'].includes(j.status))return json({error:'正在生成的任务暂时不能删除'},409);
  let cursor;do{const list=await env.BUCKET.list({prefix:'assets/'+j.id+'/',limit:1000,cursor});if(list.objects.length)await env.BUCKET.delete(list.objects.map(o=>o.key));cursor=list.truncated?list.cursor:undefined}while(cursor);
  await env.BUCKET.delete(metaKey(j.id));return json({ok:true})
 }
 const assetMatch=path.match(/^\/notes\/([a-f0-9-]{36})\/(.+)$/);
 if(assetMatch){
  const j=await read(env,metaKey(assetMatch[1]));if(!j||(j.owner!==user&&!service))return new Response('笔记不存在或无权访问',{status:404});
  const key=decodeURIComponent(assetMatch[2]);if(key.includes('..')||key.includes('\\'))return new Response('Invalid path',{status:400});
  const object=await env.BUCKET.get('assets/'+j.id+'/'+key);if(!object)return new Response('文件不存在',{status:404});
  const headers=new Headers({'Cache-Control':'private,max-age=60','X-Content-Type-Options':'nosniff'});object.writeHttpMetadata(headers);
  const range=request.headers.get('Range');
  if(range&&key==='video.mp4'){
   const m=range.match(/^bytes=(\d+)-(\d*)$/);if(!m)return new Response(null,{status:416});const start=Number(m[1]),end=m[2]?Math.min(Number(m[2]),object.size-1):object.size-1;
   if(start>=object.size||end<start)return new Response(null,{status:416});const part=await env.BUCKET.get('assets/'+j.id+'/'+key,{range:{offset:start,length:end-start+1}});headers.set('Content-Range','bytes '+start+'-'+end+'/'+object.size);headers.set('Content-Length',String(end-start+1));headers.set('Accept-Ranges','bytes');return new Response(part.body,{status:206,headers})
  }headers.set('Accept-Ranges','bytes');return new Response(object.body,{headers})
 }
 return json({error:'页面不存在'},404)
}
export default {async fetch(request,env){try{return await handle(request,env)}catch(e){return json({error:'服务处理失败，请稍后重试'},500)}}};
