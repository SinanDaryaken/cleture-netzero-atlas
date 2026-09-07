# Admin'e iletilecek iş — onaylı çözümün gerçek Atlas tüketimi

Tarih: 2026-09-07. Kaynak: cleture-netzero-atlas. Atlas temel teslim commit'i
`0c82082` (origin/main); sonraki hazırlık kontrolü aynı branch'tedir.
Owner kapsamı: Atlas geliştirmesi ve Admin görevine verilecek somut işin hazırlanması.
Bu belge Admin'e otomatik çalıştırma veya gerçek insan onayı üretme talimatı değildir.
Admin kendi sahiplik, bağımlılık, çalışma ağacı ve kabul kapısından yeniden değerlendirmelidir.

## Amaç ve mevcut kanıt

Atlas'ın hazırladığı adayda kullanılan kaynak çözümünün exact kanıtlarını doğrulamak,
Admin'deki insan kararına bağlamak ve nihai kabulü tutarlı biçimde Admin'de yapmak.
Katalog kaydı, kaynak çözümü onayı, candidate kabulü ve publish ayrı kalır.

- Atlas'ta current-approval request/response şemaları bağımsız pinli, HMAC/nonce/
  UUID/request/delivery/state hash bağları doğrulanıyor. Bounded retry, no-cache,
  eski base katalog ve published target kontrolleri var.
- Admin runtime `atlas_intake.current_approval`: enabled=false, allowed_key_ids=[],
  allowed_source_codes=[]. Servis container'ları çalışıyor.
- Atlas runtime: istemci disabled; endpoint/key_id/secret tanımlı değil. Bu kontroller
  secret değerlerini göstermeden raporlayan readiness komutuyla yapıldı.
- Atlas container'ında `cleture-netzero-admin.test` adresi **127.0.0.1** çözümleniyor.
  Kimlik bilgisi taşımayan HEAD denemesi port 443'e bağlanamadı (`curl` exit 7).
  Bu adres Atlas container'ının kendisine işaret ediyor. TLS handshake, sertifika güveni
  ve Admin HMAC yetkisi bu denemede doğrulanmış değildir.
- Admin private delivery dizinindeki iki manifestte de resolution=null:
  `38de9ae94013840926af3e6a223188cfabd05e1c12fc4990cf4c11513c2f408c` ve
  `1df33a28f113ea13ae5242baad06979b5dd17510d5c5f93505c372addc7c7fbf`.
  İkinci manifest yalnız keşif kanıtıdır; bağımsız onaylı teslim pini olarak benimsenmedi.
  Admin DB'deki olası insan kararları Atlas tarafından sorgulanmadı. “Hiç gerçek karar
  yok” iddiası yapılmıyor; hazırlanmış onaylı teslim bulunamadı.

## 1. Servis etkinleştirme teslimi

Sahipler: Admin servis yetkilendirmesi, platform erişim/TLS, Atlas istemci ayarı.

Admin değerlendirmesinden beklenen somut çıktı:

- Atlas container'ından erişilebilen, Admin'in exact internal path'ini sunan HTTPS
  adresi ve sertifika güven zinciri. TLS doğrulamasını kapatma veya HTTP'ye sessiz
  downgrade çözüm değildir. Ortak proxy/network değişiklikleri platform kapsamında
  ve diğer projeleri etkilemeden hazırlanmalıdır.
- Mevcut HMAC kimliğiyle eşleşen explicit key ve kaynak kapsamı. Admin'in current
  approval allow-list'i ile genel HMAC source scope kesişimi korunmalıdır. Secret
  rapor/commit/komut argümanı içinde paylaşılmamalı; gerekiyorsa onaylı secret teslim
  mekanizması ayrıca tarif edilmelidir. İnsan Admin aktörü servis kimliği olamaz.
- Güvenli etkinleştirme sırası, config cache etkisi ve geri dönüş adımı. Default kapalı
  davranış korunmalı; dev/prod ortamları karıştırılmamalı. Genel candidate intake/V2
  kapısını current-approval etkinleştirmesi nedeniyle açmak kapsam dışıdır.

Kabul kanıtı: gerçek Atlas runner→Admin HTTPS isteği; yetkili key/source için doğru
imzalı yanıt, yetkisiz key/source ve tekrar nonce reddi. Boş/yanlış secret veya
untrusted TLS ile istemci kapalı kalır. Geri dönüşte yeni sorgular açılamaz.
Canlı sistemde gerçek kararı bozarak negatif test yapılması beklenmez; revocation
senaryoları izole test ortamında kanıtlanabilir.

## 2. Gerçek insan onaylı çözümün teslimi

Sahip: Admin insan review ve teslim hazırlama; Atlas immutable transfer/read-back.

Admin'den gerekli bağımsız girdiler:

- Gerçek kaynak/dataset/release ve raw artifact kimliği, exact raw SHA/byte sayısı.
- Uygun, mevcut insan onaylı resolution ve current decision kimlik/hash'leri;
  revision, önceki resolution, supersession, ruleset ve gerekiyorsa published target.
  Uygun kayıt yoksa insan review yapılması gerekir; fixture, otomatik onay veya
  rastgele aktif Admin UUID'si seçmek gerçek onay yerine geçmez.
- Onayın orijinal published base katalog pini; new_unit/new_quantity_kind için exact
  onaya bağlı published hedef ayrıca. Latest katalogla repin yapılmamalı.
- Hazırlanmış private immutable delivery kökü, manifest byte sayısı ve **teslimden
  bağımsız sağlanan manifest SHA**, artifact envanteri ve bağımsız expected resolution
  envelope. Envelope kaynağı ve hangi gerçek işlem için beklenildiği açık olmalı.

Mevcut Admin hazırlama arayüzü `atlas:prepare-delivery`:
`--resolution`, `--decision-sha256`, `--admin`, `--raw`, tekrarlanabilir `--catalog`.
Bu seçeneklerin varlığı doğrulandı; gerçek değerler seçilmedi ve komut çalıştırılmadı.
Hazırlama operator yetkisiyle unit export yapabilir; current-approval HTTP sorgusu
export yapmaz. Operator işlemi ile servis sorgusu ayrı değerlendirilmelidir.

Atlas devamı: bağımsız pinleri yerelde doğrula → onaylı private atlas-catalogs
deposuna manifest-last immutable transfer → aynı içerikle retry → tüm artifact'leri
hedeften yeniden oku → exact expected resolution ve eski base/yeni target bağlarını
kontrol et → gerçek authenticated current-approval sorgusu yap. Eksik paket veya
409 sonucunda latest fallback ve otomatik yeni onay yoktur.

## 3. Authority body şemaları ve nihai kabul protokolü

Sahip: Admin sözleşme ve nihai kabul; Atlas tüketici ve provisional candidate hazırlama.
Mevcut current-approval v1 wire byte'ları geriye dönük genişletilmemelidir.

### 3A — Authority belgelerinin kapalı şemaları

Mevcut delivery envelope şeması bu belgelerin içeriğinin kapalı şeması değildir.
Admin exact ürettiği body formatları için sürümlü, bağımsız hash-pinned bir kök ve
artifact→schema eşleşmesi sağlamalı; ilgili conditional tür ilişkilerini tanımlamalıdır:

| Artifact | Beklenen kapsam |
| --- | --- |
| source/receipt.json | Kaynak kabul makbuzu, revision/proposal/identity pinleri ve yetki sınırı |
| resolution/payload.json | Altı türün form/validation çıktıları, source decision/revision ve ruleset bağları |
| resolution/decision.json | İnsan approve/reject kararı, resolution/ruleset ve supersession kimlikleri |
| evidence/*.receipt.json | Attachment kimliği, exact bytes/hash, kaynak/karar bağı ve locator |
| resolution/scientific-provenance.json | Approved resolution/decision, base, target release ve reference ilişkisi |
| resolution/scientific-reference.json | Published reference body için mevcut veya yeni pinli şema eşleşmesi |

Source proposal ve published katalogların mevcut kapalı sözleşmeleri yeniden
uydurulmamalı; yeni authority kökü bunların bağımlılık pinlerini açık taşımalıdır.
Unknown field/type, missing evidence, nested hash mismatch, null/empty object/list,
UUIDv7 ve decimal semantiği fail-closed tanımlanmalı. Geçmiş immutable belge yeni
şemaya uymuyorsa byte'ları değiştirmek yerine owner sürüm/geçiş politikası gerekir.

### 3B — İşlemle bağlı son onay kontrolü

`current` yanıtı sorgu anını gözler; daha sonra bir başka veritabanına yazılan sonucu
atomik biçimde yetkilendiremez. Yalnız ikinci bir HTTP sorgusu eklemek yarış aralığını
ortadan kaldırmaz. Candidate publish veya production kullanım izni de üretmez.

Admin'in değerlendirmesi için önerilen dar yaklaşım: Atlas'ın provisional çıktısı
immutable üretildikten sonra **o exact çıktının Admin tarafından kabulü**, güncel
source/revision/resolution/decision/ruleset kontrolleri ve kabul kaydıyla aynı Admin
transaction'ında yapılır. Böylece global dağıtık transaction veya süresiz onay token'ı
iddiası gerekmez. Bu henüz kabul edilmiş wire/API değildir; endpoint uydurulmadı.

Owner sözleşmesinin açıkça tanımlaması gerekenler:

- İzin verilen işlemin amacı ve sınırı: candidate hazırlama sonucunun review'a kabulü
  ile automatic mapping/FX/recipe/applicability/usage/publish ayrımı. Mevcut v1
  usage=false alanını farklı yorumlayarak yetki açılamaz.
- Caller/source kapsamı, bağımsız expected decision set, delivery SHA, base/target
  pinleri, exact çıktı/package SHA ve işlem idempotency kimliği arasındaki bağ.
- Karar değiştiren bütün yollarla ortak lock sırası ve transaction içindeki yeniden
  doğrulama. Yeni revision/ret/yeniden onay/ruleset değişiminin yarışı hangi anda
  kazandığı ve sonuçların deterministik kabul/ret davranışı.
- DB unique constraint ve replay politikası: aynı anahtar+aynı exact çıktı aynı
  tarihsel kabul kaydına döner; farklı çıktı/amaç/kaynak/pin conflict olur. Önceki
  kabulün tekrar okunması bugünkü güncel onay veya yeni işlem yetkisi sayılmaz.
- Admin commit olup yanıt kaybolursa güvenli retry; Atlas crash/retry; sonradan
  revocation halinde geçmiş kanıt korunurken yeni kullanım/review/publish davranışı.
- Bağımsız closed request/response/receipt pinleri, yanıt HMAC bağları ve hata
  sınıflandırması. Bounded retry yalnız uygun geçici hata durumlarında.
- Worker staging veya mevcut V2 intake'a dokunulacaksa bunun ayrı dependency ve
  integration path'leri. Atlas tenant DB veya merkezi DB bağlantısı eklenmez.

Kabul testleri: ret/yeniden onay/source revision/ruleset değişimi ile eşzamanlı
finalization; aynı/farklı payload idempotency; kayıp yanıt; yanlış caller/source;
eski base ve scientific target; policy genişletme girişimi; başarısız doğrulamada
kalıcı kabul oluşmaması. Snapshot doğrulaması veya sadece happy-path mock yeterli değildir.

## Atlas'a geri teslim ve durma sınırı

Geri teslimde Admin çalışma ağacı/commit referansı, tüm bağımsız contract hash'leri,
test kanıtı, gerçek paket envanteri, expected envelope ve secret içermeyen runtime
activation durumu olmalı. Atlas her yeni teslimi tekrar inceleyip yeni şemaları
ayrı pinleyecek; uygun olduğunda tüketici/finalization adapter'ını geliştirecek.

Bu girdiler olmadan Atlas `requireForUse` kapısı kaldırılmaz. Readiness başarısı
yalnız yerel sorgu önkoşullarıdır; gerçek insan onayı veya kullanım izni değildir.
