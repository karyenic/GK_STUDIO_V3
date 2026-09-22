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

print("")
print("=== OTOMATIK KONTROLLER ===")
required = [
    "[1. ASAMA - GOOGLE SEARCH BULGULARI]",
    "[2. ASAMA - URL CONTEXT DERIN OKUMA]",
    "[KANIT DEFTERI]",
    "[TUTARLILIK KONTROLU]",
    "[WEB GUARD]",
]
for marker in required:
    print(f"{marker}: " + ("OK" if marker in result else "EKSIK"))

if "[KANIT DEFTERI]" in result:
    ledger_part = result.split("[KANIT DEFTERI]", 1)[1]
    ledger_part = ledger_part.split("[TUTARLILIK KONTROLU]", 1)[0]
    evidence_rows = [
        line for line in ledger_part.splitlines()
        if "|" in line and "https://" in line
    ]
    print("Doğrudan veri-kaynak satırı:", len(evidence_rows))
'@ | python -

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[HATA] WebResearchAgent calistirilemedi." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "TEST TAMAMLANDI." -ForegroundColor Green