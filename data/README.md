# 本地数据目录

此目录只跟踪本说明和空目录占位文件，原视频、识别缓存与已生成笔记不上传 GitHub。

- raw/<视频ID>/：video.mp4、video.info.json 等来源数据。
- processed/<视频ID>/：OCR、ASR、截图、笔记和验证结果。
- index.html、library.json：由工具生成的历史记录入口。
- 来源与状态统一登记在根目录 DATASET_CATALOG.md。

全新克隆的历史笔记为空。复制自己有权限使用的数据后，可运行 python -m video_agent.library 重建本地首页。勿将登录 Cookie、令牌或私人订单截图加入版本控制。
