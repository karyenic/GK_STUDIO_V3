# GK Studio V3 - Vision Runtime Diagnostic
param(
    [Parameter(Mandatory=$false)]
    [string]$ImagePath = ""
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

$OllamaUrl = "http://127.0.0.1:11434"

Write-Host ""
Write-Host "=== V3 VISION RUNTIME DIAGNOSTIC ===" -ForegroundColor Cyan
Write-Host ""

function Get-OllamaJson {
    param(
        [string]$Url,
        [string]$Method = "GET",
        [object]$Body = $null
    )

    if ($Method -eq "GET") {
        return Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 15
    }

    $json = $Body | ConvertTo-Json -Depth 20 -Compress
    $params = @{
        Uri         = $Url
        Method      = "Post"
        ContentType = "application/json"
        Body        = $json
        TimeoutSec  = 300
    }
    return Invoke-RestMethod @params
}

Write-Host "[1/5] Ollama API kontrolü..." -ForegroundColor Yellow
try {
    $version = Get-OllamaJson "$OllamaUrl/api/version"
    Write-Host "[OK] Ollama version: $($version.version)"
} catch {
    Write-Host "[HATA] Ollama /api/version erişilemiyor: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[2/5] Yüklü modeller..." -ForegroundColor Yellow
$tags = Get-OllamaJson "$OllamaUrl/api/tags"
$modelNames = @($tags.models | ForEach-Object { [string]$_.name })

if (-not $modelNames.Count) {
    Write-Host "[HATA] 11434 üzerinde hiç model görünmüyor." -ForegroundColor Red
    exit 2
}

$modelNames | ForEach-Object { Write-Host " - $_" }

$qwen = $modelNames | Where-Object { $_ -match '^qwen2\.5vl(:7b)?$' } | Select-Object -First 1
$moon = $modelNames | Where-Object { $_ -match '^moondream(?::.*)?$' } | Select-Object -First 1

Write-Host ""
Write-Host "Qwen2.5-VL 7B: " -NoNewline
if ($qwen) { Write-Host "$qwen [BULUNDU]" -ForegroundColor Green }
else { Write-Host "BULUNAMADI" -ForegroundColor Red }

Write-Host "Moondream:     " -NoNewline
if ($moon) { Write-Host "$moon [BULUNDU]" -ForegroundColor Green }
else { Write-Host "BULUNAMADI" -ForegroundColor Red }

Write-Host ""
Write-Host "[3/5] Model capability bilgileri..." -ForegroundColor Yellow

foreach ($m in @($qwen, $moon)) {
    if (-not $m) { continue }

    try {
        $show = Get-OllamaJson "$OllamaUrl/api/show" "POST" @{ model = $m }
        Write-Host ""
        Write-Host "MODEL: $m"

        if ($show.capabilities) {
            Write-Host ("  capabilities: " + (($show.capabilities -join ", ")))
        } else {
            Write-Host "  capabilities: API çıktısında belirtilmedi"
        }

        if ($show.details) {
            if ($show.details.family) {
                Write-Host "  family: $($show.details.family)"
            }
            if ($show.details.parameter_size) {
                Write-Host "  params: $($show.details.parameter_size)"
            }
            if ($show.details.quantization_level) {
                Write-Host "  quant: $($show.details.quantization_level)"
            }
        }
    } catch {
        Write-Host "  [UYARI] /api/show başarısız: $($_.Exception.Message)" -ForegroundColor DarkYellow
    }
}

Write-Host ""
Write-Host "[4/5] Vision API doğrudan test..." -ForegroundColor Yellow

if (-not $ImagePath) {
    Write-Host "[ATLANDI] Görsel yolu verilmedi."
    Write-Host "Gerçek görsel testi için bu scripti bir PNG/JPG yolu ile tekrar çalıştır."
} elseif (-not (Test-Path -LiteralPath $ImagePath -PathType Leaf)) {
    Write-Host "[HATA] Görsel dosyası bulunamadı: $ImagePath" -ForegroundColor Red
    exit 3
} else {
    $resolved = (Resolve-Path -LiteralPath $ImagePath).Path
    $base64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($resolved))
    Write-Host "Görsel: $resolved"
    Write-Host "Base64 uzunluğu: $($base64.Length)"

    foreach ($m in @($qwen, $moon)) {
        if (-not $m) { continue }

        Write-Host ""
        Write-Host "TEST MODEL: $m" -ForegroundColor White

        try {
            $body = @{
                model = $m
                messages = @(
                    @{
                        role = "user"
                        content = "Bu görselde ne görüyorsun? Türkçe, kısa ve yalnızca görsel kanıtına dayanarak cevap ver."
                        images = @($base64)
                    }
                )
                stream = $false
                options = @{
                    num_ctx = 4096
                    temperature = 0.2
                }
            }

            $answer = Get-OllamaJson "$OllamaUrl/api/chat" "POST" $body

            if ($answer.message -and $answer.message.content) {
                Write-Host "[OK] $m görsel yanıtı verdi." -ForegroundColor Green
                Write-Host "----- YANIT -----"
                Write-Host $answer.message.content
                Write-Host "-----------------"
            } elseif ($answer.error) {
                Write-Host "[HATA] $m API hatası: $($answer.error)" -ForegroundColor Red
            } else {
                Write-Host "[UYARI] $m boş/alışılmadık yanıt döndürdü." -ForegroundColor DarkYellow
                $answer | ConvertTo-Json -Depth 20
            }
        } catch {
            Write-Host "[HATA] $m doğrudan vision testi başarısız: $($_.Exception.Message)" -ForegroundColor Red
        }
    }
}

Write-Host ""
Write-Host "[5/5] GK Studio Python vision yolunun kontrolü..." -ForegroundColor Yellow
python -c "import models, gateway; print('models.py model discovery:', models.get_installed_ollama_models()); print('qwen2.5vl profile:', __import__('config').VISION_CTX_PROFILE.get('qwen2.5vl'))"

if ($LASTEXITCODE -ne 0) {
    Write-Host "[HATA] Python tarafı derlenemedi." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "DIAGNOSTIC TAMAMLANDI." -ForegroundColor Green
