# ADR-0011 — Bitemporal dataset ve factor history

## Durum

Kabul edildi — 2026-08-27

## Bağlam

Bir factor'ın referans yılı, kaynak yayın tarihi, gerçek dünyadaki geçerlilik dönemi ve
Atlas tarafından bilindiği dönem aynı zaman ekseni değildir. Yıllık datasetleri yalnız
`reference_year` ile saklamak, kaynak geçmiş bir yılı revize ettiğinde eski değeri ya
overwrite eder ya da “belirli tarihte ne biliniyordu?” sorusunu cevapsız bırakır.

Mevcut `atlas_factors` tablosu logical entity'yi, `atlas_dataset_versions` ve
`atlas_factor_versions` tabloları immutable version kayıtlarını zaten ayırır. Bu nedenle
yeni ve paralel bir entity tablosu yerine mevcut ayrım temporal sözleşmeyle tamamlanır.

## Karar

- `atlas_factors.logical_id` kaynaktaki mantıksal varlığın kalıcı kimliğidir.
- Her yıllık release ayrı dataset version, her factor değeri ayrı factor version olur.
- Business time alanları birbirinden ayrılır:
  - `reference_year`
  - `valid_from / valid_to` (`valid_to` exclusive)
  - `source_published_at`
- System time alanları birbirinden ayrılır:
  - `retrieved_at`
  - `system_effective_from / system_effective_to` (`effective_to` exclusive)
  - `superseded_at`
- Workflow status (`review_required`, `published`, `rejected`) ile temporal version status
  (`candidate`, `current`, `superseded`, `rejected`) farklı alanlardır.
- Yeni bir version yayınlandığında yalnız aynı logical factor + reference year + validity
  period dilimindeki current version kapanır. Farklı yıllar birbirini supersede etmez.
- Replacement version `supersedes_version_id` ile önceki version'a bağlanır. Eski kayıt
  silinmez veya güncel değerle overwrite edilmez.
- Dataset version supersession aynı release year içinde çalışır. Historical backfill ile
  2020 release'inin sonradan alınması 2026 current dataset pointer'ını geriye taşımaz.
- Public factor sorgusu varsayılan `current` truth döndürür. `mode=as_known_at` ve
  `known_at` belirli system-time anındaki version'ı seçer.
- `GET /v1/datasets/{id}/versions` dataset release/revision zincirini; factor versions
  endpoint'i factor zincirini sunar.

## Sonuçlar

Atlas hem “bugün bildiğimiz en güncel 2022 factor” hem de “31 Aralık 2024 tarihinde
Atlas'ta bilinen 2022 factor” sorularını cevaplayabilir. Historical backfill, source
revision ve parser reprocessing aynı immutable temporal model içinde audit edilebilir.
Range partitioning ilk aşamada eklenmez.
