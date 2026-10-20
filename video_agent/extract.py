"""Local, resumable visual and speech extraction. All caches stay in project."""
from __future__ import annotations
import hashlib,json,os,subprocess,time
from pathlib import Path

def save_json(path:Path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)

def fingerprint(video:Path):
    h=hashlib.sha256()
    with video.open('rb') as f:
        while chunk:=f.read(1024*1024):h.update(chunk)
    return h.hexdigest()

def probe_video(video:Path):
    import cv2
    cap=cv2.VideoCapture(str(video))
    if not cap.isOpened():raise ValueError(f'Cannot open video: {video}')
    fps=cap.get(cv2.CAP_PROP_FPS);count=cap.get(cv2.CAP_PROP_FRAME_COUNT)
    data={'duration':count/fps if fps else 0,'width':int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),'height':int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),'fps':fps}
    cap.release()
    if data['duration']<=0:raise ValueError('Invalid video duration')
    return data

def extract_frames(video:Path,out:Path,interval:float=2.0,force=False):
    import cv2,numpy as np
    from rapidocr_onnxruntime import RapidOCR
    signature={'sha256':fingerprint(video),'interval':interval,'ocr':'rapidocr-onnxruntime-1.4.4','width':720}
    index=out/'ocr.json';cached={}
    if index.exists() and not force:
        old=json.loads(index.read_text(encoding='utf-8'))
        if old.get('signature')==signature:
            cached={round(x['time'],3):x for x in old['frames'] if Path(x['path']).exists()}
            if old.get('complete') and len(cached)==len(old['frames']):return old['frames'],old['video']
    info=probe_video(video);(out/'frames').mkdir(parents=True,exist_ok=True)
    engine=RapidOCR(det_use_cuda=False,cls_use_cuda=False,rec_use_cuda=False,intra_op_num_threads=2,inter_op_num_threads=1)
    cap=cv2.VideoCapture(str(video));frames=[];start=time.monotonic()
    for i,t in enumerate(np.arange(0,info['duration'],interval)):
        t=round(float(t),3)
        if t in cached:frames.append(cached[t]);continue
        cap.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,full=cap.read()
        if not ok:raise RuntimeError(f'Frame decode failed at {t}s')
        ratio=720/full.shape[1];image=cv2.resize(full,(720,round(full.shape[0]*ratio)))
        result,_=engine(image)
        ocr=[{'box':[[round(float(a),1) for a in pt] for pt in box],'text':text,'score':round(float(score),4)} for box,text,score in (result or [])]
        path=out/'frames'/f'{i:05d}_{t:07.2f}.jpg'
        if not cv2.imwrite(str(path),full,[cv2.IMWRITE_JPEG_QUALITY,90]):raise RuntimeError(f'Cannot save image: {path}')
        grey=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
        # Border/watermark excluded from sharpness so text overlays cannot dominate.
        crop=grey[int(grey.shape[0]*.15):int(grey.shape[0]*.65)]
        frames.append({'time':t,'path':str(path),'width':image.shape[1],'height':image.shape[0],'sharpness':round(float(cv2.Laplacian(crop,cv2.CV_64F).var()),3),'ocr':ocr})
        if i%10==0:
            save_json(index,{'signature':signature,'video':info,'frames':frames})
            print(f'OCR {i+1}/{int(info["duration"]//interval)+1}, time={t:.0f}s, elapsed={time.monotonic()-start:.0f}s',flush=True)
    cap.release();save_json(index,{'signature':signature,'video':info,'frames':frames,'complete':True,'elapsed_seconds':round(time.monotonic()-start,2)})
    return frames,info

def transcribe(video:Path,out:Path,root:Path,model='small',force=False):
    from faster_whisper import WhisperModel
    from imageio_ffmpeg import get_ffmpeg_exe
    signature={'sha256':fingerprint(video),'model':model,'language':'zh','beam_size':5}
    path=out/'transcript.json'
    os.environ['HF_HOME']=str(root/'.cache'/'huggingface')
    if path.exists() and not force:
        cached=json.loads(path.read_text(encoding='utf-8'))
        if cached.get('signature')==signature:return cached['segments']
    audio=out/'audio.wav'
    subprocess.run([get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-i',str(video),'-vn','-ac','1','-ar','16000',str(audio)],check=True)
    model_path=root/'models'/f'faster-whisper-{model}'
    model_arg=str(model_path) if (model_path/'model.bin').exists() else model
    print('Loading speech model',model_arg,flush=True)
    started=time.monotonic()
    engine=WhisperModel(model_arg,device='cpu',compute_type='int8',cpu_threads=6,download_root=str(root/'models'))
    segments,info=engine.transcribe(str(audio),language='zh',beam_size=5,vad_filter=True,condition_on_previous_text=False)
    data=[]
    for segment in segments:
        data.append({'start':round(segment.start,3),'end':round(segment.end,3),'text':segment.text.strip(),'avg_logprob':round(segment.avg_logprob,3),'no_speech_prob':round(segment.no_speech_prob,3)})
        if len(data)%15==0:print(f'ASR {segment.end:.1f}s: {segment.text.strip()}',flush=True)
    if not data:raise RuntimeError('No speech recognized; check audio and model')
    save_json(path,{'signature':signature,'language':info.language,'segments':data,'complete':True,'elapsed_seconds':round(time.monotonic()-started,2)})
    return data


def refine_frames(video:Path,out:Path,segments:list):
    """Densely sample near spoken transitions to retrieve fleeting title evidence."""
    import re,cv2
    from rapidocr_onnxruntime import RapidOCR
    index=out/'ocr.json';raw=json.loads(index.read_text(encoding='utf-8'))
    frames=raw['frames'];duration=raw['video']['duration'];known={round(f['time'],2) for f in frames}
    trigger=re.compile(r'第\s*[一二两三四五六七八九十\d]+\s*家|下一家|接下来这家|最后一家')
    times=set()
    # Single numbered subtitle is a transition; multi-entry recap is not.
    anchors=[]
    for f in frames:
        if Path(f['path']).name.startswith('dense_'):continue
        captions=[x['text'] for x in f['ocr'] if trigger.search(x['text'])]
        if len(captions)==1 and f['time']<duration-10:anchors.append({'start':f['time'],'text':captions[0]})
    for s in segments+anchors:
        if trigger.search(s['text']):
            for k in range(-5,16):
                t=round(s['start']+k*.4,2)
                if 0<=t<duration and t not in known:times.add(t)
    # Align a visual observation with each spoken utterance so brief dish
    # labels can correct ASR without supplying a hand-authored vocabulary.
    for segment in segments:
        t=round((segment['start']+segment['end'])/2,2)
        if 0<=t<duration and t not in known:times.add(t)
    if not times:return frames
    engine=RapidOCR(intra_op_num_threads=2,inter_op_num_threads=1)
    cap=cv2.VideoCapture(str(video));begun=time.monotonic()
    for i,t in enumerate(sorted(times)):
        cap.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,full=cap.read()
        if not ok:raise RuntimeError(f'Dense frame decode failed at {t}')
        image=cv2.resize(full,(720,round(full.shape[0]*720/full.shape[1])))
        result,_=engine(image)
        ocr=[{'box':[[round(float(a),1) for a in pt] for pt in box],'text':text,'score':round(float(score),4)} for box,text,score in (result or [])]
        path=out/'frames'/f'dense_{t:08.2f}.jpg'
        if not cv2.imwrite(str(path),full,[cv2.IMWRITE_JPEG_QUALITY,90]):raise RuntimeError(f'Cannot save image: {path}')
        grey=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY);crop=grey[int(grey.shape[0]*.15):int(grey.shape[0]*.65)]
        frames.append({'time':t,'path':str(path),'width':image.shape[1],'height':image.shape[0],'sharpness':round(float(cv2.Laplacian(crop,cv2.CV_64F).var()),3),'ocr':ocr})
        if i%20==0:print(f'Transition OCR {i+1}/{len(times)}',flush=True)
    cap.release();frames.sort(key=lambda x:x['time']);raw['frames']=frames;raw['transition_refinement']=True;raw['refinement_seconds']=round(time.monotonic()-begun,2);save_json(index,raw)
    return frames
