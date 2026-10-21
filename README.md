# Video2Note · 本地视频图文笔记工具

粘贴视频链接，生成带文字总结、截图和时间戳的图文笔记。**Agent 和网页共用同一套本地服务、处理队列、缓存与历史记录。**

当前自动生成：可匿名获取的 B 站中文美食探店视频，最长 20 分钟。商品推荐、知识讲解已有单次整理样例，通用自动生成待支持。

**运行环境：Windows、Python 3.11+。**首次配置需要联网下载依赖与 Whisper small（约 483 MB）；在本机 CPU 运行，无需 GPU 或模型 API 密钥。Agent 须能在同一台电脑执行命令。

## 快速使用一：交给 Agent

获取 `video-agent-agent.zip` 并解压；也可以轻量克隆源码：

```powershell
git clone --depth 1 --filter=blob:none --sparse https://github.com/ccandtt/video-agent.git video-agent
cd video-agent
git sparse-checkout set video_agent skills
```

把这句话交给 Agent：

> 请读取本项目 skills/video-agent/SKILL.md，安装并启动 Video Agent。成功后给我网页链接、三个简短功能和使用方式。

首次部署成功后，Agent 会回复：

> 部署成功：[打开本地工具](http://127.0.0.1:8765/)
>
> 1. B站探店图文笔记
> 2. 截图与时间戳回看
> 3. 历史分类搜索
>
> 使用：把视频链接发给我，或在网页中粘贴链接。

以后直接把要总结的视频链接发给使用该 Skill 的 Agent。完成后会返回**本条笔记链接和统一首页**。网页提交的笔记也出现在相同历史中。

`skills/` 是可选适配层，只保存 Agent 操作说明，不复制处理代码，也不自动修改全局 Agent 配置。直接指定 Agent 读取 SKILL.md 即可使用。

## 快速使用二：命令行启动，网页操作

获取 `video-agent-local.zip` 并解压；也可以只克隆核心源码：

```powershell
git clone --depth 1 --filter=blob:none --sparse https://github.com/ccandtt/video-agent.git video-agent
cd video-agent
git sparse-checkout set video_agent
```

在下载／解压后的项目目录，首次运行：

```powershell
python video-agent.py setup
```

程序安装项目内依赖、准备模型、完成 OCR／ASR／FFmpeg 自检后自动打开网页。网页中粘贴链接 → 选择美食探店 → 生成笔记并查看进度；下方分类、搜索和打开历史笔记。

以后只需：

```powershell
python video-agent.py start
```

默认首页为 `http://127.0.0.1:8765/`；端口被占用时选择可用端口，并返回实际地址。同一个项目重复启动会复用已有服务。界面与 Agent 应以命令返回的网址为准。

## 笔记类型与处理技术

“笔记类型”与历史分类统一为 **知识讲解、商品推荐与评测、美食探店**；“全部”仅用于浏览历史。当前仅美食探店开放自动生成，另外两类可浏览已有结果，选择时明确显示“自动生成待支持”。

共同基础：FFmpeg／OpenCV 解析视频，RapidOCR（ONNX Runtime）识别画面文字，faster-whisper small（CPU int8）输出带时间戳的中文语音；完整缓存按视频 SHA256 校验，截图及事实关联原视频时间。

| 类型 | 已采用的处理方式 | 自动化状态 |
| --- | --- | --- |
| 美食探店 | 2 秒基础采样，结合店铺转场及语音句中补帧；OCR 与 ASR 按时间分段、比对店名，依据文字与时序关联菜品、报价、评价和截图；输出店铺目录、推荐菜单及图文笔记。 | 已开放本地自动流程；B 站中文探店，最长 20 分钟。 |
| 商品推荐与评测 | 已验证样例采用完整 ASR、8 秒抽样 OCR，人工／Agent 结合原画面整理品牌、商品信息、视频报价及体验，选取截图并写入分节结构，再渲染 HTML／Markdown。 | 已有样例；内容整理与选图尚未实现通用自动化。 |
| 知识讲解 | 已验证样例结合完整 ASR、OCR、图表与课件截图，人工／Agent 按概念、论证和案例组织章节；课件样例另做逐秒扫描、翻页处密集取帧与逐页完整性核看，输出图文笔记或 PDF。 | 已有图文与课件样例；章节整理、PPT 完整页筛选尚未实现通用自动化。 |

自动处理流水线尚未接入生成式视觉模型或外部商家核查；菜品配图依赖文字与时序，商品名称、报价及观点保留视频来源。`curated_notes.py` 负责渲染已整理的内容结构，不会自动理解任意商品或课程视频。

## 常用命令

| 命令 | 用途 |
| --- | --- |
| `python video-agent.py setup` | 首次安装、自检并打开工具 |
| `python video-agent.py start` | 启动或复用服务并打开首页 |
| `python video-agent.py summarize "视频链接"` | 通过同一服务提交任务并等待笔记 |
| `python video-agent.py status` | 查看服务与实际网址 |
| `python video-agent.py doctor` | 检查依赖和模型文件 |
| `python video-agent.py stop` | 停止本项目服务，保留历史 |

Agent 使用 `--json` 读取结构化结果；部署和启动可加 `--no-browser`。已有完整环境可用 `setup --offline` 自检。进度写入 stderr，JSON 结果写入 stdout。

## 数据与运行方式

- 所有数据保存在安装目录：`data/` 为原视频、截图与笔记，`models/` 为模型，`.cache/` 为任务状态、安装缓存与日志。
- 新视频追加到同一历史库；相同视频复用已有结果。首页保持统一，每条笔记有独立阅读地址。
- 关闭网页或 Agent 会话不会删除笔记；后台服务仍可运行。停止服务或关闭电脑会中断计算，再次启动后历史保留，中断任务可重新提交以复用完整缓存。
- 工具只监听本机 `127.0.0.1`，服务运行期间本地网址才可访问；更新程序时保留数据、模型和缓存目录。
- 本地首页与已有公网部署的数据分别保存；当前两种入口都使用本地服务，无需配置 Sites 或公网账号。
- OCR／ASR 可能误识别，菜品和截图关联仍基于文字与时序规则；缺少的信息不补写。更完整的能力边界见项目概览。

## 精简包与开发文档

本地版只含运行核心；Agent 版在其上增加 `skills/video-agent/`。二者都不附带视频、模型、测试、架构图或公网部署代码。构建方式见 [分发与验收](docs/LOCAL_TOOL.md)；仓库当前的可访问权限保持原状。

- [项目目标与进展](PROJECT_BRIEF.md) · [数据集目录](DATASET_CATALOG.md)
- [双入口部署与命令说明](docs/LOCAL_TOOL.md) · [开发说明](docs/DEVELOPMENT.md)
- [项目架构与技术流程图](docs/ARCHITECTURE.md) · [通用技术流程图生成](docs/TECHNICAL_FLOW.md)
- [测试记录](docs/TEST_REPORT.md) · [BUG 记录](docs/BUG_LOG.md) · [公网部署（进阶）](web/README.md)

已有的 start_local_tool.ps1 / stop_local_tool.ps1 保留兼容，内部调用同一个统一入口。技术流程图和公网部署属于开发维护功能，完整源码中按需获取。
