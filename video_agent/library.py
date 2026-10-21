"""Discover saved notes and build the local tool's single homepage."""
from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
NOTE_TYPES = [
    {"id": "lecture", "label": "知识讲解", "auto_generate": False},
    {"id": "product", "label": "商品推荐与评测", "auto_generate": False},
    {"id": "restaurant", "label": "美食探店", "auto_generate": True},
]


def generation_categories():
    return [item["id"] for item in NOTE_TYPES if item["auto_generate"]]

def read(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}

def restaurant_card(notes):
    """Summarize existing extracted content without guessing a city or new facts."""
    shops = notes.get("shops") or []
    if not shops:
        return {}, ""
    dishes = []
    for shop in shops:
        # A representative dish per stop keeps a multi-stop overview varied.
        for dish in shop.get("dishes", []):
            if isinstance(dish, str) and dish.strip() and dish not in dishes:
                dishes.append(dish)
                break
        if len(dishes) == 4:
            break
    description = f"走访 {len(shops)} 处餐饮点位"
    description += "，介绍" + "、".join(dishes) + "等菜品。" if dishes else "，整理店铺与探店体验。"
    return {"subtype": "美食探店攻略"}, description


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
        fallback, overview = restaurant_card(notes)
        pdfs = sorted(folder.glob("*.pdf"))
        target = folder / "notes.html" if (folder / "notes.html").is_file() else pdfs[0] if pdfs else None
        category = classification.get("primary_scene") or summary.get("category") or (
            "美食探店" if notes.get("shops") else
            "知识讲解" if summary.get("sections") or (folder / "handout.json").is_file() else "待核对分类")
        url = lambda path: "/" + quote(path.relative_to(root).as_posix(), safe="/")
        entries.append({
            "video_id":raw.name, "title":info.get("title", raw.name), "category":category,
            "subtype":classification.get("subtype") or summary.get("subtype") or fallback.get("subtype", ""),
            "duration":float(info.get("duration") or 0), "ready":bool(target),
            "note_url":url(target) if target else "",
            "source_url":"https://www.bilibili.com/video/" + raw.name + "/",
            "description":classification.get("content_brief") or summary.get("overview") or overview,
            "markdown_url":url(folder / "notes.md") if (folder / "notes.md").is_file() else "",
            "updated_at":target.stat().st_mtime if target else raw.stat().st_mtime
        })
    return sorted(entries, key=lambda item:item["updated_at"], reverse=True)

def library_data(root=ROOT):
    entries = scan(root)
    return {"videos": entries, "ready": sum(item["ready"] for item in entries), "categories": NOTE_TYPES}


def build(root=ROOT):
    root = Path(root).resolve()
    (root / "data").mkdir(parents=True, exist_ok=True)
    data = library_data(root)
    entries = data["videos"]
    template = (Path(__file__).parent / "templates/local-tool.html").read_text(encoding="utf-8")
    # Metadata may contain HTML-like text; it must never terminate a script tag.
    bootstrap = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")
    target = root / "data/index.html"
    target.write_text(template.replace("__LIBRARY_DATA__", bootstrap), encoding="utf-8")
    (root / "data/library.json").write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"homepage":str(target),"videos":len(entries),"ready":data["ready"]},ensure_ascii=False))
    return entries

if __name__ == "__main__":
    build()
