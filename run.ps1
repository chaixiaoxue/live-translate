$ErrorActionPreference = "Continue"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:XDG_DATA_HOME = Join-Path $ProjectRoot ".local-data"
$env:XDG_CONFIG_HOME = Join-Path $ProjectRoot ".config-data"
$env:XDG_CACHE_HOME = Join-Path $ProjectRoot ".cache-data"
$env:HF_HOME = Join-Path $ProjectRoot ".cache-data\huggingface"

Set-Location $ProjectRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Main = Join-Path $ProjectRoot "main.py"
$Stdout = Join-Path $ProjectRoot "live_translate_stdout.log"
$Stderr = Join-Path $ProjectRoot "live_translate_stderr.log"

Start-Process `
    -FilePath $Python `
    -ArgumentList @($Main) `
    -WorkingDirectory $ProjectRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $Stdout `
    -RedirectStandardError $Stderr
