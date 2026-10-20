# Video Agent 本地版

需要 Windows、Python 3.11+，首次配置需要联网下载依赖与语音模型。解压后在本目录执行：

```powershell
python video-agent.py setup
```

配置和 OCR／ASR 自检成功后自动打开本地网页。粘贴 B 站视频链接 → 选择探店攻略 → 生成；历史笔记与分类在同一首页。

以后运行：

```powershell
python video-agent.py start
```

停止：`python video-agent.py stop`。状态：`python video-agent.py status`。相同视频复用已保存结果，关闭页面不会删除笔记。当前自动生成限 20 分钟以内的中文探店视频；其他类别待支持。

本包只包含本地工具，未附带 Skill、开发测试、架构图或公网部署代码。原视频、模型和笔记在首次使用时保存到当前目录，更新前保留 data、models 和 .cache。项目 https://github.com/ccandtt/video-agent 。
