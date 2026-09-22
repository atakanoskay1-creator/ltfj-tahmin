# Hata incelemesi ve ek veri kararı

İnceleme tarihi: 22 Eylül 2026. Model/eşik değiştirilmedi. Hata analizi yalnızca 2024 geliştirme döneminde yapıldı; aynı dönemde kalibrasyon ve eşik seçildiğinden bu sonuçlar bağımsız başarı ölçümü değildir. Kod: `python -m ltfj.error_audit`. Ayrıntılar: [hata tablosu](development-error-audit.json).

## Hangi durumlarda zorlanıyoruz?

2024'te 17.233 uygun tahmin zamanında 155 pozitif etiket var. V2, 110'unu yakalıyor; 45'ini kaçırıyor ve 967 yanlış uyarı veriyor. Aşağıdaki gruplar örtüşebilir; sayılar bağımsız hava olayı sayıları değildir.

| Tahmin anındaki koşul | Pozitif zaman | Yakalanan | Kaçırılan | Yanlış uyarı |
|---|---:|---:|---:|---:|
| Sıcaklık–çiy noktası farkı >2°C | 18 | 0 | 18 | 2 |
| Sıcaklık–çiy noktası farkı ≤2°C | 137 | 110 | 27 | 965 |
| Sis/pus kodu var | 47 | 46 | 1 | 143 |
| Yağmur/çisenti kodu var | 17 | 9 | 8 | 186 |
| Sis/pus/yağmur/çisenti kodu yok | 91 | 55 | 36 | 659 |
| Tavan 500–999 ft | 24 | 15 | 9 | 221 |
| Sayısal tavan yok | 94 | 65 | 29 | 477 |
| Rüzgâr >5 kt | 126 | 84 | 42 | 724 |

**Araştırma yorumu:** Mevcut nem yüksek olduğunda model çok sık alarm üretiyor; daha kuru başlangıçtan eşik altına giden 18 pozitif zamanı ise kaçırıyor. Bu, nemin ve rüzgârın gelecekteki değişimini araştırmak için gerekçe. Hataların nedeninin kesin olarak nem taşınımı, sis veya cephe olduğunu bu tablo kanıtlamaz. 2°C ayrımı tanımlayıcıdır; yeni bir alarm kuralı yapılmadı. Sayısal tavan bulunmaması tamamen bulutsuz gökyüzü demek değildir; FEW/SCT gibi tavan oluşturmayan bulutlar da bulunabilir.

Yanlış uyarıların çoğunun bir grupta olması tek başına o grubun daha zor olduğunu göstermez; örnek sayıları da farklıdır. Örneğin sis/pus grubunun uyarı doğruluğu %24,3; yağmur/çisenti grubunun %4,6. Ayrıntılı tabloda paydalar ve oranlar korunmuştur. Tek tek hata zamanları yerel `data/processed/research/development-error-cases.csv` dosyasındadır.

## Ek kaynaklarda gerçekten ne bulundu?

### GFS: öncelikli aday, küçük erişim denemesi yapıldı

[NCAR GDEX d084001](https://gdex.ucar.edu/datasets/d084001/) tarihsel GFS koşularını sunuyor. [Erişim sayfası](https://gdex.ucar.edu/datasets/d084001/dataaccess/) THREDDS erişimini ve hesap gerektiren özel altküme hizmetini ayrı listeliyor. Bu çalışmada herkese açık THREDDS nokta sorgusu kullanıldı; hesap açılmadı.

2023 ve 2024 yılbaşlarının 00 UTC koşularından +6 saatlik tahminler indirildi: 925 hPa sıcaklık, bağıl nem, u/v rüzgârı ve jeopotansiyel yükseklik. İstenen 40,9°N / 29,3°E noktasına servis 41,0°N / 29,25°E hücresini döndürüyor. Bu, havaalanının bire bir ölçümü değildir. İki örnek tüm yıllarda sürekli kapsamı kanıtlamaz. Kaynak URL'leri, zamanlar, birimler, dosya özetleri ve başarısız denemeler [erişim raporunda](archive-probes.json) korunur.

2021 çok değişkenli nokta sorgusu `illegal member name` hatası verdi. Aynı koşunun nem alanı tek değişkenle alınabildi; kod eski dosyalar için değişkenleri ayrı sorgulayarak bu sorunu ele alıyor. Her örneğin geçerlilik zamanı koşu zamanı + tahmin saati ile eşleştirilir; boş veya sonlu olmayan değer kabul edilmez. Bu aşama veri erişim denemesidir, GFS eklenerek eğitilmiş yeni bir model değildir.

[NOAA GFS sayfası](https://www.ncei.noaa.gov/products/weather-climate-models/global-forecast) analiz ve tahmin arşivlerini ayırır. Sıfır saatlik analiz yerine geleceğe yönelik koşu çıktısı kullanılmalı. [Open-Meteo Single Runs](https://open-meteo.com/en/docs/single-runs-api) kolay bir alternatif olmakla birlikte ECMWF için Mart 2024, diğer modeller için Nisan 2026 başlangıcı bildiriyor; mevcut 2021–2023 eğitimini tek başına karşılamıyor.

### TAF: denenen IEM kaynağında LTFJ kaydı çıkmadı

[IEM TAF servisi](https://mesonet.agron.iastate.edu/cgi-bin/request/taf.py?help=) ile LTFJ için hem Ocak 2024 hem 2021–20 Eylül 2026 sorgusu yapıldı. İki sorguda da yalnızca sütun başlığı döndü: **0 kayıt**. Aynı serviste DSM için bir günlük kontrol sorgusu 19 tahmin grubu döndürdü. Bu sonuç LTFJ'de TAF yayımlanmadığını değil, denediğimiz arşiv/sorgu yolunun veri sağlamadığını gösterir. Boş kayıtlar iyi hava tahmini olarak kodlanmadı.

[AWC API](https://aviationweather.gov/data/api/) dünya çapında TAF sunuyor fakat belgelenen geçmiş erişimi 30 gün; çok yıllı eğitim arşivinin yerine geçmez. Ogimet yardım sayfasına bu oturumdaki erişim 403 döndü; kapsam doğrulanamadı. Bu aşamada TAF entegrasyonu tamamlanmış sayılmıyor.

## Bir sonraki deneyin kabul koşulları

1. GFS kapsamı önce farklı ay ve yıllardan olay sonucuna bakılmadan seçilen örneklerle denetlenecek. Ardından yalnızca LTFJ çevresi ve gerekli seviyeler indirilecek; eksikler ayrıca raporlanacak.
2. Sıcaklık/nem/rüzgâr için 925 ve 850 hPa, yüzey değişkenleri ve bulunuyorsa alçak bulut alanları değerlendirilecek. Basınç seviyesi yüksekliği deniz seviyesine göredir; 925 hPa verisi doğrudan 500 ft AGL tavan tahmini değildir.
3. Her özellikte koşu başlangıcı, geçerlilik zamanı, tahmin saati ve varsayılan/yakalanabilen yayımlanma zamanı saklanacak. Koşu başlangıcı yayımlanma zamanı sayılmayacak; dosyanın bugünkü arşiv değiştirilme tarihi de tarihsel erişim kanıtı değildir. Yayımlanma gecikmesi bilinmiyorsa açıkça varsayım olarak kaydedilip duyarlılık analizi yapılacak.
4. METAR-only ve METAR+GFS, aynı uygun zamanlarda ve sabit zaman bölmeleriyle karşılaştırılacak. Eksik GFS zamanları sessizce düşürülüp başarı artırılmayacak. Ölçütler Brier, kalibrasyon, AP ve geliştirmede belirlenmiş eşiklerde yakalama/yanlış alarm yükü olacak.
5. 2025/2026 tekrar kullanıldığında sonuçlar keşifsel geçmiş karşılaştırması olarak sunulacak. Bağımsız doğrulama, sonuçlar görülmeden kaydedilen yeni tahminlerle yapılmalı.

Bu turda canlı toplama veya otomatik alarm başlatılmadı; ek veri model başarısını artırmış gibi bir iddiada bulunulmadı.
