param([switch]$Restart, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$projectDir = 'E:\Workspace\video_agent'
$baseUrl = 'http://127.0.0.1:8765'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
try {
    $health = Invoke-RestMethod -Uri "$baseUrl/api/health" -TimeoutSec 2
    if ($health.mode -eq 'local' -and -not $Restart) {
        if (-not $NoBrowser) { Start-Process -FilePath "$baseUrl/" }
        Write-Output "本地工具已经运行：$baseUrl/"
        exit
    }
    if ($health.mode -eq 'local' -and $Restart) {
        Invoke-RestMethod -Uri "$baseUrl/api/shutdown" -Method Post -ContentType 'application/json' -Body '{}' -TimeoutSec 8 | Out-Null
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            if (-not (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue)) { break }
            Start-Sleep -Milliseconds 100
        }
    }
} catch {}
$listener = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
foreach ($entry in $listener) {
    $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId=$($entry.OwningProcess)"
    $parentInfo = Get-CimInstance Win32_Process -Filter "ProcessId=$($processInfo.ParentProcessId)" -ErrorAction SilentlyContinue
    $projectPattern = '*E:\Workspace\video_agent\.venv\Scripts\python.exe*video_agent.serve*'
    $ownedPreview = $processInfo.CommandLine -like $projectPattern -or ($parentInfo -and $parentInfo.CommandLine -like $projectPattern)
    if ($ownedPreview -and $processInfo.CommandLine -like '*-m video_agent.serve*') {
        Stop-Process -Id $processInfo.ProcessId
    } else {
        throw '8765 端口已被其他程序使用，请先确认占用程序。'
    }
}
& (Join-Path $projectDir '.venv\Scripts\python.exe') -m video_agent.library
if ($LASTEXITCODE -ne 0) { throw '本地首页准备失败。' }
$localProcess = Start-Process -FilePath (Join-Path $projectDir '.venv\Scripts\python.exe') -ArgumentList '-m','video_agent.serve' -WorkingDirectory $projectDir -WindowStyle Hidden -RedirectStandardOutput (Join-Path $projectDir '.cache\local-tool.log') -RedirectStandardError (Join-Path $projectDir '.cache\local-tool.error.log') -PassThru
Set-Content -LiteralPath (Join-Path $projectDir '.cache\local-tool.pid') -Value $localProcess.Id
$ready = $false
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri "$baseUrl/api/health" -TimeoutSec 1
        if ($health.mode -eq 'local') { $ready = $true; break }
    } catch {}
    Start-Sleep -Milliseconds 150
}
if (-not $ready) { throw '本地服务未就绪，请查看 .cache/local-tool.error.log。' }
if (-not $NoBrowser) { Start-Process -FilePath "$baseUrl/" }
Write-Output "本地工具已启动：$baseUrl/"
