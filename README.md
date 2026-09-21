# LTFJ Bulut Tavanı Tahmini

LTFJ (İstanbul Sabiha Gökçen) için METAR/SPECI ve ek meteorolojik veriler kullanarak **önümüzdeki 3 saat içinde bulut tavanının 500 ft AGL altına düşme olasılığını** tahmin eden istatistiksel model projesi.

## Durum

Proje tanımı hazırlanmıştır. Henüz veri indirilmemiş, model eğitilmemiş ve başarı ölçülmemiştir.

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

Tarihsel METAR kaynağının LTFJ kapsamını ve kullanım koşullarını doğrulamak; örnek veri üzerinde kod çözme, tekrar kayıt, eksik kayıt ve rapor sıklığı denetimini yapmak. Ardından veri işleme ve ilk referans model uygulanacaktır.

## Kaynaklar

- [AWC METAR veri açıklaması](https://aviationweather.gov/help/data/)
- [ECMWF ERA5 açıklaması](https://www.ecmwf.int/en/forecasts/dataset/ecmwf-reanalysis-v5)
