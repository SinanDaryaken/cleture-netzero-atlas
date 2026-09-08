# Candidate VersionId teslimi — kabul planı

2026-09-07. İlk kod/test tesliminden sonra owner gerçek runtime işlerini onayladı.
Sentetik ZIP'in gerçek MinIO teslimi ve sınırlı 24h IAM doğrulaması tamamlandı;
Admin–Worker gerçek staging sonucu da aşağıda owner bildirimi olarak kaydedildi.

## Admin–Worker kabul sonucu — owner bildirimi

Admin koordinasyonu gerçek Worker provider ile exact VersionId GET/SHA doğrulamasını,
queue/scheduler üzerinden başarılı staging'i bildirdi. Admin package UUID
`01a07cd6-514c-71d3-9c45-845035005991`; task ilk denemede tamamlandı ve silindi,
failure=0. Beş signed HTTPS staging POST 200 döndü. Dört member eşleşti; receipt SHA
`8795afc3dc202427a6bbe0aa3606a2a93f4c0eb57872e680b0c49f8837a609e0`.
Exact manifest Admin use-case üzerinden yeniden kaydedildiğinde created=false,
ek task/package/record oluşmadı ve aynı receipt korundu.

Bu sonuç Admin görevinden iletildi; Atlas bağımsız tekrar çalıştırmadı. Atlas intake
HTTP kullanılmadı. TEST_SOURCE sentetik kapsamı ve geçici 24h IAM devam ediyor;
scientific approval veya canonical publish yapılmadı.

## Gerçek sentetik teslim — 17:00 UTC

Bucket `atlas-candidates`, profile `atlas.candidate_ingress`; ZIP SHA
`09e3f18ccd295c936a37032078caefeddc9948f61af5c9fbdc59e360337e6dff`, 6934 byte.
Gerçek VersionId `d61c8fb0-e4ec-47e9-a136-b17bbabc3b9d` exact GET/hash/boyutla
doğrulandı. Yeni manifest SHA
`3af77be6b063fc512b73e1e4d2ec269b01f48475d939af9f1014d3005572eac1`, 3449 byte;
`manifests/sha256/<SHA>.json` altında immutable saklandı ve retry/read-back geçti.

Retained local manifest değişmedi. Yeni package UUID/producer UUID/zaman ve gerçek
VersionId dışında manifest semantiği ve bütün member byte'ları aynı kaldı. Bu kontrollü
sentetik re-envelope corrected storage receipt/canonical/schema akışını kullandı;
production ingestion run/ledger veya development seed kaydı oluşturulmadı.

24h child kimliği yalnız exact ZIP ARN'ine GetObject/GetObjectVersion alır;
son kullanma `2026-09-08T17:01:33Z` (Türkiye 20:01:33). Child ile iki okuma hash/sürüm
doğrulamasını geçti. ListObjectsV2, koşullu exact-ZIP PutObject, absent-key DeleteObject,
exact-ZIP nonexistent-version DeleteObjectVersion, other-key/manifest/receipt GET
kontrollerinin tamamı 403 AccessDenied döndü. Teslim edilen ZIP değişmedi.

Private yeni manifest ve yalnız iki allowlisted credential alanı içeren 0600/0700
transfer dosyası Admin görevine iletildi. Worker ayarlarına yazılmadı; management secret
geçici mc config'i kaldırıldı. [Secret içermeyen gerçek kanıt](evidence/candidate-s3-versioned-acceptance-2026-09-07.json).

## Tamamlanan Atlas işi

| Alan | Sonuç |
| --- | --- |
| Logical profile | `atlas.candidate_ingress`; fiziksel disk `atlas_candidates` ayrı |
| S3 receipt | Exact doğrulanmış gerçek upload/reuse VersionId; sürümsüz S3 reddedilir |
| Immutable yazım | ZIP/receipt/manifest koşullu create; conflict ve retry kontrolleri |
| Manifest | Receipt sürümünden sonra canonical/hash-addressed yeni manifest |
| Internal replay | Producer/run/time reservation ve ZIP sürümü birlikte sabit |
| Admin transport | Semantic fingerprint v1 ve sıralı dört alanlı raw descriptor hash |
| Previous read | Exact manifest sürümü; eksik sürümde latest fallback yok |
| Kanıt | 29 Unit/Feature +1 yerel gerçek SDK/socket =30 test /149 assertion |

Son test logu: Windows TEMP `atlas-candidate-version-final-20260907-194410.log`.
İlk dar koşudaki fixture handler ve filesystem fake sorunları bu kapsamda düzeltildi.
Tam suite, gerçek MinIO ve production DB testleri çalıştırılmadı. Pint (24 PHP dosyası),
Composer strict validate ve git diff whitespace kontrolü geçti.

Admin görevinin bağımsız read-only preflight sonucu: manifestValidator başarılı,
semantic fingerprint/raw asset set eşleşti, entity sealed schema hatası yok,
package_fatal=false; beklenen 7 record_blocker (canonical/taxonomy/applicability/
unit/geography) korundu. Dört üye ve ZIP hash/boyutları yeniden doğrulandı.
Bu Admin'in bildirdiği yerel doğrulamadır; HTTP/S3/staging kanıtı değildir.
Son koordinasyon talebi bu dilimi commit/push yapılmadan çalışma ağacında teslim etmektir.

Admin exact local fixture'ı test temizliğinden korumak için owner-only
`/home/sinan/.local/share/netzero-worker-acceptance/20260907/fixture/manifest.local.json`
ve `candidate.zip` yollarına kopyaladığını bildirdi (0600 dosya/0700 dizin).
Manifest SHA `7e5faf10034d58baa9332f65a8e188651fd0c4132e62809acd6ec66ced0f82c5`, 3415 byte;
ZIP SHA `09e3f18ccd295c936a37032078caefeddc9948f61af5c9fbdc59e360337e6dff`, 6934 byte.
Version null'dır; bu dosyalar yalnız local semantic preflight girdisidir.

## Tek sentetik kabul sırası

1. Admin'in semantic preflight'ı için test çalışmasından çıkan TEST_SOURCE/test-dataset
   ZIP ve manifest exact hash/boyutlarıyla seçilir. Test klasörleri sonraki testte
   değişebildiği için kullanımdan önce yeniden okunur. Development DB seed edilmez.
   Yerel fixture `object_version_id=null` taşır ve durable S3 kabulü yerine geçmez.
2. Ayrı gerçek işlem kapsamı açıldığında üretim storage adapter'ı ile ZIP upload/reuse
   yapılır, S3 VersionId hash/boyut geri okumasıyla doğrulanır. Eski manifest yerinde
   düzenlenmez; gerçek receipt ve yeni producer reservation ile yeni manifest üretilir.
   Gerçek üretim girdileri seçilmeden test UUID'leri çalışma DB'sine aktarılmaz.
3. Worker owner ile secret-file teslimi netleştirilir. İlk kabul kimliği yalnız seçilen
   ZIP'in exact `arn:aws:s3:::atlas-candidates/sha256/<SHA>.zip` ARN'ine
   `s3:GetObject`/`s3:GetObjectVersion`, 24 saat ömür alır. List/Put/Delete veya root
   yetkisi verilmez; bu aşamada kalıcı hesap açılmaz. Secret mesaj/argv/log/commit'e girmez.
4. Admin sealed schema yanında manifest çapraz alanları, semantic fingerprint,
   raw set ve entity record/validation hash kurallarını bağımsız doğrular. Aynı semantic
   key/farklı ZIP için 409 beklenir; yeni key uydurarak conflict atlatılmaz.
5. Admin–Worker gerçek kabulünde exact ZIP sürümü ve hash doğrulanır; staging sonucu,
   idempotent retry ve receipt evidence kaydedilir. TEST_SOURCE unit/geography pinleri
   gerçek canonical referans değildir; authoritative blocking findings staging için
   korunur. İnsan approve/publish veya nihai kullanım izni üretilmez.

## Açık kapılar

Gerçek upload+VersionId read-back ve geçici exact-ARN IAM/özel transfer dosyası Atlas'ta
tamamlandı. Worker credential uygulaması ve gerçek Admin–Worker staging/replay kabulü
owner bildirimiyle tamamlandı. Atlas intake HTTP bu kabulde kullanılmadı. Gerçek
insan onaylı resolution ve authority/finalization sözleşmeleri ayrıca owner girdileridir.
Bu Atlas düzeltmesi bunların tamamlandığı iddiasını taşımaz.

Mimari gerekçe: [ADR-010](decisions/ADR-010-versioned-candidate-transport.md).
