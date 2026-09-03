# ADR-0007 — Geographic Coverage Engine

## Durum

Kabul edildi — 2026-08-27

## Bağlam

Bir factor'ın kaynak ülkesi, bilimsel kökeni, doğrudan uygulanabildiği coğrafya ve
fallback/proxy olarak kullanılabildiği coğrafya aynı kavram değildir. Yalnız country
code filtresi bu farkları açıklamaz ve global faktörlerin yerel faktör gibi seçilmesine
yol açabilir.

## Karar

Her canonical factor `origin_geography`, `applicable_geographies`, `geography_level`,
`geographic_specificity` ve `geographic_fit_type` taşır. Fit türleri country-specific,
country-modelled, regional, continental, global ve proxy'dir.

Fallback sırası geography configuration'da versiyonlanır. Exact geography yoksa match
sonucu seçilen factor geography'sini, fit türünü, skoru, `fallback_used=true` bilgisini
ve warning'i açıkça döndürür. Source manifestleri kendi declared coverage alanlarını
taşır; coverage matrix yalnız published, varsayılan matching'e uygun factor version'ları
üzerinden hesaplanır.

## Sonuçlar

- Geography matching sonucu açıklanabilir ve müşteri politikasına göre konfigüre edilebilir.
- Global veya proxy seçim sessizce yerel faktör gibi sunulmaz.
- Coverage sayıları origin değil applicability ve fit türü kırılımında raporlanır.
- Publisher ülkesi hiçbir zaman otomatik applicability oluşturmaz.
