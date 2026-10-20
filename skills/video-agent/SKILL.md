---
name: video-agent
description: 安装、启动和使用本地视频笔记工具。用于用户请求部署 Video Agent、提供 B 站视频链接生成探店图文笔记、打开历史笔记或检查工具状态。
---

# Video Agent

让用户把视频链接交给 Agent，得到可打开的笔记和统一工具首页。Skill 只调用项目稳定入口；与网页共用服务、队列、缓存和历史。

## 定位与部署

在用户下载的项目中找到 `video-agent.py`。本 Skill 在源码包内的位置为 `skills/video-agent/SKILL.md`，项目根目录是上两级。如果 Skill 被单独安装到全局目录，定位用户实际项目，不能把模型装在 Skill 目录。用户只给仓库地址时，可在其指定工作目录中克隆项目；不要固定盘符或改动无关目录。

需要 Python 3.11+。在项目根目录执行：

```text
python video-agent.py setup --no-browser --json
```

setup 安装项目内依赖、下载 Whisper small、执行 OCR／ASR／FFmpeg 自检并启动服务。等待命令结束，读取 JSON；只有 status=ready 且 self_test_passed=true 才报告部署成功。失败时依据 error 和 .cache/install.log 定位原因，不把中间日志当作成功；缺少 Python 或网络访问时明确告知所需条件。无需 GPU、云端模型密钥或公网部署。

成功后简短回复，使用实际 homepage_url：

> 部署成功：[打开本地工具]({homepage_url})
>
> 1. B站探店图文笔记
> 2. 截图与时间戳回看
> 3. 历史分类搜索
>
> 使用：把视频链接发给我，或在网页中粘贴链接。

## 日常使用

用户给出需总结的视频链接时，在相同项目执行：

```text
python video-agent.py summarize "视频链接" --json
```

命令自动启动／复用服务并等待任务完成。当前自动生成仅支持可匿名获取的 B 站中文探店视频，最长 20 分钟；商品、课程和其他平台不是已开放的自动类别。

- status=completed：返回实际 note_url 和 homepage_url；reused=true 时说明已复用保存结果。
- status=failed 或 error：简短解释已报告的原因；不编造笔记链接。
- timed_out=true：任务仍在后台，返回 homepage_url 供用户查看；不要当作已生成，也不要重复提交或停止任务。
- 用户要查看旧笔记：运行 `python video-agent.py start --no-browser --json`，返回统一首页。

首次部署后不重复下载环境，也不为每个视频创建新服务。保留已有数据，不覆写处理逻辑或为单条视频重写脚本。用户明确要求重做、删除或修改范围时，按其具体指令处理；本 Skill 不自动删除数据、更改仓库可见性或部署公网。

状态检查使用 `python video-agent.py status --json`；故障自检使用 `doctor --json`；用户要求停止时使用 `stop --json`。所有操作均通过本机项目运行，远程 Agent 不能将远端的 localhost 当作用户电脑地址。
