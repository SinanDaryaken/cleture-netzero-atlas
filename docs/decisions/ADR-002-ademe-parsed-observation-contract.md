# ADR-002: ADEME parsed observation ve artifact sözleşmesi

- Durum: Kabul edildi
- Tarih: 2026-09-04

## Bağlam

ADEME Base Carbone V23.6 raw exportu noktalı virgülle ayrılmış 67 kolon ve 18.616
kayıt içerir. Resmî dosya Windows-1252 encoding'indedir; aynı sözleşmenin UTF-8 veya
UTF-8 BOM ile üretilmiş fixture/exportları da güvenli biçimde işlenebilmelidir.
`Elément` toplam satırları ile bunlara ait `Poste` decomposition satırları aynı element
ID'sini paylaşır. Dolayısıyla bütün satırlarda element ID benzersizliği istemek geçerli
kaynak semantiğini yanlışlıkla reddeder.

Parse katmanının görevi canonical factor üretmek değil, immutable raw nesneden kayıpsız,
sürümlü ve yeniden üretilebilir observation'lar çıkarmaktır. Mapping, normalization ve
publish sonraki kapılara aittir.

## Karar

- Parser `ademe.base-carbone.v23.6` şema sürümünün 67 kolon adını ve sırasını exact
  doğrular; kolon birleşiminin SHA-256 fingerprint'ini artifact metadata'sında taşır.
- Encoding başlıktan belirlenir. UTF-8 BOM kaldırılır; geçerli UTF-8 doğrudan korunur,
  aksi durumda Windows-1252 açıkça UTF-8'e dönüştürülür. UTF-8 olarak sınıflanan bir
  dosyada sonraki invalid byte sessizce düzeltilmez.
- Her non-empty CSV kaydı source record number, type, element ID/type/status, 67 alanın
  tamamı ve deterministic row SHA-256 ile `parsed_observations` tablosunda saklanır.
- Aynı observation'lar UTF-8 NDJSON biçiminde geçici olarak üretilir ve dosya SHA-256'sını
  içeren content-addressed key ile private `atlas-processing` storage'a yazılır.
- Numeric source alanları decimal string olarak korunur; yalnız syntax doğrulaması
  yapılır. Binary float dönüşümü yapılmaz.
- Duplicate kontrolü yalnız valid factor `Elément` satırları için element ID üzerinde
  uygulanır. `Poste`, archived ve source-data satırları elenmez.
- Header/kolon kayması, metadata row-count farkı, zorunlu kimlik eksikliği, invalid
  encoding, invalid decimal veya duplicate valid factor kimliği kalıcı source contract
  hatasıdır ve hiçbir partial observation commit edilmez.
- Parse idempotency key'i source code, release revision ve parser version'dan üretilir.
  Aynı raw asset ve parser version ikinci bir artifact veya observation seti oluşturmaz.

## Sonuçlar

Parsed katman kaynak semantiğinin tamamını korurken normalization kararlarından bağımsız
kalır. Parser davranışı veya çıktı sözleşmesi değişirse parser version artırılmalıdır.
ADEME şeması değişirse yeni schema/parser version açıkça geliştirilmeden ingestion devam
etmez. NetZeroAdmin veya tenant veritabanlarına parse aşamasında bağlantı kurulmaz.
