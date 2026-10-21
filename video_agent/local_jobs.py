"""Persisted local generation queue. Files and subprocesses stay in the project."""
from __future__ import annotations
import json
import os
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
import re
from .library import ROOT, scan, generation_categories

class JobError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status

def video_url(value):
    try:
        url = urlsplit(str(value))
        if url.scheme not in ("http","https") or url.hostname not in (
                "www.bilibili.com","bilibili.com","m.bilibili.com"):
            raise ValueError()
        if url.username or url.password or url.port:
            raise ValueError()
        match = re.match(r"^/video/(BV[a-zA-Z0-9]{10})(?:/|$)", url.path)
        if not match:
            raise ValueError()
        return "https://www.bilibili.com/video/" + match[1] + "/"
    except (ValueError, TypeError):
        raise JobError("请输入有效的哔哩哔哩 BV 视频链接")

def now():
    return datetime.now(timezone.utc).isoformat()

class LocalJobs:
    def __init__(self, root=ROOT, autostart=True):
        self.root = Path(root).resolve()
        self.file = self.root / ".cache/local-jobs.json"
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.stopped = threading.Event()
        self.process = None
        self.thread = None
        self.records = json.loads(self.file.read_text(encoding="utf-8")).get("jobs",[]) if self.file.exists() else []
        for job in self.records:
            if job["status"] in ("downloading","processing"):
                job.update(status="failed",stage="上次服务已退出，缓存保留，可重新提交",error="处理服务中断",updated_at=now())
        self._save()
        if autostart:
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()

    def _save(self):
        temp = self.file.with_suffix(".json.tmp")
        temp.write_text(json.dumps({"jobs":self.records},ensure_ascii=False,indent=2),encoding="utf-8")
        temp.replace(self.file)

    def list(self):
        with self.lock:
            return [dict(job) for job in reversed(self.records)]

    def _update(self, id, **fields):
        with self.lock:
            job = next(item for item in self.records if item["id"] == id)
            job.update(fields, updated_at=now())
            self._save()

    def submit(self, value, category):
        url = video_url(value)
        if category not in generation_categories():
            raise JobError("当前自动生成仅支持美食探店；其他类型可浏览已保存笔记")
        bv = url.rstrip("/").rsplit("/",1)[1]
        with self.lock:
            existing = next((entry for entry in scan(self.root) if entry["video_id"] == bv and entry["ready"]), None)
            active = next((j for j in reversed(self.records) if j["url"] == url and j["status"] in ("queued","downloading","processing")), None)
            if active:
                return dict(active), True
            if not existing and sum(j["status"] in ("queued","downloading","processing") for j in self.records) >= 2:
                raise JobError("请先等待已有任务完成，本机一次处理一条视频",429)
            job = {"id":str(uuid.uuid4()),"url":url,"video_id":bv,"category":category,
                   "title":existing["title"] if existing else bv,
                   "status":"completed" if existing else "queued","progress":100 if existing else 0,
                   "stage":"已找到保存的笔记" if existing else "等待本机处理",
                   "note_url":existing["note_url"] if existing else "",
                   "created_at":now(),"updated_at":now(),"error":""}
            if existing:
                prior = next((j for j in reversed(self.records) if j["url"] == url and j["status"]=="completed"), None)
                if prior:
                    return dict(prior), True
            self.records.append(job)
            self._save()
            self.wake.set()
            return dict(job), bool(existing)

    def _command(self, args, log, id, phase):
        env = os.environ.copy()
        env.update(PYTHONIOENCODING="utf-8",PYTHONUTF8="1")
        env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        self.process = subprocess.Popen(args,cwd=self.root,env=env,stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT,text=True,encoding="utf-8",errors="replace")
        try:
            for line in self.process.stdout:
                log.write(line)
                log.flush()
                if self.stopped.is_set():
                    self.process.terminate()
                    raise RuntimeError("处理服务已停止")
                if line.startswith("OCR "):
                    self._update(id,stage="识别画面文字与店铺信息",progress=35)
                elif line.startswith("ASR "):
                    self._update(id,stage="识别讲解内容",progress=60)
                elif line.startswith("Transition OCR"):
                    self._update(id,stage="补充截图并整理笔记",progress=80)
            if self.process.wait() != 0:
                raise RuntimeError(phase + "未完成，已保留缓存；可重新提交。")
        finally:
            self.process = None

    def _run(self, job):
        id,bv = job["id"],job["video_id"]
        raw = self.root / "data/raw" / bv
        raw.mkdir(parents=True,exist_ok=True)
        video = raw / "video.mp4"
        log_path = self.root / ".cache" / ("local-job-" + id + ".log")
        with log_path.open("a",encoding="utf-8") as log:
            if not video.exists():
                from imageio_ffmpeg import get_ffmpeg_exe
                self._update(id,status="downloading",stage="下载视频",progress=5)
                self._command([sys.executable,"-m","yt_dlp","--no-playlist","--socket-timeout","20",
                    "--retries","2","--write-info-json","--match-filter","duration <= 1200",
                    "--cache-dir",str(self.root/".cache/yt-dlp"),
                    "-f","bv*[vcodec^=avc1][width<=1080][height<=1920]+ba/b",
                    "--merge-output-format","mp4","--ffmpeg-location",get_ffmpeg_exe(),
                    "-o",str(raw/"video.%(ext)s"),job["url"]],log,id,"下载")
            from .extract import probe_video
            if not video.exists() or probe_video(video)["duration"] > 1200:
                raise JobError("当前支持最长 20 分钟的视频，或该视频暂时无法下载")
            meta = json.loads((raw/"video.info.json").read_text(encoding="utf-8")) if (raw/"video.info.json").exists() else {}
            self._update(id,status="processing",title=meta.get("title",bv),stage="识别视频并整理图文笔记",progress=20)
            self._command([sys.executable,"-m","video_agent.pipeline",str(video),
                           "--output",str(self.root/"data/processed"/bv)],log,id,"视频处理")
            self._update(id,status="completed",stage="图文笔记已保存",progress=100,
                         note_url="/data/processed/"+bv+"/notes.html",error="")
            if self.root == ROOT:
                from .library import build
                build()

    def _loop(self):
        while not self.stopped.is_set():
            with self.lock:
                job = next((dict(j) for j in self.records if j["status"]=="queued"), None)
                if job:
                    self._update(job["id"],status="downloading",stage="开始本机处理",progress=3)
            if not job:
                self.wake.wait(1)
                self.wake.clear()
                continue
            try:
                self._run(job)
            except Exception as error:
                message = str(error)[:300] or "处理失败，请查看本地日志"
                self._update(job["id"],status="failed",stage="生成未完成，可重新提交",error=message)

    def close(self):
        self.stopped.set()
        self.wake.set()
        if self.process and self.process.poll() is None:
            self.process.terminate()
        if self.thread:
            self.thread.join(timeout=3)
