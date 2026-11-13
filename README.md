# Amazon.in PlayStation Gift Card – kendi stok botumuz

Takip ettiği iki ürün:
- https://www.amazon.in/dp/B093QF35KZ
- https://www.amazon.in/dp/B0C1H473H8

## Dürüst durum bilgisi

Bu bot Google Apps Script'ten **farklı** olarak GitHub Actions içinde **Chromium/Playwright** ile ürünü açmayı dener. **CAPTCHA çözmez, proxy döndürmez veya Amazon'un engellerini aşmayı garanti etmez.** İlk `diagnose` testinde ürün başlığı gerçekten okunmadan izleme sistemine güvenme. Amazon ürün sayfası CAPTCHA döndürürse e-posta ile stok bildirimi gönderilmez.

## Kurulum (GitHub)

1. https://github.com/new üzerinden `psn-stock-bot` isimli **Public** repository aç. Standard GitHub-hosted Actions public repository için ücretsizdir. Repo Issues özelliği açık olsun.
2. Bu ZIP'i aç. İçindeki `monitor.py`, `requirements.txt`, `README.md`, `tests` ve **gizli `.github` klasörünün tamamını** repo köküne yükle. `.github/workflows/monitor.yml` doğru yerde bulunmalı.
3. Repo → `Settings` → `Secrets and variables` → `Actions` → `New repository secret` ile aşağıdakileri ekle:

   **Gmail seçeneği** (kodu indiren kişi Gmail şifresini kodun içine **ASLA** yazmamalı):
   - `SMTP_USER`: E-posta gönderecek Gmail hesabın.
   - `SMTP_APP_PASSWORD`: O hesabın 2 adımlı doğrulama açıkken https://myaccount.google.com/apppasswords adresinden oluşturulan **uygulama şifresi**, normal Gmail şifren değil.
   - `ALERT_EMAIL`: `osadik1995@gmail.com`

   **İsteğe bağlı Telegram** (Gmail yerine veya yanında kullanılabilir):
   - `TELEGRAM_BOT_TOKEN`: BotFather bot tokenı.
   - `TELEGRAM_CHAT_ID`: Mesajları alacak chat ID.

   Bir bildirim kanalı yeterli. Güvenlik için bu secret değerlerini asla paylaşma.

4. `Actions` → `PSN Amazon Stock Monitor` → `Run workflow` → **diagnose** → `Run workflow`. Çalışmanın loglarını aç. İki ASIN için `OUT_OF_STOCK`, `IN_STOCK` veya `POSSIBLE` çıkarsa gerçek ürün başlığını okumuş olabilir. İkisi de `BLOCKED` ise CAPTCHA devam ediyor ve bu altyapı **işe yaramıyor**; alternatif veri kaynağı gerekecek.
5. Ardından `Run workflow` → **test** ile bildirim e-postasını dene. Daha sonra `Run workflow` → **monitor** çalıştır.
6. **Sadece teşhis başarılıysa:** `Settings` → `Secrets and variables` → `Actions` → **Variables** → `New repository variable` bölümünde `BOT_ENABLED` = `true` oluştur. Bu adımı yapana kadar otomatik tarama çalışmaz. Otomatik zamanlama `7,17,27,37,47,57` dakikalarında çalışmak üzere tanımlıdır; GitHub yoğunlukta gecikebilir.

## Nasıl çalışır?

- Ürün başlığı doğrulanır. Amazon robot / CAPTCHA ekranı stok sinyali **sayılmaz**.
- `IN_STOCK`: Amazon'un availability kutusunda açık stok ifadesi.
- `POSSIBLE`: Ürün sayfası tanındı ve bir satın alma butonu göründü, **stok kesin değil**.
- `OUT_OF_STOCK`: Amazon stokta yok diyor.
- `BLOCKED` veya `UNKNOWN`: Güvenilir bilgi alınamadı. Üç ardışık başarısız kontrolde bir defa teşhis uyarısı gönderilir.
- Önceki bilinen durum `OUT_OF_STOCK` iken `IN_STOCK` / `POSSIBLE` görünürse bildirim gelir, aynı durum devam ettikçe spam olmaz.
- Durum `GitHub Issues` üzerinde `[psn-stock-bot-state]` başlıklı bir issue içinde kaydedilir (e-posta ve şifre **içermez**). **Bu issue'yu silmeyin veya elle düzenlemeyin.**

## Sınırlar

- 10 dakikada bir **planlanır**, dakika garantisi yoktur. GitHub bazı planlı çalışmaları geciktirebilir. Public repo 60 gün etkinlik olmazsa planlı iş otomatik kapatılabilir.
- Amazon.in GitHub IP adreslerini de engelleyebilir. Playwright normal bir tarayıcı motorudur; güvenilir bypass yöntemi değildir.
- Amazon India'da stok ve satın alma imkânı kullanıcı hesabı/konumuna ve hediye kartı özel şartlarına göre farklılaşabilir. Gelen e-posta bir **uyarıdır**, satın alma garantisi değildir.
- Bu bot otomatik satın alma yapmaz, giriş bilgisi istemez, CAPTCHA çözmez.

## Yerel test

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m unittest discover -s tests -v
python monitor.py --mode diagnose
```

## Resmi belgeler

- GitHub Actions: https://docs.github.com/en/actions
- Playwright: https://playwright.dev/python/docs/intro
- Google uygulama şifreleri: https://support.google.com/accounts/answer/185833
