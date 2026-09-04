# ADR-003: Normalization ve candidate package sözleşme sınırı

- Durum: Kabul edildi
- Tarih: 2026-09-04

## Bağlam

Her veri kaynağı kendi satır tiplerine, taxonomy yapısına, lifecycle decomposition
alanlarına ve kalite işaretlerine sahiptir. ADEME Base Carbone için `Elément` ve
`Poste` ilişkisini bilmeyen genel bir normalizer bu semantiği kaybedebilir. Buna
karşılık candidate kayıt hash'i, dört archive member'ın oluşturulması, manifest,
content-addressed storage ve NetZeroAdmin teslimatı kaynak formatından bağımsızdır.
Bunları her source adapter'ında yeniden kurmak farklı paket protokolleri üretir.

NetZeroAdmin candidate package ve entity JSON şemalarının canonical sahibidir. İlk
paketin deterministik üretilebilmesi için Atlas'ın çalışırken uzak bir repository
veya değişebilir dokümana bakmaması; kullandığı sözleşme kopyasının commit, blob ve
SHA-256 kimliklerini taşıması gerekir. Mevcut upstream sözleşmede
`relationships.ndjson`, `findings.ndjson` ve `source-diff.ndjson` satır şemaları henüz
sürümlü olarak tanımlı değildir.

## Karar

- ADEME normalization motoru `app/Infrastructure/Sources/Ademe` altında source'a
  özel olacaktır. ADEME alan adları, `Elément`/`Poste` ilişkisi ve source taxonomy
  yorumları domain veya genel orchestrator içine taşınmayacaktır.
- Source-neutral candidate value object'leri `app/Domain/Candidate`, use-case
  orkestrasyonu `app/Application`, package builder, canonical JSON/hash, storage ve
  transport adapter'ları `app/Infrastructure` altında ortak kalacaktır.
- Her yeni kaynak `SourceNormalizationAdapter` sözleşmesini uygular; ortak candidate
  package motorunu yeniden yazmaz. Registry source code üzerinden adapter seçer ve
  orchestrator source formatını bilmez.
- NetZeroAdmin'ın commitlenmiş V1 package ve entity şemaları
  `resources/contracts/netzero-admin/candidate-v1` altında immutable contract snapshot
  olarak pinlenmiştir. Manifest local SHA-256 ile upstream commit/blob/path/SHA-256
  provenance'ını birlikte taşır. JSON dosyasına eklenen son newline nedeniyle local
  byte hash'i upstream blob hash'inden farklıdır; JSON sözleşme içeriği aynıdır.
- Contract registry dosyayı kullanmadan önce local hash ve schema kimliğini doğrular.
  Eksik bir sözleşme veya hash sapması fail-closed kabul edilir.
- Dört member için kayıt sözleşmeleri tamamlanmadan ortak package builder üretime
  açılmaz. Boş NDJSON member oluşturarak veya Atlas'ın kendi şemasını icat ederek bu
  kapı aşılmaz.
- Kaynaktan çözülemeyen unit, geography veya taxonomy değeri elenmez ve canonical
  varsayımla doldurulmaz; provenance ile unresolved/ambiguous proposal olarak tutulur.

## ADEME candidate ilkeleri

- Geçerli factor `Elément` satırı candidate entity'nin ana kaydıdır.
- `Poste` satırları bağımsız canonical factor gibi yayımlanmaz; parent source element
  altında decomposition/component kanıtı olarak korunur.
- Gaz bileşenleri ve source toplamı ayrı decimal quantity olarak tutulur. Binary float
  kullanılmaz ve formül sonucu Atlas içinde yeniden hesaplanmaz.
- Negatif değer yalnız işaretinden dolayı avoided-emission sayılmaz. Source
  metodolojisi kanıtlamıyorsa review finding üretilir.
- Unit ve geography eşlemesi yalnız sürümlü NetZeroAdmin ve Logi snapshot'larına karşı
  proposal üretir; Atlas canonical katalog sahibi olmaz.

## Sonuçlar

Single responsibility source semantiği düzeyinde uygulanır: her kaynak kendi
normalizer'ına sahip olur. Paket protokolü düzeyinde ise tek bir ortak motor korunur.
İlk normalization uygulaması ADEME'ye özeldir; ortaya çıkan domain kayıtları ve paket
altyapısı sonraki kaynaklar tarafından tekrar kullanılabilir.

Package builder geliştirmesi; üç eksik member record şeması, sürümlü unit/geography
snapshot girişleri ve lisans terms snapshot sözleşmesi tamamlanana kadar bloke kalır.
Bu eksikler ADEME normalizer'ın source-derived ve unresolved candidate üretmesine
engel değildir, fakat review'a teslim edilebilir tam paketin kabul kapısıdır.
