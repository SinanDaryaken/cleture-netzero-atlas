# Agent Memory ve Codebase Memory işletim planı

## Agent Memory

Project key her istemcide `cleture-atlas` olmalıdır. İş başında tek, dar kapsamlı recall
yapılır. Memory; ADR'lerdeki seçimin kendisini tekrar etmek için değil, kararın arkasında
repo üzerinden kolay çıkarılamayan gerekçe veya operasyonel gotcha varsa kullanılır.

Kaydedilecek örnekler:

- belirli bir kaynakta ETag'in güvenilmez olduğu ve neden SHA256 fallback seçildiği,
- parser'ın belirli workbook sürümündeki non-obvious davranışı,
- kullanıcı tarafından kalıcı olarak tercih edilen review/quality politikası.

Kaydedilmeyecekler: task ilerlemesi, test çıktıları, secret'lar, koddan okunabilen sınıf
ve endpoint listeleri.

## Codebase Memory

- Proje adı: `cleture-atlas`.
- Büyük scaffold/migration/parser eklemelerinden sonra indeks freshness kontrol edilir.
- Mimari keşif ve impact analysis graph-first yapılır.
- Parser ve mapping gibi YAML/fixture ağırlıklı alanlarda graph yeterli değilse hedefli
  `rg`/doğrudan okuma kullanılır.
- Operasyon öncesi kullanılan tüm aday kod yolları tek coverage çağrısında doğrulanır.
- `.codebase-memory/graph.db.zst` ancak ekipte artifact paylaşımı kararlaştırıldığında
  repository'ye alınır; varsayılan olarak local cache kullanılır.
