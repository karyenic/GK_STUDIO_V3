# C:\AI_YEREL\GK_STUDIO_V3\baslat.ps1
# -*- coding: utf-8 -*-
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Continue"
$Host.UI.RawUI.WindowTitle = "GK STUDIO V3 - Intel Arc 140V (Unified Console)"

Set-Location "C:\AI_YEREL\GK_STUDIO_V3"

Write-Host "============================================================" -ForegroundColor DarkMagenta
Write-Host " GK STUDIO V3 - INTEL ARC 140V (32GB VRAM / 32K CONTEXT)    " -ForegroundColor DarkMagenta
Write-Host "============================================================" -ForegroundColor DarkMagenta

# 1. Eski Süreçleri Temizle
Write-Host "[1/3] Eski süreçler ve portlar temizleniyor..." -ForegroundColor Cyan
Stop-Process -Name "ollama" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "ollama-lib" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# 2. Arka Plan Tarayıcı Açıcı
Write-Host "[2/3] Arayüz hazır olduğunda tarayıcı otomatik açılacak..." -ForegroundColor Green
$BrowserScript = {
    $ready = $false
    $retry = 0
    while (-not $ready -and $retry -lt 40) {
        try {
            $tcp = New-Object System.Net.Sockets.TcpClient
            $tcp.Connect("127.0.0.1", 5000)
            if ($tcp.Connected) {
                $ready = $true
                $tcp.Close()
            }
        } catch {
            Start-Sleep -Seconds 1
            $retry++
        }
    }
    if ($ready) { Start-Process "http://127.0.0.1:5000" }
}
Start-Job -ScriptBlock $BrowserScript | Out-Null

# 3. Orkestratör Başlat
Write-Host "[3/3] Modüler Orkestratör başlatılıyor..." -ForegroundColor Yellow
python orchestrator.py

Get-Job | Remove-Job -Force -ErrorAction SilentlyContinue
Read-Host "Süreç sonlandı. Pencereyi kapatmak için Enter'a basın..."