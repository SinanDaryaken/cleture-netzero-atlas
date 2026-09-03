# ADR-0010 — AIB residual mix ve doğrudan CO₂ semantiği

## Durum

Kabul edildi — 2026-08-27

## Bağlam

AIB, Avrupa elektrik disclosure sistemi için yıllık residual mix workbook'u yayımlar.
2025 sonuçları Version 1.0 olarak 26 Mayıs 2026 tarihinde hazırlanmıştır. Ülke residual
mix'i, tüketici adına Guarantee of Origin iptal edilmemiş untracked elektrik için
kullanılır. Kaynak CO₂ değerleri yalnız direct emissions içerir; lifecycle, biogenic
carbon ve toplam CO₂e değildir. Austria, Switzerland ve Netherlands full disclosure
uyguladığı için workbook'ta residual mix değeri `NA` taşır.

Workbook'un özet `Residual Mixes` sheet'inde formatlanmış bazı hücreler güvenilir
sayısal değer olarak okunmayabilir. CO₂ ve radioactive waste için ayrıca ayrılmış `CO2`
ve `RW` sheet'leri kaynak sözleşmesinin sayısal otoritesidir.

## Karar

- Landing page her kontrolde çözülür; en yeni annual XLSX, takvim yılı ve metodoloji
  version'ı dataset identity olarak alınır.
- Parser `Residual Mixes`, `CO2` ve `RW` sheet/header sözleşmesini exact doğrular ve ülke
  kümelerini çapraz kontrol eder. Şema değişimi yeni parser version gerektirir.
- Canonical factor yalnız `CO2` sheet'indeki residual mix CO₂ kolonundan üretilir.
  `gCO2/kWh`, deterministik olarak `kgCO2/kWh` birimine çevrilir.
- Kayıt `factor_value_kind=co2_only` taşır; `gases.co2` doldurulur, `gases.co2e` boş
  bırakılır ve varsayılan CO₂e matching'e girmez.
- Fuel shares, untracked share ve radioactive waste factor değildir; methodology details
  içinde source bağlamı olarak korunur.
- Valid değeri olan 31 ülke country-specific origin ve applicability taşır. Full
  disclosure nedeniyle `NA` olan AT, CH ve NL parsed history'de kalır fakat factor
  üretilmez.
- European Attribute Mix ayrı bir dengeleme girdisidir; country residual factor veya
  continental fallback gibi sunulmaz. İleride ayrı calculation model ile ele alınır.
- AIB FAQ veri kullanımına attribution ile izin verir. Commercial/API/raw redistribution
  açık olmadığı için license quality gate otomatik publish'i durdurur.

## Sonuçlar

AIB kayıtları ülkeye özgü elektrik residual mix coverage'ı sağlar, fakat direct CO₂
değerleri toplam CO₂e gibi yanlış eşleşmez. Yıllık workbook yapısı değiştiğinde ingestion
sessizce bozuk değer üretmek yerine fail eder. İlk dataset license ve initial-dataset
review nedenleri çözülmeden production API'ye yayınlanmaz.
