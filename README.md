# Amazon India PlayStation stok izleyicisi

Bu depo üç ürünü bağımsız kontrol eder. **Gerçek GitHub Actions teşhisi doğrulanmadan otomatik izlemeyi açmayın.** Kod testlerinin geçmesi Amazon'a erişilebildiği anlamına gelmez. Ücretli servis, proxy veya CAPTCHA çözücü kullanılmaz.

13 Kasım 2026 doğrulaması: son üç bağımsız GitHub runner denemesinde 36/36 gerçek ürün kontrolü başarılı, üç ürün de stokta yok. Secret'lar eklendi; son Gmail testi uygulama şifresi biçimi geçersiz olduğu için gönderimden önce durdu. Gmail testi tamamlanana kadar otomatik izleme kapalıdır. Kanıtlar [DIAGNOSTICS.md](DIAGNOSTICS.md) dosyasındadır.

| Ürün | ASIN | Doğrudan bağlantı |
|---|---|---|
| ₹1.000 Sony PlayStation Store Gift Card | B07K6RYVHR | https://www.amazon.in/dp/B07K6RYVHR |
| PlayStation Gift Card | B093QF35KZ | https://www.amazon.in/dp/B093QF35KZ |
| PlayStation E-Gift Card | B0C1H473H8 | https://www.amazon.in/dp/B0C1H473H8 |

E-postada Amazon'dan gerçekten okunan ürün başlığı kullanılır. İkinci/üçüncü ürünün tutarı canlı sayfadan doğrulanmadan tahmin edilmez.

## Çalıştırma

[Actions → PSN Amazon Stock Monitor](https://github.com/olcaysadik/psn-stock-bot/actions/workflows/monitor.yml) → **Run workflow**:

- `diagnose`: Her ASIN için kısa ve özgün URL'yi iki turda, ayrı anonim tarayıcı oturumlarında kontrol eder. Bildirim göndermez; stok geçmişini değiştirmez. Başlık, ASIN, HTTP, son URL, görünür stok alanları ve satın alma kontrollerini raporlar. `report.json`, `summary.md` ve 12 ekran görüntüsü artifact olarak yüklenir. Sorgu parametreleri, çerezler, tarayıcı profilleri ve ham HTML kaydedilmez.
- `test`: Yalnızca gerçek Gmail SMTP test e-postası gönderir. Stok kontrolü veya stok geçmişi değişikliği yapmaz. SMTP kabulü gelen kutusuna teslim garantisi değildir; spam klasörünü de kontrol edin.
- `monitor`: Canlı kontrolleri yapar, GitHub Issue geçmişini kullanır ve yalnızca doğrulanmış stok için e-posta gönderir. Bunun için `BOT_ENABLED=true` ve e-posta secret'ları gerekir. Yerel paralel monitor çalıştırmaları desteklenmez.

`main` dalındaki kod değişiklikleri otomatik olarak test ve **diagnose** çalıştırır; stok e-postası göndermez. Pull request'lerde yalnızca testler çalışır. Doğrulanamayan gerçek teşhis **exit code 2** ile başarısız görünür; bu, kurulum hatasından farklıdır. Artifact yüklemesi başarısız teşhiste de yapılır.

## Gmail bağlantısı

[Repository secrets](https://github.com/olcaysadik/psn-stock-bot/settings/secrets/actions) bölümüne ekleyin:

| Secret | Değer |
|---|---|
| `SMTP_USER` | Gönderen Gmail adresi |
| `SMTP_APP_PASSWORD` | Bu hesabın Google uygulama şifresi; normal hesap şifresi değil |
| `ALERT_EMAIL` | `osadik1995@gmail.com` |

Uygulama şifresini [Google hesabından](https://myaccount.google.com/apppasswords) oluşturun. [Google koşulları](https://support.google.com/accounts/answer/185833) geçerlidir; iki adımlı doğrulama gerekir, bazı hesaplarda seçenek bulunmayabilir. Şifreyi koda, issue'ya veya sohbete yazmayın. `test` modunu çalıştırın. Eksik secret adları hata mesajında gösterilir; değerleri gösterilmez.

Google uygulama şifresi 16 karakterdir; kopyalanan boşluklar otomatik ayıklanır. Biçim doğrulanmadan SMTP bağlantısı kurulmaz. Önce 465 üzerinde TLS kullanılır; mesaj gönderimi başlamadan bağlantı kesilirse 587 üzerinde zorunlu STARTTLS denenebilir. Kimlik doğrulama reddi veya mesaj gönderimi başladıktan sonraki bir hata otomatik tekrar gönderim üretmez. Teşhis yalnızca aşama, port, hata türü ve varsa sayısal SMTP kodunu kaydeder; sunucu yanıtı ve secret değerleri yazılmaz.

## Otomatik çalışma kapısı

Önce gerçek `diagnose` raporunda **üç ürünün tümünde**, kısa/özgün URL kontrollerinin iki turda da aynı doğrulanmış sonucu verdiğini görün. Farklı zamanlarda tekrar teşhis ederek erişimin devam ettiğini kontrol edin. `UNKNOWN` veya `BLOCKED` varsa izlemeyi etkinleştirmeyin.

Erişim doğrulandıktan ve Gmail testi teslim alındıktan sonra [Repository variables](https://github.com/olcaysadik/psn-stock-bot/settings/variables/actions) içinde **`BOT_ENABLED` = `true`** ayarlayın. Bu değer yokken veya `false` iken planlı işin tarayıcısı çalışmaz; elle `monitor` da engellenir. Durdurmak için değişkeni `false` yapın.

Cron: **`*/10 * * * *`**, yaklaşık 10 dakikada bir. Bilgisayarın açık olması gerekmez. [GitHub zamanlayıcısı](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule) gecikebilir veya yoğunlukta işleri düşürebilir; kesintisiz zaman garantisi vermez. Public depolarda 60 gün depo etkinliği olmazsa zamanlama kapatılabilir. Gerektiğinde GitHub'dan tekrar etkinleştirin.

Standart Ubuntu runner ve public depo kullanılır. [GitHub Actions ücretlendirmesi](https://docs.github.com/en/billing/concepts/product-billing/github-actions) uyarınca public depolardaki standart runner kullanımı ücretsizdir. Artifact'lar yalnızca üç gün saklanır; ücretli/larger runner veya harici ücretli servis eklenmez. Depoyu private yapmak ücretsiz dakika bütçesini değiştirebilir.

## Stok kararının anlamı

- `IN_STOCK`: HTTPS Amazon.in ürün URL'si doğru ASIN'i gösterir, sayfanın ASIN alanı aynı üründür, PlayStation hediye/voucher/wallet başlığı vardır, görünür stok alanında açık olumlu ifade ve görünür **etkin** satın alma kontrolü birlikte vardır.
- `OUT_OF_STOCK`: Aynı kimlik doğrulamalarından geçen ürünün kendi görünür stok alanında açık stok yok ifadesi vardır. Genel sayfa metnindeki öneriler kullanılmaz.
- `BLOCKED`: CAPTCHA/doğrulama sayfası veya HTTP 403/429/503. HTTP 503 tek başına CAPTCHA kanıtı değildir.
- `UNKNOWN`: Kimlik doğrulanamadı, sayfa eksik, zaman aşımı, çelişkili sinyaller veya yeterli stok kanıtı yok. Yalnızca fiyat ya da satın alma düğmesi yeterli değildir.

E-hediye kartı formları ve `gc-` satın alma kontrolleri de incelenir; yalnızca tutar seçicisinin görünmesi stok kanıtı sayılmaz. Giriş gerektiren veya hesaba/konuma bağlı bir teklif doğrulanmış stok olarak tahmin edilmez. Bot satın alma yapmaz.

## Kalıcı geçmiş ve tekrar bildirimleri

İlk gerçek monitor çalışması `[psn-stock-bot-state] Otomatik durum kaydi` başlıklı bir GitHub Issue oluşturur. Son doğrulanmış durum, bildirim durumu, kontrol zamanları ve hata sayıları burada saklanır. Geçmiş için her kontrolde commit oluşturulmaz. **Bu issue'yu silmeyin veya elle değiştirmeyin.** Birden fazla/bozuk/eski biçimli kayıt varsa bot geçmişi sıfırlamak yerine durur.

Tüm workflow modları/dalları sabit `psn-stock-monitor` concurrency grubunda sırayla çalışır (`cancel-in-progress: false`). `UNKNOWN`/`BLOCKED` son doğrulanmış stok durumunu veya bildirim kilidini sıfırlamaz. İlk doğrulanmış stokta bir e-posta girişimi yapılır; yeni bir girişim ancak doğrulanmış `OUT_OF_STOCK` ve daha sonra `IN_STOCK` görülürse açılır.

E-posta girişimi önce kalıcı kayda `reserved` olarak yazılır. SMTP kabulünden sonra `sent` olur. Bağlantı koparsa `uncertain` olarak kalır; otomatik tekrar yapılmaz. Gönderimden hemen sonra runner çökerse de eski `reserved` kaydı tekrarı önler. **SMTP ve GitHub arasında atomik işlem olmadığından tam bir kez teslim garantisi mümkün değildir:** bu yaklaşım aynı stok dönemi için en fazla bir gönderim girişimini tercih eder; nadir hata durumunda bildirim kaçabilir. Bu durum issue ve Actions hatasında görünür. Sonraki doğrulanmış stok yok dönemi kilidi yeniden açar.

Bir ürünün sayfa veya SMTP hatası diğer ürünleri durdurmaz. Kalıcı geçmişe erişim/yazma hatası ise tekrar bildirim riskini önlemek için bütün e-posta işlemlerini durdurur. Erişim başarısızlıkları ayrıca stok e-postası üretmez; Actions özeti ve hata sayıları kontrol edilir.

## Testler

```powershell
python -m pip install -r requirements-dev.txt
python -m py_compile monitor.py
python -m unittest discover -s tests -v
python -m playwright install chromium
$env:RUN_BROWSER_TESTS='true'
python -m unittest discover -s tests -v
python monitor.py --mode diagnose
```

Sınıflandırma, CAPTCHA, ASIN/host kontrolü, yanlış pozitifler, stok geçişleri, yeniden başlayan runner, SMTP belirsizliği, yarım kalan kayıt ve issue kalıcılığı test edilir. Tarayıcı testleri Amazon'a gitmez; yerel HTML yanıtlarıyla gerçek Chromium'da görünür/etkin kontrolleri sınar. Bunlar gerçek Amazon erişim testi yerine geçmez.

## Amazon erişimi engellenirse

Normal `Continue shopping` ara ekranında yalnızca o düğme bir kez izlenir. Amazon ana sayfasına gidilirse aynı anonim oturumda hedef ürün bir kez yeniden açılır; ürün/ASIN/stok yeniden doğrulanır. Önceki ara ekranın görüntüsü ve geçiş bilgisi raporda saklanır. CAPTCHA alanı/görseli veya robot doğrulama metni varsa düğmeye basılmaz. Devam sayfası tekrar gelirse `BLOCKED` kalır; döngü, CAPTCHA çözümü veya gizleme tekniği kullanılmaz.

Önce Actions artifact ekran görüntülerini ve `report.json` içindeki denemeleri karşılaştırın. Yalnızca başlığın `Amazon.in` olması CAPTCHA kanıtı değildir; doğrulama metni/alanı ayrıca kaydedilir. Kısa URL'nin özgün URL'den daha iyi olduğu varsayılmaz. Tek bir başarılı sayfa, bütün ürünler için sürekli erişim anlamına gelmez.

Amazon'un güncel resmi [Creators API](https://affiliate-program.amazon.in/creatorsapi/docs/en-us/introduction) hizmeti ürün katalog erişimi sağlar. India Associates üyeliği, onay, API kaydı ve belgedeki satış uygunluğu şartları vardır (belgede son 30 günde en az 10 uygun satış belirtilir). Eski PA-API dokümanları yeni kullanıcıları Creators API'ye yönlendirir. Bu proje için herkese açık, kimlik bilgisi gerektirmeyen bir stok API'si doğrulanmamıştır; bu üç dijital ASIN'in API kapsamı da ayrıca test edilmelidir.

[Keepa API](https://keepa.com/api-docs/) abonelik ve API anahtarı ister; ücretsiz çözüm gibi sunulmaz. Kamuya açık fiyat geçmişi sayfaları bu ürünler için güncel, 10 dakikalık doğrulanmış Amazon stok akışı değildir. Arama sonuçlarından veya geçmiş fiyattan stok tahmini yapılmaz.

Bulut erişimi engelli kalırsa programı kapalı bırakın. Ürün sayfasında sunuluyorsa Amazon'un kendi stok bildirimi veya uygunluk varsa resmi API en pratik seçeneklerdir. Yerel tarayıcı alternatifi bilgisayar açıkken denenebilir fakat bilgisayar kapalı 24/7 hedefini karşılamaz. Mevcut ücretsiz bulut seçenekleriyle güvenilir veri doğrulanmadan sistem tamamlandı sayılmaz.
