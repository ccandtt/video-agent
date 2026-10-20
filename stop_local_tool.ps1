$ErrorActionPreference = 'Stop'
try {
    Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/shutdown' -Method Post -ContentType 'application/json' -Body '{}' -TimeoutSec 8 | Out-Null
    Write-Output '本地工具已停止，已保存笔记保留。'
} catch {
    Write-Output '本地工具未运行，或当前端口为旧版预览服务。'
}
