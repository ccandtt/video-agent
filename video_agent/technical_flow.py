"""Configuration-driven technical flow diagrams: input, technology and artifacts."""
from __future__ import annotations
import argparse
from collections import defaultdict, deque
from html import escape
from io import BytesIO
import hashlib
import json
import math
from pathlib import Path
import re
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "docs/architecture/technical-flow.json"
BG, INK, MUTED = "#f6f8fc", "#183045", "#617487"
BLUE, GREEN, BORDER = "#3768ab", "#25877e", "#d4dfeb"

def inside(path):
    path = Path(path)
    path = (path if path.is_absolute() else ROOT / path).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("输入和输出必须位于项目目录内")
    return path

def string(value, field, limit=500):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{field} 必须是非空文本，长度不超过 {limit}")
    if any(ord(c) < 32 and c not in "\n\t" for c in value):
        raise ValueError(f"{field} 含无效控制字符")
    return value.strip()

def strings(value, field, required=False):
    if value is None and not required:
        return []
    if not isinstance(value, list) or (required and not value) or len(value) > 8:
        raise ValueError(f"{field} 必须是最多 8 项的文本列表")
    return [string(item, field) for item in value]

def validate(spec):
    if not isinstance(spec, dict):
        raise ValueError("配置必须是 JSON 对象")
    result = {
        "title":string(spec.get("title"), "title", 160),
        "subtitle":string(spec.get("subtitle", "输入 → 核心步骤 → 中间产物 → 输出"), "subtitle", 300),
        "notes":strings(spec.get("notes", []), "notes"),
    }
    raw = spec.get("nodes")
    if not isinstance(raw, list) or not 1 <= len(raw) <= 24:
        raise ValueError("nodes 必须包含 1–24 个步骤")
    nodes = []
    ids = set()
    for node in raw:
        if not isinstance(node, dict):
            raise ValueError("步骤必须是对象")
        id = string(node.get("id"), "id", 40)
        if not re.fullmatch(r"[A-Za-z0-9_-]+", id) or id in ids:
            raise ValueError("步骤 ID 必须唯一，且仅含字母、数字、下划线或连字符")
        ids.add(id)
        nodes.append({
            "id":id, "title":string(node.get("title"), "步骤标题", 160),
            "inputs":strings(node.get("inputs"), "inputs", True),
            "technology":strings(node.get("technology"), "technology", True),
            "outputs":strings(node.get("outputs"), "outputs", True),
        })
    edges = spec.get("edges", [])
    if not isinstance(edges, list) or len(edges) > 64:
        raise ValueError("edges 必须是最多 64 项的列表")
    clean_edges, pairs = [], set()
    children, parents = defaultdict(list), defaultdict(list)
    for edge in edges:
        if not isinstance(edge, dict):
            raise ValueError("连接必须是对象")
        a, b = edge.get("from"), edge.get("to")
        if not isinstance(a, str) or not isinstance(b, str) or a not in ids or b not in ids or a == b:
            raise ValueError("连接必须引用不同的现有步骤")
        if (a,b) in pairs:
            raise ValueError("不支持重复连接")
        pairs.add((a,b))
        label = edge.get("label", "")
        if label:
            label = string(label, "连接标签", 100)
        elif not isinstance(label,str):
            raise ValueError("连接标签必须是文本")
        clean_edges.append({"from":a, "to":b, "label":label})
        children[a].append(b)
        parents[b].append(a)
    indegree = {id:len(parents[id]) for id in ids}
    queue = deque(n["id"] for n in nodes if indegree[n["id"]] == 0)
    levels, order = {id:0 for id in queue}, []
    while queue:
        id = queue.popleft()
        order.append(id)
        for child in children[id]:
            levels[child] = max(levels.get(child,0), levels[id]+1)
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if len(order) != len(nodes):
        raise ValueError("流程存在回路；当前支持有向无环流程")
    seen = set()
    pending = [nodes[0]["id"]]
    while pending:
        id = pending.pop()
        if id in seen:
            continue
        seen.add(id)
        pending.extend(children[id]+parents[id])
    if seen != ids:
        raise ValueError("步骤未连成同一个流程")
    rows = defaultdict(list)
    for n in nodes:
        rows[levels[n["id"]]].append(n)
    if max(map(len,rows.values())) > 3:
        raise ValueError("同一层最多 3 个分支，请拆分过宽的流程")
    result.update(nodes=nodes, edges=clean_edges)
    return result, levels

def load_spec(path):
    path = inside(path)
    if path.stat().st_size > 512_000:
        raise ValueError("配置文件超过 512 KB")
    return json.loads(path.read_text(encoding="utf-8"))

class Canvas:
    def __init__(self, scale):
        self.scale = scale
        candidates = [
            ("C:/Windows/Fonts/msyh.ttc","C:/Windows/Fonts/msyhbd.ttc"),
            ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
             "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
        ]
        self.fonts = next(((a,b) for a,b in candidates if Path(a).is_file() and Path(b).is_file()), None)
        if not self.fonts:
            raise ValueError("请安装 Microsoft YaHei 或 Noto Sans CJK 字体")
        self.cached = {}
        self.measure = ImageDraw.Draw(Image.new("RGB",(1,1)))
        self.parts = []
        self.text_count = 0

    def font(self,size,bold=False):
        key = size,bold
        if key not in self.cached:
            self.cached[key] = ImageFont.truetype(self.fonts[int(bold)],size*self.scale)
        return self.cached[key]

    def wrap(self,value,width,size=19,bold=False):
        lines = []
        for paragraph in value.splitlines() or [""]:
            line = ""
            tokens=re.findall(r"[A-Za-z0-9_./-]+|[ \t]+|.",paragraph)
            for token in tokens:
                if self.measure.textlength(token,font=self.font(size,bold))/self.scale > width:
                    pieces=list(token)
                else:
                    pieces=[token]
                for piece in pieces:
                    if line and self.measure.textlength(line+piece,font=self.font(size,bold))/self.scale > width:
                        lines.append(line.rstrip())
                        line=piece.lstrip()
                    else:
                        line+=piece
            if line:
                lines.append(line.rstrip())
        return lines or [""]

    def begin(self,width,height,title):
        self.width,self.height=width,height
        if width*height*self.scale*self.scale > 48_000_000:
            raise ValueError("图过大，请使用 --scale 1 或拆分流程")
        self.image=Image.new("RGB",(width*self.scale,height*self.scale),BG)
        self.draw=ImageDraw.Draw(self.image)
        self.parts=[
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title">',
            f'<title id="title">{escape(title)}</title>',
            f'<rect width="{width}" height="{height}" fill="{BG}"/>',
        ]

    def rect(self,x,y,w,h,fill="#fff",stroke=BORDER,radius=14):
        self.draw.rounded_rectangle((x*self.scale,y*self.scale,(x+w)*self.scale,(y+h)*self.scale),
                                    radius=radius*self.scale,fill=fill,outline=stroke,width=self.scale)
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>')

    def text(self,x,y,value,size=19,color=INK,bold=False,anchor="start"):
        width=self.measure.textlength(value,font=self.font(size,bold))/self.scale
        left=x if anchor=="start" else x-width/2
        if left < 0 or left+width > self.width:
            raise ValueError("文本超出画布")
        self.draw.text((round(x*self.scale),round(y*self.scale)),value,font=self.font(size,bold),fill=color,
                       anchor="lm" if anchor=="start" else "mm")
        self.parts.append(f'<text x="{x}" y="{y}" fill="{color}" font-family="Microsoft YaHei,Noto Sans CJK SC,sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" text-anchor="{anchor}" dominant-baseline="central">{escape(value)}</text>')
        self.text_count+=1

    def arrow(self,points):
        self.draw.line([(round(x*self.scale),round(y*self.scale)) for x,y in points],fill=BLUE,width=3*self.scale)
        self.parts.append('<polyline points="'+" ".join(f"{x},{y}" for x,y in points)+f'" fill="none" stroke="{BLUE}" stroke-width="2.5" stroke-linejoin="round"/>')
        (px,py),(x,y)=points[-2:]
        length=math.hypot(x-px,y-py);ux,uy=(x-px)/length,(y-py)/length
        triangle=[(x,y),(x-10*ux+5*uy,y-10*uy-5*ux),(x-10*ux-5*uy,y-10*uy+5*ux)]
        self.draw.polygon([(round(a*self.scale),round(b*self.scale)) for a,b in triangle],fill=BLUE)
        self.parts.append('<polygon points="'+" ".join(f"{a:.2f},{b:.2f}" for a,b in triangle)+f'" fill="{BLUE}"/>')

def render(spec,output,scale=2):
    if scale not in (1,2):
        raise ValueError("scale 仅支持 1 或 2")
    output=inside(output)
    if output.suffix not in ("",".png",".svg"):
        raise ValueError("输出应为无扩展名的路径，或 .png／.svg")
    output=output.with_suffix("")
    if output == ROOT or output.is_dir():
        raise ValueError("输出必须是项目内的文件名前缀，不能是目录")
    targets = {
        suffix:inside(output.with_suffix(suffix)) for suffix in (".svg", ".png")
    }
    audit_path=inside(output.with_name(output.name+".validation.json"))
    for target in targets.values():
        inside(target.with_suffix(target.suffix+".tmp"))
    data,levels=validate(spec)
    canvas=Canvas(scale)
    rows=defaultdict(list)
    for node in data["nodes"]:
        rows[levels[node["id"]]].append(node)
    longest=max(len(row) for row in rows.values())
    card_w=1120 if longest==1 else 690
    long_edges=[e for e in data["edges"] if levels[e["to"]]-levels[e["from"]]>1]
    lane_space=170*len(long_edges)
    content_x=72+lane_space
    main_width=longest*card_w+(longest-1)*64
    width=content_x+main_width+72
    title_lines=canvas.wrap(data["title"],width-144,34,True)
    subtitle_lines=canvas.wrap(data["subtitle"],width-144,20)
    top=48+len(title_lines)*45+len(subtitle_lines)*30+30
    positions,prepared={},{}
    y=top
    edge_labels=[e["label"] for e in data["edges"] if e["label"] and levels[e["to"]]-levels[e["from"]]==1]
    row_gap=max([64]+[len(canvas.wrap(label,min(360,card_w-60),17))*23+40 for label in edge_labels])
    col_w=(card_w-64)/3
    for level in sorted(rows):
        row=rows[level]
        start=content_x+(main_width-(len(row)*card_w+(len(row)-1)*64))/2
        max_h=0
        for i,node in enumerate(row):
            title=canvas.wrap(node["title"],card_w-108,25,True)
            cells=[]
            for field in ("inputs","technology","outputs"):
                lines=[]
                for item in node[field]:
                    lines.extend(canvas.wrap(item,col_w-22,19))
                cells.append(lines)
            header=26+len(title)*33+14
            h=header+38+max(map(len,cells))*27+22
            prepared[node["id"]]=(title,cells,header)
            positions[node["id"]]=(start+i*(card_w+64),y,card_w,h)
            max_h=max(max_h,h)
        y+=max_h+row_gap
    note_lines=[]
    for note in data["notes"]:
        note_lines.extend(canvas.wrap(note,width-184,18))
    height=round(y-30+max(1,len(note_lines))*27+64)
    canvas.begin(math.ceil(width),height,data["title"])
    cursor=48
    for line in title_lines:
        canvas.text(72,cursor,line,34,bold=True);cursor+=45
    for line in subtitle_lines:
        canvas.text(72,cursor+8,line,20,MUTED);cursor+=30
    lane=0
    for edge in data["edges"]:
        ax,ay,aw,ah=positions[edge["from"]]
        bx,by,bw,bh=positions[edge["to"]]
        if levels[edge["to"]]-levels[edge["from"]]>1:
            lx=72+lane*170
            points=[(ax,ay+ah/2),(lx,ay+ah/2),(lx,by+bh/2),(bx,by+bh/2)]
            label_x,label_y=lx+4,(ay+ah/2+by+bh/2)/2
            lane+=1
            label_lines=canvas.wrap(edge["label"],145,17) if edge["label"] else []
        else:
            mid=(ay+ah+by)/2
            points=[(ax+aw/2,ay+ah),(ax+aw/2,mid),(bx+bw/2,mid),(bx+bw/2,by)]
            label_x,label_y=(ax+aw/2+bx+bw/2)/2,mid
            label_lines=canvas.wrap(edge["label"],min(360,card_w-60),17) if edge["label"] else []
        canvas.arrow(points)
        if label_lines:
            label_width=max(canvas.measure.textlength(s,font=canvas.font(17))/scale for s in label_lines)+20
            label_h=len(label_lines)*23+12
            if edge in long_edges:
                label_x=max(label_width/2+8,label_x)
            canvas.rect(label_x-label_width/2,label_y-label_h/2,label_width,label_h,fill=BG,stroke=BG,radius=4)
            for i,line in enumerate(label_lines):
                canvas.text(label_x,label_y+(i-(len(label_lines)-1)/2)*23,line,17,BLUE,anchor="middle")
    ordered=[node for level in sorted(rows) for node in rows[level]]
    for number,node in enumerate(ordered,1):
        x,y,w,h=positions[node["id"]]
        title,cells,header=prepared[node["id"]]
        canvas.rect(x,y,w,h)
        canvas.rect(x+18,y+18,40,35,fill="#eaf0fa",stroke="#eaf0fa",radius=8)
        canvas.text(x+38,y+35,f"{number:02}",18,BLUE,True,"middle")
        for i,line in enumerate(title):
            canvas.text(x+76,y+32+i*33,line,25,BLUE,True)
        labels=(("输入",MUTED),("关键技术",BLUE),("产物",GREEN))
        for i,((label,color),lines) in enumerate(zip(labels,cells)):
            cx=x+24+i*col_w
            canvas.text(cx,y+header+10,label,17,color,True)
            for j,line in enumerate(lines):
                canvas.text(cx,y+header+44+j*27,line,19,INK)
    footer=height-max(1,len(note_lines))*27-38
    for i,line in enumerate(note_lines):
        canvas.text(92,footer+i*27,line,18,MUTED)
    canvas.parts.append("</svg>")
    svg=("\n".join(canvas.parts)+"\n").encode("utf-8")
    stream=BytesIO();canvas.image.save(stream,format="PNG",optimize=True);png=stream.getvalue()
    output.parent.mkdir(parents=True,exist_ok=True)
    for suffix,content in ((".svg",svg),(".png",png)):
        path=targets[suffix];temp=path.with_suffix(suffix+".tmp")
        temp.write_bytes(content);temp.replace(path)
    result={
        "nodes":len(data["nodes"]),"edges":len(data["edges"]),"levels":max(levels.values())+1,
        "png_dimensions":[canvas.width*scale,canvas.height*scale],"text_labels":canvas.text_count,
        "png_sha256":hashlib.sha256(png).hexdigest(),"svg_sha256":hashlib.sha256(svg).hexdigest(),
        "spec_sha256":hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
        "layout":"topological layers; inputs / technology / artifacts per step",
    }
    audit_path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return result

def main(argv=None):
    parser=argparse.ArgumentParser(description="通用技术流程图：JSON 步骤配置 → PNG / SVG")
    parser.add_argument("--config",type=Path,default=DEFAULT_CONFIG)
    parser.add_argument("--output",type=Path,default=ROOT/"docs/architecture/technical-flow")
    parser.add_argument("--scale",type=int,choices=(1,2),default=2)
    args=parser.parse_args(argv)
    try:
        result=render(load_spec(args.config),args.output,args.scale)
    except (ValueError,OSError,TypeError) as error:
        parser.error(str(error))
    print(json.dumps(result,ensure_ascii=False))

if __name__=="__main__":
    main()
