# 公网版源码

此目录包含 Video Agent 的公网网页和 API。主工具的本地使用方法见 [根 README](../README.md)。

## 源码与构建

- `ui.html`：网页界面。
- `worker/service.js`：任务、登录身份、存储、媒体访问和删除接口。
- `worker/index.js`：由构建脚本将上述两者合成的 Worker 入口；不直接修改。
- `scripts/build.mjs`：生成 Worker 及 dist 目录。
- `scripts/test-web.mjs`：接口、隔离与状态行为检查。
- `scripts/validate-artifact.mjs`：构建产物和 ESM 入口检查。
- `hosting.example.json`：不含本机部署身份的配置示例。

需要 Node.js。没有第三方 npm 依赖：

```powershell
Set-Location E:\Workspace\video_agent\web
New-Item -ItemType Directory -Force .openai | Out-Null
Copy-Item hosting.example.json .openai\hosting.json
# 发布前，将 .openai/hosting.json 的 project_id 改为自己的 Sites 项目 ID
node scripts/test-web.mjs
npm run build
npm run validate
```

已有本机部署时保留原 `.openai/hosting.json`，不要用示例覆盖。构建输出为 `dist/server/index.js` 和 `dist/.openai/hosting.json`；dist 不进 Git。

## 部署与计算

已有实例由 Sites 托管，Worker 使用绑定名 `BUCKET` 的 R2 存储。部署需要配置平台身份验证，使用平台提供的 `oai-authenticated-user-id` 区分用户；不得在未验证客户端身份的普通 Worker 上直接信任该请求头。

运行密钥保存在云端 secret `WORKER_KEY` 和本机 `web/.env.local`。复制 `.env.example` 为 `.env.local`，自行生成足够随机的密钥并同步云端；两端应一致，不要把真实值写进 Git。

本机工作器命令（在项目根目录）：

```powershell
.\.venv\Scripts\python.exe -m video_agent.cloud_worker --site https://YOUR_SITE_HOST
```

本机 `start_web_worker.ps1` / `stop_web_worker.ps1` 为既有实例提供后台启动和停止；重用到新部署前需要更改站点地址。

GitHub 私有仓库仅保存源码，不会自动创建 Sites、R2、身份验证或启动计算服务，也没有配置自动部署。提交源码不会更新现有线上实例。

公网与本地历史列表分别保存。本机模型服务离线时无法生成新笔记；已上传的云端笔记仍可阅读。
