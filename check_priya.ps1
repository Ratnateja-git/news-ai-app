[CmdletBinding()]
param()

$ProjectRoot = $PSScriptRoot
$Port = 8000
$ModelName = "gemma3:4b"
$Failures = 0

function Report([string]$Name, [bool]$Passed, [string]$Detail = "") {
    if ($Passed) {
        Write-Host "PASS  $Name $Detail" -ForegroundColor Green
    } else {
        Write-Host "FAIL  $Name $Detail" -ForegroundColor Red
        $script:Failures++
    }
}

$Python = @(
    (Join-Path $ProjectRoot ".venv\\Scripts\\python.exe"),
    (Join-Path $ProjectRoot "venv\\Scripts\\python.exe")
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
Report "Python virtual environment" ($null -ne $Python) $(if ($Python) { $Python } else { "not found" })
if ($Python) {
    try { & $Python --version | Out-Null; Report "Python launcher" ($LASTEXITCODE -eq 0) } catch { Report "Python launcher" $false "cannot execute" }
}

$Ollama = Get-Command ollama -ErrorAction SilentlyContinue
Report "Ollama executable" ($null -ne $Ollama) $(if ($Ollama) { $Ollama.Source } else { "not on PATH" })
try {
    $OllamaTags = Invoke-RestMethod "http://127.0.0.1:11434/api/tags" -TimeoutSec 3
    Report "Ollama server (11434)" $true
    $InstalledModels = @($OllamaTags.models | ForEach-Object { $_.name })
    Report "Gemma model $ModelName" ($InstalledModels -contains $ModelName)
} catch {
    Report "Ollama server (11434)" $false
    Report "Gemma model $ModelName" $false
}
try { Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$Port/health" -TimeoutSec 3 | Out-Null; Report "FastAPI server ($Port)" $true } catch { Report "FastAPI server ($Port)" $false }

$KokoroDirectory = if ($env:PRIYA_KOKORO_DIR) { $env:PRIYA_KOKORO_DIR } else { $ProjectRoot }
Report "Kokoro model" (Test-Path -LiteralPath (Join-Path $KokoroDirectory "kokoro-v1.0.onnx") -PathType Leaf)
Report "Kokoro voices" (Test-Path -LiteralPath (Join-Path $KokoroDirectory "voices-v1.0.bin") -PathType Leaf)

$Cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
Report "cloudflared" ($null -ne $Cloudflared) $(if ($Cloudflared) { $Cloudflared.Source } else { "not on PATH" })

if ($Failures) { exit 1 }
