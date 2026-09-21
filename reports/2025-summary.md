# LTFJ 2025 veri denetimi

Bu rapor indirilen verinin ve etiketlerin denetimidir; model başarısı veya güncel hava tahmini değildir. Makine tarafından üretilen ayrıntılar [2025-audit.json](2025-audit.json) dosyasındadır.

## Kaynak ve kapsam

Iowa State University Iowa Environmental Mesonet (IEM), `TR__ASOS / LTFJ`. İstasyon metadatası arşiv başlangıcını 18 Kasım 2003 olarak gösterir; bu bilgi tüm yılların eksiksiz olduğunu kanıtlamaz. Bu aşamada yalnızca 2025 indirildi ve denetlendi.

Kaynak, materyallerinin kamu malı olduğunu ve yasal amaçlarla serbestçe kullanılabildiğini belirtir; doğruluk garantisi vermez. Kaynak atfı: Iowa Environmental Mesonet, Iowa State University.

- [İstasyon bilgisi](https://mesonet.agron.iastate.edu/sites/site.php?station=LTFJ&network=TR__ASOS)
- [Kullanım koşulları](https://mesonet.agron.iastate.edu/disclaimer.php)
- [İndirme API'si](https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?help)

İstek aralığı `[2025-01-01 00:00Z, 2026-01-01 00:00Z)`; rutin ve özel raporlar birlikte istendi (`report_type=3,4`). Kaynak URL'si, indirme zamanı ve SHA-256 özeti JSON raporunda saklanır. API tekrar kullanılırken saniyede bir istek sınırına uyulmalıdır; bu indirme tek istektir.

## Bulgular

| Ölçüm | Sonuç |
|---|---:|
| İndirilen gözlem | 17.513 |
| Tekil gözlem zamanı | 17.513 |
| Tekrar veya aynı zamanda çelişen rapor | 0 |
| İlk / son gözlem (UTC) | 1 Ocak 00:20 / 31 Aralık 23:50 |
| Medyan gözlem aralığı | 30 dakika |
| En uzun gözlem aralığı | 90 dakika |
| 35 dakikayı aşan aralık | 5 |
| Ölçülen BKN/OVC/VV tavanı | 5.900 |
| Sayısal tavan raporlanmayan geçerli gökyüzü durumu | 11.613 |
| Belirsiz tavan durumu | 0 |
| 500 ft altındaki gözlem | 188 |
| Kesintisiz düşük tavan dizisi | 32 |

Düşük tavan dizisi, aralarında en fazla 35 dakika olan ardışık eşik altı gözlemlerdir. Dizi sayısı bağımsız meteorolojik olay sayısı olarak yorumlanmamalıdır.

Tüm gözlemler saatin `:20` veya `:50` dakikasındadır. Metinde açık SPECI öneki yoktur; bu tek başına rapor türünü kanıtlamaz. Özel raporlar istenmiş olsa da **SPECI kapsamının eksiksizliği doğrulanmamıştır**. Kısa süreli eşik altı olaylar arşivde görünmeyebilir.

## Üç saatlik hedefler

UTC `:00/:30` çizelgesinde 17.520 tahmin zamanı üretildi:

| Durum | Sayı |
|---|---:|
| Gelecek üç saatte gözlenen eşik altı olay (1) | 161 |
| Kapsam yeterli, gözlenen eşik altı olay yok (0) | 17.132 |
| Tavan zaten eşik altında; geçiş eğitiminden hariç | 188 |
| Güncel gözlem yok/eski | 8 |
| Gelecek gözlem kapsamı yetersiz | 25 |
| Arşiv sonunda tamamlanamayan pencere | 6 |

Etiketlenebilir 17.293 örneğin yaklaşık %0,93'ü pozitiftir. Bu, bu veri ve protokole özgü örnek sıklığıdır; belirli bir an için tahmin edilen olasılık değildir. Örtüşen üç saatlik pencereler nedeniyle satırlar bağımsız değildir.

Ekim–Aralık 2025'te 500 ft altında gözlem yoktur. Çok yıllı veri olmadan bu dönemi tek test kümesi yapmak, modelin düşük tavan olaylarını yakalama yeteneğini ölçemez.

## Sınırlar ve doğrulama

Arşiv gözlem zamanını sağlar; gerçek alım zamanı yoktur. `features.csv` gelecekteki gözlemleri kullanmaz, ancak gecikmiş raporların ve sonradan gelen düzeltmelerin geçmişte erişilebilirliği kanıtlanmış değildir. Veri araştırma amaçlı ilk hazırlık setidir.

21 birim testi; tam 500 ft sınırı, VV, eksik yükseklik, tahmin/açıklama bölümlerinin dışlanması, başka meteorolojik alanlardaki eksikler, yinelenen/çelişen raporlar, üç saat sınırı, gelecekteki veri sızıntısı ve yetersiz gözlem kapsamını kontrol eder. Ham kaynak dosyası SHA-256 ile doğrulanarak veri seti yeniden üretildi.
