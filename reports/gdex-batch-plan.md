# GFS toplu altküme planı

1 Ekim 2026. Tek dosyalı THREDDS aktarımının sınırlı paralel denemesinde 21 yeni istek başlatıldı; yalnızca iki yeni dosya doğrulanabildi. Diğer denemelerin çoğu zaman aşımı veya HTTP 503 ile sonuçlandı. Dört eşzamanlı istek bile kamu sunucusunda tam arşiv için yeterli ve istikrarlı bir aktarım sağlamadı. Paralel kod doğrulama ve küçük kurtarma işleri için korunuyor; 33.424 dosyayı bu yöntemle zorlamaya devam etmek ana plan değil.

NCAR'ın resmî GDEX API'si `d084001` için sunucu tarafında altküme üretimini destekliyor. Genel API'den kontrol dosyası şablonu ve metadata okundu. Beş alanın — sıcaklık, bağıl nem, u/v rüzgârı ve jeopotansiyel yükseklik — 925/850 hPa ile +6/+9/+12/+15 saat ürünlerinde bulunduğu doğrulandı. Kaynaklar: [GDEX veri erişimi](https://gdex.ucar.edu/datasets/d084001/dataaccess/), [resmî API istemcisi](https://github.com/NCAR/gdex-api-client) ve [API belgeleri](https://github.com/NCAR/gdex-api-client/blob/main/docs/README.md).

`python -m ltfj.gdex_batch prepare` yedi kontrol isteği üretir: 2020 son koşusu ve 2021–2026 için yıllık parçalar. Her istek yalnızca 41°N, 29,25°E hücresini, gerekli iki seviyeyi, beş alanı ve dört tahmin saatini ister. Böylece on binlerce istemci tarafı sorgu yerine NCAR'ın sunucuda hazırladığı birkaç küçük çıktı hedeflenir. [Makine tarafından okunabilir plan](gdex-batch-plan.json).

Yedi kimlik doğrulamalı istek 30 Eylül 2026'da gönderildi. 2021 yıllık isteği açıklamasız hata verdi ve dört çeyreklik istek olarak başarıyla yeniden alındı. 2020 sınırı, 2021 çeyrekleri ve 2022–2026 paketleri indirildi. Beklenen 33.424 tekil tahmin dosyasının 33.304'ü (%99,64) paketlerde bulundu ve içerik doğrulamasını geçti. Eksik 120 dosya açık biçimde raporlandı; her yıl uygun ve pozitif METAR zamanı kapsamı önceden belirlenen %95 eğitim kapısını geçti.

## Kimlik doğrulama sınırı

GDEX, altküme isteği göndermek, durumunu okumak ve çıktı listesini almak için bearer token zorunlu tutuyor. Token ücretsiz GDEX hesabının kullanıcı profilinden alınır. Kod tokenı yalnızca ortam değişkeninden okur; URL, rapor, `.env.example`, Git veya çıktı mesajlarına yazmaz. `.env` dosyaları Git tarafından yok sayılır.

Token ortamda tanımlandıktan sonra akış:

```sh
python -m ltfj.gdex_batch submit
python -m ltfj.gdex_batch status
python -m ltfj.gdex_batch retry-failed
python -m ltfj.gdex_batch fetch
python -m ltfj.gdex_ingest
```

`submit` her isteğin kimliğini hemen yerel ve Git dışında kalan `data/raw/gdex-batch/requests.json` dosyasına kaydeder; tekrar çalıştırma aynı yılı yeniden göndermez. `status` işleme durumunu yeniler. `fetch` yalnızca sunucunun tamamladığı dosyaları indirir ve kaynak URL/özet bilgisini saklar.

Toplu çıktı doğrudan eğitime alınmaz. `gdex_ingest` arşivi güvenli biçimde açar; değişken, birim, basınç seviyesi, koordinat, koşu ve geçerlilik zamanını doğrular. [Eğitim kapsam kapısı](gfs-training-readiness.json) bütün yıllar için geçti ve sabit GFS ek veri deneyi çalıştırıldı. Sonuçlar [GFS model kartında](model-gfs-card.md) raporlandı.
