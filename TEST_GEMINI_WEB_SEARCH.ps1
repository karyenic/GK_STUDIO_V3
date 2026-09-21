# GK STUDIO V3 - Gemini Web Search Diagnostic
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$envFile = Join-Path $root ".env"
Write-Host ""
Write-Host "=== GEMINI WEB SEARCH TEST ===" -ForegroundColor Cyan
if (-not (Test-Path $envFile)) { Write-Host "[HATA] .env yok." -ForegroundColor Red; exit 1 }
$key = ""
Get-Content $envFile -Encoding UTF8 | ForEach-Object {
$line = $_.Trim()
if ($line -match "^(?!#)\s*GEMINI_API_KEY\s*=\s*(.+?)\s*$") { $key = $Matches[1].Trim().Trim(""") }
}
if ([string]::IsNullOrWhiteSpace($key)) { Write-Host "[HATA] GEMINI_API_KEY yok." -ForegroundColor Red; exit 1 }
Write-Host "[1] Model listesi..." -ForegroundColor Yellow
try {
$models = Invoke-RestMethod -Uri "https://generativelanguage.googleapis.com/v1beta/models" -Headers @{ "x-goog-api-key" = $key } -Method Get -TimeoutSec 30
$found = $models.models | Where-Object { $_.name -eq "models/gemini-2.5-flash" }
if ($found) { Write-Host "[OK] gemini-2.5-flash gorunuyor." -ForegroundColor Green } else { Write-Host "[UYARI] model bulunamadi." -ForegroundColor DarkYellow }
} catch { Write-Host "[HATA] Model API testi basarisiz: $($_.Exception.Message)" -ForegroundColor Red; exit 1 }
Write-Host "[2] Google Search grounding..." -ForegroundColor Yellow
$payloadObject = @{
contents = @(@{ parts = @(@{ text = "Guncel Turkiye otomobil satislari icin resmi bir kaynak bul ve URL belirt." }) })
tools = @(@{ google_search = @{} })
generationConfig = @{ temperature = 0.1 }
}
$payload = $payloadObject | ConvertTo-Json -Depth 10
$headers = @{ "Content-Type" = "application/json"; "x-goog-api-key" = $key }
try {
$result = Invoke-RestMethod -Uri "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent" -Headers $headers -Method Post -Body $payload -TimeoutSec 90
Write-Host "[OK] Google Search istegi basarili." -ForegroundColor Green
$result | ConvertTo-Json -Depth 12 | Out-String -Width 240
} catch { Write-Host "[HATA] Google Search istegi basarisiz: $($_.Exception.Message)" -ForegroundColor Red; exit 2 }