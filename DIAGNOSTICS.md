# Gerçek doğrulama kaydı — 13 Kasım 2026

## İlk onarım ve canlı bulut testi

- Depo: https://github.com/olcaysadik/psn-stock-bot
- İlk onarım commit'i: https://github.com/olcaysadik/psn-stock-bot/commit/f1474fd9e7c530287fa6af4d8c095d4b05751dfd
- Gerçek Ubuntu GitHub Actions teşhisi: https://github.com/olcaysadik/psn-stock-bot/actions/runs/43475632573
- Ekran görüntüleri ve JSON raporu: https://github.com/olcaysadik/psn-stock-bot/actions/runs/43475632573/artifacts/14063211841
- Amazon kontrolleri 18:45–18:46 Europe/Berlin (17:45–17:46 UTC) civarında yapıldı.

| ASIN | Okunan gerçek ürün | Deneme | HTTP | Ürün kimliği | Stok | CAPTCHA |
|---|---|---|---|---|---|---|
| B07K6RYVHR | Rs.1000 Sony PlayStation Store Gift Card (Email Delivery in 1 hour- Digital Voucher Code) | 4/4 | 200 | Doğru | OUT_OF_STOCK | Yok |
| B093QF35KZ | Rs.2000 Sony PlayStation Store Gift Card (Email Delivery in 1 hour- Digital Voucher Code) | 4/4 | 200 | Doğru | OUT_OF_STOCK | Yok |
| B0C1H473H8 | Playstation / E-Gift Card / Instant Delivery / Valid for in-game purchases | 4/4 | 200 | Doğru | OUT_OF_STOCK | Yok |

Her ürün kısa `/dp/ASIN` ve özgün başlıklı URL ile iki bağımsız turda kontrol edildi. Son URL'ler beklenen ürün yollarında kaldı; kısa ve uzun URL arasında bu testte stok/erişim farkı bulunmadı. Ürün alanlarında açık `Currently unavailable` mesajı vardı ve etkin satın alma kontrolü yoktu. Artifact içindeki 12 PNG ve `report.json` bu bulguları gösterir. Aynı sonuçlar yerel Chromium testinde de 12/12 görüldü.

**Bu sonuç, şu testlerde gerçek stok yok bilgisinin okunabildiğini kanıtlar. CAPTCHA'nın kalıcı olarak çözüldüğü veya gelecekte engel olmayacağı iddia edilmez. Gerçek IN_STOCK sayfası bu oturumda görülmedi; olumlu durum ve e-posta geçişleri örnek sayfalarla test edildi.**

## Önceki hataların nedeni

- Run #3 (`43472470411`): `monitor.py` ilk satırına YAML yapıştırılmış, `SyntaxError: invalid syntax`.
- Run #4 (`43472912503`): Python dosyası `try` bloğunun ortasında bitmiş, satır 96'da `SyntaxError: expected 'except' or 'finally' block`.
- Eski yeşil run #1 (`43470009447`): B093QF35KZ için HTTP 200, başlık `Amazon.in`, ürün başlığı yok; B0C1H473H8 için gerçek başlık ve stok yok bilgisi var. Eski kod teşhis başarısızlığını exit code'a yansıtmıyordu.
- Eski UNKNOWN yanıtlarının ekran görüntüsü/HTML kanıtı olmadığı için CAPTCHA, genel Amazon ara sayfası ve geçici erişim sorunu arasında kesin ayrım yapılamaz. Mevcut canlı sonuçlar, bu üç gerçek ürünün yeni kimlik doğrulamasından geçebildiğini gösterir. HTTP 200 tek başına artık yeterli değildir.

E-hediye kartında ayrıca alıcı e-postası/mesaj alanları ve `gc-order-form-asin`, `gc-order-form-type`, `submit.gc-buy-now` form alanları görüldü. Gizli form alanı veya boş tutar/özelleştirme formu stok kanıtı sayılmaz. Görünür etkin satın alma kontrolü ile açık stok ifadesi birlikte gerekir. Anonim Amazon sayfası Mumbai varsayılan teslimat konumunu gösterebilir; kişisel hesap/teslimat uygunluğu farklı olabilir.

## Test ve kurulum durumu

- Python 3.12 sözdizimi, bağımlılık kurulumu ve `pip check` başarılı.
- Yerelde ilk sürümde 32 test geçti; son güvenlik düzeltmesiyle 33 test geçti (6'sı gerçek Chromium'da çevrimdışı HTML testidir).
- İlk GitHub run'ında 26 birim testi ve ayrıca 6 Chromium testi geçti; gerçek teşhis de geçti.
- YAML ayrıştırması ve yapı testleri geçti; yerelde actionlint 1.7.12 hata vermedi.
- Kalıcı geçmişin yeniden yüklenmesi, UNKNOWN/BLOCKED sonrası tekrar bildirim olmaması, doğrulanmış stok yok→stok var geçişi, SMTP belirsizliği ve gönderim sonrası kayıt hatası örneklerle test edildi. Canlı SMTP olmadan uçtan uca gerçek stok e-postası ve gerçek monitor geçmiş döngüsü tamamlanmış sayılmaz.
- Gmail test modu GitHub'da gerçekten çalıştırıldı: https://github.com/olcaysadik/psn-stock-bot/actions/runs/43476159047
- Bu test `Missing GitHub Actions secrets: SMTP_USER, SMTP_APP_PASSWORD` ile durdu; SMTP sunucusuna gerçek gönderim yapılmadı.
- `ALERT_EMAIL` alıcısı repo secret'ına eklendi. İki eksik secret kullanıcının kendi Gmail hesabı/uygulama şifresi gerektirir.
- `BOT_ENABLED` değişkeni yok; otomatik izleme **kapalı**. Gmail testi başarılı olmadan etkinleştirilmedi.

## Kalan minimum işlem

1. Repo Actions secret'larına `SMTP_USER` ve o hesabın `SMTP_APP_PASSWORD` değerini ekleyin. Şifreyi sohbet veya depoya düz metin olarak yazmayın.
2. Workflow'u `test` modunda çalıştırıp test e-postasını alın.
3. Yeniden `diagnose` çalıştırın; üç ürün de doğrulanmışsa `BOT_ENABLED=true` repository variable'ını ekleyin ve `monitor` çalıştırın. Bundan sonra yaklaşık 10 dakikada bir bulutta çalışır.

Resmi API ve ücretsiz kaynak araştırmasının sonucu README'dedir: Creators API uygunluk/kimlik bilgisi ister; Keepa API aboneliklidir. Bu üç ASIN için ücretsiz, 10 dakikalık güncel ve doğrulanmış alternatif stok akışı bulunmadığından fiyat geçmişi stok kaynağı olarak kullanılmadı.
