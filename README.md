# Video Agent

将视频整理为带**文字总结、关键截图和时间戳**的图文笔记，并在一个工具页管理历史结果。

当前可自动生成的是 **哔哩哔哩中文美食探店攻略**。实现采用本地 OCR、Whisper 语音识别和时序规则，支持店铺目录、简介、推荐菜单、价格或评价、图片及视频回看。商品推荐、知识讲解已有单独整理的样例，通用自动生成仍待实现。

> 当前为私有开发仓库。仓库包含源码、测试和项目文档；原视频、识别缓存、已生成笔记、模型和部署密钥只保留在本机，不随 Git 上传。

## 项目概览与架构

### 结构与节点

| 图中位置 | 节点 |
| --- | --- |
| 顶部：目标 | 视频理解 → 多模态信息提取 → 视觉证据关联 → 图文笔记 |
| 顶部：用户 | 消费决策用户 · 知识学习用户 · 视频资料整理用户 |
| 场景层 | 美食探店（自动生成）· 商品推荐与评测／知识讲解（已有单次整理样例） |
| 入口层 | 本地工具页 · 公网工具页 · 命令行 CLI |
| 功能层 | 视频导入 · 任务进度 · 店铺与菜单整理 · 截图与时间戳 · 笔记生成 · 分类／搜索／历史管理 |
| 处理层 | 任务编排 · 视频下载 · 媒体解析 · 画面 OCR · 语音 ASR · 时序分段与事实抽取 · 菜单与截图关联 · 笔记渲染 |
| 数据层 | 原视频与元数据 · OCR／ASR 缓存 · 图片与时间戳 · HTML／Markdown／JSON · 本地任务记录与笔记索引 · 云端任务与结果 |
| 技术层 | HTML／CSS／JavaScript · Python · yt-dlp · FFmpeg／OpenCV · RapidOCR／ONNX Runtime · faster-whisper（CPU int8）· JSON |
| 部署层 | 本地 Python 服务与 CPU 工作器 · Sites Worker · R2 存储 |
| 版本管理 | GitHub 私有仓库 → 源码／测试／文档 |

### 节点关系清单

- 用户 → 本地工具页／公网工具页／CLI。
- 本地工具页 ↔ 本地服务 → 本地任务队列 → 处理流水线。
- CLI → 处理流水线。
- 公网工具页 ↔ Sites Worker API ↔ R2 任务与结果。
- 本地云端工作器 → 轮询 Sites Worker 任务 API → 处理流水线。
- 视频链接 → yt-dlp → 原视频与元数据；本地视频 → 处理流水线。
- 原视频 → FFmpeg／OpenCV → 视频画面＋音轨。
- 视频画面 → RapidOCR／ONNX Runtime → OCR 文字与时间。
- 音轨 → faster-whisper → ASR 文本与时间。
- OCR＋ASR → 时序分段与事实抽取 → 店铺／名称／菜品／价格／评价。
- 店铺与事实＋源画面 → 菜单与截图关联 → 笔记渲染 → HTML／Markdown／JSON。
- 本地处理结果 → 本地数据目录 → 笔记索引 → 本地工具页。
- 本地云端工作器 → 上传笔记／截图／回看视频 → Sites Worker API → R2。
- R2 结果 → Sites Worker 授权接口 → 公网工具页。
- 截图／时间戳 → 对应原视频位置 → 视频回看。
- GitHub 私有仓库 → 源码／测试／文档版本管理。

### 三段式汇报顺序

1. **目标与用户**：长视频 → 图文笔记；消费决策／知识复习／资料整理；美食探店 MVP → 后续场景。
2. **功能与数据流**：视频输入 → OCR＋ASR → 结构化抽取 → 截图关联 → 图文笔记与回看。
3. **技术与部署**：本地 Python 处理 → 本地网页／Sites Worker＋R2 → GitHub 私有仓库版本管理。

## 快速使用

已安装的本机项目在 `E:\Workspace\video_agent`。在 PowerShell 运行：

```powershell
Set-Location E:\Workspace\video_agent
.\start_local_tool.ps1
```

浏览器会打开 [本地工具首页](http://127.0.0.1:8765/)：

1. 粘贴哔哩哔哩 BV 视频链接，选择“探店攻略”，提交生成。
2. 查看任务进度，完成后打开图文笔记。
3. 在同一页分类、搜索和打开以前保存的笔记。

自动生成入口当前限制为 **20 分钟以内的中文探店视频**，视频需能匿名获取。首次运行会下载语音模型并进行本地计算，耗时取决于视频长度与电脑性能。

关闭网页不会删除笔记；重启后会从磁盘重新读取历史记录。停止服务会中断正在运行的计算，重提可复用完整且指纹一致的缓存。相同视频已有笔记时复用结果。

```powershell
.\stop_local_tool.ps1                 # 停止本地工具
.\start_local_tool.ps1 -Restart       # 重启
.\start_local_tool.ps1 -NoBrowser     # 启动但不自动打开浏览器
```

本地工具只监听 `127.0.0.1`，不需要云端账号或 API 密钥。CPU 在处理期间需要保持运行。

## 首次安装

已验证环境：**Windows、Python 3.11、CPU int8**。当前机器只在 `E:\Workspace\video_agent` 内构建和保存项目文件。

新机器安装（已有项目请跳过克隆）：

```powershell
git clone https://github.com/ccandtt/video-agent.git E:\Workspace\video_agent
Set-Location E:\Workspace\video_agent

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --cache-dir .\.cache\pip -r requirements.txt
.\start_local_tool.ps1
```

私有仓库需要有权限的 GitHub 账号登录。OCR 组件随依赖安装；Whisper 模型首次下载到项目的 `models/`，首次识别需要网络。FFmpeg 由 `imageio-ffmpeg` 提供，无需另装系统 FFmpeg。

全新克隆没有历史笔记，生成后会自动显示。本机已有的 `data/` 不会因 Git 提交、推送或更新而自动清空。

## 命令行处理

原视频必须位于项目目录内。以自己放入的数据为例：

```powershell
Set-Location E:\Workspace\video_agent
$env:PYTHONIOENCODING = 'utf-8'

# 完整识别与生成：先将视频放在 data/raw/my-video/video.mp4
.\.venv\Scripts\python.exe -m video_agent.pipeline .\data\raw\my-video\video.mp4

# 只重建笔记，复用已存在的完整 OCR / ASR 缓存
.\.venv\Scripts\python.exe -m video_agent.pipeline .\data\raw\my-video\video.mp4 --stage notes

# 以前台方式运行工具，终端关闭时服务结束
.\.venv\Scripts\python.exe -m video_agent.serve
```

可选参数：`--interval 2` 设置基础采样间隔，`--model small` 选择 Whisper 模型，`--force` 忽略缓存，`--output` 指定项目内输出目录。带时长限制的是网页入口；CLI 接受项目内本地视频，但内容抽取仍针对中文探店。

CLI 直接传入任意本地视频可生成笔记；工具页历史发现依赖 `data/raw/<BV号>/video.info.json` 等来源元数据，建议通过工具页提交链接来统一管理。

## 项目结构

```text
video_agent/
├── README.md                 使用、安装与当前边界
├── PROJECT_BRIEF.md          项目目标、场景、进展与 TODO
├── DATASET_CATALOG.md        本地样例来源与处理状态
├── AGENTS.md                 项目开发约束
├── requirements.txt          已验证的 Python 依赖
├── video_agent/              Python 处理流水线、本地工具与计算工作器
│   └── templates/            本地工具页面模板
├── web/                      公网版网页、Worker 和构建脚本
├── tests/                    单元、接口和可选真实样例验收
├── docs/                     文档索引、开发说明、验收和 BUG 记录
├── data/                     原视频、缓存、笔记（内容不上传）
├── models/                   本地语音模型（不上传）
├── output/                   PDF 等导出文件（不上传）
├── .cache/                   任务状态、下载缓存与日志（不上传）
└── tmp/                      临时检查文件（不上传）
```

文档入口：[文档索引](docs/README.md) · [项目概览](PROJECT_BRIEF.md) · [数据集目录](DATASET_CATALOG.md) · [开发说明](docs/DEVELOPMENT.md) · [测试记录](docs/TEST_REPORT.md) · [BUG 记录](docs/BUG_LOG.md)。

`DATASET_CATALOG.md` 描述这台机器上的数据资产，其中结果链接在纯源码克隆中不可用。数据不包含在仓库内；BUG 文档中已选择的前后对比图属于小型文档附件，会随仓库保存。

## 公网版本

已有部署入口：[Video Agent](https://video-agent-food-notes.freechick3.chatgpt.site/)。

公网版使用 Sites Worker / R2 保存结果，按登录用户隔离笔记，支持生成、搜索、查看与删除。新任务仍由本地 CPU 工作器处理；电脑或工作器离线时，已有云端笔记可阅读，但无法处理新视频。

公网“我的笔记”和本地历史分别保存，**本地结果不会自动同步到云端**。现有部署并非克隆仓库就能使用的独立托管环境，重新部署需要配置存储、身份验证和运行密钥，见 [web/README.md](web/README.md)。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q

# 可选：公网 Worker 检查，需要 Node.js
Set-Location web
node scripts/test-web.mjs
npm run build
npm run validate
```

真实视频验收依赖本机数据和完整缓存；新克隆缺少这些数据时相关测试会跳过。检查结果及限制见 [测试记录](docs/TEST_REPORT.md)。测试通过不表示所有店名、菜品与价格均已人工核实。

## 当前边界与后续方向

- 名称、价格和评价依赖语音、OCR 与时序证据；可能误识别，缺少的信息不补写。
- 未具名的小摊使用有来源的描述性名称，图片不一定是门头。
- 目前没有接入生成式视觉模型，无法保证每道菜都能找到语义上最佳的画面。
- 极短订单画面、完整动画 PPT 提取、通用商品和课程自动总结尚未作为稳定功能开放。
- YouTube、小红书等平台属于后续方向，当前网页自动入口只支持哔哩哔哩。
- 当前尚未指定开源许可证；先以私有仓库管理，后续是否公开及许可证另行确定。

完整范围与计划见 [PROJECT_BRIEF.md](PROJECT_BRIEF.md)。
