$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$projectDir = 'E:\Workspace\video_agent'
$pidFile = Join-Path $projectDir '.cache\cloud-worker.pid'
if (Test-Path -LiteralPath $pidFile) {
    $workerPid = [int](Get-Content -LiteralPath $pidFile)
    $existing = Get-CimInstance Win32_Process -Filter "ProcessId=$workerPid" -ErrorAction SilentlyContinue
    if ($existing -and $existing.CommandLine -like '*video_agent.cloud_worker*') {
        Write-Output '计算服务已经运行。'
        exit
    }
}
$process = Start-Process -FilePath (Join-Path $projectDir '.venv\Scripts\python.exe') -ArgumentList '-m','video_agent.cloud_worker','--site','https://video-agent-food-notes.freechick3.chatgpt.site' -WorkingDirectory $projectDir -WindowStyle Hidden -RedirectStandardOutput (Join-Path $projectDir '.cache\cloud-worker.log') -RedirectStandardError (Join-Path $projectDir '.cache\cloud-worker.error.log') -PassThru
Set-Content -LiteralPath $pidFile -Value $process.Id
Write-Output '计算服务已在后台启动。'
