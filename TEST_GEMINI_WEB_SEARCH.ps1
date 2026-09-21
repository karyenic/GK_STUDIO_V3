# GK STUDIO V3 - Gemini Web Search Diagnostic
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$envFile = Join-Path $root ".env"
Write-Host ""
Write-Host "=== GK STUDIO V3 GEMINI WEB SEARCH TEST ===" -ForegroundColor Cyan
if (-not (Test-Path -LiteralPath $envFile)) { Write-Host "[HATA] .env dosyasi bulunamadi." -ForegroundColor Red; exit 1 }
$key = ""
foreach ($rawLine in (Get-Content -LiteralPath $envFile -Encoding UTF8)) {
    $line = ([string]$rawLine).Trim()
    if ($line.Length -eq 0 -or $line.StartsWith("#")) { continue }
    $parts = $line.Split("=", 2)
    if ($parts.Count -ne 2) { continue }
    if ($parts[0].Trim() -ne "GEMINI_API_KEY") { continue }
    $key = $parts[1].Trim()
    if ($key.StartsWith([char]34) -and $key.EndsWith([char]34)) { $key = $key.Substring(1, $key.Length - 2) }
    break
}
if ([string]::IsNullOrWhiteSpace($key)) { Write-Host "[HATA] GEMINI_API_KEY bulunamadi." -ForegroundColor Red; exit 1 }

Write-Host "[1/2] Gemini model erisimi..." -ForegroundColor Yellow
try {
    $models = Invoke-RestMethod -Uri "https://generativelanguage.googleapis.com/v1beta/models" -Headers @{ "x-goog-api-key" = $key } -Method Get -TimeoutSec 30
    $model = $models.models | Where-Object { $_.name -eq "models/gemini-2.5-flash" } | Select-Object -First 1
    if ($model) { Write-Host "[OK] gemini-2.5-flash gorunuyor." -ForegroundColor Green } else { Write-Host "[UYARI] gemini-2.5-flash listede yok." -ForegroundColor DarkYellow }
} catch { Write-Host "[HATA] Model testi basarisiz: $($_.Exception.Message)" -ForegroundColor Red; exit 2 }

Write-Host "[2/2] Gemini + Google Search grounding..." -ForegroundColor Yellow
$bodyObject = @{
    contents = @(
        @{
            parts = @(
                @{ text = "Guncel Turkiye otomobil satislari icin resmi bir kaynak bul. Kisa cevap ver ve kaynak URL belirt." }
            )
        }
    )
    tools = @(@{ google_search = @{} })
    generationConfig = @{ temperature = 0.1 }
}
$body = $bodyObject | ConvertTo-Json -Depth 10
try {
    $result = Invoke-RestMethod -Uri "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent" -Headers @{ "Content-Type" = "application/json"; "x-goog-api-key" = $key } -Method Post -Body $body -TimeoutSec 90
    Write-Host "[OK] Google Search istegi basarili." -ForegroundColor Green
    Write-Host ""
    Write-Host "Gemini cevabi:" -ForegroundColor Cyan
    $texts = @()
    foreach ($candidate in @($result.candidates)) {
        foreach ($part in @($candidate.content.parts)) {
            if ($part.text) { $texts += [string]$part.text }
        }
    }
    if ($texts.Count -gt 0) { Write-Host ($texts -join "") } else { Write-Host "[UYARI] Metin cevap yok." -ForegroundColor DarkYellow }
    Write-Host ""
    $g = $result.candidates[0].groundingMetadata
    if ($g) {
        Write-Host "Arama sorgulari: " + @($g.webSearchQueries).Count
        Write-Host "Kaynak chunk: " + @($g.groundingChunks).Count
        foreach ($q in @($g.webSearchQueries)) { Write-Host (" - SORGU: " + $q) }
        foreach ($c in @($g.groundingChunks)) { if ($c.web) { Write-Host (" - " + $c.web.title); Write-Host ("   " + $c.web.uri) } }
    } else { Write-Host "[UYARI] Grounding metadata yok." -ForegroundColor DarkYellow }
} catch {
    Write-Host "[HATA] Google Search istegi basarisiz: $($_.Exception.Message)" -ForegroundColor Red
    try {
        if ($_.Exception.Response) {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $server = $reader.ReadToEnd()
            if ($server) { Write-Host "Sunucu cevabi:" -ForegroundColor DarkYellow; Write-Host $server }
        }
    } catch {}
    exit 3
}
Write-Host ""
Write-Host "TEST TAMAMLANDI." -ForegroundColor Green