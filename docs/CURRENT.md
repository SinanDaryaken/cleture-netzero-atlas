# Atlas — güncel devam noktası

Güncelleme: 2026-09-07, Europe/Istanbul. Önceki kayıt: [2026-09-05 günlüğü](journal/2026-09-05.md).

## Admin–Atlas adım 6 — güncel sonuç

Gerçek katalog teslimi tamamlandı: owner seçimiyle Atlas MinIO private `atlas-catalogs`
bucket'ı oluşturuldu. Manifest SHA
`38de9ae94013840926af3e6a223188cfabd05e1c12fc4990cf4c11513c2f408c`, 9404 byte;
25 artifact /937372 byte hedeften yeniden okundu. Aynı paket tekrar aktarıldı;
byte'lar aynı. Beş katalog exact loader ile bu hedeften tüketildi.
[Dosya bazlı kanıt](evidence/admin-atlas-step6-readback-2026-09-07.json),
[işletim](catalog-delivery.md), [ADR-008](decisions/ADR-008-exact-admin-delivery-and-current-approval-boundary.md).

Admin current approval transport/caller/freshness ve kapalı authority artifact
schema'ları henüz yok. Altı tür sentetik çözüm historical-only doğrulanır; güncel
yetki talebi fail-closed. Gerçek pakette `resolution=null`. Adım 6 bütünü kapalı değil.
Admin'de currency nested hash kabulü ve taxonomy parent sıra tutarsızlığı salt okunur
kod + `/tmp` sentetik tekrar üretimle bulundu; [geri bildirim raporu](admin-atlas-step6-review.md).
Admin/Worker/core dosyaları, Admin migration/V2 intake ve gerçek kararlar değiştirilmedi.

### Doğrulamalar tamamlandı

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

Atlas katalog dilimi doğrulandı ve mevcut `main` branch'inde commit/push edilir;
commit kimliği `git log` ile okunur. Devam için Admin current-approval sözleşmesi ve
bulgu geri dönüşü yeniden kabul kapısından geçmeli. Mevcut candidate `.env` pinleri
kendiliğinden değiştirilmedi; explicit delivery loader CLI kullanılabilir.

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
| NetZeroAdmin | Güncel çözüm onayı transport/schema/freshness, A1/A2 bulgu değerlendirmesi, compound applicability ve V2 intake/blocking review politikası. Katalog provisioning 2026-09-07 tamamlandı. | [Adım 6 geri bildirim](admin-atlas-step6-review.md); tarihsel `/home/sinan/projects/cleture-netzero-admin/ai/codex/CURRENT.md` kaydı |
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
