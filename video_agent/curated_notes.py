"""Render an explicitly source-curated video note; this does not classify videos."""
from __future__ import annotations
import html
import json
import sys
from pathlib import Path
from urllib.parse import quote
from PIL import Image
from .extract import fingerprint, save_json

ROOT = Path(__file__).resolve().parents[1]

def stamp(t):
    seconds = int(t)
    return f"{seconds//3600}:{seconds//60%60:02}:{seconds%60:02}" if seconds >= 3600 else f"{seconds//60:02}:{seconds%60:02}"

def render(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT / "data/processed"):
        raise ValueError("Curated notes must remain under project data/processed")
    out = path.parent
    data = json.loads(path.read_text(encoding="utf-8"))
    video = ROOT / "data/raw" / data["video_id"] / "video.mp4"
    sha = fingerprint(video)
    for cache in ("ocr.json", "transcript.json"):
        cached = json.loads((out / cache).read_text(encoding="utf-8"))
        if not cached.get("complete") or cached.get("signature", {}).get("sha256") != sha:
            raise ValueError("Incomplete extraction or a cache for a different video")
    esc = lambda value: html.escape(str(value), quote=True)
    cards, navigation, images = [], [], []
    md = [f'# {data["title"]}', "", f'来源：{data["source_url"]}', "", data["overview"], ""]
    for index, section in enumerate(data["sections"], 1):
        time = float(section["time"])
        end = float(section["end"])
        if not 0 <= time < end <= data["duration"] + .1:
            raise ValueError("Invalid chapter range")
        anchor = f"section-{index}"
        navigation.append(f'<a href="#{anchor}">{index:02} · {esc(section["title"])}</a>')
        md.extend([f'## {section["title"]}', "", f'[视频 {stamp(time)}]({data["source_url"]}?t={int(time)})', ""])
        content = ""
        for paragraph in section["paragraphs"]:
            md.extend([paragraph, ""])
            content += f"<p>{esc(paragraph)}</p>"
        if section.get("table"):
            table = section["table"]
            content += '<div class="table-wrap"><table>' + "".join("<tr>" + "".join(f'<{"th" if row_index==0 else "td"}>{esc(value)}</{"th" if row_index==0 else "td"}>' for value in row) + "</tr>" for row_index, row in enumerate(table)) + "</table></div>"
            md.extend(["| " + " | ".join(table[0]) + " |", "| " + " | ".join(["---"] * len(table[0])) + " |"] + ["| " + " | ".join(row) + " |" for row in table[1:]] + [""])
        gallery = ""
        for frame in section.get("images", []):
            file = (out / frame["path"]).resolve()
            if not file.is_relative_to(out) or not file.is_file() or not time <= frame["time"] < end:
                raise ValueError("Image is missing, outside its chapter or outside the note directory")
            with Image.open(file) as image:
                image.verify()
            src = quote(frame["path"].replace("\\", "/"), safe="/")
            gallery += f'<figure><a href="{src}" target="_blank" rel="noopener"><img src="{src}" alt="{esc(frame["caption"])}" loading="lazy"></a><figcaption><button data-time="{frame["time"]}">{stamp(frame["time"])}</button><span>{esc(frame["caption"])}</span></figcaption></figure>'
            md.extend([f'![{frame["caption"]}]({src})', "", f'画面 {stamp(frame["time"])}：{frame["caption"]}', ""])
            images.append(frame["path"])
        cards.append(f'<article id="{anchor}"><div class="section-head"><h2>{esc(section["title"])}</h2><button data-time="{time}">{stamp(time)}</button></div>{content}<div class="gallery">{gallery}</div></article>')
    css = '*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f6f5f0;color:#253a35;font:15px/1.9 system-ui,"Microsoft YaHei",sans-serif}header{background:#24463c;color:#fff;padding:38px max(22px,calc((100vw - 1200px)/2))}h1{font-size:clamp(25px,3vw,34px);line-height:1.5;margin:12px 0}header .overview{max-width:920px;color:#dfebe4}.tag{font-size:12px;letter-spacing:.08em;color:#d6c99e}.header-links{display:flex;gap:24px;font-size:13px}header a{color:#e8ddbf}.layout{max-width:1200px;padding:0 22px;margin:28px auto;display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:24px}article{background:#fff;border:1px solid #e0e4dc;border-radius:12px;padding:26px;margin-bottom:22px;scroll-margin-top:16px}.section-head{display:flex;justify-content:space-between;gap:16px;align-items:baseline}h2{font-size:22px;line-height:1.5;margin:0 0 12px}p{margin:12px 0}a{color:#2e7057;text-decoration:none}a:hover{text-decoration:underline}button{font:inherit;font-size:12px;white-space:nowrap;cursor:pointer;border:0;border-radius:5px;padding:4px 8px;background:#e9f2e9;color:#2a684f}.gallery{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}figure{margin:14px 0 0;border:1px solid #e1e5dc;border-radius:8px;overflow:hidden}figure a{display:block;background:#eef0e9}figure img{display:block;width:100%;height:350px;object-fit:contain}figcaption{font-size:12px;padding:10px 12px;display:flex;align-items:start;gap:8px}figcaption span{flex:1}aside{align-self:start;position:sticky;top:18px}.panel{background:#fff;border:1px solid #e0e4dc;border-radius:10px;padding:16px;margin-bottom:16px}video{width:100%;max-height:380px;background:#111}.small{font-size:12px;color:#6e7b70}nav{display:grid;gap:8px}nav a{font-size:13px}footer{max-width:1200px;padding:4px 22px 30px;margin:auto;font-size:12px;color:#718076}.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #dce3d9;text-align:left;padding:8px;min-width:90px}th{background:#eff4ec}@media(max-width:850px){.layout{grid-template-columns:1fr}aside{position:static;grid-row:1}video{max-height:240px}nav{grid-template-columns:1fr 1fr}}@media(max-width:520px){.layout{padding:0 12px}header{padding:25px 18px}article{padding:20px 16px}.gallery{grid-template-columns:1fr}figure img{height:380px}h2{font-size:20px}}'
    js = "const video=document.querySelector('video');let pending=null;function seek(time){pending=time;if(video.readyState>=1){video.currentTime=Math.min(time,video.duration-.1);pending=null;}video.scrollIntoView({block:'nearest',behavior:'smooth'});}document.addEventListener('click',e=>{const button=e.target.closest('[data-time]');if(button)seek(Number(button.dataset.time));});video.addEventListener('loadedmetadata',()=>{if(pending!==null)seek(pending);});"
    video_url = quote("../../raw/" + data["video_id"] + "/video.mp4", safe="/")
    page = f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(data["title"])} · 图文笔记</title><style>{css}</style></head><body><header><div class="tag">{esc(data["category"])} · {esc(data.get("subtype",""))}</div><h1>{esc(data["title"])}</h1><p class="overview">{esc(data["overview"])}</p><div class="header-links"><a href="/">← 返回工具首页</a><a href="{esc(data["source_url"])}" target="_blank" rel="noopener">原视频 ↗</a></div></header><div class="layout"><main>{"".join(cards)}</main><aside><div class="panel"><video controls preload="metadata" src="{video_url}"></video><p class="small">点击时间戳回看原视频，点击截图查看大图。</p></div><div class="panel"><h3>内容目录</h3><nav>{"".join(navigation)}</nav></div><div class="panel small">{esc(data["note"])}</div></aside></div><footer>{esc(data["note"])}</footer><script>{js}</script></body></html>'
    (out / "notes.html").write_text(page, encoding="utf-8")
    md.extend(["---", "", data["note"], ""])
    (out / "notes.md").write_text("\n".join(md), encoding="utf-8")
    result = {"video_id":data["video_id"], "sections":len(cards), "selected_images":len(images),
              "all_images_readable":True, "all_timestamps_valid":True, "input_sha256":sha,
              "ocr_frames":len(json.loads((out/"ocr.json").read_text(encoding="utf-8"))["frames"]),
              "asr_segments":len(json.loads((out/"transcript.json").read_text(encoding="utf-8"))["segments"]),
              "method":"基于完整语音、抽样 OCR 与截图核看的单视频整理；未开放为通用网页生成类别。"}
    save_json(out / "summary_validation.json", result)
    print(json.dumps(result, ensure_ascii=False))
    return result

if __name__ == "__main__":
    render(sys.argv[1])
