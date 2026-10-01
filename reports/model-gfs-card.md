# GFS ek veri deneyi

1 Ekim 2026. Bu deney, LTFJ'de önümüzdeki üç saat içinde tavanın 500 ft AGL altına düşmesi hedefinde GFS'nin ek tahmin değeri sağlayıp sağlamadığını ölçer.

## Tasarım

GFS toplu arşivinde beklenen 33.424 dosyanın 33.304'ü doğrulandı (%99,64). Her yıl hem uygun tahmin zamanı hem pozitif örnek kapsamı için önceden belirlenen %95 kapısını geçti. Model yalnızca aynı zamanlarda GFS verisi bulunan eşleşmiş satırlarda karşılaştırıldı.

İki model aynı sabit küçük HistGradientBoosting yapılandırmasını kullanır. Birincisi yalnızca yerel METAR değişkenlerini, ikincisi bunlara 925/850 hPa sıcaklık, bağıl nem, u/v rüzgâr ve jeopotansiyel yüksekliğin mevcut değerleri ile üç saatlik değişimlerini ekler. Eğitim 2021–2023, yalnızca sabit terim kalibrasyonu ve alarm eşiği 2024'tür. 2025 ve 2026 daha önce görülmüş retrospektif tekrar dönemleridir; yeni bağımsız test değildir.

## Sonuçlar

| Dönem | Model | Brier | Ortalama kesinlik | Yakalama | Alarm kesinliği | Yanlış alarm |
|---|---|---:|---:|---:|---:|---:|
| 2024 kalibrasyon | METAR | 0,007980 | 0,189 | %70,3 | %10,0 | 976 |
| 2024 kalibrasyon | METAR + GFS | 0,007736 | 0,239 | %71,6 | %9,5 | 1.059 |
| 2025 tekrar | METAR | 0,009358 | 0,122 | %54,4 | %9,2 | 916 |
| 2025 tekrar | METAR + GFS | 0,009354 | 0,128 | %49,7 | %7,5 | 1.044 |
| 2026 tekrar | METAR | 0,014829 | 0,314 | %73,5 | %18,5 | 681 |
| 2026 tekrar | METAR + GFS | 0,014519 | 0,344 | %78,7 | %18,0 | 758 |

2024'te GFS modeli 28 düşük tavan dizisinin 27'sini, 2025'te 36 dizinin 30'unu yakaladı; yerel modelle aynıydı. 2026'da yerel model 39 dizinin 37'sini, GFS modeli 38'ini yakaladı. Diziler bağımsız meteorolojik olaylar değildir.

## Karar

GFS alanları olasılık sıralamasına yararlı sinyal ekliyor: ortalama kesinlik üç dönemde de yükseldi ve Brier skoru kötüleşmedi. Bununla birlikte 2025 alarm performansı geriledi, 2024 ve 2026'da yanlış alarm sayısı arttı. Haftalık bloklarla eşleştirilmiş Brier kazanımının %95 aralığı her dönemde sıfırı içeriyor; iyileşme kesinleşmiş değil.

GFS modeli araştırma adayı olarak saklanır; mevcut v1/v2 modeli otomatik olarak değiştirmez. Sonraki doğru değerlendirme, modeli ve alarm politikasını dondurup ileri tarihte gelecek yeni veride sınamaktır. Tarihsel GFS yayımlanma gecikmesi kaydedilmediği için altı saatlik erişilebilirlik gecikmesi varsayımdır; operasyonel kullanımdan önce gerçek alım zamanlarıyla doğrulanmalıdır.
