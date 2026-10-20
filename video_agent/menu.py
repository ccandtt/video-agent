"""Associate menu entries with local, timestamped recognition evidence."""
from __future__ import annotations
import math
import re


def key(text):
    return re.sub(r"\s+", "", str(text)).casefold()


def dish_name_groups(shop, frames=None):
    """Conservatively reconcile adjacent OCR variants; keep all raw aliases."""
    names = list(dict.fromkeys(shop.get('dishes') or []))
    groups = {name: [name] for name in names}
    local = [f for f in (frames or []) if shop.get('start', 0) <= f['time'] < shop.get('end', float('inf'))]
    observations = {name: [(f['time'], o.get('score', 0)) for f in local for o in f.get('ocr', [])
                          if key(o.get('text', '')) == key(name)] for name in names}
    for i, left in enumerate(names):
        for right in names[i+1:]:
            if left not in groups or right not in groups:
                continue
            a, b = key(left), key(right)
            if len(a) < 8 or len(a) != len(b) or sum(x != y for x,y in zip(a,b)) != 1:
                continue
            if a[:3] != b[:3] or a[-3:] != b[-3:]:
                continue
            # Nearby separate products displayed together are not OCR aliases.
            if any(any(key(o.get('text','')) == a for o in f.get('ocr', [])) and
                   any(key(o.get('text','')) == b for o in f.get('ocr', [])) for f in local):
                continue
            one, two = observations[left], observations[right]
            if not one or not two or min(abs(t-u) for t,_ in one for u,_ in two) > 2:
                continue
            score_a, score_b = max(c for _,c in one), max(c for _,c in two)
            if max(score_a,score_b) < .98 or abs(score_a-score_b) < .04:
                continue
            winner, loser = (left,right) if score_a > score_b else (right,left)
            groups[winner].extend(groups.pop(loser))
    return groups


def build_menu(shop, frames=None):
    refs = (shop.get('fact_evidence') or {}).get('dishes', [])
    groups = dish_name_groups(shop, frames)
    dishes = list(groups)
    # Collapse a short label only when the longer label refers to the same mention.
    dishes = [name for name in dishes if not any(name != other and other.startswith(name)
              and any(a.get('original') == b.get('original') and abs(a['time']-b['time']) < 2
                      for a in refs if a.get('text') == name
                      for b in refs if b.get('text') == other) for other in dishes)]
    local = [f for f in (frames or []) if shop.get('start', 0) <= f['time'] < shop.get('end', float('inf'))]
    used = set()
    menu = []
    for name in dishes:
        aliases = groups[name]
        mentions = [dict(r, text=name, recognized_name=r.get('text')) for r in refs if r.get('text') in aliases and r.get('time') is not None]
        if mentions and all(re.search(re.escape(name) + r'的味道|综合店|种类', r.get('original', '')) for r in mentions):
            continue
        price = ''
        price_ref = None
        # A shop-wide price or nearby unrelated price must not be assigned to a dish.
        texts = [(r.get('original', ''), r['time'], r.get('source', '')) for r in mentions]
        texts += [(r.get('original', ''), r['time'], r.get('source', '')) for r in (shop.get('fact_evidence') or {}).get('prices', []) if key(name) in key(r.get('original', ''))]
        texts += [(o.get('text', ''), f['time'], 'ocr') for f in local for o in f.get('ocr', [])
                  if key(name) in key(o.get('text', ''))]
        for text, time, source in texts:
            suffix = key(text).split(key(name), 1)[-1] if key(name) in key(text) else ''
            match = re.match(r'(?:[，,:：]|价格|售价|单价|是|为|\s)*(?:[¥￥])?(\d{1,4}(?:\.\d{1,2})?)(?:元|块|$)', suffix)
            if match and float(match.group(1)) > 0:
                price = '¥' + match.group(1)
                price_ref = dict(time=time, source=source, original=text)
                break
        review = ''
        review_ref = None
        for ref in (shop.get('fact_evidence') or {}).get('highlights', []):
            text = re.sub(r'^讲解摘录（自动识别）：', '', ref.get('text', ''))
            clauses = re.split(r'[，。！？]', text)
            for n, clause in enumerate(clauses):
                if key(name) in key(clause):
                    detail = '，'.join(clauses[n:n+2])
                    if len(detail) <= 65:
                        review, review_ref = detail, ref
                        break
            if review:
                break
        choices = []
        for frame in local:
            if frame.get('path') in used:
                continue
            matching = [o for o in frame.get('ocr', []) if key(name) in key(o.get('text', ''))]
            if not matching:
                continue
            # Reject title/entrance frames and dense menu boards as food thumbnails.
            if any(e.get('path') == frame.get('path') and e.get('kind') in {'shop_name', 'storefront'} for e in shop.get('evidence', [])):
                continue
            text = ' '.join(o.get('text','') for o in matching)
            if re.search(r'第.{1,3}家', text):
                continue
            if len(frame.get('ocr', [])) >= 12:
                continue
            score = math.log1p(max(0, frame.get('sharpness', 0)))
            if mentions:
                score -= min(abs(frame['time']-r['time']) for r in mentions) * .6
            choices.append((score, frame, text))
        image = None
        if choices:
            _, chosen, original = max(choices, key=lambda x: x[0])
            image = dict(path=chosen['path'], time=chosen['time'], original=original,
                         source='ocr', selection='菜名文字与同时段画面匹配；尚未做视觉语义确认')
            used.add(chosen['path'])
        else:
            # Legacy output may have only a few screenshots; require an explicit dish match.
            for item in shop.get('evidence', []):
                if item.get('kind') not in {'shop_name', 'storefront', 'location'} and item.get('path') not in used and key(name) in key(item.get('text', '')):
                    image = dict(path=item['path'], time=item['time'], original=item.get('text', ''), source='ocr')
                    used.add(item['path'])
                    break
        menu.append(dict(name=name, aliases=aliases, references=mentions, price=price, price_evidence=price_ref,
                         review=review, review_evidence=review_ref, image=image))
    return menu
