$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot ".venv\Scripts\pythonw.exe"
$serverScript = Join-Path $projectRoot "scripts\run_web.py"
$dataDirectory = Join-Path $projectRoot "data"
$logPath = Join-Path $dataDirectory "planning_ai_launcher.log"
$serverLogPath = Join-Path $dataDirectory "planning_ai_server.log"
$errorLogPath = Join-Path $dataDirectory "planning_ai_launcher_error.log"
$port = if ($env:PLANNING_WEB_PORT) { [int]$env:PLANNING_WEB_PORT } else { 8000 }
$healthUrl = "http://127.0.0.1:$port/api/status"
$chatUrl = "http://127.0.0.1:$port"

function Show-PlanningError([string]$message) {
    if ($env:PLANNINGAI_HEADLESS -eq "true") { throw $message }
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show($message, "PlanningAI could not start", "OK", "Error") | Out-Null
}

function Write-LauncherLog([string]$message) {
    "$(Get-Date -Format o) $message" | Add-Content -LiteralPath $logPath
}

function Test-PlanningReady {
    try {
        $status = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
        return [bool]$status.ready
    } catch {
        return $false
    }
}

try {
    if (-not (Test-Path -LiteralPath $pythonPath)) {
        throw "PlanningAI is not installed yet. The expected Python environment was not found at:`n$pythonPath"
    }

    New-Item -ItemType Directory -Path $dataDirectory -Force | Out-Null
    Write-LauncherLog "Launcher started"

    if (-not (Test-PlanningReady)) {
        $ollamaCommand = Get-Command "ollama.exe" -ErrorAction SilentlyContinue
        $ollamaPath = if ($ollamaCommand) { $ollamaCommand.Source } else { $null }
        if (-not $ollamaPath) {
            $commonOllama = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
            if (Test-Path -LiteralPath $commonOllama) { $ollamaPath = $commonOllama }
        }
        Write-LauncherLog "Ollama found"
        if (-not $ollamaPath) {
            throw "Ollama was not found. Install Ollama and create the planning-kimi model before using PlanningAI."
        }

        try {
            Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2 | Out-Null
        } catch {
            Start-Process -FilePath $ollamaPath -ArgumentList "serve" -WindowStyle Hidden
            Start-Sleep -Seconds 2
        }

        $modelList = & $ollamaPath list 2>$null
        if (($modelList -join "`n") -notmatch "planning-kimi") {
            throw "The local model 'planning-kimi' is not installed. Run:`nollama create planning-kimi --file models\Kimi.Modelfile"
        }
        Write-LauncherLog "planning-kimi model found"

        Write-LauncherLog "Starting FastAPI"
        Start-Process -FilePath $pythonPath -ArgumentList @($serverScript) -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput $serverLogPath -RedirectStandardError $errorLogPath

        $ready = $false
        for ($attempt = 0; $attempt -lt 120; $attempt++) {
            if (Test-PlanningReady) { $ready = $true; break }
            Start-Sleep -Seconds 1
        }
        if (-not $ready) {
            throw "PlanningAI did not become ready within two minutes. See:`n$logPath"
        }
        Write-LauncherLog "FastAPI is ready"
    }

    Write-LauncherLog "Opening browser"
    Start-Process $chatUrl
} catch {
    try { Write-LauncherLog "ERROR: $($_.Exception.Message)" } catch {}
    Show-PlanningError $_.Exception.Message
    exit 1
}
