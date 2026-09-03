# ADR-0024 — ÖKOBAUDAT module-GWP LCA sonuç sınırı

## Durum

Kabul edildi — 28 Ağustos 2026.

## Bağlam

ÖKOBAUDAT, BMWSB/BBSR tarafından bina yaşam döngüsü değerlendirmesi için sunulan living
bir ILCD+EPD veri stokudur. Güncel 2024-II CSV exportu ürün/veri seti başına birden çok
EN 15804 lifecycle module ve scenario satırı; A1 ve A2 çevresel göstergeleri, beyan
birimi, coğrafya, EPD owner/registration ve teknik metadata taşır. CSV'deki her çevresel
gösterge bir emisyon faktörü değildir ve source açıkça ürün LCA'sı hazırlamak için
tasarlanmadığını belirtir.

## Karar

- `sources/oekobaudat` yalnız resmî 2024-II data-stock UUID'sinin nokta ondalık ayırıcılı
  CSV exportunu ingest eder. Stok sentetik annual release'lere bölünmez; content SHA-256
  living snapshot değişimini belirler.
- Canonical scope, her data set + record version + module + scenario için publisher'ın
  `GWP` (A1) veya `GWPtotal (A2)` sonucudur. Diğer çevresel göstergeler immutable raw
  snapshotta kalır; emission factor diye çoğaltılmaz.
- Sonuçlar `LCA_RESULT`, `CO2E_TOTAL`, `CHARACTERIZATION` olarak modellenir ve default
  matching'e uygun değildir. Negatif module D ve diğer LCA kredi sonuçları korunur;
  avoided-emissions inventory factor'a çevrilmez.
- Beyan sonucu `Bezugsgroesse` miktarına bölünerek bir `kg`, `m²`, `m³`, `m`, `piece`,
  `kg·km`, `MJ` veya `year` başına normalize edilir. Original miktar/birim provenance ve
  methodology'de tutulur. Miktarı ya da birimi bulunmayan kayıt tahmin edilmez.
- A2 biogenic, fossil ve land-use/land-use-change bileşenleri publisher totalini yeniden
  hesaplamak için kullanılmaz; normalize bileşen metadata'sı olarak korunur.
- Coğrafyalar ISO ülke, Europe/region ve global olarak açıkça eşlenir. Europe datasetleri
  country-specific yapılmaz; bilinmeyen kod proxy ya da global varsayılmaz.
- Kullanım koşulu yalnız değiştirilmemiş verinin kaynak gösterilerek ücretsiz dağıtımına
  açık izin verir. Raw redistribution bu koşulla mümkündür; normalize edilmiş API çıktısı
  ayrı izin olmadan external distribution'a açılmaz.

## Sonuçlar

ÖKOBAUDAT 2024-II, 4.286 data setten 44.013 izlenebilir lifecycle-module GWP sonucu
üretir. Bunların 14.897'si country-modelled, 27.541'i regional/continental ve 1.575'i
globaldir; hiçbir kayıt klasik emission-factor matching havuzuna girmez. Total GWP'si
olmayan 700 ve beyan referansı olmayan 6 satır açık exclusion metriği olarak görünür.
Dataset license ve initial-dataset review'u owner-approved/published; aynı snapshotın
tekrar koşusu `NO_CHANGE` sonucundadır.
