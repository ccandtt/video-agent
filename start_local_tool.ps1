param([switch]$Restart, [switch]$NoBrowser)
$ErrorActionPreference='Stop'
$python=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw '首次使用请运行 python video-agent.py setup' }
$arguments=@((Join-Path $PSScriptRoot 'video-agent.py'),'start')
if ($Restart) { $arguments+='--restart' }
if ($NoBrowser) { $arguments+='--no-browser' }
& $python @arguments
exit $LASTEXITCODE
