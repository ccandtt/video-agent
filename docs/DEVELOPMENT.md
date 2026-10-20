# 开发与仓库管理

## 处理链路

Agent 的 summarize 与工具页均通过同一个本地 HTTP 服务提交链接，`local_jobs.py` 管理本地队列并调用 `pipeline.py`。`extract.py` 提取画面 OCR 与完整语音，`mining.py` 分段及抽取名称与事实，`menu.py` 关联菜单与图片，`render.py` 输出 HTML / Markdown。`library.py` 扫描已保存结果，`serve.py` 提供本机页面、接口和视频 Range 回看。

`curated_notes.py` 是已整理好内容结构的渲染器，不是通用商品或课程自动总结器。公网部分在 `web/`；`cloud_worker.py` 连接云端队列，在本机计算并上传结果。

## 修改与验证

1. 按 AGENTS.md 的约束在项目内操作，先阅读相关模块与测试。开发测试依赖使用 `python -m pip install -r requirements-dev.txt`；普通安装仅使用运行依赖。
2. 修改实际逻辑，不能把样例店名、数量或 tests/fixtures 中的答案加入处理流程。
3. 运行 `python -m pytest tests -q`。真实样例测试需要 data 中原始数据和完整缓存；无数据时跳过。
4. 修改公网源码时，在 web 中运行 `node scripts/test-web.mjs`、`npm run build`、`npm run validate`。源码上传到 GitHub 不会自动发布站点。
5. 需要时核看真实视频、图片和回看交互；把范围、结论与限制记入 TEST_REPORT。
6. 范围变化更新 PROJECT_BRIEF，使用方法更新 README，数据变化更新 DATASET_CATALOG。

## 文件归档约定

- 根目录保留启动入口和主要说明；Python 源码、测试、文档、公网源码分别保留在已有目录。
- data 保存原视频、OCR/ASR、笔记和截图；models、output、.cache、tmp 保存对应本地运行资产。它们不进 Git，也不在整理过程中删除。
- 小型 BUG 对比图保留在 docs/bugs/assets，作为文档附件纳入版本控制。
- `.env.local`、令牌、私钥、日志、虚拟环境和构建产物不上传。仓库是私有的，也应保持这一规则。
- `web/.openai/hosting.json` 是本机部署配置，不进 Git；新部署按 web/README 从示例配置开始。
- 原有 web 子目录的独立 Git 元数据如需合并管理，先归档到项目内 .cache/repository-backups，再将 web 源码纳入根仓库；不丢弃其历史备份。

## 本机 Git 常用命令

```powershell
Set-Location E:\Workspace\video_agent
git status
git diff
git add README.md docs video_agent tests web requirements.txt
git diff --cached --stat
git commit -m "Describe the change"
git push
```

提交前确认待提交清单中没有运行数据或秘密。忽略规则不会删除本机文件，也不会自动清理已经被 Git 跟踪的文件。
