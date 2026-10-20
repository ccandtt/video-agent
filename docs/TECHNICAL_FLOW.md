# 技术流程图生成

将任务的步骤配置生成 PNG 和可编辑 SVG。图中每个节点包含步骤名称、输入、关键技术与中间产物；连接描述处理顺序、分支、汇合或跳过路径。

## 本项目一键生成

```powershell
Set-Location E:\Workspace\video_agent
.\.venv\Scripts\python.exe -m video_agent.technical_flow
```

默认读取 [technical-flow.json](architecture/technical-flow.json)，生成：

- [technical-flow.png](architecture/technical-flow.png)：高清阅读与汇报用图。
- [technical-flow.svg](architecture/technical-flow.svg)：包含原生文字和矢量图形的可编辑源图。
- [technical-flow.validation.json](architecture/technical-flow.validation.json)：节点数、连接数、层数、尺寸及配置／图片哈希。

默认图对应本地工具的“链接 → 探店笔记”主链路。基础 OCR 和 ASR 按当前 CLI 的实际顺序排列；完整性及 SHA256 校验后进行画面补采样。已有笔记命中时直接复用阅读入口。公网的任务编排、R2 存储关系见 [项目架构图](architecture/project-architecture.png)。

## 其他任务

复制 [通用示例](architecture/technical-flow.example.json)，修改为自己的步骤：

```powershell
.\.venv\Scripts\python.exe -m video_agent.technical_flow --config docs\architecture\technical-flow.example.json --output output\diagrams\my-task
```

输出为 output/diagrams/my-task.png、my-task.svg 与 my-task.validation.json，均保存在项目内；output 不上传 Git。生成器只读取配置并绘图，不执行图中描述的数据处理任务，也不自动分析源码或视频内容。

## 配置字段

| 字段 | 类型 | 内容 |
| --- | --- | --- |
| title | 文本 | 图标题 |
| subtitle | 文本，可选 | 图的范围或任务说明 |
| nodes | 步骤列表 | 1–24 个节点 |
| nodes[].id | 文本 | 唯一 ID，字母／数字／下划线／连字符 |
| nodes[].title | 文本 | 核心处理动作 |
| nodes[].inputs | 文本列表 | 本步骤接收的输入 |
| nodes[].technology | 文本列表 | 关键方法、工具或模型 |
| nodes[].outputs | 文本列表 | 本步骤的中间产物或最终结果 |
| edges | 连接列表 | from → to；可带 label |
| notes | 文本列表，可选 | 范围、条件和补充说明 |

最小例子：

```json
{
  "title": "文本处理流程",
  "nodes": [
    {
      "id": "read",
      "title": "读取输入",
      "inputs": ["input.txt"],
      "technology": ["UTF-8 文件读取"],
      "outputs": ["原始文本"]
    },
    {
      "id": "export",
      "title": "导出结果",
      "inputs": ["原始文本"],
      "technology": ["文本规范化"],
      "outputs": ["result.txt"]
    }
  ],
  "edges": [{"from": "read", "to": "export", "label": "传递文本"}]
}
```

## 布局与边界

- 按有向无环关系自动分层；声明列表可不按拓扑顺序，编号按图的阅读顺序生成。
- 支持顺序、常见分支与汇合、向后续步骤的跳过路径；同层最多 3 个节点。复杂网状流程建议拆图。
- 节点文本自动换行，尽量保留完整英文术语与文件名；SVG 对文字做 XML 转义。
- 输入配置与输出路径必须位于项目内；不写出项目根目录。配置最大 512 KB，大图会提示降低倍率或拆分。
- `--scale 2` 为默认高清输出，`--scale 1` 生成较小 PNG；SVG 保持矢量。
- 绘图复用 Pillow，无新增 Python 依赖；中文字体使用 Microsoft YaHei 或 Noto Sans CJK。
- 配置必须随实现变化维护；本图不是运行时性能追踪或通用代码理解模型。

源码：[video_agent/technical_flow.py](../video_agent/technical_flow.py)。
