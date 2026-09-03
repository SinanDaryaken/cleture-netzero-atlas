# ADR-0031: Database-backed multilingual concepts ve calculation profiles

## Durum

Kabul edildi — 2026-08-28.

## Bağlam

Factor adları source terminolojisini taşır; aynı activity farklı dil ve synonym'lerle
aranabilir. Metinsel benzerlik tek başına corporate carbon, LCA, PCF, CBAM veya freight
hesabında kullanılabilirlik anlamına gelmez.

## Karar

- English canonical concepts oluşturulur; factor'lar concept ID'ye versioned mapping ile
  bağlanır.
- Translation ve synonym'ler PostgreSQL `atlas_concept_labels` tablosunda language, kind,
  method/model, confidence, review status ve registry version ile saklanır. Original source
  ve factor text overwrite edilmez.
- İlk search stack PostgreSQL full-text search, exact concept short-circuit ve GiST KNN
  `pg_trgm` fallback olur. OpenSearch/vector yalnız benchmark ihtiyacı kanıtlarsa eklenir.
- Search context ister; match/resolve calculation profile ister.
- Search eligibility ve calculation eligibility ayrı kararlar ve reason code'lar üretir.
- Resolve entity type, factor kind, intended use, methodology scope, unit, geography,
  quality, license ve publication kapılarını geçmeyen kaydı seçmez.

## Sonuçlar

Atlas merkezi veri deposu olmaya devam eder ancak veriyi calculation context'e göre açar.
Translation modeli yalnız draft label üretebilir; unreviewed label tek başına calculation
kararına dönüşmez. Ranking deterministik ve policy-version'lıdır.
