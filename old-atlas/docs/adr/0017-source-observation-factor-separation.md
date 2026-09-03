# ADR-0017: Source observation ile curated factor ayrımı

## Durum

Kabul edildi — 2026-08-28.

## Bağlam

UNFCCC/TÜİK CRF ve CRT submission'ları activity data, reported emissions,
gas-specific implied emission factors ve calculation parameter hücreleri üretir. Yedi
submission'ın 297.590 numeric hücresini `atlas_factor_versions` içinde tutmak provenance
sağlasa da public factor sayısını ve matching semantiğini bozar. Observation sayısı,
logical factor sayısı ve temporal factor version sayısı aynı kavram değildir.

## Karar

Atlas üç ayrı veri katmanı kullanır:

```text
Immutable raw asset
  ↓
atlas_source_observations
  ↓ deterministic curation
atlas_factors → atlas_factor_versions
```

- `atlas_source_observations`, source-native numeric değeri dataset version, raw asset,
  workbook/sheet/row ve parser/mapping provenance ile saklar.
- `atlas_factors`, yalnız stable logical curated factor kimliklerini taşır.
- `atlas_factor_versions`, reference-time ve system-time tarihçesini tutar.
- Activity data ve emission result observation olarak kalır.
- Gas-specific implied factor'lar ancak denominator, unit, gas, GWP ve boundary açıkça
  çözülebildiğinde `co2e_total + inventory` factor'a dönüştürülür.
- Belirsiz kayıtlar için factor üretilmez; exclusion metriği tutulur ve raw observation
  yeniden işlenebilir kalır.

## Sonuçlar

- Public factor API ve coverage sayımları gerçek curated factor seviyesine iner.
- 297.590 source observation kaybolmadan audit ve parser/mapping reprocessing korunur.
- Bir factor birden fazla gas observation'ına component provenance ile geri izlenebilir.
- Yeni source adapter'ları observation katmanını kullanabilir; mevcut doğrudan canonical
  factor üreten adapter'ların sözleşmesi değişmez.
