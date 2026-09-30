# GFS toplu altküme planı

1 Ekim 2026. Tek dosyalı THREDDS aktarımının sınırlı paralel denemesinde 21 yeni istek başlatıldı; yalnızca iki yeni dosya doğrulanabildi. Diğer denemelerin çoğu zaman aşımı veya HTTP 503 ile sonuçlandı. Dört eşzamanlı istek bile kamu sunucusunda tam arşiv için yeterli ve istikrarlı bir aktarım sağlamadı. Paralel kod doğrulama ve küçük kurtarma işleri için korunuyor; 33.424 dosyayı bu yöntemle zorlamaya devam etmek ana plan değil.

NCAR'ın resmî GDEX API'si `d084001` için sunucu tarafında altküme üretimini destekliyor. Genel API'den kontrol dosyası şablonu ve metadata okundu. Beş alanın — sıcaklık, bağıl nem, u/v rüzgârı ve jeopotansiyel yükseklik — 925/850 hPa ile +6/+9/+12/+15 saat ürünlerinde bulunduğu doğrulandı. Kaynaklar: [GDEX veri erişimi](https://gdex.ucar.edu/datasets/d084001/dataaccess/), [resmî API istemcisi](https://github.com/NCAR/gdex-api-client) ve [API belgeleri](https://github.com/NCAR/gdex-api-client/blob/main/docs/README.md).

`python -m ltfj.gdex_batch prepare` yedi kontrol isteği üretir: 2020 son koşusu ve 2021–2026 için yıllık parçalar. Her istek yalnızca 41°N, 29,25°E hücresini, gerekli iki seviyeyi, beş alanı ve dört tahmin saatini ister. Böylece on binlerce istemci tarafı sorgu yerine NCAR'ın sunucuda hazırladığı birkaç küçük çıktı hedeflenir. [Makine tarafından okunabilir plan](gdex-batch-plan.json).

## Kimlik doğrulama sınırı

GDEX, altküme isteği göndermek, durumunu okumak ve çıktı listesini almak için bearer token zorunlu tutuyor. Bu çalışma ortamında `GDEX_TOKEN` tanımlı değil; bu nedenle yedi istek **hazırlandı ama gönderilmedi**. Token ücretsiz GDEX hesabının kullanıcı profilinden alınır. Kod tokenı yalnızca ortam değişkeninden okur; URL, rapor, `.env.example`, Git veya çıktı mesajlarına yazmaz. `.env` dosyaları Git tarafından yok sayılır.

Token ortamda tanımlandıktan sonra akış:

```sh
python -m ltfj.gdex_batch submit
python -m ltfj.gdex_batch status
python -m ltfj.gdex_batch fetch
```

`submit` her isteğin kimliğini hemen yerel ve Git dışında kalan `data/raw/gdex-batch/requests.json` dosyasına kaydeder; tekrar çalıştırma aynı yılı yeniden göndermez. `status` işleme durumunu yeniler. `fetch` yalnızca sunucunun tamamladığı dosyaları indirir ve kaynak URL/özet bilgisini saklar.

Toplu çıktı geldiğinde doğrudan eğitime alınmayacak. Değişken, birim, basınç seviyesi, koşu ve geçerlilik zamanı kontrolleri toplu dosya biçimine uyarlanacak; ardından [eğitim kapsam kapısı](gfs-training-readiness.json) tekrar çalıştırılacak. Şu an tek dosyalı önbellekte 33.424 gerekli dosyanın 32'si var ve 2021 uygun zaman kapsamı yaklaşık %0,20; diğer yıllar %0. Model eğitimi için hazır değil.
