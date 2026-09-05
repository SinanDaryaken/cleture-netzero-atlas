# Atlas — güncel devam noktası

Güncelleme: 2026-09-05, Europe/Istanbul. Ayrıntılı kayıt: [günlük](journal/2026-09-05.md).

## Durum

Atlas'ın mevcut sahip sözleşmelerinden bağımsız validation ve candidate build dilimi
tamamlandı. Sabit build komutu, hash-pinned semantic policy, lisans evidence consumer,
validation ledger, verified previous package reader, disk tabanlı diff V2 ve eşzamanlı
idempotent package assembly mevcut. Bu durum gerçek ADEME candidate üretildi veya
Admin intake/publish hazır demek değildir.

Son doğrulama: 91 Unit/Feature test / 344 assertion; gerçek PostgreSQL + MinIO üzerinde
1 integration test / 10 assertion geçti. Pint ve Composer strict validate geçti.
Yeni migration yalnız `atlas_netzero` üzerinde uygulandı. Geçici entegrasyon DB'si ve
random test bucket temizlendi; çalışma DB'si resetlenmedi.

## Sahip projelerde BEKLEYEN — başlamayacaklar

İlk olarak ilgili task'lara yalnız günlük/backlog kaydı iletildi. Kullanıcı yeniden
durum sorduğunda buradan değerlendirme yapılacak; bu kayıt otomatik işe başlama,
test, migration, deploy veya rollout talimatı değildir.

| Sahip | Bekleyen girdi/karar | Kalıcı kayıt |
| --- | --- | --- |
| NetZeroAdmin | Exact unit/geography descriptor+payload provisioning, compound unit kapsamı, taxonomy/intended-use sürümlü snapshot, V2 intake ve blocking review kabul politikası | `/home/sinan/projects/cleture-netzero-admin/ai/codex/CURRENT.md`, “Atlas bağımlılıkları — BEKLEYEN (2026-09-05)” |
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
