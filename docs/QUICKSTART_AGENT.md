# Video Agent Agent 版

本包包含与本地版相同的工具，以及可选 `skills/video-agent/`。需要 Windows、Python 3.11+ 和可执行本机命令的 Agent。

解压后将以下内容交给 Agent：

> 请读取本项目 skills/video-agent/SKILL.md，安装并启动 Video Agent。成功后给我网页链接、三个简短功能和使用方式。

Agent 完成配置与自检后会返回实际本地网页地址。以后把要总结的 B 站探店视频链接发给它，即可返回本条笔记和统一首页。

也可以直接运行 `python video-agent.py setup`，用同一网页生成和管理笔记。Skill 不会自动安装到全局配置，不必复制第二套程序。

当前自动生成限 20 分钟以内中文探店视频；Agent 与服务须在同一台电脑运行。原视频、模型、缓存和历史均保留在本项目目录。项目 https://github.com/ccandtt/video-agent 。
