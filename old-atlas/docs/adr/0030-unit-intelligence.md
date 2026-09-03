# ADR-0030: Canonical unit ontology ve factor conversion

## Durum

Kabul edildi — 2026-08-28.

## Bağlam

Atlas factor unit'leri enerji, kütle, hacim, para, ürün ve transport-work gibi farklı
dimension ve semantic qualifier'lar taşır. Basit multiplier tablosu activity quantity ile
factor denominator dönüşümünün yönünü karıştırır; farklı dimension'lar arasında gerekli
physical bridge bilgisini gizler.

## Karar

- Versioned canonical unit definition ve alias registry kullanılır; optional UCUM code
  referanstır, Atlas canonical code otoritedir.
- Original factor/activity unit korunur; parsed numerator/denominator expression ayrı
  tabloda tutulur.
- Activity ve factor conversion ayrı domain operasyonlarıdır. Factor denominator ratio'su
  reciprocal uygulanır.
- Sonuç yalnız exact, conditional veya incompatible olabilir.
- Conditional dönüşüm density, calorific value, occupancy, load veya exchange-rate gibi
  provenance-bearing parametre ister.
- Hesaplamalar `Decimal` ile yapılır; qualifier uyuşmazlığı exact sayılmaz.

## Sonuçlar

Unit compatibility matching'in hard eligibility girdisi olur. Parse edilemeyen source
parameter unit'leri observation/audit katmanında korunur; strict resolve için factor adayı
olmaz. Registry backfill'i idempotent bulk SQL ile yeniden üretilebilir.
