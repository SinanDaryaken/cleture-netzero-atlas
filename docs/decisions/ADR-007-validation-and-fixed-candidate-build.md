# ADR-007 — Validation kanıtı ve sabit candidate build

Tarih: 2026-09-05. Durum: Atlas yerel build sınırında kabul edildi; canlı teslim kapalı.

## Karar

Kaynak formatından bağımsız PrepareCandidatePackage sabit pipeline'ı yürütür.
ADEME normalizer kendi adapter'ında kalır. Kataloglar merkezi DB'den değil hash'li
Admin snapshot sözleşmesinden; lisans source/release'e bağlı immutable kanıttan gelir.
Genel DAG, ikinci calculation engine, otomatik canonical publish eklenmez.

Semantic validator schema doğrulamasını tamamlar: referanslar, provenance, mapping,
primary quantity/component ve temporal kontroller policy'ye bağlı findings üretir.
Validation policy exact hash ile pinlidir. Bütünlük kuralları policy değiştirilerek
advisory'ye indirilemez. Eksik owner sözleşmesi başarılı çözüm gibi gösterilmez.

Paket bütünlüğü ile adayın publish uygunluğu ayrı kapılardır. Unresolved/unknown
canonical semantik review paketinde blocking finding olarak korunabilir; yanlış
referans/hash/hedef paket üretimini engeller. Admin intake politikası bu ayrımı ayrıca
kabul etmeden canlı gönderim yapılmaz. Atlas insan review/publish kaydı sahiplenmez.

Validation findings ve receipt Atlas ledger'ına immutable kaydedilir. BuildCandidatePackage
eşleşen, package-blocked olmayan receipt ister. İdempotency kimliği için package UUID,
run ve timestamp kısa DB transaction ve release lock altında ayrılır; network/storage
yazısı transaction dışında kalır. Retry aynı manifesti üretir. Archive içerik kimliği,
manifest kimliği ve package kayıt kimliği ayrı kavramlardır.

V1 diff byte'ları korunur. V2 proposal domain'ini discriminator'dan alır; candidate key
normalization yalnız tanımlı referans pointer'larında uygulanır, source metni değiştirilmez.
Önceki paket doğrulanarak okunur. Karşılaştırma disk SQLite indeksinde yapılır; entity
payload'larının tamamı RAM'e alınmaz. Validation'ın duplicate/disposition anahtarları
kayıt sayısıyla büyür; sınırsız/O(1) bellek iddiası yoktur.

## Migration ve işletim etkisi

candidate_validation_runs ve candidate_package_attempts eklenir; candidate_packages
archive_object_key unique kısıtı kaldırılır. Down yeni tabloları kaldırır fakat shared
archive verileri var olabileceğinden eski unique kısıtı geri kurmaz. Bu bilinçli asimetri
nedeniyle production rollback öncesi veri/kod uyumluluğu ayrıca değerlendirilmelidir.
Migration yalnız Atlas çalışma DB'sine uygulanır.

Build planı, eksik girdiler ve exit kodları [işletim sözleşmesinde](../candidate-build.md).
Bekleyen sahiplik işleri ve devam noktası [CURRENT](../CURRENT.md) içinde tutulur.
