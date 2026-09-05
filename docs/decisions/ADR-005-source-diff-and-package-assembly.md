# ADR-005: Source diff ve candidate package assembly

- Durum: Kabul edildi
- Tarih: 2026-09-05

## Bağlam

Candidate V2 sözleşmesi `findings.ndjson` ve `source-diff.ndjson` member'larını,
release karşılaştırma kimliğini ve dört member'lı full-snapshot ZIP artifact'ini
tanımlar. Bu davranış ADEME kolonlarına veya tek bir source release'ine bağlanırsa her
yeni adapter farklı diff ve paket protokolü üretir. Öte yandan candidate key, provenance
key ve component/proposal referansları release kimliğini taşıdığı için bunların ham
string karşılaştırması değişmeyen bir faktörü yanlış biçimde `changed` yapar.

## Karar

- Finding ve source-diff satırları ortak canonical NDJSON writer tarafından yazılır.
  Writer her kaydı ilgili pinned Admin V2 JSON Schema'sına karşı doğrular, RFC 8785 ile
  encode eder ve duplicate record kimliğinde fail-closed davranır. Boş member exact
  sıfır byte ve boş SHA-256 kimliği taşır.
- Normalization finding key'i finding içeriğinin canonical SHA-256 değerinden
  deterministik türetilir; rastgele veya source'a özel key üretimi kullanılmaz.
- Release karşılaştırması `(logical_key, variant_key)` kimliğiyle yapılır. Duplicate
  semantic kimlik package-fatal hatadır. Sonuçlar semantic kimliğe göre sıralanır ve
  `added`, `changed`, `unchanged`, `removed` sınıfları üretir.
- Karşılaştırılacak scalar alanlar, domain eşlemeleri, dışlanacak JSON Pointer desenleri
  ve release-scoped candidate key token'ı
  `resources/rules/candidate/source-diff-v1.json` içinde sürümlenir. Ruleset exact
  SHA-256 pininden geçmeden yüklenmez. Engine içinde ADEME/source adı veya alanına bağlı
  branch bulunmaz.
- Top-level candidate/record schema kimliği ile raw asset taşıma kimlikleri semantic
  karşılaştırmadan çıkarılır. Candidate key içeren nested key/reference string'leri
  ruleset token'ına normalize edilir. Value, unit, geography, temporal, methodology,
  taxonomy, applicability, quality ve source-derived provenance değişiklikleri kendi
  domain'iyle korunur.
- İlk release'te her candidate `added`, kaybolan candidate `removed` olur ve boundary
  kanıtı record SHA-256 üzerinden verilir. İki tarafta bulunan kayıtlarda scalar-leaf
  diff üretilir; contract'ın 512 change sınırı aşılırsa kayıt kesilmez, işlem fail-closed
  sonlanır.
- Package assembly tam olarak `entities.ndjson`, `relationships.ndjson`,
  `findings.ndjson`, `source-diff.ndjson` alır. Eksik, fazla veya duplicate member
  reddedilir. ZIP giriş sırası ve zamanı sabittir, sıkıştırma uygulanmaz; aynı byte
  girdileri aynı artifact SHA-256 değerini üretir.
- Sidecar manifest artifact ve member kimliklerinden üretilir; counts ve source diff
  özeti member sayılarıyla uyuşmak zorundadır. Idempotency key immutable package
  kimliğinin canonical SHA-256 değeridir. Manifest pinned package V2 schema doğrulaması
  geçmeden kullanılmaz.
- Package ID, producer run, source/release, pipeline, catalog ve license kanıtları
  caller tarafından açık context olarak sağlanır. Builder bunları source'a özel default
  veya tahminle doldurmaz.

## Sonuçlar

Findings, diff ve ZIP/manifest üretimi yeni kaynaklar için tekrar kullanılabilir ve
aynı girdide deterministiktir. Bu karar package artifact'ini runtime storage'a yazmaz,
package ledger oluşturmaz ve Admin'e teslim etmez. Immutable persistence, validation
orkestrasyonu, gerçek license/catalog girdileri ve canlı V2 intake ayrı kapılardır.
