# 项目约束

- 项目唯一构建目录为 `E:\Workspace\video_agent`。源码、依赖、模型、下载数据、生成产物、测试临时文件与日志均只存放在此目录内。
- 当前第一版仅实现本地中文探店视频的图文笔记；目标、场景、功能状态与后续 TODO 统一维护在根目录 `PROJECT_BRIEF.md`。
- 不将测试视频名称、店铺数量或人工验收标注硬编码进处理逻辑。`tests/fixtures/` 仅用于独立验收，流水线不得读取。
- 名称、菜品、价格、地点及评价需保留时间与原始识别依据；缺失信息保持缺失，不臆造地址。
- 语音识别文本可能不准确；摘要采用抽取式规则，不能把模型输出称为已核实事实。
- 视频对应的缓存必须匹配 SHA256 并完整；处理失败时先定位证据，再修复和重跑。

- 产品范围或当前迭代目标发生实质变化时更新 `PROJECT_BRIEF.md`；运行方法保留在 `README.md`，验收证据保留在 `docs/TEST_REPORT.md`。

- `PROJECT_BRIEF.md` 的核心流程使用居中的纯文本树状图：`text` 代码块、纵向主干、对称分支，按字符显示宽度用空格对齐。

## 运行和验证

```powershell
Set-Location E:\Workspace\video_agent
$env:PYTHONIOENCODING = 'utf-8'
.\.venv\Scripts\python.exe -m video_agent.pipeline .\data\raw\BV1cHen6EEen\video.mp4
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m video_agent.serve
```

## 结构

- `video_agent/extract.py`：本地 OCR/ASR、指纹缓存、密集视觉补采样。
- `video_agent/mining.py`：时序分段、名称核对、事实抽取、证据选择。
- `video_agent/render.py`：Markdown/HTML，包括事实级时间戳。
- `video_agent/pipeline.py`：CLI 编排和结构检查。
- `video_agent/serve.py`：仅本机 data 预览，支持视频 Range。

验证不仅包括测试，还应在真实视频中核对店铺介绍画面、关键事实及截图。程序成功退出不能证明所有语义正确。

- 网页源码在 web/，公网托管是 Sites Worker／R2，计算服务是本地 cloud_worker.py。修改网页后运行 Node 检查并发布同一 Site；不得泄露 web/.env.local 的秘密。
- 默认只在用户明确要求时新增 BUG_LOG 条目；普通实测修复写入 TEST_REPORT，不自动新增 BUG 记录。

- 样例数据统一登记在根目录 DATASET_CATALOG.md；新增／删除视频、补充产物或变更处理状态时同步更新，不能将目录文件当作实时云端任务列表。

- 无店名的小摊与餐饮点位应使用有视频依据的描述性名称，并标记 name_type=descriptive；不得将菜品或摊位描述伪装成已确认店名。非门头画面使用中性的点位图片标签。

## Git 仓库

- 根仓库统一管理源码、测试与文档；不要将 web 再次初始化为独立子仓库。
- 提交前检查暂存清单；不得上传 data 运行内容、models、output、.cache、tmp、.venv、web/.env.local 或 web/.openai 本机部署配置。
- README 负责运行入口，docs/README 是文档索引；不要把本地样例结果当成仓库已附带的文件。
- 私有仓库不等于已开源；未得到用户要求前不擅自添加开源许可证、更改仓库可见性或发布站点。
