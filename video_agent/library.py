"""Discover saved notes and build the local tool's single homepage."""
from __future__ import annotations
import html
import json
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}

def scan(root=ROOT):
    root = Path(root).resolve()
    entries = []
    for raw in sorted((root / "data/raw").glob("BV*")):
        info = read(raw / "video.info.json")
        if not info:
            continue
        folder = root / "data/processed" / raw.name
        classification = read(folder / "classification.json")
        summary = read(folder / "summary.json")
        notes = read(folder / "notes.json")
        pdfs = sorted(folder.glob("*.pdf"))
        target = folder / "notes.html" if (folder / "notes.html").is_file() else pdfs[0] if pdfs else None
        category = classification.get("primary_scene") or summary.get("category") or (
            "美食探店" if notes.get("shops") else
            "知识讲解" if summary.get("sections") or (folder / "handout.json").is_file() else "待核对分类")
        url = lambda path: "/" + quote(path.relative_to(root).as_posix(), safe="/")
        entries.append({
            "video_id":raw.name, "title":info.get("title", raw.name), "category":category,
            "subtype":classification.get("subtype") or summary.get("subtype", ""),
            "duration":float(info.get("duration") or 0), "ready":bool(target),
            "note_url":url(target) if target else "",
            "source_url":"https://www.bilibili.com/video/" + raw.name + "/",
            "description":classification.get("content_brief") or summary.get("overview", ""),
            "markdown_url":url(folder / "notes.md") if (folder / "notes.md").is_file() else "",
            "updated_at":target.stat().st_mtime if target else raw.stat().st_mtime
        })
    return sorted(entries, key=lambda item:item["updated_at"], reverse=True)

def build():
    entries = scan()
    data = {"videos":entries, "ready":sum(item["ready"] for item in entries)}
    template = (Path(__file__).parent / "templates/local-tool.html").read_text(encoding="utf-8")
    # Metadata may contain HTML-like text; it must never terminate a script tag.
    bootstrap = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")
    target = ROOT / "data/index.html"
    target.write_text(template.replace("__LIBRARY_DATA__", bootstrap), encoding="utf-8")
    (ROOT / "data/library.json").write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"homepage":str(target),"videos":len(entries),"ready":data["ready"]},ensure_ascii=False))
    return entries

if __name__ == "__main__":
    build()
