# ADR-008: Exact Admin delivery ve güncel onay sınırı

- Tarih: 2026-09-07
- Durum: Katalog adapter'ı ve gerçek teslim uygulanmış; current-approval entegrasyonu bekliyor.

## Karar

Admin'in incelenen uncommitted çalışma ağacı artifact sağlayıcısıdır; bağımsız trust
root yerine geçmez. Atlas ayrı `delivery-v1` resources ve kodda pinli manifest hash'leri
kullanır. Unit contract 2.1.0, payload/descriptor v2 ve candidate 2.0.0 birbirinden
bağımsızdır; eski kapalı şemalar ve kimlikleri değişmez.

Katalog snapshot'ları package içindeki content-addressed nesnelerden çözülür. Logical
payload/descriptor adlarının ayrıca storage köküne yazılması gerekmez. Atlas S3 store
koşullu create ve tam read-back yapar; tüm byte+schema+semantic kontroller geçmeden son
manifest marker yazılmaz. Aynı hash altında farklı içerik korunur ve hata verilir.
Loader explicit delivery SHA + catalog + version + payload SHA ister.

V2 unit code global tekil değildir; canonical quantity-kind bağları ve exact kayıt
hash'leri korunur. Unit alias/isimler global source aliası olmaz. Review katalog kaydı
applicability/kullanım izni değildir. `entry_sha256` lookup kanıtıdır; candidate schema'ya
izinsiz eklenmez. Current candidate loader'a geçiş explicit runtime pin seçimiyle yapılır.

Resolution envelope ve authority bytes tarihsel kanıttır. Current Admin approval
kanalı yokken kabul/mapping/recipe/FX/publish kararı üretilemez. Tüketici kaynak/raw,
revision/resolution/decision/ruleset/supersession ve eski base katalog pinini korur.
Yeni unit/kind için exact yayımlanmış hedef ve bağlı provenance zorunludur; bunun
byte doğrulaması dahi güncel insan onayı yerine geçmez.

## Sonuç

Katalog provisioning bağımsız tamamlanabilir. Güncel çözüm tüketimi için Admin-owned
transport, caller authority, kapalı artifact schema'ları ve kullanım anında freshness/
fencing sözleşmesi gerekir. Atlas geçici endpoint/credential veya production hesap
motoru üretmez. Admin bulguları ayrı owner değerlendirmesine gider.

[Gerçek read-back](../evidence/admin-atlas-step6-readback-2026-09-07.json),
[inceleme](../admin-atlas-step6-review.md), [işletim](../catalog-delivery.md).
