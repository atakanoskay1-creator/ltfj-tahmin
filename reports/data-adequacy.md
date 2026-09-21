# Veri yeterliliği incelemesi

**Karar:** 2025 IEM verisi veri işleme prototipi için uygun, güvenilir olay tahmini ve bağımsız performans değerlendirmesi için tek başına yetersizdir. Rutin rapor kapsamı iyi olsa da SPECI eksikleri hedef etiketlerini değiştiriyor. Çok yıllı METAR + SPECI birleştirmesi model eğitiminden önce tamamlanmalıdır.

Bu incelemede 2020–2024 arşivi de indirildi. Hesaplamalar [data-adequacy.json](data-adequacy.json), beş yıllık hazırlık denetimi [2020-2024-audit.json](2020-2024-audit.json) dosyasındadır. Bunlar model performansı sonuçları değildir.

## 1. Örnek sayısı ile olay sayısı aynı değil

| Yıl | IEM raporu | Eksik rutin zaman dilimi | <500 ft gözlem | Düşük tavan günü (UTC) | Kesintisiz düşük tavan dizisi | Pozitif tahmin zamanı |
|---|---:|---:|---:|---:|---:|---:|
| 2020 | 16.590 | 978 | 68 | 14 | 16 | 81 |
| 2021 | 17.508 | 12 | 246 | 28 | 31 | 169 |
| 2022 | 17.519 | 6 | 174 | 29 | 32 | 170 |
| 2023 | 17.515 | 5 | 204 | 28 | 33 | 171 |
| 2024 | 17.541 | 27 | 204 | 28 | 25 | 146 |
| 2025 | 17.513 | 7 | 188 | 27 | 32 | 161 |
| Toplam | **104.186** | **1.035** | **1.084** | **154** | **169** | **898** |

Eksik rutin zamanlar `:20/:50` çizelgesine göre sayılır. 2022'de ayrıca çizelge dışı beş rapor vardır. Yıllık etiketlerde yıl sınırını geçen son pencereler kesildiğinden, bu tablo tek bir kesintisiz altı yıllık eğitim seti olarak yorumlanmamalıdır.

2025'te 32 dizinin 13'ü tek rapordan oluşur. Düşük gözlemler arasındaki aralık için 24 saatlik bir ayırma kuralı uygulandığında 18 küme kalır. Altı yılda aynı kuralın yıllık toplamı 107 kümedir. Bu kümeler de kanıtlanmış bağımsız hava olayları değildir; örnek bağımlılığının boyutunu gösterir.

2025'te en uzun dizi 25 rapor, sonraki ikisi 24 ve 18 rapordur. Üç dizi 188 düşük gözlemin 67'sini oluşturur. Çok sayıda satırın birkaç uzun olaydan gelmesi nedeniyle rastgele satır bölmek yanıltıcı olur.

## 2. Zaman kapsamı ve mevsimsellik

2025 rutin kapsamı 17.513 / 17.520, yaklaşık %99,96'dır. En uzun aralık 90 dakikadır. Buna karşın 2020'de **10 Nisan 23:50Z–1 Mayıs 00:20Z** arasında 20 gün 30 dakikalık boşluk bulunur. Boşluğun nedeni bu çalışmada doğrulanmadı; iklimsel olay yokluğu olarak yorumlanamaz.

2025 Nisan ayı 95 düşük gözlemle yılın yaklaşık yarısını taşır. Ekim–Aralık'ta sıfır düşük gözlem vardır. Bu tüm sonbahar/kış dönemlerinin risksiz olduğu anlamına gelmez: 2021 Kasım'da 80, Aralık'ta 13 düşük gözlem vardır. 2025'i tek başına mevsimsel ilişki öğrenmek için kullanmak bu nedenle kırılgandır.

2021–2025, rutin kapsam bakımından 2020'den daha tutarlıdır. İlk modelde 2020'yi ayrı duyarlılık deneyi olarak ele almak makuldür; bu bir veri kalite tercihidir, model başarısına bakılarak yapılan seçim değildir.

## 3. SPECI eksikliği doğrulandı

NOAA ISD istasyon kataloğunda LTFJ'nin kimliği `17063099999` olarak doğrulandı. İndirilen 2025 NOAA dosyası 24 Ağustos 21:20Z'de sonlanıyor:

| NOAA dosyasındaki rapor türü | Sayı |
|---|---:|
| FM-15 / rutin METAR | 11.190 |
| FM-16 / SPECI | 446 |
| FM-12 / sinoptik | 1.854 |

**446 SPECI'nin tamamı IEM dosyasında yok. Bunların 33'ü <500 ft.** Eşleşen 11.190 rutin raporun ham METAR tavan çözümlemesinde bir fark bulundu: 12 Şubat 07:50Z için IEM 2.000 ft, NOAA düzeltilmiş raporu 900 ft. İkisi de hedef eşik üstünde. Rapor düzeltmelerinin geliş sırası bilinmeden geçmişte hangisinin kullanılabilir olduğu kesinleştirilemez.

Ters yönde de eksik var: NOAA'nın kapsadığı zaman aralığındaki 131 IEM raporu NOAA'da yok. Dolayısıyla NOAA dosyası IEM'in doğrudan yerine geçirilmemelidir. İki arşiv kısmen aynı üst kaynakları kullanır; karşılaştırma bağımsız bir sensör doğrulaması değildir.

### Hedefe etkisi

Yalnızca IEM'de olmayan NOAA raporlarını ekleyen deneme yapıldı; çelişen rutin raporlar değiştirilmedi. Bu, kalıcı eğitim seti değil, eksik raporlara duyarlılık analizidir.

- 2025 düşük gözlem sayısı 188'den 221'e, düşük tavan dizisi 32'den 35'e çıkar.
- İlk IEM gözlemini sabit tutup yalnızca gelecek gözlemleri zenginleştirince **7 negatif tahmin zamanı pozitife döner**.
- Güncel gözlem de ek raporlarla güncellendiğinde pozitif tahmin zamanı 161'den 169'a çıkar. Bu farkın tamamı yeni olay değildir; güncel durumun değişmesi de etkilidir.
- Yedi negatiften pozitife dönüşün altısı 26 Mayıs 10:30–13:00Z tahmin zamanlarıdır. Bütün bir üç saatlik uyarı dizisi eksik SPECI yüzünden kaçırılabilir.
- Karşılaştırma sadece 24 Ağustos'a kadar ek SPECI sağlar. Eylül–Aralık için eksik SPECI olmadığı sonucu çıkarılamaz.

[NOAA kaynak dosyası](https://www.ncei.noaa.gov/data/global-hourly/access/2025/17063099999.csv) ve [ISD alan tanımları](https://www.ncei.noaa.gov/pub/data/noaa/isd-format-document.pdf).

## 4. Hazır tavan sütununu doğrudan kullanmak da sakıncalı

NOAA'nın sayısal `CIG` alanı ile ham METAR'dan çıkardığımız tavan, kaliteli ve sayısal olarak eşleşebilir 3.545 raporun 93'ünde 1,1 metreden fazla farklıdır. Örneğin `SCT009 SCT035 BKN090` raporunda ham METAR tavanı 9.000 ft iken NOAA `CIG` alanı 1.067 metre verir. Bu farkın nedenini bu inceleme kanıtlamaz; ham kodun korunması ve uyuşmazlık işareti gerekir. Birim yuvarlamasıyla açıklanamayacak örnekler JSON raporuna kaydedildi.

500 ft tam sınırda ayrıca önemlidir: 2025'te tam 500 ft olan 16 gözlem bulunur ve bunlar hedefe dahil değildir. Metrik arşivde 500 ft'nin yuvarlanmış 152 metre karşılığını doğrudan `152 < 152.4` diye sınıflamak yanlış pozitif üretebilir. Hedefi mümkün olduğunca ham METAR'ın özgün yükseklik kodundan çıkarmalıyız.

## 5. Girdilerin kullanılabilirliği

2025'te sıcaklık, çiy noktası ve QNH tüm ham raporlarda çözümlenebildi; rüzgâr hızı 10, görüş bir raporda eksik. Negatif sıcaklık–çiy noktası farkı bulunmadı. Bu kontroller ölçümlerin bağımsız doğruluğunu kanıtlamaz.

11.613 raporda sayısal tavan olmaması sıradan bir eksik veri problemi değildir; CAVOK/NSC/FEW/SCT gibi kodların anlamı korunmalıdır. Bu kayıtları silmek yaklaşık üçte iki veriyi ve olay öncüllerini kaybettirir. 2025'in 161 pozitif tahmin zamanının 80'inde güncel raporda sayısal tavan yoktur. Yalnızca mevcut alçak tavana odaklanan bir kural yeterli olmayabilir; bu bulgu bir modelin başarısını ölçmez.

Rapor zamanı ile ulaşma zamanı ayrı tutulmalıdır. Şimdiki arşivde ulaşma zamanları yoktur. As-of birleştirme gözlem zamanı bakımından geleceği kullanmasa da gerçek zamanlı erişilebilirliği garanti etmez.

## 6. Hangi ek kaynak, hangi amaç için?

| Öncelik | Kaynak | Beklenen katkı | Bu incelemedeki durum |
|---|---|---|---|
| 1 | Çok yıllı IEM + NOAA ham METAR/SPECI | Olay çeşitliliği ve eksik özel raporların tamamlanması | IEM 2020–2025 indirildi; NOAA 2025 dosyası karşılaştırıldı |
| 1 | NOAA GHCNh | ISD sonrası güncel arşiv ve ek kaynaklar | Resmi belgeler incelendi; LTFJ dosya/alan kapsamı henüz test edilmedi |
| 1 | MGM/MEVBİS; varsa havaalanı ölçüm arşivi | SPECI, düzeltmeler, alım zamanları; erişilebilirse sık aralıklı ceilometre/AWOS | MGM veri erişim kanalı doğrulandı; bu özel alanların LTFJ'de teslim edilebilirliği doğrulanmadı |
| 2 | Çevre istasyon METAR/SPECI | Rüzgâr yönünden gelen alçak bulut ve görüş bozulmasının takibi | LTFM, LTBA, LTBQ ve LTBR inceleme adayları; kapsam/mesafe/temsil yeteneği denetlenmeli |
| 3 | Yayımlanmış model çalıştırmalarının arşivi | Alt seviye nem profili, inversiyon, rüzgâr, alçak bulut ve yağış | Modelin başlangıç zamanı, geçerli zamanı ve erişim gecikmesi saklanmalı |
| 4 | Meteosat bulut/sis ürünleri | Denizden yaklaşan alçak bulutun alan ve hareketi | Ürün/erişim araştırması yapıldı; veri indirilmedi |

NOAA, ISD'nin güncellenmesini sonlandırıp GHCNh'ye geçtiğini belirtiyor. Eski dosyanın Ağustos 2025'te durması, yeni arşive bakma gereğini doğurur. GHCNh kaynak ve kalite bayraklarıyla değerlendirilmelidir. [NOAA geçiş duyurusu](https://www.ncei.noaa.gov/operating-system-upgrade-outage), [GHCNh](https://www.ncei.noaa.gov/products/global-historical-climatology-network-hourly).

MGM'nin veri erişim sayfasında AWOS ve radiosonde arşivleri yer alır. Tam LTFJ METAR/SPECI ve ceilometre verisinin erişim kapsamı, ücret ve koşulları ayrıca teyit edilmelidir. Hiçbir ücretli sipariş veya kurumla iletişim başlatılmadı. [MGM veri erişimi](https://www.mgm.gov.tr/site/bilgi-edinme.aspx?r=d).

Open-Meteo Historical Forecast API ardışık model çalıştırmalarının ilk saatlerini birleştirir; bunu tahmin anında yayımlanmış üç saatlik tahmin diye doğrudan kullanamayız. Single Runs API çalıştırma yapısını korur. Belgede IFS HRES için Mart 2024, diğer modeller için 2 Nisan 2026 başlangıcı belirtiliyor; önce kapsam ve yayım gecikmesi denetlenmelidir. [Historical Forecast](https://open-meteo.com/en/docs/historical-forecast-api), [Single Runs](https://open-meteo.com/en/docs/single-runs-api).

ERA5 fiziksel örüntüleri incelemek için yardımcı olabilir; gerçek zamanda yayımlanmış tahmin yerine kullanılmamalıdır. Uydu bulut tepe yüksekliği de bulut tabanı/tavanı değildir; hedef etiketi olarak kullanılmaz. [EUMETSAT bulut ürünleri](https://user.eumetsat.int/data/themes/weather/cloud-types).

## 7. Önerilen karar

1. Mevcut 2025 etiketlerini **IEM-only ön sürüm** olarak tut; model başarı iddiasında kullanma. İlk rapordaki iyi rutin kapsam, SPECI tamlığı anlamına gelmiyordu; karşılaştırma artık somut eksiklik gösteriyor.
2. Önce 2021–2025 rutin + SPECI birleşimini kaynak önceliği, düzeltme ve çakışma kurallarıyla oluştur. GHCNh veya MGM üzerinden 2025 son dört ayını doğrula. 2020 boşluğunu ayrıca raporla.
3. Önerilen ilk geliştirme düzeni: 2021–2023 eğitim, 2024 doğrulama/kalibrasyon, 2025 tutulan değerlendirme yılı. 2025 bu veri incelemesinde görülmüştür; tamamen dokunulmamış nihai test sayılmaz. Nihai güven için yeni bir tam dönem veya ileriye dönük test ayır.
4. Her zaman sınırında en az üç saatlik hedef taşmasını önle; hava olayı kümelerinin sınırdan taşmasını da kontrol et. Başarı belirsizliğini satır düzeyinde değil olay/gün bloklarıyla değerlendir.
5. Az sayıda özellikli düzenlileştirilmiş lojistik modelle başla. 2021–2023'teki 96 düşük tavan dizisi ilk deneme için yararlıdır; çok karmaşık model veya ince mevsim/rüzgâr alt grupları için güçlü kanıt değildir. Sabit bir “yeterli olay sayısı” garantisi yoktur; öğrenme eğrisi ve belirsizlik aralıklarıyla karar ver.
6. Komşu istasyonları, ardından arşivlenmiş sayısal tahminleri ayrı ekleme deneylerinde karşılaştır. Etiket kalitesi düzelmeden yüzlerce yeni girdi ekleme.

## Yeniden üretme

Python standart kütüphanesi yeterlidir. Depo kökünde:

```sh
python -m ltfj.pipeline fetch --start 2020-01-01 --end 2025-01-01 --output data/raw/LTFJ_2020_2024.csv
python -m ltfj.pipeline prepare --input data/raw/LTFJ_2020_2024.csv --output data/processed/2020_2024 --report reports/2020-2024-audit.json
curl --fail --output data/raw/NOAA_LTFJ_2025.csv https://www.ncei.noaa.gov/data/global-hourly/access/2025/17063099999.csv
python -m ltfj.adequacy --inputs data/raw/LTFJ_2020_2024.csv data/raw/LTFJ_2025.csv --noaa data/raw/NOAA_LTFJ_2025.csv --output reports/data-adequacy.json
python -m unittest discover -s tests -v
```

2025 IEM indirme komutu README'dedir. Mevcut ham dosyaları tekrar indirmek gerekmez. Analiz dosyaları kaynak URL'lerini ve SHA-256 özetlerini içerir; arşivler sonradan düzeltilebildiğinden yeniden indirme farklı sonuç üretebilir. NOAA karşılaştırması 2025 LTFJ örneğine özeldir; genel bir NOAA içeri alma modülü değildir.
