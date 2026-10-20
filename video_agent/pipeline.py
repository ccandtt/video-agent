from __future__ import annotations
import argparse,json,os,time,math
from pathlib import Path
from .extract import extract_frames,transcribe,save_json,fingerprint,refine_frames

def project_root():return Path(__file__).resolve().parents[1]
def within(path:Path,root:Path):
    path=path.resolve()
    if not path.is_relative_to(root.resolve()):raise ValueError(f'Path must be inside project directory {root}: {path}')
    return path

def validate_result(data,out):
    from PIL import Image
    duration=data['duration'];errors=[]
    if not data['shops']:errors.append('No shop detected')
    for shop in data['shops']:
        if not 0<=shop['start']<shop['end']<=duration+.01:errors.append(f'Invalid segment: {shop["name"]}')
        if not shop['evidence']:errors.append(f'No evidence: {shop["name"]}')
        for ev in shop['evidence']:
            if not shop['start']-.01<=ev['time']<=shop['end']+.01:errors.append(f'Evidence outside shop: {shop["name"]}')
            p=Path(ev['path']);p=p if p.is_absolute() else out/p
            p=within(p,project_root())
            if not p.exists():errors.append(f'Missing image: {p}')
            else:
                with Image.open(p) as im:im.verify()
    if errors:raise RuntimeError('\n'.join(errors))
    return {'shops':len(data['shops']),'screenshots':sum(len(x['evidence']) for x in data['shops']),'duration':duration,'all_evidence_images_readable':True,'all_timestamps_valid':True,'note':'Structural validation does not prove semantic accuracy.'}

def main():
    parser=argparse.ArgumentParser(description='本地探店视频 → 有视觉证据的中文图文笔记')
    parser.add_argument('video',type=Path);parser.add_argument('--output',type=Path);parser.add_argument('--interval',type=float,default=2);parser.add_argument('--model',default='small');parser.add_argument('--stage',choices=['ocr','asr','notes','all'],default='all');parser.add_argument('--force',action='store_true')
    args=parser.parse_args();root=project_root();video=within(args.video,root)
    if not video.is_file():parser.error(f'Video does not exist: {video}')
    if not math.isfinite(args.interval) or args.interval<=0:parser.error('--interval must be finite and positive')
    if args.model not in ['tiny','base','small','medium','large-v3','large-v3-turbo']:parser.error('Unsupported model name')
    out=within(args.output or root/'data'/'processed'/video.parent.name,root);out.mkdir(parents=True,exist_ok=True)
    os.environ['HF_HOME']=str(root/'.cache'/'huggingface');os.environ['HF_HUB_DISABLE_XET']='1'
    begun=time.monotonic()
    if args.stage in ['ocr','all']:frames,info=extract_frames(video,out,args.interval,args.force)
    if args.stage in ['asr','all']:segments=transcribe(video,out,root,args.model,args.force)
    if args.stage in ['notes','all']:
        from .mining import infer_shops
        from .render import render_notes,shop_introduction,display_shop_name,shop_cuisine
        raw=json.loads((out/'ocr.json').read_text(encoding='utf-8'));frames=raw['frames'];info=raw['video']
        speech=json.loads((out/'transcript.json').read_text(encoding='utf-8'))
        expected_hash=fingerprint(video)
        if raw.get('signature',{}).get('sha256')!=expected_hash or speech.get('signature',{}).get('sha256')!=expected_hash:
            raise RuntimeError('Caches belong to a different video; rerun --stage all --force')
        if not raw.get('complete') or not speech.get('complete'):
            raise RuntimeError('Extraction cache is incomplete; rerun --stage all to resume')
        for frame in frames:within(Path(frame['path']),root)
        segments=speech['segments']
        frames=refine_frames(video,out,segments)
        metadata_path=video.with_suffix('.info.json');meta=json.loads(metadata_path.read_text(encoding='utf-8')) if metadata_path.exists() else {}
        data={'title':meta.get('title',video.stem),'source_url':meta.get('webpage_url',''),'video_path':str(video),'duration':info['duration'],'method':f'本地中文 OCR + Whisper {speech["signature"]["model"]} 语音识别 + 证据规则分段与抽取式摘要','limitations':['OCR 与语音识别可能误读；请结合截图和原视频核对。','价格、口味与评价仅反映视频当时信息和博主观点。','未查询外部地图或商家资料；不补写未展示的地址。','2秒画面采样可能遗漏极短展示；当前不保证识别所有视频的店铺。'],'shops':infer_shops(frames,segments,info['duration'])}
        from .menu import build_menu
        for shop in data['shops']:
            shop['display_name']=display_shop_name(shop,frames)
            shop['cuisine']=shop_cuisine(shop)
            shop['menu']=build_menu(shop,frames)
            existing={e['path'] for e in shop['evidence']}
            for item in shop['menu']:
                image=item.get('image')
                if image and image['path'] not in existing:
                    shop['evidence'].append(dict(path=image['path'],time=image['time'],kind='dish',text=item['name']))
                    existing.add(image['path'])
            shop['introduction']=shop_introduction(shop)
            check=shop.get('name_evidence')
            if check:
                print(f"[名称核对] {shop['name']}：已比对视频文字；{check.get('reason', '')}（自动识别仍可能有误）",flush=True)
        result=validate_result(data,out);save_json(out/'notes.json',data);render_notes(data,out);result['elapsed_seconds']=round(time.monotonic()-begun,2);result['ocr_frames']=len(frames);result['asr_segments']=len(segments);result['input_sha256']=expected_hash;result['uncertain_names']=sum(x['uncertain'] for x in data['shops']);save_json(out/'validation.json',result);print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
