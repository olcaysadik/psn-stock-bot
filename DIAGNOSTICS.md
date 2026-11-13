# Gerçek doğrulama kaydı — 13 Kasım 2026

**Güncel durum: zamanlama açık, Gmail testi teslim edildi, iki bağımsız gerçek monitor çalışması başarılı.** Son üç bağımsız teşhis runner'ında 36/36 ürün kontrolü başarılı. İki gerçek monitor runner'ında üç ürün de stokta yok olarak okundu; aynı kalıcı geçmiş yüklenip güncellendi. Gerçek stok-var sayfası görülmediğinden stok geçiş e-postası örneklerle; SMTP teslimi ise gerçek test e-postasıyla doğrulandı. İlk `schedule` tetiklemesi 20:05 Europe/Berlin itibarıyla henüz gözlenmedi; gerçek monitor çalışmaları elle tetiklendi.

## Etkinleştirme ve ilk gerçek monitor çalışması

- Kullanıcı Google uygulama şifresini düzeltti. Gmail testi ikinci denemede başarılı: https://github.com/olcaysadik/psn-stock-bot/actions/runs/43485742946
- Gmail sunucusu 19:52 Europe/Berlin (18:52 UTC) civarında TLS port 465 üzerinden mesajı kabul etti. Kullanıcı `PSN STOCK BOT - Gmail test` mesajını teslim aldığını doğruladı. Alternatif port kullanılmasına gerek kalmadı.
- `BOT_ENABLED=true` repository variable'ı yaklaşık 19:53 Europe/Berlin'de kaydedildi. Otomatik cron `*/10 * * * *`; GitHub gecikmeleri olabilir.
- İlk gerçek monitor: https://github.com/olcaysadik/psn-stock-bot/actions/runs/43487201153 — başarılı.
- Kalıcı geçmiş: https://github.com/olcaysadik/psn-stock-bot/issues/1 — üç ASIN için `last_confirmed=OUT_OF_STOCK`, `notification=armed`, `failures=0` kaydedildi.
- İlk monitor artifact: https://github.com/olcaysadik/psn-stock-bot/actions/runs/43487201153/artifacts/14067836950
- Bu kontrolde stok yok olduğundan stok e-postası gönderilmedi.
- Aynı monitor run'ı ikinci bağımsız runner'da tekrar çalıştırıldı ve başarılı oldu. Issue #1 yeniden kullanıldı; üç ürünün kontrol zamanı 19:56'dan 20:02–20:03 Europe/Berlin'e güncellendi. Üçünde de `OUT_OF_STOCK`, `armed`, `failures=0` korundu; yeni state issue'su oluşturulmadı.
- İkinci monitor artifact: https://github.com/olcaysadik/psn-stock-bot/actions/runs/43487201153/artifacts/14067349927
- Workflow'un açık olduğu GitHub arayüzündeki `Disable workflow` seçeneğiyle doğrulandı. `BOT_ENABLED=true` kaydedildi; cron `*/10 * * * *` yapılandırması geçerli. Ancak 20:00 takviminin `schedule` olayı 20:05 itibarıyla run listesinde henüz görünmedi. Bu nedenle ilk otomatik tetiklemenin çalıştığı iddia edilmez; GitHub'ın belgelenmiş zamanlama gecikmeleri geçerlidir.

## Gmail kurulumunda düzeltilen hatalar

- Secret'lar eklendikten sonra eski testin ikinci denemesi `SMTPServerDisconnected` hatasıyla durdu. Kullanıcı test e-postasının ulaşmadığını doğruladı; gelen GitHub başarısız-workflow bildirimi botun test e-postası değildir.
- Güvenli SMTP aşama teşhisi, Google uygulama şifresi biçim kontrolü ve yalnızca gönderim başlamadan TLS 587 alternatifi eklendi: https://github.com/olcaysadik/psn-stock-bot/commit/07a7a86b603b676d9a0f84e2353c7624376dd182
- Yeni kodla ilk Gmail denemesi: https://github.com/olcaysadik/psn-stock-bot/actions/runs/43485742946
- İlk denemedeki hata: `SMTP_APP_PASSWORD must be a 16-character Google app password (spaces are ignored)`.
- Biçimi geçersiz olan ilk deneme SMTP'ye bağlanmadı ve e-posta göndermedi. Kullanıcı secret'ı düzelttikten sonra ikinci deneme başarılı oldu. Secret değerleri okunmadı veya loglanmadı.
- Son kodda GitHub üzerinde 34 birim testi ve 8 Chromium testi başarılı (toplam 42).
- Yeni gerçek Amazon teşhisi de 12/12 başarılı: https://github.com/olcaysadik/psn-stock-bot/actions/runs/43485665089
- Artifact: https://github.com/olcaysadik/psn-stock-bot/actions/runs/43485665089/artifacts/14067427581

## Son sürümün gerçek doğrulaması

- Kod commit'i: https://github.com/olcaysadik/psn-stock-bot/commit/97c50020b054a79a1597938c16a1d27bf7027fe4
- Son workflow ve iki bağımsız denemesi: https://github.com/olcaysadik/psn-stock-bot/actions/runs/43478951226
- Deneme 1 artifact: https://github.com/olcaysadik/psn-stock-bot/actions/runs/43478951226/artifacts/14064865589
- Deneme 2 artifact: https://github.com/olcaysadik/psn-stock-bot/actions/runs/43478951226/artifacts/14064074208
- Gerçek ürün kontrolleri yaklaşık 19:05–19:10 Europe/Berlin (18:05–18:10 UTC) arasında yapıldı.

| ASIN | Deneme 1 | Deneme 2 | Gerçek sonuç | HTTP | Ürün kimliği | Görsel CAPTCHA |
|---|---|---|---|---|---|---|
| B07K6RYVHR | 4/4 | 4/4 | OUT_OF_STOCK | 200 | Doğru | Yok |
| B093QF35KZ | 4/4 | 4/4 | OUT_OF_STOCK | 200 | Doğru | Yok |
| B0C1H473H8 | 4/4 | 4/4 | OUT_OF_STOCK | 200 | Doğru | Yok |

Normal devam düğmesi çoğu istekte Amazon ana sayfasını açtı. Aynı anonim oturumda hedef ürün URL'si bir kez yeniden açılınca gerçek ürün başlığı, tam ASIN ve açık `Currently unavailable` alanları okundu. Son sürümde ilk denemenin 12/12, ikinci denemenin 9/12 isteği bu normal gezinme yolunu kullandı; diğerleri doğrudan ürün sayfasıydı. Kısa ve özgün başlıklı URL'ler iki denemenin ikişer turunda da aynı doğrulanmış sonucu verdi.

Bu, gözlenen ara ekran sorunu için gerçek bir iyileşmedir; görsel CAPTCHA çözülmedi, oturum/cookie dosyası kaydedilmedi, proxy veya ücretli servis kullanılmadı. Gelecekte farklı engel gelirse güvenilir stok tahmin edilmez; `BLOCKED`/`UNKNOWN` olarak kalır. Süresiz erişim garantisi verilmez. Gerçek IN_STOCK sayfası bu oturumda görülmedi; olumlu stok sınıflandırması örnek sayfalarla test edildi.

## Bağımsız tekrar testleri

- Run #7: https://github.com/olcaysadik/psn-stock-bot/actions/runs/43476793358 — 12 isteğin 10'u doğrulama ara ekranı, 2'si gerçek stok yok sayfası. Üç ASIN'in tamamı için tutarlılık testi başarısız (`BLOCKED`).
- Run #8: https://github.com/olcaysadik/psn-stock-bot/actions/runs/43476960724 — 12/12 istek ara ekran. Hiçbir stok bilgisi doğrulanamadı.
- Run #9: https://github.com/olcaysadik/psn-stock-bot/actions/runs/43477943799 — normal devam düğmesi 11 istekte denendi, Amazon ana sayfasına gidildi; bu sayfalar doğru biçimde UNKNOWN kaldı. Sadece bir B093QF35KZ isteği doğrudan gerçek stok yok sayfasına ulaştı. Bu yüzden devam düğmesinden sonra aynı anonim oturumda hedef ürünü bir kez yeniden açma düzeltmesi eklendi. Üç ürün için tutarlı stok bilgisi bu çalışmada da doğrulanmadı.
- Run #7 artifact: https://github.com/olcaysadik/psn-stock-bot/actions/runs/43476793358/artifacts/14062937468

Ekran görüntüsü, başlık `Amazon.in`, ürün başlığı yok ve `Click the button below to continue shopping` mesajını gösterir. Bu, ürün stok bilgisi değildir. Bu ekran tek başına görsel CAPTCHA kanıtı da değildir; önceki sürüm bunu ortak CAPTCHA/verification bayrağında raporluyordu. Yeni sürüm normal ara ekranı ayrı kaydeder, gerçek CAPTCHA alanı/görseli varsa müdahale etmez. IP itibarı, oturum ve bölge etkileri bu örneklerden tek başına kesin ayrıştırılamaz; sorun gerçek sayfa doğrulamasının yanlış reddi değildir çünkü dönen ekran ürün sayfası değildir.

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
- İlk doğrulanmış sürümde yerelde 36 test geçti; 8'i Chromium'da çevrimdışı HTML testidir. SMTP düzeltmesinden sonra yerelde 34 birim testi geçti; 8 Chromium testi GitHub'da çalıştırıldı.
- Son GitHub sürümünde 34 birim testi ve 8 Chromium testi geçti. Bu örnek testler ayrıca yapılan gerçek Amazon erişim teşhislerinin yerine geçmez.
- YAML ayrıştırması ve yapı testleri geçti; yerelde actionlint 1.7.12 hata vermedi.
- Kalıcı geçmişin yeniden yüklenmesi, UNKNOWN/BLOCKED sonrası tekrar bildirim olmaması, doğrulanmış stok yok→stok var geçişi, SMTP belirsizliği ve gönderim sonrası kayıt hatası örneklerle test edildi. Gerçek SMTP test mesajı kullanıcı tarafından teslim alındı; gerçek monitor modunda kalıcı kayıt oluşturuldu. Gerçek IN_STOCK geçişi gözlenmediği için stok geçiş e-postası örneklerle sınandı.
- Gmail test modu GitHub'da gerçekten çalıştırıldı: https://github.com/olcaysadik/psn-stock-bot/actions/runs/43476159047
- İlk deneme `Missing GitHub Actions secrets: SMTP_USER, SMTP_APP_PASSWORD` ile durmuştu; sonradan secret'lar eklendi ve uygulama şifresi düzeltildi. Güncel Gmail testi başarılıdır.
- `ALERT_EMAIL`, `SMTP_USER` ve `SMTP_APP_PASSWORD` secret'ları mevcuttur; değerleri rapora yazılmaz.
- `BOT_ENABLED=true`; otomatik izleme **açık**. Gerçek Amazon teşhisleri ve Gmail teslimi doğrulandıktan sonra etkinleştirildi.

## Kullanıcının yapması gerekenler

Kurulum için ek manuel işlem gerekmiyor. State issue'sunu silmeyin/düzenlemeyin. Gmail hesap şifresi değişirse Google uygulama şifresini iptal edebilir; yeni uygulama şifresiyle secret'ı güncelleyin. Public depolarda 60 günlük hareketsizlik sonrası GitHub zamanlamayı devre dışı bırakabilir; böyle bir durumda yeniden etkinleştirin. Zamanlama gecikmeleri ve kesintisiz erişim garantisi olmaması README'de açıklanmıştır.

Resmi API ve ücretsiz kaynak araştırmasının sonucu README'dedir: Creators API uygunluk/kimlik bilgisi ister; Keepa API aboneliklidir. Bu üç ASIN için ücretsiz, 10 dakikalık güncel ve doğrulanmış alternatif stok akışı bulunmadığından fiyat geçmişi stok kaynağı olarak kullanılmadı.
