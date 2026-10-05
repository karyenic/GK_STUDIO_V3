@echo off
color 0A
echo GK STUDIO V3 - GitHub Repo Senkronizasyonu Basliyor...
echo.

:: Proje dizinine git
cd /d C:\AI_YEREL\GK_STUDIO_V3

:: Eger klasorde eski bir git gecmisi varsa tamamen sil (Sifirdan temiz bir baslangic icin)
if exist .git (
    echo Eski yerel Git gecmisi temizleniyor...
    rd /s /q .git
)

:: Git'i yeniden baslat
echo Yeni Git reposu baslatiliyor...
git init

:: Tum dosyalari ekle (.gitignore'da olanlar haric)
echo Dosyalar ekleniyor...
git add .

:: Ilk commiti at
echo Commit olusturuluyor...
git commit -m "GK STUDIO V3 - Master Devir ve Temiz Kurulum"

:: Branch adini main olarak ayarla
git branch -M main

:: Uzak repoyu (GitHub) ekle
git remote add origin https://github.com/karyenic/GK_STUDIO_V3.git

:: GitHub'daki her seyi EZIP yereldeki klasoru ORAYA YAZ (Force Push)
echo.
echo GitHub'a yollaniyor... (Bu islem repodaki eski verileri tamamen silecektir)
git push -u origin main --force

echo.
echo Islem basariyla tamamlandi! Yeni yapi https://github.com/karyenic/GK_STUDIO_V3 adresine yuklendi.
pause