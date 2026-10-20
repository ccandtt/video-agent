$ErrorActionPreference = 'Stop'
$pidFile = 'E:\Workspace\video_agent\.cache\cloud-worker.pid'
if (Test-Path -LiteralPath $pidFile) {
    $workerPid = [int](Get-Content -LiteralPath $pidFile)
    $existing = Get-CimInstance Win32_Process -Filter "ProcessId=$workerPid" -ErrorAction SilentlyContinue
    if ($existing -and $existing.CommandLine -like '*video_agent.cloud_worker*') {
        Stop-Process -Id $workerPid
        Write-Output '计算服务已停止。云端已完成笔记仍可访问。'
    }
}
