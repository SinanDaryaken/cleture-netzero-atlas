# Admin–Atlas adım 6 incelemesi — 2026-09-07

## Güncel ek değerlendirme — current-approval adapter

Aşağıdaki A1/A2 ve kanal yokluğu kayıtları ilk incelemenin tarihsel bulgularıdır.
Admin mevcut çalışma ağacı yeniden incelendi: `FactorContextContract::assertCurrencyIntegrity`
kayıt hash/tekillik/usable kontrolünü yapıyor; `LookupReviewCatalog::taxonomyPath`
parent listelerini typed küme olarak sıralayıp karşılaştırıyor. Mevcut Admin sınıflarını
`tests/Support/reproduce-admin-delivery.php` ile `/tmp` sentetik girdiler üzerinde
çalıştırınca **currency accepted=false**, **taxonomy status=registered** elde edildi.
İki bulgu mevcut çalışma ağacında giderilmiştir; Admin repository/DB yazımı yapılmadı.

Yeni `POST /internal/v1/atlas/current-approval` sözleşmesi yeniden kabul kapısından
geçirildi. Atlas adapter'ı, imzalı yanıt doğrulaması, bağımsız schema pinleri ve
her çağrıda yeni sorgu geliştirildi. Canlı etkinleştirme, authority body şemaları ve
atomik finalization açık; final kullanım kontrolü kapalıdır.
[Güncel kapsam, kanıt ve kalan owner girdileri](current-approval.md).

## Kapsam ve kabul

Admin mevcut çalışma ağacı salt okunur incelendi; yalnız HEAD kullanılmadı. Atlas
loader/teslim adapter'ı Atlas sorumluluğunda kabul edildi. Admin/Worker/core dosyaları,
Admin migration'ları, V2 intake kapısı ve gerçek insan kararları değiştirilmedi.
Başlangıçta Atlas çalışma ağacı temizdi. Runtime PHP 8.5.8, Composer 2.10.2,
Laravel 13.30.1 ve mevcut Boost 2.7.0 doğrulandı. Host'ta PHP/Composer/rg yok;
çalışan `cleture-netzero-atlas-php-1` runner'ı ve doğrudan kaynak okuması kullanıldı.
Memory/graph araçları sunulmadı; index nesli ve coverage sertifikası doğrulanamadı.
`START_HERE.md` repository ve proje dizini aramalarında bulunmadı; AGENTS.md,
README, docs/CURRENT.md, roadmap, ADR-004 ve candidate-build okundu.

## Admin bulguları

### A1 — Currency tesliminde kayıt hash'i semantik olarak doğrulanmıyor (P2)

- Kaynak: `app/Actions/AtlasCatalogSnapshot/ReadDeliveryCatalog.php:49`, özellikle
  50–52; çağırdığı `FactorContextContract::assertValid` yalnız JSON Schema doğrular.
- Tekrar üretim: sentetik EUR kaydının `sha256` alanını 64 sıfır yap; payload'ın
  exact byte hash'ini ve descriptor'ı buna göre doğru oluştur. Admin private katalog
  okuyucusunun kullandığı storage arayüzünü yalnız `/tmp` sentetik dosyalara yönlendir.
  `ReadDeliveryCatalog::handle('currency', outer_hash)` başarıyla descriptor döndürür.
- Etki: başarılı hazırlama, nested currency kayıt bütünlüğünün geçtiğini kanıtlamaz.
  `entry_sha256` ile exact lookup yapan tüketici aynı teslimi reddedebilir.
- Beklenen düzeltme: currency export ve delivery/lookup sınırında ortak semantik
  kontrol; kayıt hash'ini hash alanı hariç exact sorted JSON üzerinden doğrulama,
  ID/code tekilliği ve usable = active && !deleted kontrolü. Yanlış nested hash'i
  doğru outer hash ile veren bağımsız negatif fixture eklenmesi değerlendirilmeli.
- Gözlenen kanıt: `Admin_ReadDeliveryCatalog_accepted=true`, `entry_hash_valid=false`.
  Gerçek teslimde currency kayıt hash'leri Atlas doğrulamasından geçti; gerçek paketin
  bozuk olduğu iddia edilmiyor.

### A2 — Taxonomy parent sırası için sözleşme/lookup tutarsızlığı (P2)

- Kaynak: `app/Actions/AtlasCatalogSnapshot/LookupReviewCatalog.php:49`, özellikle
  54–55. `ReviewCatalogContract::assertValid` parent kind'larını sıralayıp karşılaştırır;
  schema parent dizi sırasını sabitlemez.
- Tekrar üretim: geçerli altı tür graph'ta segment parents listesini
  `[scope:<id>, protocol:<id>]` yap; node ve payload hash'lerini yeniden hesapla.
  Sözleşme doğrulaması başarılı, aynı altı kimlikle `taxonomyPath` sonucu
  `context_mismatch` olur. Graph bağlantısı değişmemiştir.
- Etki: sözleşmeye uygun bağımsız producer veya yeniden sıralanmış export yanlış
  biçimde bağlantısız kabul edilir. Export+lookup testinin aynı builder sırasını
  kullanması bu farkı gizler.
- Beklenen düzeltme: ya typed parent kümesini karşılaştırma ya da yeni sürümlü
  sözleşmede sıra zorunluluğunu açıkça tanımlama. Geçerli permütasyonla bağımsız test.
- Gözlenen kanıt: `Admin_contract_accepted=true`, `Admin_lookup_status=context_mismatch`.

Her iki tekrar üretim mevcut Admin PHP sınıflarını çalıştırdı. Admin repository'sine
dosya/test yazılmadı, Admin DB bağlantısı açılmadı, test fixture'ları geçici alanda
temizlendi. İlk kanıt logu:
`C:\Users\Sinan\AppData\Local\Temp\atlas-admin-review-20260907-151457.log`.
Admin düzeltmeleri bu görev kapsamında uygulanmadı; bulgular değerlendirme girdisidir.

## Atlas bulguları ve değişiklikler

- Eski loader yalnız V1 unit/geography biliyordu. Ayrı `delivery-v1` trust registry ve
  content v2 / contract 2.1.0 unit validator eklendi. Eski schema byte/hash'leri ve
  kapalı candidate 2.0.0 sözleşmesi değişmedi.
- Gerçek 181 unit definition içinde aynı code farklı quantity-kind'larda bulunuyor.
  Eski global code tekilliği V2 için yanlış. V2 kind/unit ilişkileri doğrulanır;
  code/symbol resolver birden çok hedefte ambiguous kalır, kimlik yeniden üretilmez.
- Exact manifest SHA bağımsız girdidir. Beş contract root hash'i Atlas kodunda pinli;
  schema/dependency dosyaları Admin'in incelenen çalışma ağacından exact kopyadır.
  Paket içindeki schema kendi güven kaynağı değildir. Registry tüm import hash ve
  schema ID bağlarını doğrular; eski source-proposal importları değiştirilmedi.
- Canonical JSON, candidate RFC8785'ten ayrı tutulur. Null/empty object/list ve decimal
  string korunur; floating point, duplicate key ve noncanonical byte reddedilir.
- Descriptor/payload/schema/version, nested kayıt hash'leri, scientific kind/definition/
  conversion bağları, taxonomy parents/links ve lifecycle kontrolleri eklendi.
- S3 `If-None-Match: *`, conflict halinde byte koruma, bounded read-back, manifest-last
  aktarım ve explicit catalog/version/hash loader eklendi. Kısmi teslim yüklenemez.
- Review lookup `entry_sha256` alanını kendi sonucunda taşır; candidate hedef shape'ine
  eklemez. Üç intended-use kaydı kullanım/publish yetkisi vermez.

## Ortak sözleşme: güncel onay tüketimi açık

İncelenen Admin `LookupApprovedResolution`, CLI ve route/controller çağrı noktalarında
Atlas'a yetkili servis kanalı tanımlanmamış. CLI aktif `Admin` actor ve bağımsız raw
bytes ister; ayrıca unit export ile yerel snapshot yazımı yapabilir. Atlas bunu HTTP
API veya salt okunur servis endpoint'i kabul etmez; actor/credential uydurmaz.

Mevcut teslimde `resolution=null`. Altı tür için sentetik historical evidence
doğrulayıcı var; bu bir current-approval consumer değildir. `approved_at_lookup` kalıcı
yetki sayılmaz. `requireCurrentApproval` exact beklenen envelope kontrolünden sonra bile
kanal yokluğunda fail-closed kalır. Eski kaynak/revision/resolution/decision/ruleset,
supersession ve ret/yeniden onay eski teslimi güncel hale getirmez.

Admin'den yeniden değerlendirme için beklenen somut sözleşme:

1. Yetkili servisler arası transport veya yetkilendirilmiş operator handoff modelinin
   sahibi, caller kimliği ve scope; mevcut web admin kimliği Atlas credential'ı olmaz.
2. İstek pinleri: family/identity, source code/dataset/release/raw key+SHA+size,
   proposal key/revision ID+number+SHA/receipt SHA, resolution ID+version+SHA,
   decision ID+SHA/supersession, expected validation ruleset ve base published katalog.
3. Yanıt: bu exact isteğe bağlı güncel head/ret/supersession/ruleset sonucu;
   eski pin, yeni revision, yeniden onay veya kurallar değiştiğinde açık fail-closed
   durumlar. Retry/error ayrımı, yanıt kimlik/hash doğrulaması ve kullanım anındaki
   freshness/fencing davranışı tanımlanmalı; hazırlanma zamanındaki lookup yeterli değil.
4. Resolution payload/decision/receipt/scientific provenance için bağımsız pinli,
   kapalı transport schema'ları. Mevcut delivery envelope artifact hash'lerini taşır;
   artifact body'lerinin tam wire schema'ları henüz bu bundle'da tanımlı değildir.
5. Yeni unit/kind'da exact onaya bağlı eski base ve yayımlanmış yeni hedef/provenance
   birlikte korunmalı. Alias/context çözümü otomatik mapping, executable recipe,
   FX, applicability veya publish yetkisi vermez.

Bu bağımlılık gerçek katalog provisioning'den ayrı raporlanır. Admin 7A V2 migration
ve Worker rollout bu görev kapsamı dışında kalır.

## Test ve gerçek teslim sonucu

Gerçek katalog aktarımı ve retry/read-back tamamlandı; manifest hash, gerçek hedef ve
her artifact için gözlenen boyut/SHA [kanıt JSON'unda](evidence/admin-atlas-step6-readback-2026-09-07.json).
Gerçek MinIO conditional-create/conflict/partial test'i ayrı random bucket'ta başarılı;
bucket temizlendi. Taxonomy sıra/lifecycle lookup testiyle birlikte 2 test /16 assertion.

İlk delivery 42 testten 39'u, mevcut regresyon 91 testten 86'sı geçti. Kullanıcının
ayrı onayıyla iki sentetik bilimsel fixture'ın eksik `names.tr` alanları, retry
assertion'ının stdClass identity karşılaştırması ve beş eski candidate testini
etkileyen fixture katalog döngüsü düzeltildi. Schema veya üretim kontrolleri gevşetilmedi.

Son dar kontroller **47 test /121 assertion**, tam Unit/Feature **134 test /447
assertion**, gerçek MinIO integration **1 test /9 assertion** başarılı. Pint, Composer
strict validate ve diff kontrolü başarılı. Atlas katalog dilimi commit/push için
doğrulanmıştır; current approval bağımlılığı açık kalır. Ayrıntı ve loglar CURRENT'tadır.
