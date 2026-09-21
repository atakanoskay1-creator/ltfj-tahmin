# LTFJ Bulut Tavanı Tahmini

LTFJ (İstanbul Sabiha Gökçen) için METAR/SPECI ve ek meteorolojik veriler kullanarak **önümüzdeki 3 saat içinde bulut tavanının 500 ft AGL altına düşme olasılığını** tahmin eden istatistiksel model projesi.

## Durum

2025 yılı LTFJ arşivi indirilmiş ve denetlenmiştir. METAR çözümleme, geçmişe dayalı özellik çıkarımı ve üç saatlik hedef etiketleme çalışmaktadır. Henüz model eğitilmemiş ve tahmin başarısı ölçülmemiştir.

İlk denetim: **17.513 gözlem, 188 eşik altı gözlem, 32 kesintisiz düşük tavan dizisi ve 161 pozitif tahmin zamanı**. Pozitif tahmin zamanları bağımsız hava olayları değildir. Ayrıntılar: [2025 veri raporu](reports/2025-summary.md).

## Çalıştırma

Python 3.10 veya üstü yeterlidir; ek paket kurulumu gerekmez. Komutlar depo kökünde çalıştırılır:

```sh
python -m ltfj.pipeline fetch --start 2025-01-01 --end 2026-01-01 --output data/raw/LTFJ_2025.csv
python -m ltfj.pipeline prepare --input data/raw/LTFJ_2025.csv --output data/processed/2025 --report reports/2025-audit.json
python -m unittest discover -s tests -v
```

Başlangıç dahil, bitiş hariçtir; saatler UTC'dir. İndirici mevcut ham dosyayı değiştirmez. Yeniden hazırlama, CSV yanındaki `.manifest.json` dosyasını ve SHA-256 doğrulamasını gerektirir. Aynı kaynağı tekrar indirmek için farklı bir çıktı adı kullanın. `prepare` türetilmiş çıktıları yeniden üretir.

- `data/raw/`: Ham CSV ve kaynak URL'si, indirme zamanı, tarih aralığı, dosya özeti içeren manifest; Git'e yüklenmez.
- `data/processed/2025/features.csv`: Yalnızca tahmin anına kadar olan gözlemlerden özellikler.
- `data/processed/2025/labels.csv`: Hedef, hedef penceresinin sonu ve etiket durumu. Eğitimde yalnızca hedefi 0 veya 1 olan satırlar kullanılır; boş hedefler 0'a çevrilmez.
- `reports/2025-audit.json`: Aylık sayımlar, boşluklar, eksikler ve kullanılan protokol; Git'te saklanır.

`features.csv` ve `labels.csv`, `time` alanı üzerinden bire bir birleştirilir. `label_status` ve `target_end` model girdisi değildir. Sayısal tavanın boş olması açık gökyüzünü veya bilinmeyen ölçümü temsil edebilir; `ceiling_state` korunmalıdır. Rüzgâr yönündeki boşluk değişken yönü, gust alanındaki boşluk raporlanmamış hamleyi de içerebilir.

## İlk veri protokolü

Tahmin zamanları UTC `:00/:30`; son gözlemin en fazla 35 dakika eski olmasına izin verilir. Üç saatlik gelecek pencerede pozitif gözlem varsa olay etiketi verilir. Negatif etiket için gelecekte belirsiz tavan bulunmaması, pencere sınırları dahil gözlem aralıklarının en fazla 35 dakika olması ve arşivin tüm hedef penceresini kapsaması gerekir. Bu 35 dakikalık sınır, örnekteki 30 dakikalık rutin sıklığa göre seçilmiş ilk sürüm kuralıdır; meteorolojik bir garanti değildir.

Ham METAR'daki TEMPO/BECMG/NOSIG ve RMK bölümleri gözlemden ayrılır. Aynı zamanın farklı sürümleri varsa geliş sırası bilinmediği için belirsiz sayılır. Arşivde alım/yayım zamanı bulunmadığından bu veri seti **gözlem zamanına dayalı araştırma sürümüdür**; gerçek zamanlı erişilebilirlik doğrulanmış değildir. İlk gerçek zamanlı testten önce rapor gecikmeleri ve düzeltmeler ele alınmalıdır.

## Tahmin hedefi

- Tahmin zamanı: `t`.
- Tahmin penceresi: `(t, t + 3 saat]`.
- Olay: Bu pencerede geçerli bir METAR/SPECI gözleminde tavanın **500 ft AGL altında** olması. Tam 500 ft olay değildir.
- Çıktı: 0–1 arasında olay olasılığı; arayüzde yüzde olarak gösterilebilir.
- Tahmin anında tavan zaten 500 ft altındaysa `already_below_threshold` durumu gösterilir. Bu durum yeni eşik geçişi modeliyle karıştırılmaz; devam/iyileşme tahmini ayrı bir hedeftir.

Gözlemler arasındaki kısa olaylar kaçırılabileceği için ilk modelin hedefi fiziksel olarak kesintisiz üç saati değil, **raporlanmış eşik altı olayı** temsil eder.

## Tavanın çıkarılması

En alçak BKN veya OVC tabakasının yerden yüksekliği kullanılır. Sayısal VV, gökyüzünün örtülü olduğu durumda tavan karşılığı olarak değerlendirilir. FEW ve SCT tek başına tavan değildir. `VV///` bilinmeyendir.

CAVOK, açık gökyüzü veya BKN/OVC bulunmaması sayısal bir tavan yüksekliğine çevrilmez. Kodun raporlama anlamı ve diğer alanların geçerliliği korunur. Eksik, bozuk veya belirsiz kayıtlar düşük tavan yokmuş gibi etiketlenmez.

## Veri ve model planı

1. LTFJ METAR/SPECI geçmişi: tavan, bulut miktarı, görüş, sıcaklık, çiy noktası, rüzgâr, QNH ve mevcut hava kodları.
2. Yalnızca geçmiş gözlemlerden son 1–3 saatlik değişimler; sıcaklık–çiy noktası farkı, tavan/görüş eğilimi, rüzgâr bileşenleri.
3. Veri kapsamı doğrulandıktan sonra çevre istasyonlar ve tahmin anında yayımlanmış sayısal hava tahminleri: alt seviye nemi, sıcaklık profili, sınır tabakası yüksekliği ve alçak bulut verileri.
4. Başlangıç referansları: mevsim/saat bazlı olay sıklığı ve basit mevcut durum kuralları. İlk öğrenilen model düzenlileştirilmiş lojistik regresyon; doğrusal olmayan ilişkiler için GAM karşılaştırması.
5. Kronolojik doğrulama, olasılık kalibrasyonu ve bağımsız son dönem testi.

ERA5 gibi yeniden analiz verileri keşif için kullanılabilir; tahmin anında erişilebilir olmayan veriler operasyonel testin girdisi olamaz.

## Etiketleme ve doğrulama

- Gelecek pencerede doğrulanmış eşik altı gözlem varsa pozitif etiket verilir.
- Negatif etiket için yeterli gözlem kapsamı gerekir. Beklenen rapor sıklığı ve kabul edilebilir boşluk veri denetimi sırasında belirlenecek, eğitimden önce sabitlenecektir. Yetersiz kapsam bilinmeyen etikettir.
- Tahmin zamanları sabit bir çizelge üzerinde seçilir; SPECI sıklığının kötü hava dönemlerini gereksiz ağırlıklandırması önlenir. Çizelge aralığı veri kapsamı denetiminden sonra seçilir.
- Eğitim/test sınırını geçen üç saatlik hedef pencereleri eğitimden çıkarılır. Rastgele satır bölünmesi kullanılmaz.
- Ek veri birleştirmesinde gözlem/geçerlilik zamanı kadar yayımlanma veya erişilebilirlik zamanı da dikkate alınır.
- Ön işleme, değişken seçimi, kalibrasyon ve alarm eşiği seçimi test dönemini görmez.
- Brier skoru, kalibrasyon, PR-AUC, yakalama oranı, kaçırma oranı ve yanlış alarm oranı raporlanır. Birbirine bağımlı raporların yanında olay bazında sonuçlar da incelenir.
- Alarm eşiği varsayılan olarak %50 seçilmez; yanlış alarm ve kaçırma dengesi doğrulama verisinde değerlendirilir.

## Sonraki somut adım

Birden fazla yılın verisini aynı protokolle denetlemek, SPECI kapsamını karşılaştırmalı doğrulamak ve kronolojik eğitim/doğrulama/test dönemlerini belirlemek. Ardından olay sıklığı referansı ve lojistik regresyon modeli kurulacaktır. 2025'in son üç ayında pozitif olay bulunmadığından bu yılın son bölümünü tek başına test kümesi yapmak uygun bir ilk başarı değerlendirmesi sağlamaz. Çevre istasyonlar ve sayısal hava tahmini girdileri sonraki aşamada eklenecektir.

## Kaynaklar

- [AWC METAR veri açıklaması](https://aviationweather.gov/help/data/)
- [ECMWF ERA5 açıklaması](https://www.ecmwf.int/en/forecasts/dataset/ecmwf-reanalysis-v5)
- [Iowa Environmental Mesonet veri kaynağı](https://mesonet.agron.iastate.edu/request/download.phtml?network=TR__ASOS)
- [IEM veri kullanım koşulları](https://mesonet.agron.iastate.edu/disclaimer.php)
