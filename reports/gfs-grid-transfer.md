# GFS aktarım sorunu çözüldü

Tek nokta profil yanıtının değişken atlama sorunu, aynı hücreyi **grid altkümesi** olarak istemekle giderildi. Seçilen hücre 41°N, 29,25°E. Tek istekte sıcaklık, bağıl nem, iki rüzgâr bileşeni ve jeopotansiyel yükseklik alınabiliyor. Dosyalar yaklaşık 7 KB; küresel GRIB dosyaları indirilmiyor.

Eski dosyalarda sıcaklık ile nem/rüzgâr alanları farklı basınç dizilerine bağlı. Okuyucu her alanın kendi basınç koordinatında tam 92500 ve 85000 Pa değerlerini arıyor. Eksik alan, eksik seviye, yanlış birim, yanlış koşu/geçerlilik zamanı, yanlış hücre ve doldurma değerleri reddediliyor. Kaynak URL'si ve SHA-256 dosya özeti korunuyor.

## Gerçekte tamamlanan iş

2021–2026'nın Ocak, Nisan ve Temmuz aylarından seçilmiş 18 koşu için bu aktarım sınandı; kesin sayım [mevsimsel denetim raporunda](gfs-grid-audit.json). Önceki yalnızca nem denemesinden farklı olarak burada beş değişkenin iki basınç seviyesinde bulunması zorunlu.

Tam indirme manifestinin ilk sekiz dosyası da indirildi: 31 Aralık 2020 18 UTC ve 1 Ocak 2021 00 UTC koşularının +6/+9/+12/+15 saatleri. Mevsimsel denetim dosyaları aynı önbellekte tekrar kullanılabiliyor. [Güncel manifest ilerlemesi](gfs-grid-progress.json) tamamlanan ve kalan dosya sayılarını verir. **Tam veri seti henüz indirilmedi; GFS eklenerek model eğitilmedi.**

Tek değişken/tek seviye yöntemi 334.240 istek gerektirirken grid yöntemi 33.424 isteğe indiriyor. Bu hâlâ uzun süren bir iş; tamamı bu turda başlatılmış veya arka planda sürüyormuş gibi kabul edilmemeli. İndirici sınırlı partiler halinde çalışır ve doğrulanmış dosyaları yeniden indirmez.

## METAR ile eşleştirme hazır

Her tahmin zamanı için koşu, açıkça belirtilmiş 6 saatlik yayımlanma gecikmesi varsayımıyla seçilir. O koşunun tahmin alanlarından mevcut zaman ve üç saat sonraki değerler hesaplanır; üç saatlik model adımları arasında doğrusal ara değer alınır. Bu işlem gelecekteki gözlemleri kullanmaz. Bu 20 özellik mevcut modelin girdilerine henüz eklenmedi.

Gerekli dosya yoksa durum `missing_required_forecast` olur. Daha yeni koşu, ölçülmüş gelecek hava veya sıfır ile doldurulmaz. 9 ve 12 saat gecikmelerin kapsamı da ayrıca hesaplanır. [Özellik kapsamı](gfs-feature-coverage.json), yüz bin civarındaki tahmin zamanının henüz çok küçük kısmının eşleştiğini gösterir. Bu küçük örnekle performans hesabı yapılmadı. Gecikmeler gerçek yayımlanma kaydıyla doğrulanmış değildir.

## Tekrar üretim

```sh
python -m ltfj.gfs_download --audit
python -m ltfj.gfs_download --limit 48
python -m ltfj.gfs_download --limit 0
python -m ltfj.gfs_features
python -m unittest discover -s tests -q
```

İkinci komut her çalıştırmada en fazla 48 henüz doğrulanmamış dosyayı dener. Üçüncü komut yalnızca önbelleği denetleyip ilerleme raporunu yeniler; ağ isteği yapmaz. Ham dosyalar ve türetilmiş özellikler yerelde; raporlar, kod ve testler Git'tedir. Kalan iş tam kapsamın indirilmesi, eksiklerin denetlenmesi ve aynı zaman bölmeleriyle METAR-only / METAR+GFS karşılaştırmasıdır.
