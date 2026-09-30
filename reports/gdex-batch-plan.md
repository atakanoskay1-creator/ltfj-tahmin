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

Resmî API belgesine göre istemci düzeltildi: kontrol dosyasında güncel veri kimliği `d084001` kullanılıyor; yanıtlar `result`, hatalar `messages` alanından okunuyor; HTTP hataları tokenlı URL yazılmadan raporlanıyor. `fetch` önce isteğin `Completed` olduğunu kontrol ediyor ve indirilen dosya boyutunu API'nin bildirdiği boyutla karşılaştırıyor. GDEX bir kullanıcıya aynı anda en fazla 8 açık istek tanıyor ve tamamlanan çıktıları varsayılan olarak 7 gün saklıyor; `fetch` bu süre içinde çalıştırılmalı.

`submit` her isteğin kimliğini hemen yerel ve Git dışında kalan `data/raw/gdex-batch/requests.json` dosyasına kaydeder; tekrar çalıştırma aynı yılı yeniden göndermez. `status` işleme durumunu yeniler. `fetch` yalnızca sunucunun tamamladığı dosyaları indirir ve kaynak URL/özet bilgisini saklar.

Toplu çıktı geldiğinde doğrudan eğitime alınmayacak. Değişken, birim, basınç seviyesi, koşu ve geçerlilik zamanı kontrolleri toplu dosya biçimine uyarlanacak; ardından [eğitim kapsam kapısı](gfs-training-readiness.json) tekrar çalıştırılacak. Şu an tek dosyalı önbellekte 33.424 gerekli dosyanın 32'si var ve 2021 uygun zaman kapsamı yaklaşık %0,20; diğer yıllar %0. Model eğitimi için hazır değil.

## Toplu çıktılar (1 Ekim 2026)

GDEX'ten 2020 son koşusu ve 2021–2026 isteklerinin tamamı geldi. 2021 dört çeyreklik arşiv olarak alındı; aynı klasördeki birden çok arşiv birlikte doğrulanır. Arşivler `data/raw/gdex-batch/<istek>/` altına `.tar` olarak konur ve açılmadan okunur:

```sh
python -m ltfj.gdex_ingest
python -m ltfj.gfs_features
python -m ltfj.gfs_readiness
```

Toplu dosya biçimi THREDDS'ten farklıdır (`TMP_L100`, `level0` mbar, `ref_date_time`, `forecast_hour`); [`gdex_ingest`](../ltfj/gdex_ingest.py) bunun için ayrı bir katı doğrulayıcıdır. Her dosyada değişken kümesi, koşu/geçerlilik zamanı, tahmin saati, ürün adı, 41°N 29,25°E hücresi, 925/850 mbar seviyeleri, birimler, eksik değer ve nem sınırları kontrol edilir; arşiv üyeleri istek aralığı dışındaysa veya tekrar ediyorsa işlem durur. Doğrulanan kayıtlar THREDDS alan adlarına çevrilir; aynı koşu/saat iki kaynakta varsa değerlerin uyuşması zorunludur. `gfs_features` arşiv SHA-256 özetini her çalıştırmada yeniden doğrular.

| İstek | Tam koşu | Dosya | Eksik | 00/30 tahmin anı kapsamı (6 sa gecikme) |
|---|---|---|---|---|
| 2020_tail | 1/1 | 4/4 | yok | — |
| 2021 | 1.460/1.460 | 5.840/5.840 | yok | %100,00 |
| 2022 | 1.458/1.460 | 5.834/5.840 | 2022041718; 2022071418 +6/+9 | %99,86 |
| 2023 | 1.459/1.460 | 5.836/5.840 | 2023122518 | %99,93 |
| 2024 | 1.460/1.464 | 5.843/5.856 | 2024051918, 2024102112, 2024110612; 2024052806 +15 | %99,77 |
| 2025 | 1.459/1.460 | 5.839/5.840 | 2025082618 +15 | %99,97 |
| 2026 | 1.023/1.051 | 4.108/4.204 | 16 Ocak 12Z – 21 Ocak 18Z arası 22 koşu; 6 koşuda bazı saatler | %97,49 |

Ayrıntı: [gdex-ingest.json](gdex-ingest.json). Kapsam sütunu etiketlerden bağımsız tüm 00/30 anlarını sayar; eğitim kapısı yalnızca etiketi 0/1 olan anlara ve pozitif anlara ayrıca bakar, bu yüzden `gfs_readiness` ile yeniden ölçülmelidir. Eksik koşular eksik bırakılır, doldurulmaz. İstek yalnızca +6…+15 saat ürünlerini kapsadığından 9 ve 12 saatlik gecikme duyarlılık senaryoları için +18 ve +21 saat ürünleri de gerekir (2026'da kapsam %56,9 ve %8,1). Toplam 33.304 dosya doğrulandı; tüm yıllar etiketlerden bağımsız sayımda %95 eşiğinin üstünde. Kapının resmî sonucu etiketli ve pozitif anlar üzerinden `gfs_readiness` ile verilir; bu çalışma ortamında IEM/NOAA erişimi olmadığından etiketler yeniden üretilemedi ve kapı henüz çalıştırılmadı.
