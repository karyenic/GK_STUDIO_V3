# GK STUDIO V3 - Exact Web Research Agent Diagnostic
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
Write-Host ""
Write-Host "=== V3 WEB RESEARCH AGENT TEST ===" -ForegroundColor Cyan
Write-Host ""

@'
import json
from web_research import WebResearchAgent

prompt = "Türkiye otomobil satışlarında son 6 ayın toplam otomobil adetlerini araştır. Resmi kaynakları önceliklendir ve kaynak URLlerini belirt. Veri yoksa uydurma."
result = WebResearchAgent.research(prompt)
print(result)
'@ | python -

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[HATA] WebResearchAgent calistirilemedi." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "TEST TAMAMLANDI." -ForegroundColor Green