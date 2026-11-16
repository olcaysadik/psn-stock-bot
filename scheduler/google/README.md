# Bağımsız 5 dakikalık zamanlayıcı

Google Apps Script → GitHub workflow API → mevcut Python/Chromium stok kontrolü → Gmail.

Google yalnızca sabit GitHub HTTPS adresine kimlik doğrulamalı bir `monitor` isteği gönderir. Amazon erişimi, stok kararı, kalıcı Issue geçmişi ve e-posta mevcut workflow'da çalışır. Bilgisayarın açık olması gerekmez. Google zamanlayıcısı da küçük zaman sapmaları gösterebilir.

## Kurulum

1. Kullanıcı hesabında paylaşılmayan bir `PSN GitHub Scheduler` Apps Script projesi oluşturun. `Code.gs` içeriğini kod dosyasına, `appsscript.json` içeriğini manifeste koyun.
2. GitHub'da yalnızca `olcaysadik/psn-stock-bot` seçili fine-grained token oluşturun. Gerekli yazma izni **Repository permissions → Actions → Read and write**; zorunlu Metadata izni read-only kalır. Contents veya hesap yönetimi yazma izni gerekmez.
3. Token'ı yalnızca özel Google projesinin **Script Properties** bölümüne `GITHUB_DISPATCH_TOKEN` adıyla kaydedin. Kaynak koda, bu depoya, issue'ya, sohbete veya loga koymayın. Anahtarı kullanıcı oluşturup girer.
4. `installPsnScheduler` işlevini bir kez çalıştırıp Google izinlerini kullanıcı hesabından onaylayın. Manifest dış HTTPS istekleri ve bu projenin zamanlayıcılarını yönetme izinlerini ister. Gmail/Drive dosyalarını okuma izni istemez.
5. Kurulum önce gerçek GitHub isteğini sınar; kabul edilmezse tekrarlayan tetikleyici oluşturmaz. Başarıdan sonra tek `dispatchPsnMonitor` clock tetikleyicisi 5 dakikada bir çalışır. Yeniden kurulum mevcut tetikleyiciyi kullanır. Mevcut bir tetikleyicinin aralığını değiştirmek için Google Tetikleyiciler ekranında Düzenle → Dakika aralığı → 5 dakikada bir → Kaydet kullanılır; yalnızca kaynak kodunu kaydetmek eski tetikleyiciyi değiştirmez.
6. **Yürütmeler → Zaman tabanlı** kaydını, `source=time_trigger` logunu, onun GitHub run kimliğini ve başarılı stok/geçmiş güncellemesini doğrulayın. Elle yapılan kurulum testi tek başına otomasyon kanıtı değildir.

Bu kaynaktan gelen GitHub olayının adı `workflow_dispatch` olur. Google'daki `Zaman tabanlı` execution ve eşleşen run kimliği otomatik çalışmanın kanıtıdır. GitHub'ın kendi cron olayı `schedule` olarak görünür. İki kaynak aynı anda çalışırsa mevcut sabit concurrency grubu ve kalıcı bildirim geçmişi korunur.

## Bakım ve durdurma

- `psnSchedulerStatus`: Anahtarı göstermeden etkinlik, son tetikleme zamanı/kaynağı, run bağlantısı ve güvenli hata kodunu gösterir.
- `pausePsnScheduler`: Google'ın sonraki GitHub isteklerini durdurur.
- GitHub repository variable `BOT_ENABLED=false`: Gerçek monitor işlemlerini engeller.
- Anahtar süreli oluşturulur; sona ermeden aynı dar izinlerle yenilenip Google Script Properties'te güncellenmelidir. HTTP 401/403 veya Google tetikleyici hatalarını Yürütmeler ekranında kontrol edin.
- Projeyi paylaşmayın veya web uygulaması olarak yayımlamayın. Projeye düzenleme erişimi olan kişiler Script Properties'e de erişebilir.

İstekler TLS sertifikasını doğrular, yönlendirme takip etmez, 30 saniyeyle sınırlıdır. Token, ham sunucu yanıtı ve ağ hatası ayrıntıları loglanmaz. Belirsiz ağ hatası hemen tekrar gönderilmez. Google clock sonraki periyotta normal kontrolü sürdürür.

Yaklaşık 288 GitHub çağrısı/gün kullanılır. Google tüketici kotası 20.000 URL Fetch çağrısı ve 90 dakika toplam trigger süresi/gündür. GitHub public depoda standart Ubuntu runner kullanılır; ücretli servis veya API etkinleştirilmez.

## Yerel test

`node --test scheduler/google/test_scheduler.cjs`

Sekiz test; sabit endpoint/payload, TLS ve log güvenliği, gerçek clock olayının kaynak etiketi, durdurma, tek tetikleyici, başarısız yetkilendirmede kurmama, belirsiz ağ hatasında tekrar göndermeme ve eski HTTP 204 yanıtını kapsar. Gerçek Google/GitHub çalışması ayrıca doğrulanmalıdır.

## Resmi kaynaklar

- [Google installable triggers](https://developers.google.com/apps-script/guides/triggers/installable)
- [Google quotas](https://developers.google.com/apps-script/guides/services/quotas)
- [UrlFetchApp](https://developers.google.com/apps-script/reference/url-fetch/url-fetch-app)
- [GitHub workflow dispatch](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event)
