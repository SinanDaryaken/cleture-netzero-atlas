# ADR-0021 — EU CBAM default-values ve benchmark semantiği

## Durum

Kabul edildi — 28 Ağustos 2026.

## Bağlam

EU CBAM definitive regime için Avrupa Komisyonu ülke bazlı embedded-emissions default
değerlerini ve mal benchmarklarını ayrı XLSX dosyalarında yayımlar. XLSX dosyaları
bilgilendirme amaçlıdır; bağlayıcı değerler Commission Implementing Regulation (EU)
2025/2621'in, (EU) 2026/1740 ile düzeltilmiş halinde; benchmarklar ise (EU) 2025/2620'de
yer alır. Default tablo direct, indirect ve publisher total sütunlarını; benchmark tablosu
farklı hesaplama amaçlarına sahip Column A `BMg*` ve Column B `BMg` değerlerini taşır.

## Karar

- Source-specific kontrat `sources/cbam` altında kalır. Düzeltilmiş default-values v2 ve
  benchmark v1 dosyaları resmî URL'lerden alınarak iki member'lı, deterministik ZIP
  acquisition bundle oluşturulur; dosyalar repository'ye vendored edilmez.
- Numeric default total satırları `EMBODIED_EMISSION_FACTOR + CO2E_TOTAL +
  CALCULATION_INPUT` olarak saklanır. Bunlar corporate inventory için generic default
  matching havuzuna girmez.
- Kaynağın total sütunu canonical değerdir. Direct ve indirect sütunları yuvarlanmış
  methodology ayrıntılarıdır; yeniden toplanıp publisher total'ı overwrite etmez.
- `tCO2e/tonne of good` sayısal olarak eşdeğer `kgCO2e/kg` birimine normalize edilir.
- Ülke sheet'leri ISO alpha-2 geography ve `country_modelled` fit alır. “Other Countries
  and Territories” ile Annex IV highest defaults ülke değeri gibi sunulmaz; sırasıyla
  `CBAM_OTHER` ve `CBAM_ANNEX_IV` custom origin'li, global-applicable açık proxy kalır.
- Benchmark Column A, actual-data/free-allocation hesabındaki process-related `BMg*`;
  Column B default `BMg` calculation parameter'dır. İkisi de `SourceObservation` olarak
  saklanır, canonical factor sayısını şişirmez. `(1)` göstergesi 2026–2027, `(2)`
  2028–2030, göstergesiz route 2026–2030 geçerlilik attribute'u taşır.
- Düzenlemedeki sector/year markup base default değere ingest sırasında uygulanmaz.
  Cement, iron/steel, aluminium ve hydrogen için 2026 `%10`, 2027 `%20`, 2028 sonrası
  `%30`; fertilisers için 2026 sonrası `%1` schedule methodology'de
  `markup_not_applied=true` ile korunur. Uygulama, ilgili CBAM hesabının sorumluluğudur.
- CBAM certificate price bu source phase'ine dahil edilmez; emisyon/default-factor
  kaynağı ile dönemsel finansal fiyat serisi ayrı veri sözleşmeleridir.
- European Commission legal notice uyarınca EU-owned web content CC BY 4.0 attribution
  ve değişiklik bildirimiyle yeniden kullanılabilir. Manifest attribution zorunluluğunu
  ve workbook'un legal-text yerine geçmediği kısıtını açıkça kaydeder.

## Sonuçlar

Atlas ülke defaultlarını, fallback proxy'leri ve yasal highest-default değerlerini
birbirine karıştırmaz. Benchmarklar inventory emission factor diye eşleşmez; yıl bazlı
markup sessizce iki kez uygulanamaz. Her değer bundle member URL/checksum ile workbook
sheet/row/column provenance'ına ve bağlayıcı legal act'e geri izlenebilir.
