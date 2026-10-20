"""Local CPU worker for the cloud Video Agent queue."""
from __future__ import annotations
import argparse,json,mimetypes,os,re,subprocess,sys,threading,time,urllib.request
import httpx
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Client:
    def __init__(self,base,key):
        self.base=base.rstrip('/')
        self.http=httpx.Client(timeout=120,headers={'Authorization':'Bearer '+key,'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36'})
    def request(self,path,method='GET',data=None,content_type='application/json'):
        raw=json.dumps(data,ensure_ascii=False).encode() if isinstance(data,dict) else data
        response=self.http.request(method,self.base+path,content=raw,headers={'Content-Type':content_type})
        response.raise_for_status()
        return response.json()
    def update(self,id,**fields):return self.request('/internal/jobs/'+id,'PATCH',fields)
    def upload(self,id,path,file):
        return self.request('/internal/jobs/'+id+'/assets/'+path,'PUT',file.read_bytes(),mimetypes.guess_type(path)[0] or 'application/octet-stream')
def run(client,job):
    id=job['id'];match=re.fullmatch(r'https://www\.bilibili\.com/video/(BV[a-zA-Z0-9]{10})/',job['url'])
    if not match:raise ValueError('仅支持哔哩哔哩 BV 视频链接')
    bv=match.group(1);raw=ROOT/'data/raw'/bv;out=ROOT/'data/processed'/bv
    raw.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True,exist_ok=True)
    video=raw/'video.mp4'
    if not video.exists():
        from imageio_ffmpeg import get_ffmpeg_exe
        args=[sys.executable,'-m','yt_dlp','--no-playlist','--socket-timeout','25','--retries','2','--write-info-json','--max-filesize','90M','--match-filter','duration <= 1200','-f','bv*[height<=480]+ba/b[height<=480]/b','--merge-output-format','mp4','--ffmpeg-location',get_ffmpeg_exe(),'-o',str(raw/'video.%(ext)s'),job['url']]
        client.update(id,status='downloading',stage='下载视频，首次处理需要一些时间',progress=5)
        subprocess.run(args,cwd=ROOT,check=True,timeout=600)
    if not video.exists():raise ValueError('视频不可获取，或超过 20 分钟／90 MB 限制')
    from .extract import probe_video
    duration=probe_video(video)['duration']
    if duration>1200:raise ValueError('首版支持最长 20 分钟视频')
    metadata=raw/'video.info.json';meta=json.loads(metadata.read_text(encoding='utf-8')) if metadata.exists() else {}
    client.update(id,status='processing',title=meta.get('title',bv),stage='识别画面、语音并整理攻略',progress=15)
    env=os.environ.copy();env['PYTHONIOENCODING']='utf-8';env['PYTHONUTF8']='1'
    proc=subprocess.Popen([sys.executable,'-m','video_agent.pipeline',str(video)],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
    last=time.monotonic();tail=[]
    try:
        for line in proc.stdout:
            print(line.rstrip(),flush=True);tail.append(line.strip());tail=tail[-12:]
            if time.monotonic()-last>12:
                phase='识别画面' if line.startswith('OCR ') else '识别语音' if line.startswith('ASR ') else '整理菜品与截图'
                client.update(id,stage=phase,progress=35 if phase=='识别画面' else 65 if phase=='识别语音' else 80);last=time.monotonic()
        if proc.wait()!=0:raise RuntimeError('识别失败：'+' '.join(tail)[-500:])
    finally:
        if proc.poll() is None:proc.terminate()
    client.update(id,status='uploading',stage='保存笔记、截图和回看视频到云端',progress=85)
    notes=json.loads((out/'notes.json').read_text(encoding='utf-8'))
    if not notes.get('shops'):raise ValueError('未发现可识别店铺，请使用有店名与介绍转场的探店视频')
    page=(out/'notes.html').read_text(encoding='utf-8')
    page=re.sub(r'(<video\b[^>]*\bsrc=")[^"]*(")',r'\1video.mp4\2',page)
    webcopy=out/'web-notes.html';webcopy.write_text(page,encoding='utf-8')
    client.upload(id,'notes.html',webcopy);client.upload(id,'notes.md',out/'notes.md')
    # Only the final summary and its referenced media are hosted.
    files={Path(e['path']) for s in notes['shops'] for e in s.get('evidence',[])}
    from concurrent.futures import ThreadPoolExecutor
    def upload_image(file):
        resolved=file.resolve()
        if not resolved.is_relative_to(out.resolve()):raise ValueError('图片路径越界')
        client.upload(id,'frames/'+file.name,file)
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(upload_image,sorted(files)))
    from imageio_ffmpeg import get_ffmpeg_exe
    preview=out/'web-video.mp4'
    if not preview.exists() or preview.stat().st_mtime<video.stat().st_mtime:
        subprocess.run([get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-i',str(video),'-vf','scale=-2:480','-c:v','libx264','-preset','fast','-crf','29','-c:a','aac','-b:a','64k','-movflags','+faststart',str(preview)],check=True,timeout=600)
    client.upload(id,'video.mp4',preview)
    client.update(id,status='completed',progress=100,stage=str(len(notes['shops']))+' 家店铺 · '+str(len(files))+' 张关联截图',shops=len(notes['shops']),error='')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--site',required=True);parser.add_argument('--once',action='store_true');args=parser.parse_args()
    config=ROOT/'web/.env.local';key=next(line.split('=',1)[1].strip() for line in config.read_text().splitlines() if line.startswith('WORKER_KEY='))
    client=Client(args.site,key);stop=threading.Event()
    def beat():
        while not stop.is_set():
            try:client.request('/internal/heartbeat','POST',{})
            except Exception:pass
            stop.wait(20)
    threading.Thread(target=beat,daemon=True).start()
    print('Video Agent worker connected',flush=True)
    while True:
        try:
            result=client.request('/internal/next','POST',{});job=result.get('job')
            if job:
                print('Processing',job['id'],flush=True)
                try:run(client,job)
                except Exception as e:
                    print('Job failed:',str(e),flush=True)
                    try:client.update(job['id'],status='failed',stage='生成失败，可以删除后重试',error=str(e)[:500])
                    except Exception:pass
                if args.once:break
            elif args.once:break
        except Exception as e:print('Worker connection:',str(e)[:200],flush=True)
        time.sleep(8)
if __name__=='__main__':main()
