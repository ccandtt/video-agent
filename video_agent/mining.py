"""Evidence-first extraction of food-exploration stops.

The module does not call an LLM, geocoder or external database. OCR chapter cards
and explicit narration transitions create stops; unconfirmed names stay marked.
"""
from __future__ import annotations

from collections import Counter
from difflib import SequenceMatcher
import math
import re
from typing import Any

_CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3,
              "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_ORDINAL = r"(?:\d{1,2}|[一二两三四五六七八九十]{1,3})"
_CARD = re.compile(rf"^(?:第\s*)?({_ORDINAL})\s*(?:[.．、:：)）-]|家(?:店)?|站)\s*(.+)$")
_INTRO = re.compile(rf"第\s*({_ORDINAL})\s*(?:家(?:店)?|站)\s*(.*)")
_ROUTE = re.compile(r"(?:再|然后|接着)?(?:往前|往|走)[^，。]{0,18}就是(?:个|一家|)([^，。]{2,35})")
_NEXT = re.compile(r"(?:下一家(?:店)?|接下来(?:的)?这家|接下来(?:来到|是)|再来一家)\s*(.*)")
_TRANSITION_VERBS = re.compile(r"^(?:我们|我)?(?:先|就)?(?:从|来到|来吃|吃|去了|去|选择|选|推荐|是|叫做|叫|为|打卡)?\s*")
_NON_NAME = re.compile(r"(?:[，,。！？!?；;]|位于|地址|就在|人均|点了|推荐|主打|主营|开了|已经|属于|是一家|是一个|这家)")
_NAME_SUFFIX = re.compile(r"(?:餐厅|餐馆|饭店|酒家|小吃|面馆|食堂|咖啡|茶馆|烤肉店|饼店|糕点店|烧烤店|牛肉面|烤鸭店|甜品店|饭馆|食府|面包房|烙锅|居|轩|斋|记|坊|馆)$")
_OUTRO = re.compile(r"(?:这期|本期)(?:的)?(?:文字版)?(?:总结|攻略)|下期(?:给|将|再)|欢迎(?:关注|观众)|今天(?:的)?(?:视频|分享).*到这里")
_SENTENCE = re.compile(r"(?:我们|你们|个人|感觉|觉得|喜欢|好吃|非常|真的|这个|那个|没有|可以|就是|属于|配着|吃完|吃起来|口感|而且|不过|但是|不腻|搭配)")
_PRICE = re.compile(r"(?:[¥￥]\s*\d+(?:\.\d+)?|\d+(?:\.\d+)?\s*(?:元|块钱|块)(?:\s*[/／]\s*(?:人|份|个|斤|杯))?|人均\s*(?:\d+(?:\.\d+)?|[一二两三四五六七八九十百千]+)(?:多)?(?:元|块)?)")
_ADDRESS = re.compile(r"(?:地址[：:]?\s*|位于\s*|就在\s*)([^，,。！？!?；;]{2,35}(?:街|路|胡同|巷|号|广场|商场|大厦|公园|地铁站)(?:[^，,。！？!?；;]{0,12}))")
_ADDRESS_LINE = re.compile(r"^(?=.{5,45}$)(?=.*(?:街|路|胡同|巷))(?=.*\d+(?:号|弄))[^。！？!?]+$")
_HIGHLIGHT = re.compile(r"喜欢|推荐|建议|错峰|高峰|排大队|装修|正宗|觉得|遗憾|不足|服务|排队|营业|适合|不建议|个人|口感|味道|特色|招牌|主打|老店|开了|搭配|价格|人均|点了|好吃|甜|辣|咸|腻|香|鲜|脆|嫩|拍照")
# A vocabulary of food categories, not a list of the supplied video's shops.
_FOODS = re.compile(r"(?:提拉米苏|黑森林蛋糕|肉骨茶|咖喱鸡|咖喱牛肉|烤鸭|烤鸡|烤肉|烤鱼|炸鸡|牛肉面|羊肉串|羊肉汤|炸酱面|凉面|拌面|炒面|炒饭|炒米粉|螺蛳粉|酸辣粉|米线|披萨|比萨|意大利面|意面|三明治|汉堡|煎饼|烧饼|薄饼|油条|包子|饺子|馄饨|豆汁|豆腐脑|土豆泥|沙拉|咖啡|奶茶|酸奶|冰淇淋|慕斯|蛋糕|泡芙|面包|布丁|酥皮|麻辣烫|火锅|串串|小龙虾|牛排|鹅肝|豆花|甜甜圈|炸糕|卤煮|炒肝|爆肚|糖葫芦)")
_DISH_WORDS = "提拉米苏 千层面 意大利面 意面 披萨 比萨 奶酪 沙拉 塔可 塔克 吐司 土司 芝士饼 薄饼 黄油饼 咖喱 土豆泥 曲奇 羊角包 可颂 年糕 香肠 包尔萨克 包尔沙克 手抓羊肉 手扒羊肉 羊肉焖饼 粽子 烤鸽子 白肉 折耳根 鼻筋 卷粉 燃面 凉皮 豆腐 脑花 辣子鸡 肉夹馍 奶酪卷 肉桂苹果 胡桃夹子 宽粉 酿皮子 酿皮 牛奶醪糟 米酒 烙锅 坨坨肉 脆肠 炒饭 咖啡 奶茶 面包 蛋糕 甜甜圈 饺子 米线 面条 拉面 火锅 麻辣烫 豆花 羊肉串 牛排 包子 馄饨 烤鸭 炒肝 卤煮 炸糕 煎饼 烧饼 三明治 汉堡 冰淇淋 泡芙 布丁 螺蛳粉 酸辣粉 羊肉汤 牛肉面 肉骨茶 牛舌 南瓜汤 罗宋汤 羊角 小龙虾 羊肉 牛肉 鸡肉 猪肉 酿米酒 咔饼 寿司 刨冰 奶冰 月饼 卷圈 泡面 卤蛋 大饼 鸡肉卷 巧克力奶冰 八珍豆腐 锅塌牛肉 口袋鸡丝 盐爆散丹 芥末虾球 扒牛肉条 皮皮虾馅 猪肉三鲜".split()
_FOOD_NOUN = re.compile("|".join(re.escape(word) for word in sorted(_DISH_WORDS, key=len, reverse=True)))
_FOOD_TAIL = "(?:" + "|".join(re.escape(word) for word in sorted(_DISH_WORDS, key=len, reverse=True)) + r"|饼|汤|面|粉|饭|粥|肉|鸡|鱼|虾|卷|糟|茶|包)"
_DISH_NOUN = re.compile(r"[\u4e00-\u9fff]{0,13}" + _FOOD_TAIL)
_DISH_PREFIX = re.compile(r"^(?:(?:他|她|它|这|那)家(?:的)?|大家的|我(?:们)?|没有|又|还|都|是|点了|点的|团购了|要了|推荐|招牌|主打|吃了|蘸着|站着|蘸|这个|这款|这份|这碗|那个|一款|一个|一份|一道|一碗|一盘|的)+")
_DISH_BAD = re.compile(r"然后|要加|所以|他这|\d+两|菜单|写|一斤|一两|一只|单买|之前|上桌|最后|底下|全是|店叫|去了|再加|他们|它这|这一道|看到|吃了|吃|肉类|多元|第|地主|热评榜|热瓶榜|三款|两款|各种|蘸|混合|对|属于|其实|像|加厚|一口|主打|餐品|菜品|我们|你们|大家|觉得|认为|口感|味道|内馅|外皮|表皮|里面|里边|上面|底部|每一层|之后|真的|可以|那种|这种|很多|一种|所有|非常|特别|超级|这个|那个|怎么|时候|没有|不足|缺点|甜而|太油|太甜|喜欢|不|的|和|又|比|有")
_DISH_AFTER = re.compile(r"(?:点了|点的|推荐|招牌|主打|吃了|要了)(?:一个|一份|一道|一碗|一盘|这款|的是|的|了)?\s*([^，,。！？!?；;]{2,18})")


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _key(value: str) -> str:
    return re.sub(r"[^\w\u3400-\u9fff]", "", value).lower()


def _number(value: str) -> int | None:
    value = value.strip()
    if value.isdigit():
        return int(value)
    if "十" in value:
        left, right = value.split("十", 1)
        return (10 * _CN_DIGITS.get(left, 1) + _CN_DIGITS.get(right, 0))
    return _CN_DIGITS.get(value)


def _similar(a: str, b: str) -> bool:
    a, b = _key(a), _key(b)
    if not a or not b:
        return False
    if a == b:
        return True
    if min(len(a), len(b)) >= 3 and (a in b or b in a):
        return True
    return SequenceMatcher(None, a, b).ratio() >= 0.5


def _bounds(line: dict[str, Any], frame: dict[str, Any]) -> tuple[float, float, float, float]:
    """Return normalized x, y, width, height; missing boxes are not titles."""
    box = line.get("box") or []
    width, height = max(1, frame.get("width", 1)), max(1, frame.get("height", 1))
    if len(box) >= 4 and isinstance(box[0], (list, tuple)):
        xs, ys = [float(p[0]) for p in box], [float(p[1]) for p in box]
        return min(xs) / width, min(ys) / height, (max(xs) - min(xs)) / width, (max(ys) - min(ys)) / height
    if len(box) == 4 and all(isinstance(p, (int, float)) for p in box):
        x, y, right, bottom = box
        return x / width, y / height, (right - x) / width, (bottom - y) / height
    return 0, 0, 0, 0


def _progress(text: str, y: float) -> bool:
    """Ignore persistent chapter-number bars; they are not chapter cards."""
    numeric = re.findall(r"\d+", text)
    return y < 0.08 or (len(numeric) >= 4 and len(re.sub(r"[\d\s|/.,·，、]", "", text)) <= 5)


def _trim_name(text: str) -> str:
    text = _clean(text).strip("：:、.．- ")
    text = _TRANSITION_VERBS.sub("", text, count=1)
    text = _NON_NAME.split(text, maxsplit=1)[0].strip("：:、.．- ")
    text = re.sub(r"(?:开始|走起|走起吧|来一顿|吃起|尝尝)$", "", text).strip()
    return text[:35]


def _plausible_name(text: str) -> bool:
    key = _key(text)
    return (2 <= len(key) <= 30 and not key.isdigit() and not _SENTENCE.search(text)
            and not _PRICE.search(text) and not re.search(r"调料|调味料|配料表|生产日期|保质期|净含量", text))


def _poster(frame: dict[str, Any]) -> bool:
    """A multi-stop recap poster is evidence, not simultaneous new chapters."""
    numbers = set()
    for line in frame.get("ocr") or []:
        text = _clean(line.get("text"))
        match = _INTRO.search(text) or _CARD.match(text)
        if match:
            numbers.add(_number(match[1]))
    return len(numbers) >= 2


def _ocr_candidates(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for frame in frames:
        if _poster(frame):
            continue
        for line in frame.get("ocr") or []:
            text = _clean(line.get("text"))
            x, y, width, height = _bounds(line, frame)
            if not text or float(line.get("score", 1)) < 0.5 or _progress(text, y):
                continue
            match = _CARD.match(text)
            if match and y < 0.68 and height >= 0.022:
                number, name = _number(match[1]), _trim_name(match[2])
                if _plausible_name(name) and number and number < 100:
                    result.append(dict(time=float(frame["time"]), name=name, number=number,
                                       source="ocr", confidence=float(line.get("score", 1)), score=5 + height * 10, explicit=True,
                                       frame=frame, text=text))
                continue
            # Ordinary bottom narration, menus and small storefront lettering do
            # not create boundaries. A large isolated name can be a title card.
            if 0.08 <= y < 0.68 and width >= 0.15 and height >= 0.015 and _plausible_name(text):
                named_sign = re.search(r"(?:\bBAR\b|CAFE|BAK\w*|DELI|KITCHEN|RESTAURANT)", text, re.I)
                if (named_sign and height >= 0.017) or (_NAME_SUFFIX.search(text) and height >= 0.035) or height >= 0.045:
                    result.append(dict(time=float(frame["time"]), name=text, number=None,
                                       source="ocr", confidence=float(line.get("score", 1)), score=2.7 + height * 10, explicit=False,
                                       standalone=bool(named_sign or _NAME_SUFFIX.search(text)),
                                       frame=frame, text=text))
    # Isolated large lettering may be packaging or background scenery. A
    # name without venue syntax or a sign suffix needs repeated local frames.
    return [c for c in result if c["explicit"] or c.get("standalone") or sum(
        other["time"] != c["time"] and abs(other["time"] - c["time"]) <= 6
        and _key(other["name"]) == _key(c["name"]) and other.get("confidence", 0) >= .9
        for other in result) >= 1]


def _venue_intro(text: str) -> tuple[str, bool, bool] | None:
    """Recognize conversational venue introductions, including unnamed stops."""
    match = re.search(r"(?:我(?:们)?去的是|这家(?:店)?叫|这(?:个)?摊(?:位)?叫|(?:它|他|她)叫|我(?:们)?去吃)([^，。！？]{2,30})", text)
    if not match:
        match = re.search(r"(?:有一?家|一家)[^，。！？]{0,8}?(?:店|馆|摊)叫([^，。！？]{2,30})", text)
    if match:
        name = re.sub(r"(?:那家|这家)$", "", _trim_name(match[1])).strip()
        # "它叫..." can describe a dish; require venue context or a venue suffix.
        if re.search(r"^(?:它|他|她)叫", match[0]) and not re.search(r"店|馆|摊|总店|分店|糕点|面包|餐厅", name):
            return None
        if _plausible_name(name):
            return name, False, False
    alternate = re.search(r"(?:另一(?:个|家|摊)(?:是|叫)|接下来(?:换|去|吃)(?:一家|一个|一摊)?)([^，。！？]{0,25})", text)
    if alternate:
        name = _trim_name(alternate[1])
        if _plausible_name(name):
            return name, False, True
        return "", True, True
    if re.search(r"(?:还有一(?:点|地儿|处)|(?:路边|岸边|河边)).{0,20}(?:喝酒|喝饮料|喝饮品)", text):
        return "饮品点位", True, True
    street = re.search(r"(?:有一些|有一家|有个|一个摊|路边).{0,5}卖(.{1,15})", text)
    if street:
        foods = _dish_phrases(street[1])
        if foods:
            return foods[0] + "点位", True, True
    if re.search(r"(?:一家|一摊)是(?:这个|这家|那个)", text):
        return "", True, True
    if re.search(r"早餐|早饭|中午|午餐|晚餐|最后吃一顿", text):
        foods = _dish_phrases(text)
        if foods or re.search(r"(?:中午|午餐|晚餐).{0,8}菜", text):
            food = foods[0] if foods else "午餐"
            return food + "点位", True, True
    return None

def _speech_candidates(transcript: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for position, segment in enumerate(transcript):
        text = _clean(segment.get("text"))
        match = _INTRO.search(text)
        number = _number(match[1]) if match else None
        rest = match[2] if match else ""
        if not match:
            match = _NEXT.search(text)
            rest = match[1] if match else ""
        if not match:
            match = _ROUTE.search(text)
            rest = match[1] if match else ""
        if not match:
            intro = _venue_intro(text)
            if intro:
                name, descriptive, new_stop = intro
                result.append(dict(time=float(segment.get("start", 0)), name=name, number=None,
                                   source="asr", score=2, explicit=True, text=text, frame=None,
                                   descriptive=descriptive, new_stop=new_stop, conversational=True))
            continue
        name = _trim_name(rest)
        if not _plausible_name(name):
            name = ""
        # ASR often separates "第 X 家" and the proper noun into consecutive
        # segments. Only bridge a close, short, plausible name-only segment.
        if not name and position + 1 < len(transcript):
            following = transcript[position + 1]
            following_text = _clean(following.get("text"))
            candidate = _trim_name(following_text)
            gap = float(following.get("start", 0)) - float(segment.get("end", segment.get("start", 0)))
            if 0 <= gap <= 2 and len(candidate) <= 30 and _plausible_name(candidate):
                name = candidate
        result.append(dict(time=float(segment.get("start", 0)), name=name, number=number,
                           source="asr", score=2, explicit=True, text=text, frame=None))
    return result


def _subtitle_candidates(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for frame in frames:
        if _poster(frame):
            continue
        for line in frame.get("ocr") or []:
            text = _clean(line.get("text"))
            _, y, _, _ = _bounds(line, frame)
            confidence = float(line.get("score", 1))
            # A narrated ordinal is allowed; a persistent numeric bar and
            # unrelated bottom subtitles cannot create a chapter.
            if not 0.68 <= y <= 0.9 or confidence < 0.85:
                continue
            match = _INTRO.search(text)
            if match:
                name, number = _trim_name(match[2]), _number(match[1])
            else:
                intro = _venue_intro(text)
                if not intro or not intro[0]:
                    continue
                name, number = intro[0], None
            if not _plausible_name(name):
                continue
            result.append(dict(time=float(frame["time"]), name=name, number=number,
                               source="subtitle", confidence=confidence, score=6, explicit=True,
                               frame=frame, text=text, new_stop=bool(not match and intro[2]),
                               descriptive=bool(not match and intro[1])))
    return result



def _conversational_name_evidence(frames: list[dict[str, Any]], speech: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Retrieve a fleeting caption matching a nearby spoken venue introduction."""
    result = []
    for cue in speech:
        if not cue.get("conversational") or cue.get("descriptive") or not cue["name"]:
            continue
        target = _key(cue["name"])
        for frame in frames:
            if abs(float(frame["time"]) - cue["time"]) > (2.5 if len(target) <= 2 else 6):
                continue
            for line in frame.get("ocr", []):
                _, y, _, height = _bounds(line, frame)
                confidence = float(line.get("score", 0))
                if confidence < .9 or not .08 <= y <= .9:
                    continue
                text = _clean(line.get("text"))
                intro = _venue_intro(text)
                name = intro[0] if intro and not intro[1] else text
                candidate = _key(name)
                if not _plausible_name(name) or not candidate:
                    continue
                similarity = SequenceMatcher(None, target, candidate).ratio()
                short = len(target) <= 2 and len(candidate) == len(target) and candidate[:1] == target[:1] and y < .68 and height >= .03
                # Honorific prefixes and several ASR character errors can make a
                # long venue name look dissimilar. Require repeated, local,
                # high-confidence visual agreement before relaxing that match.
                spoken = re.sub(r"^(?:清真|老字号)", "", target)
                compared = re.sub(r"^(?:清真|老字号)", "", candidate)
                repeated = (len(compared) >= 6 and compared[-2:] == spoken[-2:]
                            and SequenceMatcher(None, spoken, compared).ratio() >= .55
                            and confidence >= .95 and sum(
                                any(_key(_clean(l.get("text"))) == candidate and float(l.get("score", 0)) >= .95
                                    for l in other.get("ocr", []))
                                for other in frames if abs(float(other["time"]) - cue["time"]) <= 6) >= 2)
                if similarity < .6 and not (short and similarity >= .5) and not repeated:
                    continue
                result.append(dict(time=float(frame["time"]), name=name, number=None, source="subtitle",
                                   confidence=confidence, score=6, explicit=True, frame=frame, text=text,
                                   new_stop=cue.get("new_stop", False)))
    return result

def _group_candidates(candidates: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    for candidate in sorted(candidates, key=lambda c: (c["time"], -c["score"])):
        same = None
        for group in reversed(groups):
            gap = candidate["time"] - max(c["time"] for c in group)
            group_number = next((c["number"] for c in group if c["number"]), None)
            matching_number = bool(candidate["number"] and group_number == candidate["number"])
            matching_name = any(_similar(candidate["name"], c["name"]) for c in group)
            if candidate.get("descriptive"):
                matching_name = any(_key(candidate["name"]) == _key(c["name"]) and bool(candidate["name"]) for c in group)
            # Matching chapter numbers remain one stop; adjacent ASR/OCR evidence
            # may disagree phonetically, but only within the local introduction.
            local_intro = gap <= 5 and candidate["source"] != group[0]["source"]
            # A later name may identify a meal introduced shortly before it.
            descriptive_lead = group is groups[-1] and gap <= 18 and any(c.get("descriptive") for c in group) and not any(c["name"] and not c.get("descriptive") for c in group) and not candidate.get("descriptive") and not candidate.get("new_stop")
            if candidate.get("new_stop") and not matching_name:
                continue
            compatible_numbers = not (candidate["number"] and group_number and candidate["number"] != group_number)
            if compatible_numbers and ((matching_number and gap <= 90) or (matching_name and gap <= 30) or local_intro or descriptive_lead):
                same = group
                break
            if gap > 90:
                break
        if same is None:
            groups.append([candidate])
        else:
            same.append(candidate)
    # An unnumbered storefront seen once should not split a narrated chapter.
    accepted = []
    for group in groups:
        explicit = any(c["explicit"] for c in group)
        times = {c["time"] for c in group}
        strong = any(c.get("standalone") and c.get("confidence", 0) >= 0.85 for c in group)
        if explicit or strong:
            accepted.append(group)
    return sorted(accepted, key=lambda group: min(c["time"] for c in group))


def _select_name(group: list[dict[str, Any]], index: int) -> tuple[str, bool, dict[str, Any] | None, dict[str, Any] | None]:
    ocr = [c for c in group if c["source"] in {"ocr", "subtitle"} and c["name"] and not c.get("descriptive")]
    speech = [c for c in group if c["source"] == "asr" and c["name"] and not c.get("descriptive")]
    if ocr:
        counts = Counter(_key(c["name"]) for c in ocr)
        # First resolve the label by repeated textual agreement. Then select
        # its sharpest usable evidence frame; font size is not image quality.
        label_candidate = max(ocr, key=lambda c: (counts[_key(c["name"])], c["score"], c.get("confidence", 0)))
        agreed = [c for c in ocr if _key(c["name"]) == _key(label_candidate["name"])]
        display_candidate = max(agreed, key=lambda c: (c["source"] == "subtitle", c.get("confidence", 0), c["score"]))
        display_name = display_candidate["name"]
        chosen = max(agreed, key=lambda c: math.log1p(max(0.0, float(c["frame"].get("sharpness", 0)))) + c.get("confidence", 0) * 2)
        original = next((c for c in speech if abs(c["time"] - chosen["time"]) <= 6 and any(_similar(c["name"], o["name"]) for o in ocr)), None)
        if original is None:
            original = next((c for c in speech if abs(c["time"] - chosen["time"]) <= 6 and _ROUTE.search(c["text"])), None)
        if original is None:
            aligned = next((c for c in group if c["source"] == "alignment" and abs(c["time"] - chosen["time"]) <= 6), None)
            if aligned:
                original = dict(name=aligned["text"])
        correction = dict(original=original["name"] if original else chosen["name"], corrected=display_name,
                          reason=f"同一店铺介绍时段的画面 OCR：{chosen['text']}", time=chosen["time"])
        return display_name, max(c.get("confidence", 0) for c in agreed) < 0.85, correction, chosen
    if speech:
        return speech[0]["name"], True, None, None
    number = next((c["number"] for c in group if c["number"]), index)
    return f"第{number}家店铺", True, None, None


def _unique(items: list[str], limit: int = 12) -> list[str]:
    result, keys = [], set()
    for item in items:
        key = _key(item)
        if key and key not in keys:
            result.append(item)
            keys.add(key)
        if len(result) >= limit:
            break
    return result


def _frame_text(frame: dict[str, Any], include_progress: bool = False) -> str:
    lines = []
    for line in frame.get("ocr") or []:
        text = _clean(line.get("text"))
        _, y, _, _ = _bounds(line, frame)
        if text and float(line.get("score", 1)) >= 0.5 and (include_progress or not _progress(text, y)):
            lines.append(text)
    return "；".join(lines)


def _sources(frames: list[dict[str, Any]], transcript: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources = []
    def display_segment(segment):
        raw = _clean(segment.get("text"))
        candidates = []
        for frame in frames:
            time = float(frame["time"])
            if not float(segment["start"]) - .25 <= time <= float(segment.get("end", segment["start"])) + .5:
                continue
            for line in frame.get("ocr", []):
                caption = _clean(line.get("text"))
                if float(line.get("score", 0)) < .97 or not .68 <= _bounds(line, frame)[1] <= .9:
                    continue
                similarity = SequenceMatcher(None, _key(raw), _key(caption)).ratio()
                if max(6, len(raw) * .6) <= len(caption) <= len(raw) * 1.8 + 4 and similarity >= .48:
                    candidates.append((similarity, caption, time))
        if not candidates:
            return raw, None
        _, caption, time = max(candidates)
        return caption, dict(time=time, original=raw, text=caption, source="ocr")

    for index, segment in enumerate(transcript):
        text = _clean(segment.get("text"))
        context, caption_reference = display_segment(segment)
        context_evidence = [caption_reference] if caption_reference else []
        for following in transcript[index + 1:index + 3]:
            if float(following["start"]) - float(segment.get("end", segment["start"])) > 4:
                break
            next_text = _clean(following.get("text"))
            if _INTRO.search(next_text) or len(context) + len(next_text) > 65:
                break
            display, reference = display_segment(following)
            context += "，" + display
            if reference:
                context_evidence.append(reference)
        sources.append(dict(text=text, context=context, context_evidence=context_evidence, time=float(segment.get("start", 0)), source="asr", confidence=1, end=float(segment.get("end", segment["start"]))))
    for frame in frames:
        if _poster(frame):
            continue
        for line in frame.get("ocr") or []:
            text = _clean(line.get("text"))
            _, y, _, _ = _bounds(line, frame)
            confidence = float(line.get("score", 1))
            if text and not _progress(text, y) and confidence >= 0.5:
                sources.append(dict(text=text, time=float(frame["time"]), source="ocr", confidence=confidence, caption=0.68 <= y <= 0.9))
    return sources


def _food_supported(phrase: str, caption: str) -> bool:
    phrase_key, caption_key = _key(phrase), _key(caption)
    if phrase_key in caption_key:
        return True
    # OCR can confuse 白/自 or similarly shaped characters. Require the
    # named-food phrase to match a local caption substring, not the whole line.
    for length in range(max(2, len(phrase_key) - 1), len(phrase_key) + 2):
        for offset in range(max(1, len(caption_key) - length + 1)):
            if SequenceMatcher(None, phrase_key, caption_key[offset:offset + length]).ratio() >= 0.75:
                return True
    return False


def _dish_phrases(text: str) -> list[str]:
    # A comparison is not an assertion that the compared food was ordered.
    if re.search(r"像在吃|(?:口感|味道|觉得|很)像|像加厚", text) or _INTRO.search(text):
        return []
    result = _FOODS.findall(text) + _FOOD_NOUN.findall(text)
    for clause in re.split(r"[，,。；;、/]|和", text):
        previous_end = 0
        previous_phrase = ""
        for match in _FOOD_NOUN.finditer(clause):
            fragment = clause[previous_end:match.end()].strip()
            phrase = _DISH_PREFIX.sub("", fragment)
            phrase = re.sub(r"^(?:热(?:评|瓶)榜(?:第[一二三四五六七八九十\d]+)?|免费|吃|三款|两款)", "", phrase)
            if previous_phrase and match.start() == previous_end:
                phrase = previous_phrase + match[0]
            previous_end = match.end()
            if 2 <= len(phrase) <= 16 and not _DISH_BAD.search(phrase):
                result.append(phrase)
                previous_phrase = phrase
            else:
                previous_phrase = ""
    return _unique([item for item in result if len(item) >= 2], 30)


def _facts(sources: list[dict[str, Any]], shop_name: str) -> tuple[dict[str, list[str]], dict[str, list[dict[str, Any]]]]:
    facts: dict[str, list[str]] = {field: [] for field in ("dishes", "prices", "locations", "highlights")}
    provenance: dict[str, list[dict[str, Any]]] = {field: [] for field in facts}
    seen = {field: set() for field in facts}

    def add(field: str, value: str, source: dict[str, Any], original: str | None = None):
        value = value.strip("：:，,；; ")
        key = _key(value)
        if key and key not in seen[field]:
            seen[field].add(key)
            facts[field].append(value)
            provenance[field].append(dict(text=value, time=source["time"], source=source["source"], original=original or source["text"],
                                          **({"context_evidence": source["context_evidence"]} if source.get("context_evidence") else {})))

    # Read reliable OCR first, so a same-time visual spelling can supersede a
    # similar ASR spelling. Distinct OCR dish names are never fuzzy-merged.
    ordered = sorted(sources, key=lambda s: (s["source"] != "ocr", s["time"]))
    visual_dishes = []
    for source in ordered:
        text = source["text"]
        reliable_ocr = source["source"] != "ocr" or source.get("confidence", 0) >= 0.9
        if not reliable_ocr:
            continue
        for match in _PRICE.finditer(text):
            add("prices", match[0], source)
        location = _ADDRESS.search(text)
        if location and not _SENTENCE.search(location[1]):
            add("locations", location[1], source)
        elif source["source"] == "ocr" and source.get("confidence", 0) >= 0.92 and _ADDRESS_LINE.match(text) and not _SENTENCE.search(text):
            add("locations", text, source)
        if source["source"] == "ocr" and not source.get("caption") and _NAME_SUFFIX.search(text):
            continue
        intro = _venue_intro(text)
        if intro and not intro[1]:
            # A venue name containing a food word is not an additional dish.
            # Preserve prices and locations above, and read subsequent food narration.
            continue
        if intro and intro[1] and intro[0] == "饮品点位":
            add("dishes", "饮品", source)
        for phrase in _dish_phrases(text):
            if _key(phrase) == _key(shop_name) or (_key(text) == _key(shop_name) and _key(phrase) in _key(shop_name)):
                continue
            if source["source"] == "asr":
                near_captions = [o for o in ordered if o["source"] == "ocr" and o.get("caption") and o.get("confidence", 0) >= 0.93
                                 and source["time"] - 0.25 <= o["time"] <= source.get("end", source["time"]) + 0.5]
                if near_captions and any(_dish_phrases(o["text"]) for o in near_captions) and not any(_food_supported(phrase, o["text"]) for o in near_captions):
                    continue
                # A matching OCR food phrase in this local speech window is the
                # spelling source; the raw ASR remains in the transcript.
                near = [d for d in visual_dishes if abs(d[1]["time"] - source["time"]) <= 3 and SequenceMatcher(None, _key(phrase), _key(d[0])).ratio() >= 0.66]
                if near:
                    continue
            add("dishes", phrase, source)
            if source["source"] == "ocr":
                visual_dishes.append((phrase, source))
    # Hide redundant categories such as '面包' when an explicit named bread is
    # available; preserve distinct complete named dishes.
    specific = [(value, record) for value, record in zip(facts["dishes"], provenance["dishes"])
                if not any(value != other and len(value) >= 2 and (other.endswith(value) or (value in _DISH_WORDS and value in other)) for other in facts["dishes"])]
    facts["dishes"] = [value for value, _ in specific]
    provenance["dishes"] = [record for _, record in specific]
    highlights = []
    for source in sources:
        text = source["text"]
        if source["source"] != "asr" or len(text) < 7 or not _HIGHLIGHT.search(text):
            continue
        score = 1
        if re.search(r"不足|缺点|不太|不够|一般|太油|太甜|不喜欢|不是特别|没有很|太肥|过甜", text):
            score += 5
        if re.search(r"推荐|建议|适合|喜欢|主打|招牌|个人", text):
            score += 3
        if re.search(r"排队|营业|高峰|错峰|服务|装修|价格|人均|辣基础", text):
            score += 3
        if re.search(r"搭配|蘸|一定要|加.*吃", text):
            score += 2
        excerpt = source.get("context", text)
        # A high-confidence same-time subtitle can improve an ASR quote, with
        # both originals retained in fact_evidence rather than erased.
        captions = [s for s in sources if s["source"] == "ocr" and s.get("caption") and s.get("confidence", 0) >= 0.95
                    and abs(s["time"] - source["time"]) <= 1.5 and len(s["text"]) >= max(7, len(text) * 0.8)
                    and SequenceMatcher(None, _key(text), _key(s["text"])).ratio() >= 0.68]
        if captions:
            caption = max(captions, key=lambda s: SequenceMatcher(None, _key(text), _key(s["text"])).ratio())
            excerpt = excerpt.replace(text, caption["text"], 1)
        highlights.append((score, source, excerpt))
    selected = []
    extent = max((s["time"] for s in sources), default=0) - min((s["time"] for s in sources), default=0)
    gap = max(3.0, extent / 5)
    for score, source, excerpt in sorted(highlights, key=lambda entry: (-entry[0], entry[1]["time"])):
        if any(abs(source["time"] - previous[1]["time"]) < gap or SequenceMatcher(None, _key(excerpt), _key(previous[2])).ratio() >= 0.6 for previous in selected):
            continue
        selected.append((score, source, excerpt))
        if len(selected) >= 6:
            break
    for _, source, excerpt in sorted(selected, key=lambda entry: entry[1]["time"]):
        add("highlights", f"讲解摘录（自动识别）：{excerpt}", source)
    for field, limit in (("dishes", 18), ("prices", 8), ("locations", 5), ("highlights", 6)):
        facts[field] = facts[field][:limit]
        provenance[field] = provenance[field][:limit]
    return facts, provenance


def _pick_evidence(frames: list[dict[str, Any]], name_candidate: dict[str, Any] | None,
                   facts: dict[str, list[str]], start: float, end: float) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    used: set[str] = set()

    def add(frame: dict[str, Any], kind: str, text: str):
        path = str(frame.get("path") or "")
        if path and path not in used and start <= float(frame["time"]) < end:
            evidence.append(dict(time=float(frame["time"]), path=path, kind=kind, text=text))
            used.add(path)

    if name_candidate and name_candidate.get("frame"):
        add(name_candidate["frame"], "shop_name", f"店名画面依据：{name_candidate['text']}")
    for field, kind, label in (("prices", "price", "画面价格线索"), ("locations", "location", "画面地点线索")):
        choices = [frame for frame in frames if any(_key(value) in _key(_frame_text(frame)) for value in facts[field])]
        if choices:
            chosen = max(choices, key=lambda f: float(f.get("sharpness", 0)))
            add(chosen, kind, f"{label}：{_frame_text(chosen)}")
    # OCR is not a visual food classifier. These frames are explicitly called
    # scene evidence; a subtitle mentioning food only increases retrieval score.
    candidates = []
    for frame in frames:
        if str(frame.get("path") or "") in used:
            continue
        if any(abs(float(frame["time"]) - item["time"]) < 2.0 for item in evidence):
            continue
        text = _frame_text(frame)
        if _INTRO.search(text) or (name_candidate and _key(name_candidate["name"]) in _key(text)):
            continue
        area = 0.0
        for line in frame.get("ocr") or []:
            _, y, width, height = _bounds(line, frame)
            if not _progress(_clean(line.get("text")), y):
                area += width * height
        if area > 0.35:
            continue
        sharpness = max(0.0, float(frame.get("sharpness", 0)))
        # Prefer a sharp frame near explicit food mentions; long shopping cards
        # full of OCR receive a penalty. Evidence coverage selects separate times.
        score = math.log1p(sharpness) + min(len(_FOODS.findall(text)), 2) * 1.5 - area * 5
        candidates.append((score, frame, text))
    min_gap = min(8.0, max(2.0, (end - start) / 5))
    for _, frame, text in sorted(candidates, key=lambda item: item[0], reverse=True):
        if any(abs(float(frame["time"]) - item["time"]) < min_gap for item in evidence if item["kind"] == "scene"):
            continue
        add(frame, "scene", "探店画面（候选截图，需结合原视频核对）" + (f"；画面文字：{text}" if text else ""))
        if sum(item["kind"] == "scene" for item in evidence) >= 3:
            break
    return sorted(evidence, key=lambda item: item["time"])


def infer_shops(frames: list[dict[str, Any]], transcript: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    """Infer stops and extraction-only notes from timestamped OCR and ASR.

    Missing information is never completed from outside knowledge. ``uncertain``
    is true without an OCR title confirming the name. ``fact_evidence`` retains
    source timestamps so every extracted list entry can be audited.
    """
    duration = max(0.0, float(duration))
    frames = sorted((f for f in frames if 0 <= float(f.get("time", -1)) < duration), key=lambda f: float(f["time"]))
    transcript = sorted((s for s in transcript if 0 <= float(s.get("start", -1)) < duration), key=lambda s: float(s["start"]))
    outro = next((float(s["start"]) for s in transcript if float(s["start"]) > duration * 0.5 and _OUTRO.search(_clean(s.get("text")))), duration)
    frames = [f for f in frames if float(f["time"]) < outro]
    transcript = [s for s in transcript if float(s["start"]) < outro]
    speech_candidates = _speech_candidates(transcript)
    groups = _group_candidates(_ocr_candidates(frames) + _subtitle_candidates(frames) + speech_candidates + _conversational_name_evidence(frames, speech_candidates))
    # A new stop can be introduced before its name: "最后一天...卷圈",
    # or a place followed by "一家是这个". Include that short lead-in, rather
    # than attributing the next stop's first dish to the preceding venue.
    for group in groups:
        earliest = min(c["time"] for c in group)
        next_boundary = min((min(c["time"] for c in other) for other in groups
                             if min(c["time"] for c in other) > earliest), default=duration)
        target_foods = set(_FOOD_NOUN.findall("；".join(
            [c["name"] for c in group] +
            [_clean(t.get("text")) for t in transcript if earliest <= float(t["start"]) < min(earliest + 4, next_boundary)])))
        bare_intro = any(c.get("descriptive") and not c["name"] for c in group)
        for segment in transcript:
            time = float(segment["start"])
            text = _clean(segment.get("text"))
            if not earliest - 8 <= time < earliest or not re.search(
                    r"最后一天|最后一个.{0,18}地方|接下来去|接着去|再去一家", text):
                continue
            lead = "；".join(_clean(t.get("text")) for t in transcript if time <= float(t["start"]) < earliest)
            lead += "；" + "；".join(_clean(l.get("text")) for f in frames if time <= float(f["time"]) < earliest
                                    for l in f.get("ocr", []) if float(l.get("score", 0)) >= .95
                                    and .68 <= _bounds(l, f)[1] <= .9)
            foods = set(_FOOD_NOUN.findall(lead))
            if foods and (target_foods & foods or bare_intro):
                group.append(dict(time=time, name="", number=None, source="alignment", score=0,
                                  explicit=True, text=text, frame=None))
                break
    # Correct coarse OCR boundary timing against nearby narration mentioning
    # the same name; this also handles a phonetically corrupted spoken ordinal.
    for group in groups:
        earliest = min(c["time"] for c in group)
        name_keys = [_key(c["name"]) for c in group if c["source"] == "subtitle" and len(_key(c["name"])) >= 2]
        for segment in transcript:
            timestamp = float(segment["start"])
            text_key = _key(_clean(segment.get("text")))
            if earliest - 3 <= timestamp < earliest and any(key in text_key or key[:2] in text_key for key in name_keys):
                group.append(dict(time=timestamp, name="", number=None, source="alignment", score=0, explicit=True, text=_clean(segment.get("text")), frame=None))
                break
    if not groups and (frames or transcript):
        # A useful evidence-backed fallback, not invented chapter boundaries.
        groups = [[dict(time=0.0, name="", number=None, source="fallback", score=0,
                        explicit=True, text="未发现可确认的店铺章节", frame=None)]]
    shops = []
    for index, group in enumerate(groups, 1):
        start = max(0.0, min(c["time"] for c in group))
        end = min(duration, min(c["time"] for c in groups[index])) if index < len(groups) else outro
        if end <= start:
            continue
        name, uncertain, name_evidence, chosen = _select_name(group, index)
        local_frames = [frame for frame in frames if start <= float(frame["time"]) < end]
        # A segment belongs to the stop where it starts; an overlapping ASR
        # segment is not copied into the next shop and cannot leak its prices.
        local_transcript = [dict(start=float(s["start"]), end=min(float(s.get("end", s["start"])), end), text=_clean(s.get("text")))
                            for s in transcript if start <= float(s["start"]) < end]
        facts, provenance = _facts(_sources(local_frames, local_transcript), name)
        description = next((c for c in group if c.get("descriptive")), None)
        named = chosen is not None or any(c["source"] == "asr" and c["name"] and not c.get("descriptive") for c in group)
        name_type = "video_name" if named else "descriptive" if description or facts["dishes"] else "unknown"
        if name_type == "descriptive":
            name = (description["name"] if description and description["name"] else (facts["dishes"][0] + "点位" if facts["dishes"] else f"未具名点位{index}"))
            name_evidence = None
            uncertain = True
        evidence = _pick_evidence(local_frames, chosen, facts, start, end)
        if chosen and not _INTRO.search(chosen["text"]) and not _CARD.match(chosen["text"]) and not chosen.get("standalone"):
            for item in evidence:
                if item["kind"] == "shop_name":
                    item["kind"] = "name_reference"
        if name_type == "descriptive" and local_frames:
            drink_frames = [f for f in local_frames if re.search(r"试.{0,4}杯|喝.{0,4}杯", _frame_text(f))] if "饮品" in name else []
            context = min(drink_frames or local_frames, key=lambda f: abs(float(f["time"]) - (start + 2)))
            existing = next((e for e in evidence if e["path"] == context["path"]), None)
            if existing:
                existing["kind"] = "context"
            else:
                evidence.insert(0, dict(time=float(context["time"]), path=context["path"], kind="context", text="点位实景；视频未提供可确认店名"))
        shops.append(dict(id=f"shop-{index:02}", name=name, start=start, end=end, name_type=name_type,
                          identification=dict(kind=name_type, time=group[0]["time"], original=group[0]["text"]),
                          **facts, evidence=evidence,
                          name_evidence=name_evidence, transcript=local_transcript, uncertain=uncertain,
                          fact_evidence=provenance))
    return shops
