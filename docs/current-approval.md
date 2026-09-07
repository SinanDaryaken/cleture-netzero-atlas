# Admin güncel onay sorgusu — Atlas tüketicisi

2026-09-07: Atlas HTTP adapter'ı, bağımsız şema pinleri, uygulama sınırı ve CLI
tamamlandı. Admin mevcut çalışma ağacındaki `AtlasCurrentApprovalContract`,
`CheckAtlasCurrentApproval`, `AtlasCurrentApprovalController`,
`HmacAtlasServiceAuthenticator` ve ilgili delivery testleri salt okunur incelendi.
Admin'in key/source yetkilendirmesi ve servis principal'ı Atlas'ın sorumluluk
sınırlarına uygun; yalnız sorgu anındaki durumu bildiren tüketici kapsamı kabul edildi.

## Güven girdileri

Admin görev kaydının “Atlas tüketici bağlantısı için kesin sözleşme” bölümündeki
bağımsız pinler, Atlas `PinnedCurrentApprovalContracts::HASHES` içinde sabittir.
Şemalar `resources/contracts/netzero-admin/current-approval-v1` altında exact
kopyalandı; her doğrulamada yerel dosyanın hash'i yeniden kontrol edilir.

| Şema | SHA-256 |
| --- | --- |
| atlas-current-approval-request-v1.schema.json | `3b69965e96762d4edae9f862732cff76b7b7d4b5bf9e095a3891b7f18a569a61` |
| atlas-current-approval-response-v1.schema.json | `13c5684160586c19988365d7c85a4b71c1a81cb80e20c6da10bc3b54aa5929b6` |

Bu iki şema mevcut catalog-only MinIO tesliminin parçası değildir. Eski sealed
delivery/catalog/candidate şemaları ve gerçek manifest değiştirilmedi.

## Davranış

`CheckDeliveredResolutionApproval::inspect(deliverySha256, expected)` her çağrıda
Atlas deposundan exact teslimi yeniden okur, byte/schema/semantik doğrulamalarını
yürütür. Çağıranın bağımsız işlem bağlamından verdiği tam expected resolution
envelope teslimle eşit olmalıdır. `VerifyDeliveredResolution::inspectCurrentApproval`
tarihsel kaynak/raw/revision/resolution/decision/ruleset/supersession ve scientific
published target kontrollerini korur. Base katalog, onayın orijinal formundaki
`unit_catalog_sha256` ile teslimden seçilir; yeni scientific target base'i değiştirmez.

`HttpCurrentApprovalClient`, POST `/internal/v1/atlas/current-approval` için kapalı
şemalı exact sorted JSON üretir. Yeni UUIDv7, nonce, timestamp ve exact body SHA
ile mevcut Admin HMAC v1 sözleşmesini uygular. Header imzası `sha256=` biçimindedir.
Yanıt hash/HMAC kontrolü, gönderilen key/nonce/request SHA değerlerinden hesaplanır;
sonra closed schema, UUID, teslim SHA, HTTP/status ve bağımsız hesaplanan state SHA
karşılaştırılır. Response'un kendi iddia ettiği değerler güven kökü değildir.

200/current yalnız `CurrentApprovalObservation` döndürür. Gözlem
`validity=checked_at_only`, cache/automatic_mapping/usage/publish=false taşır;
`VerifiedAtlasDelivery::receipt()` içindeki current_approval_verified=false korunur.
Önceki başarılı gözlem yeni sorgunun yerine geçmez. Checked-at bir lease süresi değildir.

409/not_current hemen durur; eski karar veya katalog pinleri otomatik değiştirilmez.
İmzalı 503/unavailable ve bağlantı/istek timeout hataları en fazla yapılandırılmış
deneme sayısı kadar yeniden sorgulanır; her denemede yeni nonce, aynı exact body ve
beklenen pinler kullanılır. İlk bekleme 100 ms, ikinci 200 ms. Diğer HTTP durumları,
imza/schema/bağ hataları, eksik imzalı 503 dahil bozuk yanıtlar hemen durur.
Yanıt gövdesi okuma hatası da fail-closed olur. Redirect takip edilmez.
Request ve response ayrı ayrı en fazla 16384 byte; response bounded stream olarak
okunur ve kapatılır. Bağlantı hatasının credential taşıyabilen asıl mesajı aktarılmaz.

`requireCurrentApproval` ve uygulama `requireForUse` kontrolü yeni sorguyu yapar,
başarılı gözlemden sonra da final kullanımı reddeder. Historical authority body
schema provisioning ve uzaktaki işlemle atomik finalization sözleşmesi henüz yoktur.
Bu nedenle normalizer/candidate mapper içine otomatik çözüm uygulama eklenmedi.
Alias/context onayı FX, recipe, applicability veya yayın yetkisi değildir.

## İşletim

Etkinleştirme öncesi secret-safe yerel kontrol:

```bash
php artisan atlas:catalog:approval-readiness
php artisan atlas:catalog:approval-readiness <independent-delivery-sha256> --expected=/absolute/expected-resolution.json
```

Komut ağ isteği, environment değişikliği, onay veya storage yazımı yapmaz. Seçilen
Atlas teslimini her çalıştırmada yeniden okur; schema pinleri, bağlantı ayarları,
resolution varlığı ve bağımsız expected envelope kontrol edilir. Çıktıda credential
değerleri bulunmaz. Exit 0 / local_preflight_passed yalnız yerel sorgu önkoşullarıdır;
Admin grant, canlı HTTPS/HMAC ve final kullanım hâlâ ayrıca doğrulanmalıdır.
Exit 1 / blocked eksik girdileri machine-readable blocker kodlarıyla bildirir.

```bash
php artisan atlas:catalog:current-approval <independent-delivery-sha256> /absolute/expected-resolution.json
php artisan atlas:catalog:current-approval <independent-delivery-sha256> /absolute/expected-resolution.json --require-for-use
```

Expected dosyası exact sorted JSON tam resolution envelope olmalıdır; manifestten
körü körüne türetilmiş “latest” onay veya insan aktörü kabul edilmez. İlk komut
yalnız gözlem raporlar; ikinci komut v1'de final kullanım sınırı kapalı olduğundan
başarılı güncel sorgudan sonra da nonzero çıkar. Catalog-only resolution=null paket
güncel çözüm sorgusu yapamaz.

Atlas config `atlas.current_approval` varsayılan kapalıdır. Alanlar:

| Environment alanı | Varsayılan / sınır |
| --- | --- |
| ATLAS_ADMIN_CURRENT_APPROVAL_ENABLED | false |
| ATLAS_ADMIN_CURRENT_APPROVAL_ENDPOINT | boş; exact path, HTTPS; yalnız literal loopback HTTP test istisnası |
| ATLAS_ADMIN_CURRENT_APPROVAL_KEY_ID | boş; Admin tarafından yetkilendirilmiş servis key'i |
| ATLAS_ADMIN_CURRENT_APPROVAL_SECRET | boş; mevcut Admin HMAC kimliğiyle eşleşen en az 32 byte secret |
| ATLAS_ADMIN_CURRENT_APPROVAL_MAX_ATTEMPTS | 2 / 1–3 |
| ATLAS_ADMIN_CURRENT_APPROVAL_CONNECT_TIMEOUT_SECONDS | 3 / 1–10 |
| ATLAS_ADMIN_CURRENT_APPROVAL_TIMEOUT_SECONDS | 10 / 1–30 |

Endpoint userinfo/query/fragment içeremez; TLS doğrulaması açık kalır. Config/env
cache yönetimi operator etkinleştirmesine aittir. Bu geliştirmede `.env`, credential,
Admin grant, migration, gerçek onay, V2 intake veya Docker lifecycle değişmedi.
Admin kayıtlı runtime durumu enabled=false ve key/source listeleri boştur.
Canlı açılış için mevcut HMAC kaynak kapsamıyla kesişen explicit Admin key/source
grant, Atlas endpoint/kimlik ayarı ve gerçek approved-resolution teslimi gerekir.

## Doğrulama ve açık sınır

- Yeni Feature: **50 test /229 assertion**; altı tür, eski base/yeni target,
  tam beklenen pinler, signature/hash/schema/status/policy bağları, replay,
  ret sonrası tekrar sorgu, bounded retry/timeout, bozuk config, schema pin değişimi,
  büyük multibyte istek, CLI ve depodan her kullanımda yeniden okuma.
- Tam Unit/Feature: **184 test /676 assertion** başarılı.
- Ayrı gerçek socket integration: **1 test /8 assertion** başarılı. Mevcut Atlas
  runner'ında geçici standalone PHP peer istek HMAC'ini bağımsız doğruladı;
  503→200 retry'da aynı body/yeni nonce, sonraki 409 ve 302 davranışları gözlendi.
  Bu sentetik HTTP peer gerçek Admin onayı, canlı TLS veya servis grant kanıtı değildir.
- Admin A1/A2 tekrar üretimi: yanlış nested currency hash'i reddedildi; scope/protocol
  parent sırasına sahip aynı taxonomy graph'ı registered döndü. Yalnız `/tmp`
  sentetik dosyalar ve mevcut Admin PHP sınıfları; DB ve repository yazımı yok.
- İlgili 16 PHP dosyasında Pint, Composer strict validate ve git diff kontrolü geçti.

Timestamp'li geçici loglar Windows `C:\Users\Sinan\AppData\Local\Temp` altında:
`atlas-approval-final-narrow-20260907-163544.log`,
`atlas-approval-regression-20260907-163603.log`,
`atlas-approval-http-20260907-163431.log`, `atlas-admin-a1-a2-20260907-163431.log`.
Önceki delivery regresyonuyla birlikte dar ilk koşu da 90 test/315 assertion geçti.
İlk Pint çağrısı root runner'ın Git sahipliği nedeniyle çalışmadı; repository sahibi
UID 1000 ile tekrar çalıştırıldı, Git safe-directory veya environment değiştirilmedi.

Atlas kod/test dilimi tamamlandı. Canlı onaylı çözüm tüketimi, authority body schema
teslimi ve atomik finalization açık kalır; adım 6'nın bütünü kapatılmaz.

## 2026-09-07 etkinleştirme hazırlığı

Owner Atlas geliştirmesi ve Admin görevine verilecek somut işin hazırlanmasını
istedi; Admin salt okunur sınırı korundu. Readiness komutu gerçek Atlas MinIO'dan
önceki catalog-only teslimi doğruladı. İstemci kapalı, endpoint/key/secret boş,
resolution yok: atlas_connection_not_configured ve approved_resolution_delivery_required.
Admin runtime current-approval kapalı ve iki grant listesi boş olarak yeniden doğrulandı.
Admin private iki hazırlanmış tesliminde de resolution=null bulundu; Admin DB'deki
insan kararları bu incelemede sorgulanmadı.

Ayrı kimliksiz HEAD kontrolünde Atlas container'ından Admin HTTPS adresine TCP
bağlantısı kurulamadı (curl exit 7). `cleture-netzero-admin.test` container içinde
127.0.0.1 çözülüyor. TLS veya canlı HMAC başarısı iddia edilmez; platform dosyaları
ve network ayarları değiştirilmedi. [Admin'e verilecek iş](admin-approval-next-steps.md).

Yeni readiness testi 5 test/39 assertion; ilgili delivery/current-approval ile birlikte
97 test/364 assertion geçti. Tam Unit/Feature **189 test/715 assertion**, ayrı gerçek
socket integration **1 test/8 assertion**, ilgili 8 PHP dosyasında Pint ve Composer
strict validate başarılı. Test başarısızlığı yok. Windows TEMP logları:
`atlas-approval-readiness-tests-20260907-165218.log`,
`atlas-readiness-regression-20260907-165249.log`,
`atlas-approval-readiness-runtime-20260907-165248.log`,
`atlas-admin-tls-probe-20260907-165249.log`.
