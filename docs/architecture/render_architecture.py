"""Render the project architecture as editable SVG and a PNG (requires Pillow)."""
from pathlib import Path
from html import escape
import math
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
W, H, SCALE = 1920, 1480, 2
BG = "#f6f8fc"
INK, MUTED = "#183045", "#617487"
BLUE, TEAL = "#3768ab", "#25877e"
BORDER = "#d8e2ed"
FONT_CANDIDATES = (
    (Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/msyhbd.ttc")),
    (Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
     Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc")),
)
FONTS = next(((a, b) for a, b in FONT_CANDIDATES if a.exists() and b.exists()), None)
if not FONTS:
    raise SystemExit("Install Microsoft YaHei or Noto Sans CJK to render Chinese labels.")

im = Image.new("RGB", (W*SCALE, H*SCALE), BG)
draw = ImageDraw.Draw(im)
parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">',
    '<title id="title">Video Agent 项目概览与架构图</title>',
    '<desc id="desc">本地网页与 CLI、公网网页与 Sites Worker，复用本机 OCR、ASR、事实抽取和笔记渲染流水线；本地与 R2 分别保存结果。</desc>',
    f'<rect width="{W}" height="{H}" fill="{BG}"/>',
]
font_cache = {}

def font(size, bold=False):
    key = (size, bold)
    if key not in font_cache:
        font_cache[key] = ImageFont.truetype(str(FONTS[int(bold)]), round(size*SCALE))
    return font_cache[key]

def rect(x, y, w, h, fill="#ffffff", stroke=BORDER, radius=18, width=1.4):
    assert 0 <= x < x+w <= W and 0 <= y < y+h <= H
    draw.rounded_rectangle((x*SCALE, y*SCALE, (x+w)*SCALE, (y+h)*SCALE),
                           radius=radius*SCALE, fill=fill, outline=stroke, width=round(width*SCALE))
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')

def text(x, y, value, size=22, color=INK, bold=False, anchor="middle"):
    f = font(size, bold)
    width = draw.textlength(value, font=f)/SCALE
    left = x-width/2 if anchor == "middle" else x if anchor == "start" else x-width
    assert left >= 0 and left+width <= W, (value, left, width)
    pil_anchor = {"middle":"mm", "start":"lm", "end":"rm"}[anchor]
    draw.text((round(x*SCALE), round(y*SCALE)), value, fill=color, font=f, anchor=pil_anchor)
    parts.append(f'<text x="{x}" y="{y}" fill="{color}" font-family="Microsoft YaHei,Noto Sans CJK SC,sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" text-anchor="{anchor}" dominant-baseline="central">{escape(value)}</text>')

def arrow(points, color=BLUE, dashed=False, both=False, width=2.5):
    for (x1,y1),(x2,y2) in zip(points, points[1:]):
        distance=math.hypot(x2-x1,y2-y1)
        if dashed:
            pos=0
            while pos<distance:
                end=min(pos+8,distance)
                a=(x1+(x2-x1)*pos/distance,y1+(y2-y1)*pos/distance)
                b=(x1+(x2-x1)*end/distance,y1+(y2-y1)*end/distance)
                draw.line(tuple(round(v*SCALE) for p in (a,b) for v in p),fill=color,width=round(width*SCALE))
                pos+=14
        else:
            draw.line(tuple(round(v*SCALE) for p in ((x1,y1),(x2,y2)) for v in p),fill=color,width=round(width*SCALE))
    points_svg=" ".join(f"{x},{y}" for x,y in points)
    dash=' stroke-dasharray="8 6"' if dashed else ""
    parts.append(f'<polyline points="{points_svg}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round"{dash}/>')
    def head(p, previous):
        x,y=p; dx,dy=x-previous[0],y-previous[1]; length=math.hypot(dx,dy)
        ux,uy=dx/length,dy/length
        triangle=[(x,y),(x-11*ux+5*uy,y-11*uy-5*ux),(x-11*ux-5*uy,y-11*uy+5*ux)]
        draw.polygon([(round(a*SCALE),round(b*SCALE)) for a,b in triangle],fill=color)
        parts.append('<polygon points="'+" ".join(f"{a:.2f},{b:.2f}" for a,b in triangle)+f'" fill="{color}"/>')
    head(points[-1],points[-2])
    if both:head(points[0],points[1])

def label(x,y,value,color=MUTED,bg=BG,size=16):
    width=draw.textlength(value,font=font(size))/SCALE+16
    rect(x-width/2,y-14,width,28,fill=bg,stroke=bg,radius=6,width=.2)
    text(x,y,value,size,color)

def node(x,y,w,h,title,lines=(),color=BLUE,fill="#ffffff",title_size=24):
    rect(x,y,w,h,fill=fill,stroke="#bbd0e7" if color==BLUE else "#b9dad4",radius=16)
    if len(lines)==2:
        ys=(y+34,y+70,y+99)
    elif len(lines)==1:
        ys=(y+h/2-17,y+h/2+22)
    else:
        ys=(y+h/2,)
    text(x+w/2,ys[0],title,title_size,color,bold=True)
    for line,cy in zip(lines,ys[1:]):
        assert draw.textlength(line,font=font(19))/SCALE<w-20,(title,line)
        text(x+w/2,cy,line,19,MUTED)

# Header and audience strip
text(60,61,"Video Agent",42,INK,True,"start")
text(60,112,"项目概览与架构  /  视频理解 → 多模态提取 → 视觉证据 → 图文笔记",23,MUTED,anchor="start")
rect(1310,35,550,88,fill="#eaf3ef",stroke="#d4e6db")
text(1585,65,"首版自动生成：中文美食探店",24,"#2d6857",True)
text(1585,99,"商品推荐／知识讲解：已有单次整理样例",17,"#52786b")
rect(60,155,1800,88)
text(90,199,"目标用户",18,BLUE,True,"start")
text(210,199,"消费决策 · 知识学习 · 资料整理",23,INK,anchor="start")
text(1090,199,"核心输出",18,TEAL,True,"start")
text(1210,199,"文字笔记 · 关键截图 · 时间戳",23,INK,anchor="start")

# Logical lanes, not physical deployment clusters
text(80,292,"01  本地使用模式",25,BLUE,True,"start")
text(600,292,"02  共享处理流水线 · 本机 CPU",25,BLUE,True,"start")
text(1440,292,"03  公网使用模式",25,TEAL,True,"start")
rect(60,325,440,1005,fill="#eef3fa",stroke="#dde6f1",radius=22)
rect(570,325,780,1005,fill="#ffffff",stroke="#d4dfeb",radius=22)
rect(1420,325,440,1005,fill="#eef7f4",stroke="#d8eae3",radius=22)

# Connectors, behind node labels
arrow([(280,480),(280,575)])
label(280,528,"网页请求",bg="#eef3fa")
arrow([(480,410),(620,410)])
label(550,390,"CLI")
arrow([(480,640),(535,640),(535,452),(620,452)])
label(550,560,"派发任务",size=15)
arrow([(960,480),(960,515),(775,515),(775,545)])
arrow([(960,515),(1145,515),(1145,545)])
arrow([(775,675),(775,715),(960,715),(960,760)])
arrow([(1145,675),(1145,715),(960,715)])
arrow([(960,880),(960,940)])
arrow([(960,1050),(960,1120)])
arrow([(620,1185),(535,1185),(535,1030),(480,1030)])
label(547,1209,"保存结果",size=15)
arrow([(280,1100),(280,1160)])
label(280,1130,"建立索引",bg="#eef3fa")
arrow([(80,1215),(27,1215),(27,420),(80,420)],color="#8b9eb0",dashed=True)
label(280,1294,"本地历史独立保存",bg="#eef3fa",size=17)
arrow([(1640,480),(1640,575)],color=TEAL,both=True)
label(1640,528,"登录／任务／读取",TEAL,"#eef7f4")
arrow([(1640,705),(1640,800)],color=TEAL,both=True)
label(1640,753,"轮询任务／更新状态",TEAL,"#eef7f4")
arrow([(1440,865),(1385,865),(1385,452),(1300,452)])
arrow([(1300,1185),(1440,1185)],color=TEAL)
label(1370,1153,"工作器上传",TEAL,size=15)
label(1370,1212,"经 API",TEAL,size=15)
arrow([(1840,640),(1890,640),(1890,1195),(1840,1195)],color="#719b92",dashed=True,both=True)
label(1640,1294,"云端历史按登录用户隔离",TEAL,"#eef7f4",17)

# Local mode
node(80,360,400,120,"本地工具页 / CLI",["HTML · CSS · JavaScript / Python"])
node(80,575,400,130,"本地服务与任务队列",["serve.py / local_jobs.py","进度 · 任务状态持久化"])
node(80,960,400,140,"本地项目数据",["原视频 · OCR／ASR · 图文笔记","data / .cache / models"])
node(80,1160,400,110,"笔记索引与历史管理",["分类 · 搜索 · 打开与回看"])

# Shared processing
node(620,360,680,120,"视频获取与媒体解析",["yt-dlp · FFmpeg · OpenCV"])
node(620,545,310,130,"画面文字 OCR",["RapidOCR","ONNX Runtime"],title_size=23)
node(990,545,310,130,"语音识别 ASR",["faster-whisper","CPU int8"],title_size=23)
node(620,760,680,120,"时序分段与事实抽取",["店铺 · 名称 · 菜品 · 价格 · 评价"])
node(620,940,680,110,"菜单与视觉证据关联",["菜品图片 · 源画面 · 时间戳"])
node(620,1120,680,130,"图文笔记渲染",["HTML · Markdown · JSON","截图查看 · 时间戳回看"])

# Public mode: the computing worker is explicitly local
node(1440,360,400,120,"公网工具页",["HTML · CSS · JavaScript"],TEAL)
node(1440,575,400,130,"Sites Worker API",["身份验证 · 任务编排","授权读取 · 媒体接口"],TEAL)
node(1440,800,400,130,"本地云端工作器",["cloud_worker.py","运行位置：本机 CPU"],BLUE,fill="#f8fbff")
node(1440,1120,400,150,"R2 云端存储",["任务 · 笔记 · 截图","回看视频"],TEAL)
# Node-specific labels that clarify the two entry paths
text(960,1292,"OCR／ASR＋时序规则  ·  视觉证据保留来源与时间",18,MUTED)

# Footer
rect(60,1360,950,84)
text(85,1387,"工程管理",16,MUTED,True,"start")
text(85,1421,"GitHub 私有仓库 → 源码 · 文档 · 测试",23,INK,anchor="start")
rect(1040,1360,820,84)
draw.ellipse((1070*SCALE,1383*SCALE,1084*SCALE,1397*SCALE),fill=BLUE)
parts.append(f'<circle cx="1077" cy="1390" r="7" fill="{BLUE}"/>')
text(1100,1390,"本机服务／计算／数据",19,BLUE,anchor="start")
draw.ellipse((1430*SCALE,1383*SCALE,1444*SCALE,1397*SCALE),fill=TEAL)
parts.append(f'<circle cx="1437" cy="1390" r="7" fill="{TEAL}"/>')
text(1460,1390,"公网网页／API／存储",19,TEAL,anchor="start")
text(1070,1421,"实线：处理与传输    虚线：数据访问",18,MUTED,anchor="start")

parts.append("</svg>")
im.save(HERE/"project-architecture.png",optimize=True)
(HERE/"project-architecture.svg").write_text("\n".join(parts)+"\n",encoding="utf-8")
print(f"Rendered {W*SCALE} x {H*SCALE} PNG and editable SVG")
