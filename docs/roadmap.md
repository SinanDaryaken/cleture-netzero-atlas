# NetZero Atlas roadmap

## Admin entegrasyonu — adım 6 (2026-09-07)

- [x] Mevcut Admin çalışma ağacının salt okunur contract/code/test incelemesi.
- [x] Ayrı pinli delivery/unit 2.1/review/currency registry ve exact beş katalog loader.
- [x] Owner seçimiyle private Atlas MinIO `atlas-catalogs` hedefi ve conditional immutable transfer.
- [x] Gerçek 25 artifact + manifest read-back; aynı paketin retry ve beş katalog tüketimi.
- [x] Güncel yetki üretmeyen sentetik altı tür çözüm kanıtı tüketici sınırı.
- [x] Kullanıcı onaylı fixture/assertion düzeltmeleri; 134 Unit/Feature + 1 gerçek MinIO testi başarılı.
- [x] Admin'in HMAC current-approval request/response sözleşmesini salt okunur yeniden değerlendir.
- [x] Atlas bağımsız pinli HTTP adapter, taze sorgu giriş noktası ve kapalı nihai kullanım kontrolü.
- [x] Admin A1 currency nested hash ve A2 taxonomy parent sıra düzeltmelerinin bağımsız doğrulaması.
- [x] 50 yeni Feature testi; tam 184 Unit/Feature ve 1 gerçek socket integration başarılı.
- [x] Secret-safe readiness CLI; gerçek depoda catalog-only teşhisi, 189/715 regresyon ve 1/8 socket testi.
- [x] Admin'e servis etkinleştirme, gerçek teslim, body schema ve finalization için somut kabul işi.
- [ ] Atlas container→Admin HTTPS erişim yolu ve sertifika güveni; mevcut hostname loopback'e çözülüyor.
- [ ] Koordineli key/source grant ve gerçek approved-resolution teslimiyle canlı doğrulama.
- [ ] Historical authority body schema provisioning ve atomik kullanım/finalization owner sözleşmesi.

Katalog provisioning tamamlanmıştır; onaylı çözümün güncel yetki olarak tüketimi ve
adım 6'nın bütünü kapanmamıştır. [İşletim/kanıt](catalog-delivery.md),
[sahiplik ve bulgular](admin-atlas-step6-review.md), [current-approval adapter](current-approval.md).

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
- [x] Canonical unit snapshot/lookup sözleşmesini NetZeroAdmin ile tanımla.
- [x] Canonical geography snapshot/lookup sözleşmesini NetZeroAdmin ile tanımla.
- [x] ADEME `SourceNormalizationAdapter` ve registry'sini oluştur.
- [x] ADEME `Elément` ana candidate ve `Poste` decomposition modelini üret.
- [x] Parsed artifact'ten normalization input stream'i ve idempotent çalışma
  kayıtlarını oluştur.
- [x] Taxonomy source proposal'ını unresolved hedefle koru.
- [ ] Admin taxonomy snapshot sözleşmesi sonrası canonical resolution; insan review kaydı Admin'e aittir.
- [x] Negatif değerleri yalnız işaretine göre avoided-emission olarak işaretleme.
- [x] Lifecycle decomposition ve gaz bileşenlerini ayrı component olarak koru.

### Aşama 5 — Validation, diff ve candidate package

- [x] NetZeroAdmin'da relationships/findings/source-diff record şemalarını
  sürümle ve Atlas contract snapshot'ına ekle.
- [x] Candidate V1 pinlerini değiştirmeden V2 upstream manifest ve beş schema'yı
  commit/SHA-256 provenance ile ayrı snapshot olarak pinle.
- [x] Unit/geography descriptor ve payload'ları exact byte/hash, schema ve semantic
  integrity kapılarıyla runtime storage'dan yükle.
- [x] Tekil exact geography/unit eşleşmelerini proposal'a dönüştür; eksik veya birden
  çok eşleşmeyi unresolved/ambiguous koru.
- [x] Source-agnostic RFC 8785 canonical JSON ve candidate `record_sha256`
  üreticisini oluştur.
- [x] Final candidate entity'yi pinned JSON Schema'ya karşı doğrula.
- [x] Doğrulanmış normalized artifact'ten deterministik V2 `entities.ndjson` member
  üreticisini oluştur.
- [x] V2 policy'ye uygun sıfır byte/sıfır kayıt `relationships.ndjson` member üret.
- [x] `findings.ndjson` ve first-release/source `source-diff.ndjson` member'larını üret.
- [x] Yerel quality, license evidence, geography/unit hedef, temporal, referans ve provenance kapılarını uygula.
- [x] Validation findings/receipt ledger'ını ekle; receipt olmadan paket assembly'yi kapat.
- [x] Sabit candidate build komutu, doğrulanmış önceki paket okuyucu ve disk tabanlı diff ekle.
- [x] Diff V2 domain/reference düzeltmesini V1 byte'larını koruyarak sürümle.
- [x] Eşzamanlı retry kimliğini sabitle; ortak ZIP / farklı manifest senaryosunu destekle.
- [ ] Owner sözleşmeleri sonrası compound dimension/applicability, taxonomy/intended-use ve formula uygunluğunu doğrula.
- [x] Hash-pinned ve source-agnostic ruleset ile field-level release diff üret.
- [x] Dört member'ı sabit sırada içeren deterministik ZIP ve V2 sidecar manifest üret.
- [x] Candidate package ile manifesti content-addressed storage'a immutable yaz ve
  idempotent package ledger kaydını oluştur.
- [ ] Paketi NetZeroAdmin staging sınırına teslim et; canonical publish yapma.

### Dış koordinasyon kapıları

- [x] Unit/geography ve currency/taxonomy/intended-use exact byte'larını Atlas `atlas_catalogs`
  runtime storage'a provision et; manifest üzerinden exact descriptor/payload çözümlemesini doğrula.
- [ ] ADEME license terms snapshot girdilerini teslim al ve doğrula.
- [ ] NetZeroAdmin V2 intake rollout ve Worker durable staging writer hazır olduğunda
  canlı teslimi koordineli aç; V1'e downgrade etme.

2026-09-05: Admin ve Worker'a yalnız BEKLEYEN günlük kaydı bildirildi; geliştirmeye
başlama talimatı verilmedi. [Güncel durum ve devam sırası](CURRENT.md).
