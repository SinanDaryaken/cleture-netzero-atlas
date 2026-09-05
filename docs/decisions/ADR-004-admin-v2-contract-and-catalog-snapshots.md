# ADR-004: NetZeroAdmin V2 contract ve immutable katalog snapshot tüketimi

- Durum: Kabul edildi
- Tarih: 2026-09-05

## Bağlam

NetZeroAdmin `37a30fae4f68cbea24a981d4e975463a856ac0ee` commit'inde candidate
package/entity/relationship/finding/source-diff V2 sözleşmelerini ve unit/geography
katalog snapshot sözleşmelerini teslim etmiştir. V2 canlı intake rollout'u henüz
açılmamıştır; mevcut internal endpoint V1 kabul eder ve V2 isteğini `422` ile reddeder.

Geography snapshot exact payload SHA-256 değeri
`63e4c102f3622f48c746a7a1144a3e07d6d64ee519940acb66c38289bdc36ac8`, boyutu
265521 byte'tır. 250 ülke ile Türkiye için 81 il/973 ilçe içerir. Dünya genelindeki
il/ilçe kataloğu değildir. Kosova `XK/XKX/926` owner tarafından kabul edilmiş yerel
uzantıdır; resmî ISO ataması olarak yorumlanmaz.

Unit snapshot exact payload SHA-256 değeri
`dfd210dfe04c0bc2dcf613e140637c249e1be76fc5d58a98efffeab73f99ddf3`, boyutu
1659 byte'tır. Published release `01a06c48-5918-723b-b028-22cc2a3dd0cc`, version
`unit-catalog-v1` olup yalnız `g` ve `kg` tanımlarını içerir. Bu snapshot bütün ADEME
birimlerini çözmüş sayılmaz.

## Karar

- V1 contract snapshot byte'ları ve pinleri değiştirilmez. V2 upstream manifest ve beş
  schema exact byte/hash ile ayrı `candidate-v2` snapshot'ında tutulur.
- Atlas yeni normalization artifact'leri için V2 entity contract'ını aktif kullanır;
  V1 registry uyumluluğu korunur. Candidate schema sürümü source normalizer tarafından
  sabitlenmez, orchestration context'inden gelir.
- Katalog contract manifesti ve üç schema repository'de pinlenir. Gerçek katalog
  payload/descriptor dosyaları repository'ye gömülmez; ayrı `atlas_catalogs` runtime
  storage alanından okunur.
- Consumer önce descriptor exact SHA-256 değerini, ardından descriptor JSON Schema'sını
  doğrular. Payload parse edilmeden önce exact byte size ve SHA-256 doğrulanır; sonra
  content schema, parent referansları, lifecycle/usability ve unit conversion
  referansları fail-closed kontrol edilir.
- Otomatik `latest`, merkezi DB sorgusu, yeniden serialize edilerek hash hesaplama veya
  bozuk/eksik snapshot için fallback yoktur.
- Country çözümlemesi yalnız kullanılabilir kaydın exact ISO2/ISO3/numeric code veya
  kullanılabilir exact localized name eşleşmesiyle proposal üretir. Birden çok sonuç
  `ambiguous`, sonuç yoksa `unresolved` kalır. `France continentale` gibi source'a özel
  label ülke tahminiyle daraltılmaz.
- Unit çözümlemesi yalnız exact unit code/symbol ile tekil proposal üretir. Bileşik
  ADEME birimleri mevcut g/kg kataloğundan türetilmez.
- V2 entity member builder doğrulanmış normalized draft'ı yeniden okur, katalog
  proposal'larını uygular, RFC 8785 record hash'i üretir, V2 entity schema'ya karşı
  doğrular ve deterministik `entities.ndjson` üretir. Duplicate candidate veya
  `(logical_key, variant_key)` kimliği package-fatal kabul edilir.
- `relationships.ndjson` V2'de bulunur fakat sıfır byte/sıfır kayıt olmak zorundadır;
  standalone relationship kaydı üretilmez.

## Açık kapılar

- Katalog descriptor/payload exact byte'ları Atlas `atlas_catalogs` runtime storage'a
  henüz provision edilmemiştir.
- ADEME license terms snapshot somut girdileri teslim edilmemiştir. Geography kaynak
  lisansı ADEME lisansı yerine kullanılamaz.
- Finding ve first-release/source diff member üretimi ile tam ZIP/manifest assembly
  henüz tamamlanmamıştır.
- V2 package canlı NetZeroAdmin endpoint'ine gönderilmez; Admin intake rollout'u ve
  Worker durable staging writer birlikte doğrulanmadan V1'e sessiz downgrade yapılmaz.

Bu kapılar source discovery, raw acquisition, parse, V2 normalization ve bağımsız
contract/catalog consumer geliştirmesini engellemez; tam package ve canlı teslimi
engeller.
