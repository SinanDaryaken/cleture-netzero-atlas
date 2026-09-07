# ADR-009 — Güncel onay gözlemi ve kullanım sınırı

Tarih: 2026-09-07. Durum: Kabul edildi. ADR-008'in kanal yokluğu durumunu günceller;
historical-only byte doğrulaması ve kullanım/publish sınırlarını korur.

## Bağlam

Admin exact teslim ve expected resolution/base katalog için HMAC ile doğrulanmış
salt okunur current-approval endpoint'i geliştirdi. Yanıt yalnız checked-at durumudur;
uzaktaki Atlas işlemiyle atomik lease/fencing veya finalization garantisi sunmaz.
Authority payload/decision/receipt/scientific provenance kapalı body şemaları da açık.

## Karar

Atlas bağımsız request/response schema pinleriyle ayrı HTTP adapter uygular.
Application sözleşmesi `CurrentApprovalClient`, framework bağımsız
`CurrentApprovalObservation` döndürür. Historical verifier ve exact caller envelope
önkoşulları korunur; eski base katalog yeni published target ile değiştirilmez.

Uygulama giriş noktası her çağrıda depoyu ve güncel onayı yeniden okur. Cache veya
gözlemden yetki token'ı yoktur. `inspectCurrentApproval` checked-at gözlemini raporlar;
mevcut `requireCurrentApproval` kullanıma izin vermeyen `never` sözleşmesini korur ve
yeni sorgudan sonra eksik authority/finalization kapısını açıkça reddeder.

Yanıtlar gönderilen nonce/key/request UUID/body hash ve teslim/state hash'e bağlanır.
Schema ve HMAC doğrulaması olmadan durum kabul edilmez. Retry sınırlıdır, nonce yenilenir,
beklenen pinler değişmez. Redirect kapalı, uzak endpoint TLS doğrulaması zorunludur.
Varsayılan config kapalıdır; gerçek servis kimliği veya endpoint uydurulmaz.

## Sonuçlar

Katalog kaydı, historical delivery doğrulaması, güncel onay gözlemi ve nihai kullanım
ayrı kalır. Normalizer, executable mapping, candidate intake ve publish davranışı
bu gözlem nedeniyle açılmaz. Gerçek Admin/Atlas etkinleştirmesi, approved delivery
read-back, body-schema provisioning ve finalization owner sözleşmeleri ayrıca gerekir.
[İşletim ve test kanıtı](../current-approval.md).
