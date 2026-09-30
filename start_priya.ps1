[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$Port = 8000
$ModelName = "gemma3:4b"

function Get-PriyaPython {
    foreach ($candidate in @(
        (Join-Path $ProjectRoot ".venv\\Scripts\\python.exe"),
        (Join-Path $ProjectRoot "venv\\Scripts\\python.exe")
    )) {
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    throw "Python virtual environment not found. Create or repair .venv before starting Priya."
}

function Require-File([string]$Path, [string]$Description) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Description was not found: $Path"
    }
}

$Python = Get-PriyaPython
try {
    & $Python -c "import fastapi, uvicorn" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Python dependencies could not be imported." }
} catch {
    throw "The selected virtual environment cannot run Python. Repair it before starting Priya. $($_.Exception.Message)"
}

try {
    $OllamaTags = Invoke-RestMethod "http://127.0.0.1:11434/api/tags" -TimeoutSec 3
    $InstalledModels = @($OllamaTags.models | ForEach-Object { $_.name })
    if ($InstalledModels -notcontains $ModelName) {
        throw "Required model $ModelName is not installed. Run: ollama pull $ModelName"
    }
} catch {
    throw "Ollama is not ready at http://127.0.0.1:11434. Start the Ollama service, verify $ModelName, then retry. $($_.Exception.Message)"
}

$KokoroDirectory = if ($env:PRIYA_KOKORO_DIR) { $env:PRIYA_KOKORO_DIR } else { $ProjectRoot }
Require-File (Join-Path $KokoroDirectory "kokoro-v1.0.onnx") "Kokoro model"
Require-File (Join-Path $KokoroDirectory "voices-v1.0.bin") "Kokoro voices"

Write-Host "Starting Priya FastAPI on http://127.0.0.1:$Port/app/" -ForegroundColor Green
Push-Location $ProjectRoot
try {
    & $Python -m uvicorn backend.main:app --host 127.0.0.1 --port $Port
} finally {
    Pop-Location
}
