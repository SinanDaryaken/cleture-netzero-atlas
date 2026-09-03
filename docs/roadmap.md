# NetZero Atlas roadmap

## ADEME Base Carbone pilotu

### Aşama 1 — Release discovery

- [x] Resmî Data Fair dataset kimliğini doğrula.
- [x] Finalized durumunu, satır sayısını, dosya kimliğini ve açık lisansı doğrula.
- [x] Portal metadata değişikliklerinden etkilenmeyen release revision üret.
- [x] Veri indirmeden ve persist etmeden inceleme komutu sun.
- [x] Başarı, lisans değişimi ve bilinmeyen source davranışlarının testlerini yaz.
- [ ] Yazılan testleri kullanıcı talep ettiğinde çalıştır ve sonucu geçici dosyaya yaz.

### Aşama 2 — Immutable raw acquisition

- [x] Source/release/run/raw asset çalışma tablolarını oluştur.
- [x] Orijinal CSV için MD5, dosya boyutu ve SHA-256 doğrulaması uygula.
- [x] Dosyayı content-addressed key ile `atlas-raw` bucket'ına yaz.
- [x] Aynı release ve checksum için DB unique constraint ile idempotency sağla.
- [x] Acquisition başarı, checksum hatası ve idempotency testlerini yaz.
- [ ] Yazılan testleri kullanıcı talep ettiğinde çalıştır ve sonucu geçici dosyaya yaz.

### Aşama 3 — Parse ve source inventory

- [ ] 68 kolonluk CSV sözleşmesini versiyonla.
- [ ] UTF-8 BOM ve CP1252 fallback davranışını uygula.
- [ ] Bütün Elément/Poste/archive/source-data satırlarını kayıpsız sakla.
- [ ] Duplicate ID, fazla kolon ve geçersiz decimal değerlerini fail-closed ele al.
- [ ] Parsed artifact'i `atlas-processing` içinde üret.

### Aşama 4 — Mapping ve normalization candidate

- [ ] Canonical unit snapshot/lookup sözleşmesini NetZeroAdmin ile tanımla.
- [ ] Canonical geography lookup sözleşmesini Logi ile tanımla.
- [ ] Taxonomy mapping proposal ve insan review kaydını oluştur.
- [ ] Negatif değerleri yalnız işaretine göre avoided-emission olarak işaretleme.
- [ ] Lifecycle decomposition ve gaz bileşenlerini ayrı observation olarak koru.

### Aşama 5 — Validation, diff ve candidate package

- [ ] Quality, license, geography, unit, temporal ve provenance kapılarını uygula.
- [ ] Field-level release diff üret.
- [ ] Sürümlü manifest ve immutable candidate package üret.
- [ ] Paketi NetZeroAdmin staging sınırına teslim et; canonical publish yapma.
