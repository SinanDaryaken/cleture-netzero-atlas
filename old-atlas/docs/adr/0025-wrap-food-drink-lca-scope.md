# ADR-0025 — WRAP Food & Drink LCA sonuç kapsamı

## Durum

Kabul edildi — 28 Ağustos 2026.

## Bağlam

WRAP Food & Drink Emission Factor Database v2.0 aynı workbook içinde HESTIA, curated
refined ve geniş full veri katmanları; stage toplamları, functional-unit conversions,
Land Sector and Removals değerlendirmesi ve upstream kaynak kataloğu sunar. Bu katmanlar
aynı amaçla hazırlanmış eşdeğer satır listeleri değildir. User Guide, karşılaştırılabilir
ve ayrıntılı HESTIA verisini ilk tercih; UK relevance, GPC/LSRG uyumu, kalite ve lifecycle
kapsamıyla seçilmiş refined katmanı fallback olarak tarif eder. Full katman ise çok daha
geniş alternatif upstream kayıt havuzudur.

WRAP ayrıca CarbonWARM2 yayımlar. CarbonWARM2 atık yönetimi seçeneklerinin relative-net
etkisini karşılaştırır; kurumsal footprint veya GHG Protocol Scope 3 inventory factor seti
değildir. Aynı publisher'a ait olması bu iki metodolojiyi tek canonical kaynak yapmaz.

## Karar

- `sources/wrap` resmî v2.0 XLSX workbook'u content SHA-256 ile versioned database
  snapshot'ı olarak ingest eder. Workbook table version 1.2 ve 27 Mart 2024 release tarihi
  provenance'da ayrı tutulur; sentetik annual release üretilmez.
- Canonical scope, `emissions_database_hestia` içindeki yalnız `GWP100` / `IPCC2021` /
  `kg CO2e` satırları ile `emissions_database_refined` içindeki aggregate satırlardır.
  Diğer çevresel impacts ve full alternatif havuzu raw snapshotta kalır.
- 722 HESTIA ve 418 refined kayıt birbirinin yerine ezilmez. Her satır source-native veri
  katmanı, upstream database, ürün, coğrafya, production system, functional unit,
  lifecycle stage, belirsizlik/kalite ve workbook koordinatıyla ayrı provenance taşır.
- Sonuçlar `LCA_RESULT`, `CO2E_TOTAL`, `CHARACTERIZATION` olarak modellenir. Bunlar klasik
  activity × EF inventory matching'e otomatik girmez; negatif sonuçlar avoided-emission
  factor'a çevrilmeden kaynak LCA sonucu olarak korunur.
- Fonksiyonel birimler yalnız workbook'un ifade ettiği `kg` ve litre bazına normalize
  edilir. Karmaşık açıklama silinmez; methodology'de original functional unit tutulur.
- Applicability coğrafyası ISO ülke veya global olarak açıkça eşlenir. Origin geography
  ayrıca korunur ve sourcing region, applicability ülkesine dönüştürülmez.
- CarbonWARM2 WRAP Food & Drink source'una karıştırılmaz. İleride ingest edilirse
  reference/avoided comparison metriği olarak ayrı source ve ayrı kullanım sınırı ister.
- Workbook copyright notice ve WRAP website terms nedeniyle external commercial, API,
  raw, hosted, adapted, derivative ve redistribution izinleri kapalıdır. UK dışı kullanım
  için specific WRAP permission gereksinimi manifestte açıkça korunur.

## Sonuçlar

WRAP v2.0 toplam 1.140 izlenebilir food/drink climate LCA sonucu üretir: 1.006
country-modelled, 134 global; 1.130 kg ve 10 litre fonksiyonel birimlidir. Sekiz negatif
sonuç review sebebidir ve hiçbir kayıt default matching'e uygun değildir. Dataset lisans
ve negatif-LCA review'ları owner-approved olarak local reference stack'te published;
aynı SHA-256 snapshot'ın ikinci koşusu `NO_CHANGE` sonucundadır.
