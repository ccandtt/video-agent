"""One local service shared by the browser and Agent/CLI entry points."""
from __future__ import annotations
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ["B站中文探店图文笔记", "截图与时间戳回看", "历史分类与搜索"]

def project_id(root=ROOT):
    value=os.path.normcase(str(Path(root).resolve()))
    return hashlib.sha256(value.encode()).hexdigest()[:24]

def ensure_dirs(root=ROOT):
    for relative in (".cache","tmp","models","data/raw","data/processed"):
        (Path(root)/relative).mkdir(parents=True,exist_ok=True)

def environment(root=ROOT):
    root=Path(root).resolve()
    env=os.environ.copy()
    env.update(PYTHONIOENCODING="utf-8",PYTHONUTF8="1",PYTHONPATH=str(root),
               HF_HOME=str(root/".cache/huggingface"),HF_HUB_DISABLE_XET="1",
               PIP_CACHE_DIR=str(root/".cache/pip"),TMP=str(root/"tmp"),TEMP=str(root/"tmp"))
    return env

@contextmanager
def file_lock(path,timeout=30):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    deadline=time.monotonic()+timeout
    acquired=False
    while not acquired:
        try:
            descriptor=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
            os.write(descriptor,str(os.getpid()).encode());os.close(descriptor)
            acquired=True
        except FileExistsError:
            if time.monotonic()>deadline:
                raise RuntimeError("另一项安装或启动正在运行，请稍后重试；锁文件："+str(path))
            time.sleep(.15)
    try:
        yield
    finally:
        if acquired:
            path.unlink(missing_ok=True)

def request(port,path,method="GET",data=None,timeout=5):
    port=int(port)
    if not 1<=port<=65535:
        raise ValueError("端口必须位于 1–65535")
    body=None if data is None else json.dumps(data).encode()
    req=urllib.request.Request(f"http://127.0.0.1:{port}"+path,method=method,data=body,
                               headers={"Content-Type":"application/json"})
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req,timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        try:message=json.load(error).get("error","本地服务请求失败")
        except (ValueError,AttributeError):message="本地服务请求失败"
        raise RuntimeError(message) from error

def saved_port(root=ROOT):
    try:
        value=json.loads((Path(root)/".cache/local-service.json").read_text(encoding="utf-8"))
        port=value["port"]
        return port if type(port) is int and 1<=port<=65535 else None
    except (OSError,ValueError,KeyError,TypeError):
        return None

def health(port,root=ROOT):
    try:
        data=request(port,"/api/health",timeout=.6)
        return data if data.get("app")=="video-agent" and data.get("project_id")==project_id(root) else None
    except (OSError,ValueError,RuntimeError,AttributeError):
        return None

def locate(root=ROOT):
    port=saved_port(root)
    return port if port and health(port,root) else None

def status(root=ROOT):
    port=locate(root)
    return {"status":"running" if port else "stopped","homepage_url":f"http://127.0.0.1:{port}/" if port else None,
            "port":port,"project_id":project_id(root)}

def start(port=8765,open_browser=True,root=ROOT):
    root=Path(root).resolve();ensure_dirs(root)
    if not 1<=port<=65535:
        raise ValueError("端口必须位于 1–65535")
    with file_lock(root/".cache/service-start.lock"):
        existing=locate(root)
        if not existing and health(port,root):
            existing=port
        if existing:
            result={"status":"running","reused":True,"port":existing,"homepage_url":f"http://127.0.0.1:{existing}/"}
        else:
            chosen=None
            for candidate in range(port,min(port+20,65536)):
                try:
                    with socket.socket() as probe:probe.bind(("127.0.0.1",candidate))
                    chosen=candidate;break
                except OSError:continue
            if chosen is None:raise RuntimeError("没有可用本地端口，请用 --port 指定端口")
            log_path=root/".cache/local-tool.log"
            error_path=root/".cache/local-tool.error.log"
            flags=subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP if os.name=="nt" else 0
            with log_path.open("ab") as out,error_path.open("ab") as err:
                process=subprocess.Popen([sys.executable,"-m","video_agent.serve","--port",str(chosen)],cwd=root,
                    env=environment(root),stdin=subprocess.DEVNULL,stdout=out,stderr=err,
                    creationflags=flags,start_new_session=os.name!="nt")
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                if health(chosen,root):break
                if process.poll() is not None:
                    raise RuntimeError("本地服务启动失败，请查看 "+str(error_path))
                time.sleep(.15)
            else:
                process.terminate()
                raise RuntimeError("本地服务未就绪，请查看 "+str(error_path))
            result={"status":"running","reused":False,"port":chosen,"homepage_url":f"http://127.0.0.1:{chosen}/"}
        profile={"port":result["port"],"project_id":project_id(root)}
        profile_file=root/".cache/local-service.json"
        temp=profile_file.with_suffix(".json.tmp")
        temp.write_text(json.dumps(profile),encoding="utf-8");temp.replace(profile_file)
    if open_browser:
        webbrowser.open(result["homepage_url"])
    result.update(features=FEATURES,project_id=project_id(root))
    return result

def stop(root=ROOT):
    port=locate(root)
    if not port:return {"status":"stopped","already_stopped":True}
    request(port,"/api/shutdown","POST",{})
    deadline=time.monotonic()+8
    while time.monotonic()<deadline:
        if not health(port,root):break
        time.sleep(.1)
    else:raise RuntimeError("服务尚未完全停止，请稍后运行 status 检查")
    return {"status":"stopped","history_preserved":True}

def doctor(root=ROOT):
    from importlib.metadata import version
    root=Path(root)
    checks=[]
    for name in ("yt-dlp","imageio-ffmpeg","rapidocr-onnxruntime","faster-whisper","opencv-python","pillow","httpx"):
        try:checks.append({"name":name,"ok":True,"version":version(name)})
        except Exception:checks.append({"name":name,"ok":False})
    model=root/"models/faster-whisper-small"
    for filename in ("model.bin","config.json","tokenizer.json","vocabulary.txt"):
        path=model/filename
        checks.append({"name":"Whisper "+filename,"ok":path.is_file() and path.stat().st_size>0})
    return {"status":"ready" if all(c["ok"] for c in checks) else "needs_setup","checks":checks}

def setup(offline=False,port=8765,open_browser=True,root=ROOT):
    ensure_dirs(root)
    with file_lock(Path(root)/".cache/environment-setup.lock",timeout=60):
        return _setup(offline,port,open_browser,root)

def _setup(offline=False,port=8765,open_browser=True,root=ROOT):
    root=Path(root).resolve();ensure_dirs(root)
    os.environ.update({k:v for k,v in environment(root).items() if k.startswith("HF_")})
    from faster_whisper import WhisperModel
    from faster_whisper.utils import download_model
    from imageio_ffmpeg import get_ffmpeg_exe
    from rapidocr_onnxruntime import RapidOCR
    import cv2
    import numpy as np
    model=root/"models/faster-whisper-small"
    needed=("model.bin","config.json","tokenizer.json","vocabulary.txt")
    if not all((model/name).is_file() and (model/name).stat().st_size for name in needed):
        if offline:raise RuntimeError("离线检查发现 Whisper small 模型不完整，请联网运行 setup")
        print("正在下载语音模型，文件保存在项目 models/。",file=sys.stderr,flush=True)
        download_model("small",output_dir=str(model),cache_dir=str(root/".cache/huggingface"))
    subprocess.run([get_ffmpeg_exe(),"-version"],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    ocr=RapidOCR(intra_op_num_threads=2,inter_op_num_threads=1)
    ocr(np.full((64,320,3),255,dtype=np.uint8))
    speech=WhisperModel(str(model),device="cpu",compute_type="int8",cpu_threads=2)
    segments,_=speech.transcribe(np.zeros(16000,dtype=np.float32),language="zh",vad_filter=True)
    list(segments)
    del speech,ocr
    report=doctor(root)
    if report["status"]!="ready":raise RuntimeError("依赖或模型自检未通过，请查看 doctor")
    result=start(port,open_browser,root)
    result.update(status="ready",self_test_passed=True,features=FEATURES)
    (root/".cache/setup.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result

def summarize(url,category="restaurant",wait=True,timeout=3600,port=8765,root=ROOT):
    from .local_jobs import video_url
    url=video_url(url)
    if category!="restaurant":raise ValueError("当前自动生成仅支持 restaurant（中文探店）")
    if timeout<=0:raise ValueError("timeout 必须大于零")
    service=start(port,False,root)
    response=request(service["port"],"/api/jobs","POST",{"url":url,"category":category})
    job=response["job"]
    deadline=time.monotonic()+timeout
    stage=None
    while wait and job["status"] not in ("completed","failed"):
        if time.monotonic()>=deadline:break
        if job.get("stage")!=stage:
            stage=job.get("stage");print(stage,file=sys.stderr,flush=True)
        time.sleep(min(.5,max(0,deadline-time.monotonic())))
        jobs=request(service["port"],"/api/jobs")["jobs"]
        job=next(j for j in jobs if j["id"]==job["id"])
    result={**job,"homepage_url":service["homepage_url"],"reused":response.get("reused",False)}
    if job.get("note_url"):
        result["note_url"]=service["homepage_url"].rstrip("/")+job["note_url"]
    result["timed_out"]=bool(wait and job["status"] not in ("completed","failed"))
    return result
