# NetZero Atlas roadmap

## ADEME Base Carbone pilotu

### Aşama 1 — Release discovery

- [x] Resmî Data Fair dataset kimliğini doğrula.
- [x] Finalized durumunu, satır sayısını, dosya kimliğini ve açık lisansı doğrula.
- [x] Portal metadata değişikliklerinden etkilenmeyen release revision üret.
- [x] Veri indirmeden ve persist etmeden inceleme komutu sun.
- [x] Başarı, lisans değişimi ve bilinmeyen source davranışlarının testlerini yaz.
- [x] Yazılan testleri kullanıcı talep ettiğinde çalıştır ve sonucu geçici dosyaya yaz.

### Aşama 2 — Immutable raw acquisition

- [x] Source/release/run/raw asset çalışma tablolarını oluştur.
- [x] Orijinal CSV için MD5, dosya boyutu ve SHA-256 doğrulaması uygula.
- [x] Dosyayı content-addressed key ile `atlas-raw` bucket'ına yaz.
- [x] Aynı release ve checksum için DB unique constraint ile idempotency sağla.
- [x] Acquisition başarı, checksum hatası ve idempotency testlerini yaz.
- [x] Yazılan testleri kullanıcı talep ettiğinde çalıştır ve sonucu geçici dosyaya yaz.

### Aşama 3 — Parse ve source inventory

- [x] 67 kolonluk CSV sözleşmesini versiyonla ve SHA-256 fingerprint ile sabitle.
- [x] UTF-8 BOM ve Windows-1252/CP1252 fallback davranışını uygula.
- [x] Bütün Elément/Poste/archive/source-data satırlarını kayıpsız sakla.
- [x] Duplicate geçerli factor ID, kolon kayması, satır sayısı farkı ve geçersiz
  decimal değerlerini fail-closed ele al.
- [x] Content-addressed NDJSON parsed artifact'i `atlas-processing` içinde üret.
- [x] Parser, persistence, failure ve idempotency testlerini yaz.
- [x] Yazılan testleri kullanıcı talep ettiğinde çalıştır ve sonucu geçici dosyaya yaz.

### Aşama 4 — Mapping ve normalization candidate

- [x] Source-specific normalizer ile source-agnostic candidate/package sınırını
  mimari karar olarak sabitle.
- [x] NetZeroAdmin'ın commitlenmiş package ve entity V1 şemalarını provenance ve
  SHA-256 doğrulamasıyla pinle.
- [x] Eksik relationships/findings/source-diff record sözleşmeleri için package
  üretimini fail-closed kapat.
- [ ] Canonical unit snapshot/lookup sözleşmesini NetZeroAdmin ile tanımla.
- [ ] Canonical geography lookup sözleşmesini Logi ile tanımla.
- [x] ADEME `SourceNormalizationAdapter` ve registry'sini oluştur.
- [x] ADEME `Elément` ana candidate ve `Poste` decomposition modelini üret.
- [x] Parsed artifact'ten normalization input stream'i ve idempotent çalışma
  kayıtlarını oluştur.
- [ ] Taxonomy mapping proposal ve insan review kaydını oluştur.
- [x] Negatif değerleri yalnız işaretine göre avoided-emission olarak işaretleme.
- [x] Lifecycle decomposition ve gaz bileşenlerini ayrı component olarak koru.

### Aşama 5 — Validation, diff ve candidate package

- [ ] NetZeroAdmin'da relationships/findings/source-diff record şemalarını
  sürümle ve Atlas contract snapshot'ına ekle.
- [x] Source-agnostic RFC 8785 canonical JSON ve candidate `record_sha256`
  üreticisini oluştur.
- [x] Final candidate entity'yi pinned JSON Schema'ya karşı doğrula.
- [ ] Quality, license, geography, unit, temporal ve provenance kapılarını uygula.
- [ ] Field-level release diff üret.
- [ ] Sürümlü manifest ve immutable candidate package üret.
- [ ] Paketi NetZeroAdmin staging sınırına teslim et; canonical publish yapma.
