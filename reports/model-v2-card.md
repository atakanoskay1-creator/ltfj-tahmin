# İkinci deney: doğrusal olmayan modeller

## Karar

Küçük gradyan artırmalı ağaç modeli araştırma adayı olarak tutuldu. İlk modelin yerine otomatik geçirilmedi. Daha az yanlış alarm üretiyor ancak 2026'da daha fazla pozitif tahmin zamanını kaçırıyor. Olasılık hatasındaki iyileşmenin belirsizlik aralıkları sıfırı içeriyor; kesin üstünlük gösterilmiş değil.

Hedef değişmedi: tavan şu anda eşik altında değilken, **(t, t+3 saat] içinde gözlenen tavanın 500 ft AGL altına düşmesi**. Sonuçlar yarım saatlik tahmin zamanlarına aittir; ardışık pozitif zamanlar bağımsız meteorolojik olaylar değildir.

## Seçim ve sızıntı kontrolü

[Deney protokolü](../research-protocol-v2.json) çalıştırmadan önce yazıldı. Altı aday, önce 2021 ile eğitilip 2022'de, ardından 2021–2022 ile eğitilip 2023'te değerlendirildi. Eğitim ve değerlendirme dönemlerinin sonunda 24 saat ambargo ve hedef penceresi kontrolü uygulandı. İmputasyon ve dönüşümler her katın yalnızca eğitim verisinde öğrenildi. Ağaçlarda rastgele erken durdurma kapatıldı. Sınıf ağırlıkları kullanılmadı.

2022–2023 toplam 34.534 tahmin zamanı ve 344 pozitif etiket için havuzlanmış Brier skoru (küçük daha iyi):

| Aday | Brier |
|---|---:|
| Yerel lojistik | 0,009747 |
| Çevre istasyonlu lojistik | 0,009281 |
| Az değişkenli lojistik | 0,010008 |
| Az değişkenli spline | 0,009317 |
| **Yerel ağaç modeli** | **0,009245** |
| Çevre istasyonlu ağaç modeli | 0,009266 |

Aradaki farklar küçük. Bu sonuç çevre istasyonların yararsız olduğunu göstermez. Seçilen model 150 iterasyon, 7 yaprak, yaprak başına en az 100 örnek ve 0,05 öğrenme hızı kullanır. Son eğitim 2021–2023; 2024'te yalnızca log-odds sabit kaydırmasıyla kalibrasyon ve en az %70 duyarlılık sağlayan en yüksek kesinlikli eşik seçimi yapıldı. Eşik yaklaşık **%2,73**; operasyonel maliyetlere göre onaylanmış bir eşik değildir.

2024 daha önce v1 geliştirmesinde kullanıldı. 2025 ve 2026 sonuçları da önceki deneyde görüldü. Buradaki değerlendirme **yeniden kullanılan geçmiş dönem karşılaştırmasıdır; yeni bağımsız doğrulama değildir**. Seçimden sonra yalnızca kazanan aday bu dönemlere uygulandı. Model ve protokol/veri SHA-256 özetleri değerlendirmeden önce yerel `models/v2-frozen-selection.json` dosyasına kaydedildi.

## Yeniden kullanılan dönemlerde karşılaştırma

| Dönem / model | Brier | Ortalama kesinlik (AP) | Pozitif zamanı yakalama | Uyarıların doğruluk oranı | Yanlış uyarı zamanı | Kaçırılan pozitif zaman |
|---|---:|---:|---:|---:|---:|---:|
| 2025 / v1 | 0,009503 | 0,103 | %52,6 | %7,5 | 1.117 | 81 |
| 2025 / v2 | 0,009291 | 0,126 | %54,4 | %9,3 | 905 | 78 |
| 2026¹ / v1 | 0,015126 | 0,231 | %78,7 | %15,8 | 887 | 45 |
| 2026¹ / v2 | 0,014716 | 0,263 | %73,5 | %16,7 | 774 | 56 |

¹ 1 Ocak–20 Eylül; tam yıl değildir. İki modelin eşikleri ayrı ayrı 2024'te aynı %70 duyarlılık hedefiyle seçildi; değerlendirme yıllarında duyarlılıklar eşit değildir. Bu nedenle yanlış alarm azalması eşit duyarlılıkta üstünlük olarak yorumlanamaz.

V1'e göre Brier hatası 2025'te %2,23, 2026'da %2,71 azalıyor. Eşleştirilmiş 7 günlük bloklarla 500 yeniden örneklemenin %95 aralıkları sırasıyla **−%8,30 ile +%10,31** ve **−%2,08 ile +%9,31**. Bunlar sabit modeller için koşullu aralıklardır; eğitim ve model seçimi belirsizliğini kapsamaz.

2026'da v2 ortalama %1,07 olasılık üretirken gözlenen pozitif oranı %1,71. Risk hâlâ düşük tahmin ediliyor. 2024 kalibrasyonunda ortalamaların eşit olması kalibrasyon başarısının bağımsız kanıtı değildir; kullanılan yöntemin matematiksel sonucudur.

## Veri ve sonraki araştırma kararı

Mevcut veri bir başlangıç modeli kurmaya yeterli, düşük yanlış alarm yüküyle güvenilir operasyonel tahmin iddiası için yeterli değil. Yeni modelde de uyarıların yaklaşık %91'i (2025) ve %83'ü (2026 kısmı) yanlış. Daha fazla algoritma taraması yerine, tarihsel alım zamanı bilinen raporlar ve tahmin anında yayımlanmış sayısal hava tahmini arşivleri öncelikli. Önceki yıllar için sonradan oluşturulmuş reanalizi canlı kullanılabilir tahmin gibi eklemek uygun değil.

Gerçek alım zamanı henüz bulunmadığı için 10 dakikalık rapor gecikmesi varsayımı sürüyor. Gelecekte bağımsız değerlendirme için modeli önceden dondurup tahminleri ve veri alım zamanlarını sonuç görülmeden kaydetmek gerekiyor. Bu deney canlı veri toplama veya operasyonel alarm başlatmaz.

## Tekrar üretim ve kaynaklar

V1 eğitiminden ve veri hazırlığından sonra `python -m ltfj.model_v2` çalıştırılır. [Makine tarafından okunabilir sonuçlar](model-v2-results.json), kat sonuçlarını, kalibrasyon dönemi hata gruplarını, olay yakalamayı ve belirsizlik aralıklarını içerir. V1'in taşınabilir tahmin komutu korunmuştur; v2 ayrı yerel model dosyasına yazılır.

Yöntem uygulaması: [scikit-learn SplineTransformer](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.SplineTransformer.html) ve [HistGradientBoostingClassifier](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingClassifier.html) resmi belgeleri. Veriler, etiketler ve ilk modelin sınırları için [ilk model raporu](model-card.md).
