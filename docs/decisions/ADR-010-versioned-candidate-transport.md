# ADR-010 — Sürümlü candidate storage ve transport fingerprint

Tarih: 2026-09-07. Durum: Atlas kod/test ve owner onaylı gerçek sentetik S3 teslimi doğrulandı;
Admin–Worker staging kabulü owner koordinasyonunda.

## Bağlam ve sahip sözleşmeleri

Worker `config/emission_candidate_ingest.php` yalnız `atlas.candidate_ingress`
profilini tanır. `LaravelFilesystemCandidateArtifactStreamProvider` verilen S3
VersionId'yi exact okumada kullanır. Atlas eskiden disk adını profile yazıyor ve
manifesti upload öncesinde `object_version_id=null` ile kesinleştiriyordu.

Admin `CalculateEmissionCandidatePackageFingerprint` ile manifest semantic anahtarını
yeniden hesaplar; `RegisterEmissionCandidatePackage` farklı anahtarı 422, aynı semantic
anahtar/farklı ZIP hash'ini 409 ile reddeder. Eski Atlas full identity hash'i bu wire
alanıyla aynı değildir. Raw asset kümesi hash'i de provenance alanlarını içeremez.
Admin/Worker kaynakları salt okunur incelendi; owner algoritması veya schema değiştirilmedi.

## Karar

1. Builder member/schema/raw descriptor doğrulamasından sonra ZIP'i storage'a verir.
   `StoredCandidateArchive` receipt disk/key/SHA/boyut/VersionId taşır. Builder bundan
   sonra producer kimliğini ayırır, manifesti kesinleştirir ve yeniden doğrular.
2. S3 bucket versioning `Enabled` olmalıdır. ZIP, version receipt ve manifest yazıları
   `If-None-Match: *` kullanır. 412 durumunda mevcut nesne yeniden okunur; overwrite
   fallback yoktur. 409/diğer hatalar başarıya çevrilmez, sonraki build tekrar deneyebilir.
3. ZIP gerçek upload veya doğrulanmış mevcut object VersionId'siyle, exact GET sürümü,
   boyutu ve stream SHA-256 üzerinden doğrulanır. Eksik/boş/literal `null` sürüm reddedilir.
   `archive-versions/sha256/<zipSHA>.json` koşullu oluşturulan internal receipt'tir;
   ilk doğrulanmış sürümü kalıcı olarak sabitler. Sonraki retry bu sürümü okur; daha
   yeni object sürümü pin'i değiştirmez. Sabitlenmiş sürüm yoksa latest fallback yapılmaz.
4. Manifest `artifact.storage_profile=atlas.candidate_ingress` ve receipt VersionId'sini
   taşır. Manifest yazılmadan ZIP tekrar doğrulanır; manifest de sürümlü GET/hash/boyut
   kontrolünden geçer. Önceki paket okuyucusu manifestteki VersionId'yi kullanır.
5. Yerel disk ancak açık `candidate_allow_versionless_local=true` test ayarıyla
   kullanılabilir. Bu ayar S3 kontrollerini gevşetmez. Yerel receipt sürümü null'dır ve
   CLI bunu S3 teslimi olmayan yerel test çıktısı olarak açıkça gösterir.
6. Wire `manifest.idempotency_key` Admin semantic fingerprint v1'dir. Preimage:
   fingerprint version, package major, source/dataset/release/revision/raw set,
   parser/schema/normalizer/mapping/validation/catalog/license/canonicalization pinleri.
   Artifact hash/VersionId, UUID, timestamp, previous package ve full metadata dışarıdadır.
   Raw set yalnız asset_key/sha256/size_bytes/media_type descriptorlarını asset_key'e
   göre sıralayıp canonical JSON hash'ler; URI ve retrieved_at manifestte korunur.
7. Atlas internal idempotency key full immutable identity ve VersionId'yi kapsar.
   `candidate_package_attempts` ve `candidate_packages.idempotency_key` bu internal
   anahtarı tutmaya devam eder; dışarıya kayıt receipt'i manifestin semantic anahtarını
   verir. Aynı semantic key farklı ZIP/manifest Atlas'ta ayrı provisional çıktı olabilir;
   bu yeni Admin kabulü değildir, Admin'in 409/replay davranışı korunur.

## Geçiş ve sınırlar

Yeni migration yoktur. Archive VersionId'nin kalıcı kaynağı hash ile sabitlenmiş
manifest ve object receipt'tir; ledger dönüşü doğrulanmış receipt sürümünü taşır.
Önceki manifest/DB kayıtları yeniden yazılmaz. Yeni logical profile, transport raw set
ve version kimliği yeni manifest/reservation oluşturur; tarihsel V1 davranışı sessizce
yeniden yorumlanmaz. Eski sürümsüz previous manifest hash doğrulamalı legacy okumayla
okunabilir; bu durable version kanıtı sayılmaz.

Receipt/ZIP sürümlerinin silinmemesi lifecycle/IAM işletim gereğidir. Receipt S3 WORM
iddiası değildir; yetkili dış aktörün doğrudan silmesini veya üzerine yazmasını engelleyen
IAM/lifecycle ayarları bu kod değişikliğinde uygulanmaz. Worker yalnız exact ZIP ARN'ine
GetObject/GetObjectVersion alır; internal receipt/manifest erişimi gerekmez. Atlas producer
ayrıca GetBucketVersioning ve kendi object alanlarında GetObjectVersion/GetObject/PutObject
ister. Root credential Worker'a aktarılmaz.

## Kanıt

İlgili **30 test /149 assertion** geçti: SDK HTTP response parsing, koşullu 412,
kayıp upload/receipt yanıtı, version eksikliği, içerik/manifest/receipt conflict, sabit
sürümlü previous read, full pipeline retry ve internal/semantic identity ayrımı.
Bunların **1 test /17 assertion** kısmı gerçek loopback socket üzerinden SDK testidir.
Gerçek PostgreSQL/MinIO test kodu versioning/cleanup için güncellendi, çalıştırılmadı.

Admin'in sağladığı example SHA
`24ced12ed280fac1ec25d641c0b0a50d41243d51219ddd5b8107372580ac074e` üzerinden yalnız
V2 schema/geography owner/raw set uyarlaması yapılan golden vector:
raw `fca26129d6b33d9a89199ad2ac49a3a7309e296ebdb07a8eb60f8df309002507`,
semantic `sha256:89e6d4a95e9a699114bea3ace1c010ae47e75c8ca9f75c3e868473315c9d7c8c`.
Bu değerler ve ayrıca unicode/sıra/provenance değişimini kapsayan bağımsız vector testte pinlidir.

[Tek sentetik kabul planı ve kalan kapılar](../candidate-versioned-acceptance.md).
Kod/test diliminden sonra owner gerçek runtime kapsamını açtı: tek retained sentetik
ZIP actual VersionId ile teslim edildi, yeni immutable manifest retry/read-back geçti,
24h exact-ZIP child accesskey allow/deny kontrolleri doğrulandı. Uygulama DB/DML/seed
yok; [gerçek kanıt](../evidence/candidate-s3-versioned-acceptance-2026-09-07.json).
