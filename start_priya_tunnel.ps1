[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$Port = 8000
$HealthUrl = "http://127.0.0.1:$Port/health"

$Cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $Cloudflared) {
    throw "cloudflared was not found on PATH. See PUBLIC_DEPLOYMENT.md for the official Windows installation instructions."
}

try {
    Invoke-WebRequest -UseBasicParsing $HealthUrl -TimeoutSec 3 | Out-Null
} catch {
    throw "Priya is not reachable at $HealthUrl. In another PowerShell window, run .\\start_priya.ps1 first."
}

Write-Host "Starting a temporary Cloudflare Quick Tunnel for http://127.0.0.1:$Port" -ForegroundColor Green
Write-Host "Copy the https://*.trycloudflare.com URL printed below and open <URL>/app/." -ForegroundColor Yellow
& $Cloudflared.Source tunnel --url "http://127.0.0.1:$Port"
