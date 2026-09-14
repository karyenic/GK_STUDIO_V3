# GK AI STUDYO V3 - CHECKPOINT MANIFESTI

Tarih: 2026-09-15 00:12:40
Yerel proje: C:\AI_YEREL\GK_STUDIO_V3
GitHub: https://github.com/karyenic/GK_STUDIO_V3

## 1. Bu checkpoint neden alindi?

Bu surum, mevcut yerel calisma durumunu degistirmeden dondurmek icin alinmistir.
Sonraki sohbet ve duzeltmeler bu checkpoint uzerinden ilerleyecektir.

## 2. MEVCUT KULLANICI GOZLEMLERI / ACIK SORUNLAR

### A) DUR butonu
- DUR butonu artik Gonder butonunun yaninda degil.
- Istendigi gibi alt araclar satirinda Ses butonunun yanina tasinmasi hedeflendi.
- Gonder butonu ayri ve mavi kalacak.
- DUR ayri ve kirmizi dikdortgen olacak.
- Ancak mevcut uygulamada DUR'a basildiginda modelin dusunmesi/uretimi gercek anlamda durmuyor.
- Bu nedenle sonraki asamada AbortController + SSE akisinin sunucu tarafindaki iptal davranisi birlikte incelenmelidir.
- Ozellikle istemcinin stream'i kesmesi ile model runner'in gercekten durmasi birbirinden ayrilmalidir.

### B) Klasor gonderme / proje RAG
- Modellere klasor gonderme islevi bazen calisiyor, bazen calismiyor.
- Sorunun yalnızca UI olmadigi varsayilmamalidir.
- Dosya secimi, FileReader/encoding, package olusturma, API payload, backend file_package ve RAG akisi ayri ayri kontrol edilmelidir.
- Mevcut calisan RAG kodu gereksiz yere ezilmemelidir.
- RAG'in bazi dosyalari okuyabildigi, bazilarinda bos/eksik icerik davranişi goruldugu daha once raporlanmistir.

### C) Turkce karakter / encoding
- Arayuzde Turkce karakterlerin bozuldugu gorulmustur.
- Ornekler: MODULER yerine MOD├£LER, LISTESI yerine L─░STES─░ gibi mojibake goruntusu.
- GitHub'daki temel index.html UTF-8 ve charset=UTF-8 olarak gorunmektedir.
- Bu nedenle sorun sadece HTML charset olmayabilir; yerel dosyanin yazilmasi/PowerShell encoding katmani da kontrol edilmelidir.
- Sonraki duzeltmede UTF-8 byte-safe dosya yazimi kullanilmalidir.

### D) Asistan mesaj eylemleri
Hedef:
- 📋 Kopyala
- 💾 Indir
- 🗑 Sil

Sil butonu Kopyala ve Indir ile ayni msg-action stilinde olmalidir.

### E) RAG proje butonlari
Hedef butonlar:
- Ac / Calistir
- Indeksle / Yenile
- Sil

Butonlar kullanici tarafindan daha rahat gorulecek kadar buyuk olmali; aktif/calisan durumda hafif animasyon veya pulse kullanilabilir.

## 3. BILINEN V3 MIMARISI

Ana proje klasoru:
C:\AI_YEREL\GK_STUDIO_V3

Ana arayuz:
static/index.html
static/js/main.js
static/js/ui.js
static/js/api.js
static/js/state.js
static/js/workspace.js

Backend/RAG katmani proje yapisina gore Python modullerindedir.

index.html module girisi:
<script type="module" src="/js/main.js"></script>

main.js temel olarak DOMContentLoaded sonrasinda UI.init() baslatir.

api.js bilinen servisler:
- getStatus
- getModels
- chat(payload, signal)
- listProjects
- addProject
- indexProject
- deleteProject
- saveConversations
- loadConversations
- shutdown

Not: V3 api.js icinde eski incelemeye gore /api/projects/activate endpointi yoktur. Sonraki duzeltmelerde var olmayan bir activate API uydurulmamalidir.

## 4. STATE / SOHBET YAPISI

State tarafinda bilinen alanlar:
- conversations
- currentId
- nextId
- currentImages
- currentFilePackage
- activeProjectPackageContent
- activeProjectName
- activeProjectPath
- activeProjectIndexed
- activeProjectChunkCount
- projectConvMap
- projectContextSentFor
- themeMode
- sidebarOpen

Proje sohbetlerinde projectName bulunabilir.

## 5. ESKI / CALISAN ES6 PROJESINDEN ALINABILECEK REFERANS FIKIRLER

AI_ES6_YEREL_STUDYO projesinde daha guclu olan fikirler:
- Proje config icinde persistent conversationId
- Projeyi yeniden acarken yeni sohbet yaratmak yerine ayni proje sohbetini tekrar kullanma
- Indeksli durumun ve package/RAG bilgisinin aktivasyonla geri yuklenmesi
- Proje sohbetinin history icinde taninmasi ve yeniden acilabilmesi
- Asistan mesajlarinda Kopyala / Indir / Sil eylemlerinin bulunmasi

Bu fikirler V3'e tasinabilir; ancak once mevcut V3 checkpoint korunmalidir.

## 6. SON DONEMDE YAPILAN UI DUZELTMELERI

Son UI duzeltmesinde hedefler:
- Gonder ve DUR'u ayirmak
- DUR'u Ses butonunun yanina almak
- RAG butonlarini buyutmek
- aktif calisan RAG butonuna hareket/pulse vermek
- assistant mesajina Sil eklemek
- stale isGenerating durumlarini temizlemek

Daha onceki hatali regex tabanli yamalar kullanilmamali.
Gercek local dosya icerigi gorulmeden yeni regex yamasi yazilmamali.

## 7. ONEMLI TEKNIK SORU: DUR GERCEKTE MODELI DURDURMUYOR

Su ayrim yapilmalidir:
1. Browser AbortController'in fetch/SSE akisina etkisi
2. Flask/FastAPI tarafinin istemci baglantisi kesildiginde ne yaptigi
3. Ollama/IPEX runner prosesinin inference'i gercekten sonlandirip sonlandirmadigi
4. Router'in arka planda baska bir modele gecip gecmedigi
5. UI'nin sadece 'durdu' gorunup arka planda modelin devam edip etmedigi

Sonraki sohbetin ilk teknik hedefi bu bes noktayi olcmek olmali.

## 8. IKINCI ANA SORU: KLASOR GONDERME NEDEN KARARSIZ?

Asagidaki zincir sirayla test edilmelidir:

Browser file picker
 -> folderInput
 -> FileList
 -> dosya okuma/encoding
 -> packageContent
 -> /api/chat payload
 -> backend file_package
 -> RAG/indexer veya gecici context
 -> model prompt

Bir halka bozuluyorsa butun zinciri RAG sorunu olarak etiketlememeliyiz.

## 9. ENCODING KURALI

Windows/PowerShell uzerinden JS/HTML/PY dosyasi yazarken UTF-8 byte-safe yontem kullanilmalidir.
Konsol kod sayfasi veya Set-Content varsayimlari Turkce karakterlerin bozulmasina sebep olmamalidir.
Yeni PowerShell scriptleri mumkun oldugunca ASCII-safe olmali ve dosyalari UTF-8 olarak dogrudan yazmalidir.

## 10. GUVENLI CALISMA KURALI

- Her yeni duzeltmeden once checkpoint/backup alinacak.
- RAG calisiyor diye RAG backend'i gereksiz yere degistirilmeyecek.
- Gercek local dosya kontrol edilmeden fonksiyon adi varsayilmadan regex patch yapilmayacak.
- Kullaniciya parca parca kod verilmeyecek; tam PS1 veya tam dosya verilecek.
- Her asamada calisan durum korunacak.

## 11. YENI SOHBET ICIN BASLANGIC GOREVI

Once bu manifesti ve checkpoint branch'ini referans al.

Ilk hedef: DUR butonunun UI degil, GERCEK inference durdurma davranisini kanitlamak.
Ikinci hedef: klasor gonderme zincirinin hangi halkada koptugunu tek komutluk/tek testlik diagnostik ile bulmak.
Ucuncu hedef: Turkce encoding'i kalici olarak duzeltmek.

Bunlar tamamlanmadan yeni ozellik eklememek.

## 12. DONANIM / CALISMA BAGLAMI

Bilinen sistem:
- Intel Core Ultra 9 288V
- Intel Arc 140V 16 GB
- IPEX/Ollama portable yolu: C:\AI_IPEX\Ollama\portable
- normal Ollama: C:\Users\karye\AppData\Local\Programs\Ollama\ollama.exe
- Qwen coder 7B icin 29/29 GPU offload daha once dogrulanmistir.
- Bu inference altyapisinin su anki sorunu olarak gosterilmemelidir; DUR sorunu ayri test edilmelidir.

## 13. CHECKPOINT BILGISI

Onceki branch : main
Onceki HEAD   : f4d99f6efef50db1ec7af728d8b23a330c8a48a7
Yeni branch   : checkpoint/20260915_001236-v3-ui-rag
Yeni tag      : v3-checkpoint-20260915_001236

Bu dosya checkpoint commit'ine dahil edilecektir.

## 14. NOT

Bu manifest mevcut gorunen durumun calisma notudur. Gelecek sohbette yeni bulgular elde edildikce guncellenebilir; ancak bu checkpoint sonrasindaki degisiklikler ayri commitlerde tutulmalidir.