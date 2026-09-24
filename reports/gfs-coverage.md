# GFS kapsamı ve zaman eşleştirmesi

24 Eylül 2026 çalışması. 2021–2026 yıllarının 15 Ocak, 15 Nisan ve 15 Temmuz 00 UTC koşularında +6 saat, 925/850 hPa bağıl nem sorgulandı. Tarihler olay etiketlerine bakılmadan seçildi. **36/36 küçük örnek başarıyla alındı.** Zaman, birim, sonlu değer, nem aralığı ve dönen hücrenin konumu kontrol edildi. Bu, tam arşiv kapsamının veya diğer değişkenlerin sürekli varlığının kanıtı değildir. [Ayrıntılar ve kaynak özetleri](gfs-coverage.json).

## Zaman eşleştirmesi

Koşunun başlangıcı erişim zamanı kabul edilmiyor. İlk hazırlıkta 6 saat gecikme varsayılıyor; 9 ve 12 saat duyarlılık senaryoları planlandı. Gecikme henüz tarihsel yayımlanma kayıtlarıyla doğrulanmadı. Örneğin 06 UTC tahmini için 06 UTC koşusu kullanılamaz; 00 UTC koşusu kullanılabilir varsayılır. Eski veya gelecekte başlayan koşu reddedilir. Hedefe ait üç saatlik GFS adımları ayrıca hesaplanır; METAR gözlemleri gelecekteki özelliklere karıştırılmaz.

## Tam indirme kapsamı

Etiketleri okumadan 100.272 tahmin zamanı için yerel dosya manifesti üretildi. Gerekli birleşim **33.424 farklı koşu/tahmin saati dosyası**. İki seviye ve beş değişkeni ayrı sorgulamak **334.240 istek** gerektiriyor. Bu yük başlatılmadı. İlk gerekli koşu 31 Aralık 2020 18 UTC; yalnızca 2021'den indirmek başlangıç zamanlarını eksik bırakır. [Plan özeti](gfs-acquisition-plan.json).

Bir örnekte beş değişkeni birlikte küçük NetCDF düşey profilinde istemek sınandı. HTTP başarılı ve dosya okunabilir olmasına rağmen yalnızca sıcaklık ve jeopotansiyel yükseklik döndü; nem ve iki rüzgâr bileşeni yoktu. **Yanıt reddedildi.** [Deneme kanıtı](gfs-profile-check.json). Bu taşıma yöntemi doğrulanmadan toplu indirme yapılmamalı; koordinatları uyumlu değişken grupları veya ayrı profiller sınanmalı.

Mevcut model değişmedi; GFS ile yeniden eğitim yapılmadı. Sonraki teknik adım, bütün değişken ve seviyeleri koruyan toplu veri aktarımını doğrulamak. Sonrasında tam kapsam indirilecek ve METAR-only / METAR+GFS aynı tahmin zamanlarında karşılaştırılacak.

Tekrar üretim: `python -m ltfj.gfs_coverage` (ağ erişimi), `python -m ltfj.gfs_plan` (yerel features.csv), `python -m ltfj.gfs_profile_check` (kaynak URL'si raporda kayıtlı yerel NetCDF denemesi). Birleştirme kontrolleri birim testlerindedir. Ham veriler yerel, araştırma raporları Git'tedir.
