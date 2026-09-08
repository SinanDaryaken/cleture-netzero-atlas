Cleanup verification: full PHPUnit 51 passed /418 assertions, Pint and diff checks passed. Direct preparation resolves without retired services. Existing source normalization identities and central data preserved.

## 2026-09-08 — Owner-approved obsolete transport retirement

Atlas → Worker → Admin cleanup is approved by the owner in the shared task. Direct prepare-admin is the supported path. Package building, catalog delivery/current-approval lookup and their dedicated tests are retired. Historical requirements below for mandatory package/Worker transport are superseded. Preserve normalization contracts, raw data, Admin decisions, unit/geo references and the readonly old-atlas snapshot. No development schema/data deletion is authorized by this cleanup.

# Atlas — güncel devam noktası

## Açık PCI/PCS oran ayıklaması — 2026-09-08

Owner Admin örnek hesabında yakıta ve kaynak dayanağına bağlı PCI/PCS dönüşümünü
onayladı. AdemeSourceScienceExtractor kaynak birimindeki açık esası ve açıklamalarda
tam satır PCS/PCI: sayı beyanını heating_value içinde ayıklar. Yakıt Nom base français,
oran ve satır/alan dayanağı birlikte taşınır. Oran en az 1 olmalıdır; farklı beyanlar
çelişki, bilinmeyen oran null. Genel yüzde açıklamaları veya doğal gaz adı varsayılan
oran üretmez. Kaynak etiketleri ve özgün payload değerleri korunur.

Extractor 8 test/57 assertion, container Pint ve diff check geçti. Test logu TEMP
altında netzero-atlas-heating zaman damgasıyla saklandı. Admin 54 test/586 assertion,
Vue 18 test ve build/type-check/lint başarılı. Admin tanımı merkezi admin_references
içinde kalır; Atlas bu alanı değiştirmez. Yeni extraction sonraki prepare-admin'de
çalışır; bu dilimde gerçek replay/DB yazımı veya migration yapılmadı.

## Admin inceleme kararlarını koruyan replay — 2026-09-08

Owner bu konuşmada Admin eşleştirme düzeltme ve tekil/toplu onay dilimini onayladı.
Admin yeni review/admin_references alanlarını ve review event tablosunu sahiplenir;
migration Batch42 uygulandı. Atlas bunlara yazmaz. CentralFactorWriter mevcut
import satırını lockForUpdate ile kilitler; Admin onay/GWP güncellemesiyle aynı
satır kilidini paylaşır. Böylece metadata yenilemesi karar transaction'ıyla çakışmaz.
Writer regression 3 test/27 assertion geçti; tekrar aktarımda review_status,
review_revision, admin_references, reviewed_by ve reviewed_at aynen korunur.
Pint ve diff check geçti. Log:
C:/Users/Sinan/AppData/Local/Temp/netzero-atlas-review-20260908-144749.log
Admin tam 1017 test/7967 assertion +1 opt-in skipped; kaynak 6518 kayıt hash'i
değişmedi. Gerçek kayıtlar owner adına onaylanmadı; onay ekranı manuel kabul bekler.


## Kaynak satırlarından bilimsel bilgi ayıklaması — 2026-09-08

Owner'ın kaynakta bulunanı al/null bırak sınırı uygulandı. AdemeSourceScienceExtractor
Programme/Source/kategori/sınır alanlarından açık GIEC/IPCC raporu ve zaman ufkunu,
PRG kayıtlarının kendi katsayısını, varsa açık formül metni/parametre birimlerini alır.
GWP sabit varsayılan değildir. Rapor/zaman ufku çelişkileri seçilmez; sıradan faktör
ve gaz katkısı GWP katsayısı sayılmaz. Formül eval edilmez, eksik birim türetilmez.

CentralFactorWriter yeni ve tekrar aktarımda source_science alanını üretir; özgün
payload alanları/normalized artefact ve Admin GWP profiline dokunmaz. Kaynak dosyası
SHA/version ve satır/alan kanıtları taşınır. Referans linkleri korunur; bağlı dış
belge/PDF bu dilimde indirilmez ve not_fetched durumu Admin'de görünürdür.

Gerçek 6518 kaydın tamamı incelendi, 266 AR6/100 yıl ve 266 katsayı bulundu; 6252
GWP null. Açık üretim formülü 0. Örnek SF6 #43294: 24300 kgCO2e/kg; #43020: 0.002.
Aynı import korundu, eski record hash'i 51ead36d2dbc8236c87c4ba00bd01be0 değişmedi.
Yeni tam record hash'i 384baf9a0e1bcfb8ba7cdc6d10753300; gerçek replay'de aynı ve kopya yok.
Atlas ilgili 16 test /97 assertion, tam 226 test /898 assertion /10,92 saniye geçti.
Admin ilgili 24 test /217 assertion ve Vue 8 test, format/lint/type-check/build geçti.
Tam log: C:/Users/Sinan/AppData/Local/Temp/netzero-atlas-source-science-full-20260908-141119.log.
Owner oturumunda yeni kaynak kanıtı/katsayı sunumu manuel kabul bekler; runtime tamamlandı.

## GWP açıklaması gerçek veride ve replay düzeltmesi — 2026-09-08

Admin owner onayıyla GWP migration'ını uyguladı. İlk prepare-admin yeni retrieval/
normalize artifact kimliği yüzünden aynı V23.6/raw SHA için ikinci import oluşturdu.
CentralFactorWriter artık source/dataset/version/raw SHA ile mevcut importu bulur;
indirmenin zamanına bağlı normalize hash'i yeni kayıt üretmez. Değişen count hata
verir, farklı raw/version/dataset ayrı kalır. Yeni 3 test /21 assertion ve tam Atlas
220 test /855 assertion /7,92 saniye geçti; Pint/diff check başarılı.
Log: C:/Users/Sinan/AppData/Local/Temp/netzero-atlas-replay-full-20260908-134904.log.

Asıl 01a07fef-08f7-72bb-80de-c00979dc4bde içindeki 6518 kaydın açıklaması güncellendi.
Owner ayrıca açık izin verdi; yalnız yanlışlıkla üretilen ikinci import/kopyalar,
kaynak kimliği ve tüm özgün alanların eşitliği transaction içinde doğrulanarak kaldırıldı.
Son replay 1 import/6518 kayıt: tam record hash'i 7a2c566bc50b48b38ebeebc0978fc114,
özgün alan hash'i eskisiyle aynı 51ead36d2dbc8236c87c4ba00bd01be0. Admin GWP null
korundu. Gerçek doğal gazda toplam/2 aşama/gaz katkıları okunuyor. Manuel UI kabulü
owner oturumunu bekliyor; migration/cleanup onay engeli kalmadı.

## Gaz ve aşama açıklaması hazır — 2026-09-08

Owner GWP kaynak tanımı ve gaz/CO2e/aşama ayrımını onayladı. Mevcut Admin mapper
kaynak birimi ve Structure/Poste alanlarından ayrı scientific_interpretation üretir.
Gazlar CO2e katkısı olarak açıklanır; gaz kütlesine çevrilmez ve GWP uygulanmaz.
Biyojenik CO2 ayrımı görünürdür. Eski normalize artefact ve özgün payload alanları
korunur. CentralFactorWriter ilk aktarımda açıklamayı ekler; aynı import tekrarında
bu türetilmiş alanı yeniler, Admin-owned gwp_profile alanına dokunmaz.

Atlas ilgili 7 test /33 assertion ve tam suite 217 test /834 assertion /9,26 saniye
başarılı; Pint ve diff whitespace geçti. Tam log:
`C:/Users/Sinan/AppData/Local/Temp/netzero-atlas-gwp-full-20260908-132817.log`.
Gerçek doğal gaz 13515 kaydı read-only yorumlandı: toplam ve iki aşama, her grupta
7 bileşen. Merkezi 6518 kaydın özgün hash'i 51ead36d2dbc8236c87c4ba00bd01be0.
Henüz gerçek payload güncellemesi yapılmadı. Admin yeni nullable gwp_profile
migration'ı için somut owner onayı bekliyor; sonrasında önceki ingestion yetkisiyle
aynı kaynak tekrar hazırlanıp özgün alanların/hash'in korunması doğrulanacak.

## Son test düzeltmesi — 2026-09-08

Owner test sorunlarını kapatıp Admin kullanım/dönüşüm altyapısını geliştirmeyi
onayladı. Atlas'ta yalnız storage/framework/testing altındaki root sahipli kayıtlar
container çalışma UID/GID1000'e geçirildi; geniş chmod, kaynak veya live DB değişikliği
yok. Tam Atlas suite 216 test /823 assertion /9,22 saniye başarılı; önceki 22 izin
hatası kapandı. Log: `C:/Users/Sinan/AppData/Local/Temp/netzero-atlas-repair-2026-09-08T09-14-04-998Z.log`.
Admin kullanım/dönüşüm açıklamasını kendi sunum Action'ıyla kayıttaki pinned referans
kataloğundan okur; Atlas kaynak verisini yeniden yazmaz. Gerçek 6518 kayıt hash'i aynı.
Admin tam suite 994 passed /1 capacity skipped. Onay/client hesaplama sonraki dilim.

Güncelleme: 2026-09-08, Europe/Istanbul. Önceki kayıt: [2026-09-05 günlüğü](journal/2026-09-05.md).

## Son dilim — gerçek ADEME → doğrudan Admin görüntüleme

Owner sade ilk adımı onayladı: kaynak motoru parse/normalize + unit/geo bağlantısı
→ moduler_netzero gelen faktör tabloları → Admin liste/detay. Bu yol için zorunlu
Worker/API paket aktarımı ve merkezi DB yasağı kaldırıldı; eski kod korunur.
Şema sahibi Admin, referans okuma/gelen veri yazma sahibi Atlas. Onay/toplu onay,
yayın ve client sorguları sonraki kapsamdır.

`central` DB bağlantısı ve `atlas:source:prepare-admin ADEME` komutu eklendi.
Owner açık runtime onayıyla gerçek V23.6 işlendi: Atlas 18.616 parsed satır,
merkezi DB 1 import /6.518 faktör. Import `01a07fef-08f7-72bb-80de-c00979dc4bde`.
Admin `/atlas-factors` üzerinden görüntüler. 9.800 faktör/bileşen kaynak satırının
tüm 67 alanı karşılaştırıldı: fark 0. Kaynak sayılarında dönüşüm/toplama yok.

Referans yükleme nesnesi hatası düzeltildi. Birim 2.506 tam +2.973 kısmi eşleşme;
coğrafya 5.791 France continentale kaydında kısmi FR üst ülke bağlantısı. Kaynak
alt kapsamı korunur; eşleşmeyenler görünür kalır. Tekrar aktarım aynı import ve
6.518 kayıtla sonuçlandı; tüm kayıt hash'i `51ead36d2dbc8236c87c4ba00bd01be0`
değişmedi. Referans değişirse yalnız eşleşme alanları yenilenir.

Atlas ilgili 6 test /22 assertion, Admin ilgili 4 test /69 assertion ve iki proje
Pint kontrolleri geçti; Admin TypeScript/scoped lint/build başarılı. Gerçek ekran
tarayıcıda login'e yönlendi; oturumlu görsel kabul bekleniyor. Commit/push yok.
Görev: Admin `ai/codex/tasks/active/ATLAS-DIRECT-001-factor-visibility.md`, human_review.
Owner sonraki tam test isteği uygulandı: Atlas 194 geçti /22 hata, 689 assertion,
8,14 saniye. Bütün hatalar Storage::fake sırasında root:root /0700 geçici test
disklerine UID1000 kullanıcısının erişememesi. Admin tam paket 982 geçti /4 hata
(bağımlı tablolar eksik kaldırılan migration geri alma testleri) /1 kapasite atlandı.
Kod veya dosya izni düzeltilmedi. Gerçek 6.518 faktörün hash'i testlerden sonra aynı.
Atlas tam log: `C:/Users/Sinan/AppData/Local/Temp/netzero-atlas-full-tests-2026-09-08T07-45-55-716Z.log`.
Aşağıdaki candidate transport kayıtları tarihsel ayrı yoldur; doğrudan akışın
önkoşulu değildir.

## Son dilim — candidate S3 VersionId ve transport uyumu

Owner runtime onayından sonraki Atlas gerçek sentetik dilimi tamamlandı: ZIP
`09e3f18c…` /6934byte, gerçek VersionId `d61c8fb0-e4ec-47e9-a136-b17bbabc3b9d`;
yeni manifest `3af77be6…` /3449byte exact read-back ve immutable retry geçti.
24h child exact-ZIP GetObject/GetObjectVersion doğrulandı; list/write/delete ve
diğer nesne erişimi 403. Secret dosyası private0600/0700 olarak Admin koordinasyonuna
iletildi, Worker'a yazılmadı. DML/seed/commit/push yapılmadı; eski local manifest korundu.
Son kullanma 2026-09-08T17:01:33Z. [Gerçek kanıt](evidence/candidate-s3-versioned-acceptance-2026-09-07.json).
Admin koordinasyonunun sonraki bildirimi: gerçek Worker provider version GET/SHA ve
queue/scheduler üzerinden staging başarılı. Admin package
`01a07cd6-514c-71d3-9c45-845035005991`; görev ilk denemede tamamlandı/silindi, failure=0.
Beş imzalı HTTPS staging POST 200; receipt SHA
`8795afc3dc202427a6bbe0aa3606a2a93f4c0eb57872e680b0c49f8837a609e0` ve dört üye eşleşti.
Exact manifest yeniden kaydı created=false; ek task/package/record yok, receipt aynı.
Bu çapraz proje kanıtı Admin görevinin bildirimidir; Atlas burada bağımsız yeniden
çalıştırmadı. Atlas intake HTTP çağrılmadı; scientific approve/publish yok.

Admin koordinasyonuyla somut storage kusuru düzeltildi: ZIP önce gerçek upload/reuse
receipt'iyle doğrulanır, `atlas.candidate_ingress` manifesti gerçek VersionId ile bundan
sonra üretilir. Conditional create ve internal version receipt retry'da aynı sürümü
korur; previous package o sürümü okur. Sürümsüz local/fake mod açık test ayarı ister.
Admin semantic fingerprint v1 ve raw asset set descriptor hash'i ayrıca hizalandı;
Atlas internal immutable/reservation key'i ayrı tutuldu. Eski DB/manifest rewrite yok.

**30 ilgili test /149 assertion geçti**; 1/17 gerçek loopback SDK/socket kanıtıdır.
Gerçek MinIO/DB entegrasyonu çalıştırılmadı; runtime/IAM/env/migration/Docker lifecycle
değişikliği yok. Admin/Worker/core/platform salt okunur kaldı. Test çalışması sentetik
local fixture'ı yeniden üretti; development seed yapılmadı. Fixture path/hash envanteri
Admin görevine iletildi, `object_version_id=null` gerçek S3 kanıtı olarak sunulmadı.
[Kabul planı ve log](candidate-versioned-acceptance.md), [ADR-010](decisions/ADR-010-versioned-candidate-transport.md).
İlk kod tesliminde gerçek upload/IAM/secret-file ve staging adımları beklemedeydi;
üstteki owner onaylı gerçek sentetik dilim upload/IAM kısmını kapatır.
Admin bağımsız local preflight'ı geçti (manifest/fingerprint/raw set/entity schema);
package_fatal=false ve beklenen 7 record_blocker korundu. Son koordinasyon talebiyle
bu dilim commit/push yapılmadan çalışma ağacında teslim edildi; HEAD önceki `0cb394d`.

## Admin–Atlas adım 6 — güncel sonuç

Gerçek katalog teslimi tamamlandı: owner seçimiyle Atlas MinIO private `atlas-catalogs`
bucket'ı oluşturuldu. Manifest SHA
`38de9ae94013840926af3e6a223188cfabd05e1c12fc4990cf4c11513c2f408c`, 9404 byte;
25 artifact /937372 byte hedeften yeniden okundu. Aynı paket tekrar aktarıldı;
byte'lar aynı. Beş katalog exact loader ile bu hedeften tüketildi.
[Dosya bazlı kanıt](evidence/admin-atlas-step6-readback-2026-09-07.json),
[işletim](catalog-delivery.md), [ADR-008](decisions/ADR-008-exact-admin-delivery-and-current-approval-boundary.md).

Admin current-approval endpoint/sözleşmesi artık mevcut. Atlas HTTP adapter'ı,
bağımsız schema pinleri, exact HMAC/nonce/request/state doğrulaması ve CLI tamamlandı.
Her kontrol depoyu yeniden okur ve yeni sorgu yapar; checked-at gözlemi kullanım
yetkisi değildir. `requireCurrentApproval` güncel sorgudan sonra da eksik authority
body schema ve atomik finalization nedeniyle kullanımı kapalı tutar.
Gerçek paket `resolution=null`; canlı service/key/source etkinleştirmesi yapılmadı.
Adım 6 bütünü kapalı değil. [İşletim ve yeni kanıt](current-approval.md), [ADR-009](decisions/ADR-009-current-approval-observation-and-use-gate.md).
Admin currency nested hash ve taxonomy parent sıra düzeltmeleri mevcut Admin
sınıflarıyla `/tmp` sentetik tekrar üretimde doğrulandı; [rapor](admin-atlas-step6-review.md).
Admin/Worker/core dosyaları, Admin migration/V2 intake ve gerçek kararlar değiştirilmedi.

### Üç açık aşama için son çalışma

Owner Atlas geliştirmesi ve Admin görevine verilecek işin hazırlanmasını istedi;
Admin repository salt okunur sınırı teyit edildi. Yeni
`atlas:catalog:approval-readiness` komutu yerel config/schema pinleri ve seçilen
gerçek Atlas teslimini ağ isteği veya yazım yapmadan inceler. Gerçek paket kontrolü:
stored_delivery_verified=true, resolution_present=false; Atlas istemcisi kapalı ve
endpoint/key/secret boş. Admin runtime kapalı ve key/source listeleri boş.

Atlas container'ında `cleture-netzero-admin.test` 127.0.0.1 çözümleniyor; kimliksiz
HTTPS HEAD bağlantısı port 443'te kurulamadı. Network/TLS ve gerçek grant doğrulaması
açık. Admin private iki manifestte de resolution=null; merkezi DB sorgulanmadı.
[Admin'e verilecek somut iş](admin-approval-next-steps.md) hazır; başka göreve otomatik
gönderilmedi. Authority body şemaları ve finalization için endpoint/izin uydurulmadı.

Son doğrulama: **189 Unit/Feature test /715 assertion** ve **1 gerçek socket integration
test /8 assertion** geçti. İlgili dar kontroller 97/364; Pint (8 dosya), Composer
strict validate ve diff kontrolü başarılı. Loglar ve kanıt sınırı
[current-approval](current-approval.md) notundadır. Environment/migration/insan onayı
ve gerçek approved-resolution teslimi değiştirilmedi.

### Doğrulamalar tamamlandı

Güncel onay adapter'ı: **50 yeni Feature test /229 assertion**; tam Unit/Feature
**184 test /676 assertion** başarılı. Bağımsız gerçek socket peer ile **1 integration
test /8 assertion** geçti (HMAC, aynı body/yeni nonce retry, 409, redirect reddi).
Bu yerel sentetik HTTP kanıtıdır; canlı Admin grant/onay veya TLS rollout testi değildir.
İlgili 16 PHP dosyasında Pint, Composer strict validate ve diff kontrolü geçti.
Geçici loglar Windows TEMP içinde `atlas-approval-final-narrow-20260907-163544.log`,
`atlas-approval-regression-20260907-163603.log`, `atlas-approval-http-20260907-163431.log`
ve `atlas-admin-a1-a2-20260907-163431.log`.

Önceki katalog teslim doğrulaması:

Kullanıcının ayrı düzeltme onayıyla iki bilimsel sentetik fixture'a zorunlu `names.tr`
eklendi; retry assertion'ı exact JSON içerik karşılaştırmasına çevrildi. Eski candidate
fixture döngüsü desteklediği unit/geography ile sınırlandı. Üretim sözleşmeleri bu
test düzeltmeleri için gevşetilmedi.

- Dar delivery + candidate build kontrolleri: **47 test /121 assertion** başarılı.
- Tam Unit/Feature regresyon: **134 test /447 assertion** başarılı.
- Gerçek MinIO integration: **1 test /9 assertion** başarılı. Koşullu create/retry/
  tam read-back/conflict/eksik marker random `atlas-delivery-test-*` bucket'ta
  doğrulandı; bucket temizlendi. DB kullanılmadı.
- İlgili dosyalarda Pint, Composer strict validate ve diff kontrolü geçti.

Geçici loglar `C:\Users\Sinan\AppData\Local\Temp` altında:
`atlas-delivery-fixed-20260907-152533.log`, `atlas-full-step6-20260907-152604.log`,
`atlas-minio-step6-20260907-152610.log`. İlk başarısız fixture/assertion çalıştırmaları
bu sonuçlarla giderildi. Provision/transfer/read-back logları aynı dizinde
`atlas-catalog-{provision,transfer,readback}-20260907-*.log` adlarıyla.

Atlas katalog dilimi `ac6592d` ile origin/main'e gönderildi. Güncel onay adapter
dilimi de doğrulamalar sonrası mevcut `main` branch'inde commit/push edilir;
kimliği `git log` ile okunur. Devam için gerçek service/key/source etkinleştirme,
onaylı çözüm teslimi, kapalı authority body şemaları ve finalization protokolü gerekir.
Mevcut candidate `.env` pinleri kendiliğinden değiştirilmedi.

## Önceki candidate build durumu — 2026-09-05

Atlas'ın mevcut sahip sözleşmelerinden bağımsız validation ve candidate build dilimi
tamamlandı. Sabit build komutu, hash-pinned semantic policy, lisans evidence consumer,
validation ledger, verified previous package reader, disk tabanlı diff V2 ve eşzamanlı
idempotent package assembly mevcut. Bu durum gerçek ADEME candidate üretildi veya
Admin intake/publish hazır demek değildir.

Bu fazın 2026-09-05 doğrulaması: 91 Unit/Feature test / 344 assertion; gerçek PostgreSQL + MinIO üzerinde
1 integration test / 10 assertion geçti. Pint ve Composer strict validate geçti.
Yeni migration yalnız `atlas_netzero` üzerinde uygulandı. Geçici entegrasyon DB'si ve
random test bucket temizlendi; çalışma DB'si resetlenmedi.

## Sahip projelerde BEKLEYEN — başlamayacaklar

İlk olarak ilgili task'lara yalnız günlük/backlog kaydı iletildi. Kullanıcı yeniden
durum sorduğunda buradan değerlendirme yapılacak; bu kayıt otomatik işe başlama,
test, migration, deploy veya rollout talimatı değildir.

| Sahip | Bekleyen girdi/karar | Kalıcı kayıt |
| --- | --- | --- |
| NetZeroAdmin / Atlas koordinasyonu | Güncel onay transport/schema ve A1/A2 düzeltmeleri doğrulandı. Explicit service/key/source etkinleştirme, gerçek approved-resolution teslimi, authority body schema ve atomik finalization açık. Compound applicability ve V2 intake/blocking review ayrı bağımlılıklardır. | [Current approval](current-approval.md), [Adım 6 geri bildirim](admin-atlas-step6-review.md) |
| Worker, Admin koordinasyonuyla | V2 durable staging ve kanıtlı retry/permanent-failure davranışı; mevcut V1 verifier yeniden yazılmayacak | `/home/sinan/projects/cleture-netzero-worker/.ai/CROSS_PROJECT_INBOX.md`, “2026-09-05 — Atlas main 35b82db / Admin V2 durable staging coordination” |
| Atlas source evidence girdisi | Gerçek ADEME license terms exact byte'ları, kaynak/release bağı ve attribution metadata'sı | Bu günlük; Admin/Worker'a lisans edinme işi atanmadı |

Geography canonical sahibi kesin NetZeroAdmin; Logi route/mesafe sahibidir. Atlas
merkezi/tenant DB'ye bağlanmaz. Eşleşmeyen birim/coğrafya ve doğrulanamayan dimension,
formula veya taxonomy başarıya çevrilmez. Lisans evidence hash kontrolü hukuki review
yerine geçmez. İnsan review ve publish Admin'e aittir.

## Yeniden devam sırası

1. Bu dosyayı, günlüğü, git durumunu ve ilgili owner kayıtlarını oku; eski hazır
   durumunu varsayma. Memory/index araçları varsa proje/index neslini doğrula.
2. Yeni teslim varsa amaç, sahiplik, version/hash, payload byte'ları ve kabul
   kanıtlarını yeniden değerlendir. Eksik sözleşmeye Atlas workaround'u ekleme.
3. Gerçek girdiler hazır olduğunda açık normalized artifact ID ve lisans descriptor
   ile local build planı hazırla. Runtime artifact mevcudiyetini önce doğrula.
4. Bulgu dağılımını ve önceki release diff'ini incele; blocking adayları publish-ready
   sayma. [İşletim sözleşmesini](candidate-build.md) uygula.
5. V2 intake/staging kabulü ve kullanıcı yönlendirmesi olmadan canlı teslimi açma.

Şu anda bağımlılık sahiplerini çalıştırmak veya yeni phase'i kendiliğinden başlatmak yok.
