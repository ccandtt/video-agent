# 本地工具双入口与分发

## 同一核心，两种入口

Agent → 可选 Skill → video-agent.py → 统一 CLI → 本地 HTTP 服务 → LocalJobs → OCR／ASR／笔记流水线。

用户 → video-agent.py setup／start → 同一本地 HTTP 服务 → 网页表单 → 同一个 LocalJobs。

历史从 data 读取，任务记录在 .cache/local-jobs.json。Skill 不生成另一套数据，也不要求独立的 Web 服务。工具只支持本机运行，不将远端 Agent 的 localhost 地址当作用户电脑链接。

## 安装、自检和启动

`setup` 在项目目录创建 .venv，安装 requirements.txt 中的运行依赖（constraints.txt 固定已验证依赖版本），将模型保存到 models；测试依赖仅在 requirements-dev.txt。FFmpeg 随依赖提供。之后执行一次真实 OCR 空白图、ASR 静音音频推理和 FFmpeg 自检，全部成功才启动服务并返回 status=ready。

依赖安装日志：.cache/install.log。服务日志：.cache/local-tool.log、local-tool.error.log。模型首次下载需要联网，已准备模型的环境可用 --offline。模型大文件不随精简包附带。

`start` 以隐藏后台进程运行服务，记录实际端口。按项目路径标识服务，只复用或停止本项目实例；其他项目或占用端口的程序不会被关闭。服务未就绪不会返回成功。--restart 先停止本项目实例，再启动；--no-browser 适合 Agent 与验证流程。

`status` 显示运行状态与首页；`doctor` 检查依赖版本和模型文件完整性，深度推理自检在 setup 中执行。

## 任务返回

`summarize URL --json` 通过本地 HTTP 接口提交任务，不额外创建队列。默认等待完成，返回 status、homepage_url、note_url、reused 等。

- completed：note_url 是完整、可打开的笔记地址。
- failed：返回实际错误，退出码 1。
- 超过 --timeout（默认 3600 秒）：退出码 2，timed_out=true，后台任务继续；到首页查看，避免重复提交。
- --no-wait：只提交并返回任务记录；任务尚未完成时没有笔记成功承诺。

当前自动生成支持 restaurant 类别：B 站、中文探店、20 分钟以内、可匿名获取。下载失败会保留缓存并提示原因，不绕过平台访问要求。

## 可选 Skill

`skills/video-agent/SKILL.md` 为项目内分发入口；`agents/openai.yaml` 为 UI 元数据。用户在 Agent 中指定读取此文件即可使用。如自行注册到全局技能目录，Skill 会定位用户实际项目，不把全局目录当作运行数据目录。

首次部署反馈保持简短：真实首页链接、三项功能和一句使用方法；每次视频完成返回笔记链接与首页。只在本机运行，缺少 Python、下载权限或网络时报告所需条件，不伪装配置成功。

## 精简包

完整源码开发环境执行：

```powershell
python scripts/build_distribution.py
```

产物位于 output/releases：

| 文件 | 内容 |
| --- | --- |
| video-agent-local.zip | 启动器、运行依赖清单、Python 核心和本地页面模板 |
| video-agent-agent.zip | 同一核心，再附带 Skill 与 UI 元数据 |
| checksums.json | 两个包的文件数、大小和 SHA256 |

包使用固定白名单生成，排除模型、数据、缓存、私钥、运行密钥、测试和公网代码。本地版无需下载 Skill，Agent 版不复制另一套核心。发布下载资产时使用这些产物；不将本机运行数据加入版本控制。

源码轻量克隆可使用 README 中的 sparse-checkout，普通用户只取 video_agent，Agent 用户再取 skills；根目录启动器和运行依赖清单随克隆保留。

## 开发验证

```powershell
.\.venv\Scripts\python.exe -m pip install --cache-dir .\.cache\pip -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests -q
```

需要实测：两包内容、全新目录安装、setup 幂等、端口冲突、跨项目隔离、JSON 输出、任务提交／进度／笔记 URL、停止重启历史保留。验收记录见 TEST_REPORT.md。
