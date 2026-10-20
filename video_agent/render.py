"""Render evidence-linked food exploration notes without external dependencies."""
from __future__ import annotations

from .menu import build_menu
import html
import os
from pathlib import Path
import re
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit


def timestamp(seconds: float | int) -> str:
    value = max(0, int(float(seconds or 0)))
    hours, remaining = divmod(value, 3600)
    minutes, seconds = divmod(remaining, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}" if hours else f"{minutes:02}:{seconds:02}"


def _escape_md(value: Any) -> str:
    value = str(value).replace("\r", " ").replace("\n", " ")
    value = html.escape(value, quote=False)
    return re.sub(r"([\\`*_{}\[\]()#!|])", r"\\\1", value)


def _text(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _relative_url(value: str | Path, output_dir: Path) -> str:
    path = Path(value)
    if path.is_absolute():
        relative = os.path.relpath(path, output_dir)
    else:
        relative = os.fspath(path)
    return quote(relative.replace("\\", "/"), safe="/:")


def _source_at(source: str, seconds: float) -> str:
    parts = urlsplit(source)
    if parts.scheme not in {"http", "https"}:
        return ""
    query = [(key, value) for key, value in parse_qsl(parts.query) if key != "t"]
    query.append(("t", str(max(0, int(float(seconds))))))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _button(seconds: float | int, label: str | None = None) -> str:
    safe_seconds = max(0, float(seconds or 0))
    return f'<button class="time" data-time="{safe_seconds:.3f}" type="button" title="定位到视频画面">{_text(label or timestamp(safe_seconds))}</button>'


def _fact_refs(shop: dict[str, Any], field: str, value: Any) -> list[dict[str, Any]]:
    mapping = shop.get("fact_evidence") or {}
    if not isinstance(mapping, dict):
        return []
    return [item for item in mapping.get(field, []) if isinstance(item, dict)
            and str(item.get("text", "")) == str(value) and item.get("time") is not None]


def _fact_source(item: dict[str, Any]) -> str:
    source = str(item.get("source") or "来源未标注")
    return source.upper() if source.casefold() in {"ocr", "asr"} else source


def _fact_html(shop: dict[str, Any], field: str, value: Any) -> str:
    references = []
    for item in _fact_refs(shop, field, value):
        original = str(item.get("original") or "")
        title = f"识别文本（可能误识别）：{original}" if original else "自动提取依据，请结合视频核对"
        references.append(f'<span class="fact-reference" title="{_text(title)}">{_button(item["time"])} <span class="fact-source">{_text(_fact_source(item))}</span></span>')
    return _text(value) + (" " + " ".join(references) if references else "")


def _fact_md(shop: dict[str, Any], field: str, value: Any, source: str) -> str:
    references = []
    for item in _fact_refs(shop, field, value):
        seconds = float(item["time"])
        url = _source_at(source, seconds)
        position = f"[{timestamp(seconds)}]({url})" if url else timestamp(seconds)
        reference = f"{position} · {_escape_md(_fact_source(item))}"
        original = str(item.get("original") or "")
        if original and original != str(value):
            reference += f"；识别文本：{_escape_md(original)}"
        references.append(reference)
    return _escape_md(value) + ("（" + " / ".join(references) + "）" if references else "")


def _field_list(shop: dict[str, Any], field: str, label: str) -> str:
    values = shop.get(field) or []
    if not values:
        return ""
    items = "".join(f"<li>{_fact_html(shop, field, item)}</li>" for item in values)
    return f'<div class="fact"><h3>{label}</h3><ul>{items}</ul></div>'


def display_shop_name(shop: dict[str, Any], frames: list[dict[str, Any]] | None = None) -> str:
    """Keep brand casing; recover word boundaries from matching sign OCR."""
    name = re.sub(r"\s+", " ", str(shop.get("display_name") or shop.get("name") or "未识别店铺")).strip()
    name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    if frames and re.fullmatch(r"[A-Za-z ]+", name):
        compact = name.replace(" ", "").casefold()
        candidates = []
        for frame in frames:
            if not shop.get("start", 0) <= frame["time"] <= min(shop.get("end", 0), shop.get("start", 0) + 6):
                continue
            for item in frame.get("ocr", []):
                text = re.sub(r"\s+", " ", item.get("text", "")).strip()
                if " " in text and text.replace(" ", "").casefold() == compact:
                    candidates.append((item.get("score", 0), text))
        if candidates:
            sign = max(candidates)[1]
            if name.isupper():
                name = sign
            elif name[0].isupper():
                name = sign.title()
            else:
                words = sign.split()
                name = words[0].lower() + " " + " ".join(word.title() for word in words[1:])
    return name


def shop_cuisine(shop: dict[str, Any]) -> str:
    if shop.get("cuisine"):
        return str(shop["cuisine"])
    for item in shop.get("transcript", []):
        match = re.search(r"属于([\u4e00-\u9fff]{2,8})餐(?:[。！？，]|$)", str(item.get("text", "")))
        if match:
            return match.group(1) + "菜"
    return ""


def shop_introduction(shop: dict[str, Any]) -> str:
    """Write a natural, short restaurant description using recognized evidence."""
    if shop.get("introduction"):
        return str(shop["introduction"])
    name = display_shop_name(shop)
    cuisine = shop_cuisine(shop)
    separator = " " if re.search(r"[A-Za-z0-9]$", name) else ""
    descriptions = [f"{name}{separator}属于{cuisine}。"] if cuisine else []
    segments = [str(item.get("text") or "").strip() for item in shop.get("transcript", [])]
    for line in segments:
        if "主打" in line and len(line) <= 60:
            descriptions.append(line.rstrip("。！？") + "。")
            break
    intro_dishes = [m['name'] for m in shop['menu']] if 'menu' in shop else shop.get('dishes', [])
    if not descriptions and intro_dishes:
        descriptions.append(name + "的菜品包括" + "、".join(map(str, intro_dishes[:3])) + "。")
    highlights = shop.get("highlights") or []
    candidates = [value for value in highlights if not any(word in str(value).split("，")[0] for word in ("建议", "每一个", "我对"))]
    if candidates or highlights:
        detail = re.sub(r"^讲解摘录（自动识别）：", "", str((candidates or highlights)[0]))
        detail = "，".join(re.split(r"[，。！？]", detail)[:2]).strip()
        detail = detail.replace("真的非常", "").replace("非常正宗", "正宗")
        detail = re.sub(r"^(?:它家|他家|她家)的", "", detail)
        if detail:
            descriptions.append(detail[:90].rstrip("，、") + "。")
    return "".join(descriptions[:3]) or "视频未提供足够的餐厅简介信息。"


def _intro_html(shop: dict[str, Any]) -> str:
    text, cuisine = shop_introduction(shop), shop_cuisine(shop)
    if cuisine and cuisine in text:
        before, after = text.split(cuisine, 1)
        return _text(before) + "<strong>" + _text(cuisine) + "</strong>" + _text(after)
    return _text(text)


def _intro_md(shop: dict[str, Any]) -> str:
    text, cuisine = shop_introduction(shop), shop_cuisine(shop)
    if cuisine and cuisine in text:
        before, after = text.split(cuisine, 1)
        return _escape_md(before) + "**" + _escape_md(cuisine) + "**" + _escape_md(after)
    return _escape_md(text)


def storefront_evidence(shop: dict[str, Any]) -> dict[str, Any] | None:
    # Do not substitute a food/price screenshot when no entrance candidate exists.
    return next((item for item in shop.get("evidence", [])
                 if item.get("kind") in {"storefront", "shop_name", "context", "name_reference"} and item.get("path")), None)


def _point_photo_label(shop: dict[str, Any], image: dict[str, Any]) -> str:
    return "点位画面" if image.get("kind") in {"context", "name_reference"} else "店铺门头"


def _menu_html(shop, index, output_dir):
    menu = shop.get('menu') if 'menu' in shop else build_menu(shop)
    rows, cards = [], []
    for n, item in enumerate(menu or [], 1):
        anchor = f'shop-{index}-dish-{n}'
        name = _text(item['name'])
        extras = ' · '.join(_text(v) for v in (item.get('price'), item.get('review')) if v)
        refs = item.get('references') or []
        times = ' '.join(_button(r['time']) for r in refs)
        image = item.get('image')
        if not times and image:
            times = _button(image['time'])
        link = f'<a class="dish-link" href="#{anchor}">查看图片 ↓</a>' if image else ''
        rows.append(f'<li><strong>{name}</strong>{" · " + extras if extras else ""}<span class="menu-actions">{times}{link}</span></li>')
        if image:
            url = _text(_relative_url(image['path'], output_dir))
            cards.append(f'<figure class="dish-card" id="{anchor}"><div class="dish-heading"><strong>{name}</strong><span>{_text(item.get("price") or "")}</span></div><a class="image-link" href="{url}" target="_blank" rel="noopener"><img src="{url}" alt="{name}" loading="lazy"></a><figcaption><span>{_text(item.get("review") or "")}</span>{_button(image["time"])}<a href="#shop-{index}-menu">返回菜单 ↑</a></figcaption></figure>')
    listing = f'<div class="fact menu" id="shop-{index}-menu"><h3>推荐菜单</h3><p class="menu-note">整理视频中介绍的菜品，口味评价来自博主。</p><ul>{"".join(rows)}</ul></div>' if rows else '<p class="missing">视频未提取到明确菜品。</p>'
    gallery = '<h3 class="evidence-title">菜品图鉴</h3><div class="evidence">' + ''.join(cards) + '</div>' if cards else '<h3 class="evidence-title">菜品图鉴</h3><p class="missing">尚未找到能明确关联菜名的截图。</p>'
    return listing, gallery


def _render_md(data: dict[str, Any], output_dir: Path) -> str:
    source = str(data.get("source_url") or "")
    video_path = data.get("video_path")
    count = len(data.get("shops") or [])
    count_text = f"提取点位：{count} 处" if any(s.get("name_type") == "descriptive" for s in data.get("shops") or []) else f"提取店铺：{count} 家"
    lines = [f"# {_escape_md(data.get('title') or '探店攻略')}", ""]
    if source and _source_at(source, 0):
        lines.extend([f"视频来源：[打开原视频]({_source_at(source, 0)})", ""])
    if video_path:
        lines.extend([f"本地视频：[播放视频]({_relative_url(video_path, output_dir)})", ""])
    lines.extend([f"视频时长：{timestamp(data.get('duration', 0))} · {count_text}", "",
                  f"处理方法：{_escape_md(data.get('method') or '语音、画面与时间信息联合提取')}", "",
                  "条目来自视频画面与讲解；点击时间戳可回看对应内容。", ""])
    if data.get("limitations"):
        lines.extend(["## 本次处理边界", ""])
        lines.extend(f"- {_escape_md(item)}" for item in data["limitations"])
        lines.append("")
    fields = [("prices", "未关联的价格线索"), ("locations", "地点线索"), ("highlights", "讲解要点")]
    for index, shop in enumerate(data.get("shops") or [], 1):
        start, end = float(shop.get("start", 0)), float(shop.get("end", 0))
        label = f"{timestamp(start)}–{timestamp(end)}"
        source_url = _source_at(source, start)
        time_link = f"[{label}]({source_url})" if source_url else label
        uncertain = "（描述性名称，未注明店名）" if shop.get("name_type") == "descriptive" else "（名称待核对）" if shop.get("uncertain") else ""
        lines.extend([f"## {index}. {_escape_md(display_shop_name(shop))}{uncertain}", "",
                      f"视频位置：{time_link} · 本地定位：{timestamp(start)}", ""])
        lines.extend([_intro_md(shop), ""])
        storefront = storefront_evidence(shop)
        if storefront:
            lines.extend([f"![{_point_photo_label(shop, storefront)}]({_relative_url(storefront['path'], output_dir)})", "",
                          f"{_point_photo_label(shop, storefront)} · {timestamp(storefront['time'])}", ""])
        menu = shop.get('menu') if 'menu' in shop else build_menu(shop)
        lines.extend([f'<a id="shop-{index}-menu"></a>', '', '### 推荐菜单', '', '整理视频中介绍的菜品，口味评价来自博主。', ''])
        for n, item in enumerate(menu or [], 1):
            value = _fact_md(shop, 'dishes', item['name'], source)
            extras = ' · '.join(_escape_md(v) for v in (item.get('price'), item.get('review')) if v)
            link = f" · [查看图片](#shop-{index}-dish-{n})" if item.get('image') else ''
            lines.append('- ' + value + (' · ' + extras if extras else '') + link)
        lines.append('')
        lines.extend(['### 菜品图鉴', ''])
        for n, item in enumerate(menu or [], 1):
            image = item.get('image')
            if image:
                lines.extend([f'<a id="shop-{index}-dish-{n}"></a>', '', f"**{_escape_md(item['name'])}**" + (' · ' + _escape_md(item['price']) if item.get('price') else ''), '',
                              f"![{_escape_md(item['name'])}]({_relative_url(image['path'], output_dir)})", '',
                              f"{timestamp(image['time'])} · {_escape_md(item.get('review') or '')} · [返回菜单](#shop-{index}-menu)", ''])
        for field, title in fields:
            values = shop.get(field) or []
            if values:
                lines.extend([f"### {title}", ""])
                lines.extend(f"- {_fact_md(shop, field, value, source)}" for value in values)
                lines.append("")
        missing = []
        if not shop.get("locations"):
            missing.append("视频未提取到可确认的详细地址")
        if not shop.get("prices") and not any(m.get("price") for m in shop.get("menu", [])):
            missing.append("视频未提取到可确认的价格")
        if missing:
            lines.extend(["；".join(missing) + "。", ""])
        evidence = shop.get("evidence") or []
        if evidence:
            lines.extend(["### 其他视频画面", ""])
            for item in evidence:
                if item is storefront or any(m.get("image", {}).get("path") == item.get("path") for m in menu if m.get("image")):
                    continue
                seconds = float(item.get("time", start))
                note = str(item.get("text") or item.get("kind") or "画面证据")
                evidence_url = _source_at(source, seconds)
                position = f"[{timestamp(seconds)}]({evidence_url})" if evidence_url else timestamp(seconds)
                lines.extend([f"**{position} · {_escape_md(note)}**", ""])
                if item.get("path"):
                    lines.extend([f"![{_escape_md(note)}]({_relative_url(item['path'], output_dir)})", ""])
        transcript = shop.get("transcript") or []
        if transcript:
            lines.extend(["### 讲解识别文本（可能误识别）", ""])
            lines.extend(f"- {timestamp(item.get('start', start))} {_escape_md(item.get('text') or '')}" for item in transcript)
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_html(data: dict[str, Any], output_dir: Path) -> str:
    title = str(data.get("title") or "探店攻略")
    shops = data.get("shops") or []
    source = str(data.get("source_url") or "")
    mixed_stops = any(s.get("name_type") == "descriptive" for s in shops)
    directory_label = "探吃目录" if mixed_stops else "店铺目录"
    count_label = "处探吃点" if mixed_stops else "家店铺"
    source_link = _source_at(source, 0)
    source_html = f'<a class="source" href="{_text(source_link)}" target="_blank" rel="noopener">打开原视频 ↗</a>' if source_link else ""
    if data.get("video_path"):
        video = f'<video id="video" controls preload="metadata" playsinline src="{_text(_relative_url(data["video_path"], output_dir))}"></video>'
    else:
        video = '<p class="empty">未提供本地视频。</p>'
    nav = "".join(f'<a href="#shop-{index}"><span>{index:02}</span>{_text(display_shop_name(shop))}</a>' for index, shop in enumerate(shops, 1))
    cards = []
    for index, shop in enumerate(shops, 1):
        start, end = float(shop.get("start", 0)), float(shop.get("end", 0))
        name = display_shop_name(shop)
        storefront = storefront_evidence(shop)
        storefront_html = ""
        if storefront:
            url = _text(_relative_url(storefront["path"], output_dir))
            photo_label = _point_photo_label(shop, storefront)
            storefront_html = f'<figure class="storefront"><a class="image-link" href="{url}" target="_blank" rel="noopener"><img src="{url}" alt="{_text(name)} · {photo_label}" loading="lazy"></a><figcaption><span>{photo_label}</span>{_button(storefront["time"])}</figcaption></figure>'
        identity_hint = '<p class="menu-note">按视频食物线索命名，未注明店名。</p>' if shop.get("name_type") == "descriptive" else ""
        overview = f'<div class="shop-overview"><div class="shop-summary"><div class="shop-head"><div><span class="index">STOP {index:02}</span><h2>{_text(name)}</h2></div></div><p class="range">视频位置 {_button(start)} <span>— {timestamp(end)}</span></p><p class="restaurant-intro">{_intro_html(shop)}</p>{identity_hint}</div>{storefront_html}</div>'
        menu_html, dish_gallery = _menu_html(shop, index, output_dir)
        assigned_prices = {m.get('price') for m in shop.get('menu', []) if m.get('price')}
        remaining = dict(shop, prices=[v for v in shop.get('prices', []) if str(v).replace('￥', '¥') not in assigned_prices])
        fields = menu_html + ''.join(_field_list(remaining, field, label) for field, label in [("prices", "未关联的价格线索"), ("locations", "地点线索"), ("highlights", "讲解要点")])
        missing = []
        if not shop.get("locations"):
            missing.append("视频未提取到可确认的详细地址")
        if not shop.get("prices") and not any(m.get("price") for m in shop.get("menu", [])):
            missing.append("视频未提取到可确认的价格")
        missing_html = f'<p class="missing">{_text("；".join(missing))}。</p>' if missing else ""
        evidence_html = []
        for item in shop.get("evidence") or []:
            if item is storefront or any(m.get("image", {}).get("path") == item.get("path") for m in shop.get("menu", build_menu(shop)) if m.get("image")):
                continue
            seconds = float(item.get("time", start))
            caption = str(item.get("text") or item.get("kind") or "画面证据")
            img = ""
            if item.get("path"):
                url = _text(_relative_url(item["path"], output_dir))
                img = f'<a class="image-link" href="{url}" target="_blank" rel="noopener"><img src="{url}" alt="{_text(caption)}" loading="lazy"></a>'
            evidence_html.append(f'<figure>{img}<figcaption>{_button(seconds)}<span>{_text(caption)}</span></figcaption></figure>')
        evidence_section = '<details class="other-images"><summary>其他视频画面</summary><div class="evidence">' + ''.join(evidence_html) + '</div></details>' if evidence_html else ''
        transcript = shop.get("transcript") or []
        transcript_html = ""
        if transcript:
            paragraphs = "".join(f'<p>{_button(item.get("start", start))}<span>{_text(item.get("text") or "")}</span></p>' for item in transcript)
            transcript_html = f'<details class="transcript"><summary>查看讲解识别文本（可能误识别，{len(transcript)} 段）</summary>{paragraphs}</details>'
        cards.append(f'<article id="shop-{index}" class="shop">{overview}<div class="facts">{fields}</div>{missing_html}{dish_gallery}{evidence_section}{transcript_html}</article>')

    limitations = ""
    if data.get("limitations"):
        items = "".join(f"<li>{_text(item)}</li>" for item in data["limitations"])
        limitations = f'<details class="limitations" open><summary>本次处理边界</summary><ul>{items}</ul></details>'
    css = """
:root{--ink:#192938;--muted:#65707a;--accent:#bc4b25;--paper:#fbfaf7;--border:#e5e1da}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font-family:system-ui,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;line-height:1.65}a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}header{background:#17343b;color:#fff;padding:44px max(24px,calc((100vw - 1240px)/2)) 36px}header .eyebrow{font-size:12px;letter-spacing:.2em;color:#dbb68a}h1{margin:10px 0 16px;font-size:clamp(24px,3vw,36px);line-height:1.4;max-width:950px}.meta{color:#cad6d6;font-size:14px}.source{display:inline-block;margin-top:18px;color:#ffe1ba;font-size:14px}.layout{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:28px;max-width:1240px;margin:28px auto;padding:0 24px}.intro{font-size:14px;color:var(--muted);margin:0 0 20px}.shop{border:1px solid var(--border);border-radius:14px;background:#fff;margin-bottom:24px;padding:26px;scroll-margin-top:16px}.shop-overview{display:grid;grid-template-columns:minmax(0,1fr) 210px;gap:24px;align-items:start;margin-bottom:24px}.restaurant-intro{font-size:14px;margin:0;line-height:1.85}.storefront img{height:240px;object-fit:contain}.storefront figcaption{justify-content:space-between}.shop-head{display:flex;justify-content:space-between;gap:16px;align-items:center}.index{color:var(--accent);font-size:11px;font-weight:700;letter-spacing:.16em}h2{font-size:25px;line-height:1.4;margin:3px 0 0}h3{font-size:14px;margin:0 0 7px}.badge{font-size:11px;white-space:nowrap;color:#386755;background:#edf4ef;padding:4px 9px;border-radius:20px}.uncertain{background:#fff0d9;color:#9b6514}.range{font-size:13px;color:var(--muted);margin:12px 0 18px}.time{border:0;border-radius:5px;padding:3px 7px;cursor:pointer;background:#f7ede5;color:#a64621;font:inherit;font-variant-numeric:tabular-nums;white-space:nowrap}.time:hover{background:#eddbc9}.facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px 24px}.menu-note{font-size:12px;color:var(--muted);margin:0 0 10px}.menu-actions{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:5px 0 10px}.dish-link{font-size:12px}.dish-card{scroll-margin-top:20px}.dish-card:target{outline:2px solid var(--accent);outline-offset:3px}.dish-heading{display:flex;justify-content:space-between;gap:12px;padding:12px 14px;font-size:14px}.dish-heading span{color:var(--accent)}.dish-card figcaption{flex-wrap:wrap}.dish-card figcaption>span{flex:1 1 100%}.other-images{margin-top:24px;font-size:12px;color:var(--muted)}.other-images summary{cursor:pointer;margin-bottom:12px}.fact ul{margin:0;padding-left:18px;font-size:14px}.fact li{margin:4px 0;overflow-wrap:anywhere}.fact-reference{display:inline-flex;align-items:center;gap:3px;margin-left:3px;font-size:11px;vertical-align:baseline}.fact-source{color:var(--muted);font-size:10px;letter-spacing:.02em}.missing{font-size:12px;color:var(--muted);margin:18px 0}.evidence-title{margin-top:24px;padding-top:18px;border-top:1px solid var(--border)}.evidence{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}figure{margin:0;min-width:0;border:1px solid var(--border);border-radius:8px;overflow:hidden;background:#faf9f6}.image-link{display:block;background:#eef0ee}figure img{width:100%;height:310px;object-fit:contain;display:block}figcaption{padding:10px 12px;display:flex;gap:10px;align-items:start;font-size:12px}figcaption span{overflow-wrap:anywhere}.transcript{margin-top:20px;border-top:1px solid var(--border);padding-top:14px;font-size:13px}.transcript summary,.limitations summary{cursor:pointer;color:var(--muted)}.transcript p{display:flex;gap:10px;align-items:baseline;margin:10px 0}.transcript p span{flex:1;overflow-wrap:anywhere}aside{position:sticky;top:20px;align-self:start}aside .panel{background:#fff;border:1px solid var(--border);border-radius:12px;padding:18px;margin-bottom:18px}video{width:100%;max-height:390px;background:#111;border-radius:7px;display:block}.video-hint{font-size:12px;color:var(--muted);margin:12px 0 0}.current{color:var(--accent);font-weight:700;font-variant-numeric:tabular-nums}.nav{display:grid;gap:7px;max-height:320px;overflow:auto}.nav a{color:var(--ink);font-size:13px;display:flex;gap:10px;padding:6px 0}.nav a span{color:#a6aaa8;font-size:12px}.limitations{font-size:12px;color:var(--muted)}.limitations ul{padding-left:18px}.empty{font-size:13px;color:var(--muted)}footer{max-width:1240px;margin:0 auto;padding:4px 24px 30px;font-size:12px;color:var(--muted)}@media(max-width:900px){.layout{grid-template-columns:1fr}aside{position:static;grid-row:1}.player-panel{display:grid;grid-template-columns:minmax(180px,300px) 1fr;gap:16px}video{max-height:260px}.nav{grid-template-columns:repeat(2,minmax(0,1fr));max-height:none}}@media(max-width:650px){.shop-overview{grid-template-columns:1fr}.storefront{max-width:320px}.storefront img{height:280px}}@media(max-width:520px){header{padding:30px 20px}.layout{padding:0 12px;margin-top:16px}.shop{padding:20px 16px}.facts{grid-template-columns:1fr}.evidence{grid-template-columns:1fr}.shop-head{align-items:start}.badge{margin-top:4px}h2{font-size:22px}.player-panel{display:block}video{max-height:270px}figure img{height:360px}}@media print{header{background:white;color:#192938;padding:0}header .eyebrow,.source{color:#192938}.layout{display:block;padding:0}aside{display:none}.shop{break-inside:avoid}.transcript{display:none}body{background:white}.time{padding:0;background:none;color:#192938}}
"""
    js = """
const player=document.getElementById('video');
const current=document.getElementById('current-time');
let queuedSeek=null;
function seekTo(seconds){if(!player)return;queuedSeek=seconds;if(player.readyState>=1){player.currentTime=Math.min(seconds,Number.isFinite(player.duration)?Math.max(0,player.duration-.1):seconds);queuedSeek=null;}player.scrollIntoView({block:'nearest',behavior:'smooth'});}
document.addEventListener('click',event=>{const button=event.target.closest('[data-time]');if(button)seekTo(Number(button.dataset.time));});
if(player){player.addEventListener('loadedmetadata',()=>{if(queuedSeek!==null)seekTo(queuedSeek);});player.addEventListener('timeupdate',()=>{const seconds=Math.floor(player.currentTime),minutes=Math.floor(seconds/60);current.textContent=String(minutes).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0');});player.addEventListener('error',()=>{document.getElementById('player-status').textContent='视频无法加载，请保持笔记文件与原视频的相对目录关系。';});}
"""
    cards_html = "".join(cards) if cards else '<p class="empty">尚未提取到店铺条目。</p>'
    method_html = limitations or '<p class="empty">处理方法：' + _text(data.get("method") or "视频信息联合提取") + '</p>'
    return f'<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{_text(title)} · 探店图文笔记</title><style>{css}</style></head><body><header><div class="eyebrow">VIDEO → EVIDENCE → NOTES</div><h1>{_text(title)}</h1><div class="meta">{len(shops)} {count_label} · {timestamp(data.get("duration", 0))} · 探店图文笔记</div>{source_html}</header><div class="layout"><main><p class="intro">餐厅简介、菜品和截图按店铺整理。点击时间戳可定位到本地视频。</p>{cards_html}</main><aside><div class="panel player-panel"><div>{video}</div><div><h3>视频核对</h3><p class="video-hint">当前位置 <span id="current-time" class="current">00:00</span></p><p id="player-status" class="video-hint">点击笔记中的时间戳，然后播放视频核对。</p></div></div><div class="panel nav-panel"><h3>{directory_label}</h3><nav class="nav">{nav}</nav></div><div class="panel">{method_html}</div></aside></div><footer>处理方法：{_text(data.get("method") or "语音、画面与时间信息联合提取")}。未提取到的地址、价格保持缺失；自动识别原文可能有误。</footer><script>{js}</script></body></html>\n'


def render_notes(data: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    """Write notes.md and notes.html; evidence paths are absolute or output-relative.

    Values are escaped for their target format. HTML uses only local assets and
    embeds its CSS/JS, so it can be opened directly without a server.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "notes.md"
    html_path = output_dir / "notes.html"
    markdown_path.write_text(_render_md(data, output_dir), encoding="utf-8")
    html_path.write_text(_render_html(data, output_dir), encoding="utf-8")
    return {"markdown": markdown_path, "html": html_path}