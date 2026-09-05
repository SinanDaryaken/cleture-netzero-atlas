# ADR-001: Canonical coğrafya sahipliği ve Atlas eşleme sınırı

- Durum: Kabul edildi
- Tarih: 2026-09-03

## Bağlam

ADEME Base Carbone kayıtları ülke, bölge, kıta ve global uygulanabilirlik ifadeleri
taşır. Atlas bu ifadeleri canonical coğrafya kimliklerine eşlemeli, fakat canonical
coğrafya kataloğunun sahibi değildir.

`cleture-logi` repository'sinin mevcut migration ve API sözleşmesinde yalnız
`air_ports` ve `sea_ports` domain'leri vardır. Bu kayıtlar ISO 3166-1 alpha-2 ülke
kodu taşır; ülke, il ve ilçe için stable canonical kimlik veya versioned lookup API
sunulmaz. Logi'nin sorumluluğu route/mesafe bilgisiyle sınırlıdır.

Yerel PostgreSQL incelemesinde ülke/il/ilçe verisinin `base_netzero` veritabanında
bulunduğu görülmüştür. Atlas'ın bu veritabanını çalışma zamanında sorgulaması ürün
sınırını ve veri sahipliğini ihlal eder.

ADEME V23.6 içindeki 142 farklı dış-ülke label çiftinin 127 tanesi mevcut
`base_netzero.countries` İngilizce adıyla doğrudan eşleşmektedir. Kalan 15 label eski
ülke adı, yazım farkı veya politik/territorial belirsizlik taşır. Bu veri
NetZeroAdmin mapping review için iyi bir başlangıç kanıtıdır, fakat yalnız isim
eşitliği canonical eşleme kararı değildir.

## Karar

- Atlas `base_netzero`, `moduler_netzero` veya tenant veritabanlarına coğrafya
  eşlemesi için bağlanmayacak.
- ADEME source discovery, raw acquisition ve parse işleri coğrafya servisinden
  bağımsız ilerleyecek.
- Coğrafya normalizasyonu `source label -> NetZeroAdmin canonical geography id`
  biçiminde sürümlü bir resolver sözleşmesine bağlanacak.
- NetZeroAdmin canonical ülke/il/ilçe lookup veya versioned snapshot sunana kadar yalnız
  açık kaynak semantiğine sahip `GLOBAL` ve `EUROPE` gibi değerler sınıflandırılacak;
  ülke eşlemesi gerektiren kayıtlar silinmeden `review_required` kalacak.
- NetZeroAdmin verisinin Atlas'a kalıcı kopyalanması veya merkezi DB'nin doğrudan
  sorgulanması çözüm değildir. Atlas yalnız eşleme anında kullanılan canonical kimliği,
  katalog sürümünü, snapshot hash'ini ve kanıtı saklar.

## Sonuçlar

- ADEME pilotinin ilk dilimi coğrafya bağımlılığı olmadan release metadata'sını
  doğrulayabilir.
- Ülke eşlemesinin tamamlanması için NetZeroAdmin'ın stable country/province/district
  kimliklerini versioned snapshot/lookup sözleşmesiyle sunması gerekir.
- Logi route/mesafe kanıtı üretmeye devam eder; bu kanıt Atlas geography catalog
  eşlemesinden ve NetZeroAdmin referans katalog sahipliğinden ayrıdır.

## 2026-09-04 ek bulgu

NetZeroAdmin repository'sinde `countries`, `country_translations`, `provinces` ve
`districts` migration/model/admin ekranları tamamlanmıştır. Country ISO2/ISO3/numeric
code, Province değişmez Country parent'ı ve District değişmez Province parent'ı taşır;
üç katalog UUIDv7, active lifecycle ve SoftDelete semantiğine sahiptir. Tabloların boş
başlaması bilinçli karardır ve kataloglar için public/internal JSON API tanımlanmamıştır.

Canonical ülke/il/ilçe sahibi NetZeroAdmin olarak kesinleştirilmiştir. Ancak mevcut
candidate package V1 sözleşmesi geography owner alanını hâlâ `Logi` sabitine bağlamakta
ve entity target alanını `logi_canonical_id` olarak adlandırmaktadır. Bu pinlenmiş
sözleşme Atlas tarafından tek taraflı değiştirilmez. NetZeroAdmin yeni sürümlü entity
şeması ve geography snapshot/lookup sözleşmesi yayımlayana kadar Atlas:

- `moduler_netzero` veritabanına doğrudan bağlanmaz;
- boş katalogdan sahte version/hash üretmez;
- ADEME coğrafyalarını raw label ve `unresolved` target ile korur;
- ileride gelecek snapshot'ın UUID, entity level, parent zinciri, active/deleted durumu,
  ISO alias kanıtı, katalog version ve SHA-256 bilgisini taşımasını bekler;
- yeni entity şemasında Logi'ye özel target kimliği yerine NetZeroAdmin canonical
  geography kimliğini taşıyan, sahibi açık bir alan bekler.

## 2026-09-05 sözleşme teslimi

Beklenen sahiplik değişimi candidate V2 entity/package şemaları ve immutable geography
snapshot ile teslim edilmiştir. V2 target `owner=NetZeroAdmin`, UUIDv7
`canonical_geography_id`, `entity_level`, `catalog_version` ve `catalog_sha256` taşır.
İlk snapshot 250 ülke ile Türkiye'nin 81 il/973 ilçesini kapsar. V1 legacy sözleşme
korunur; Atlas yeni V2 snapshot'ı ayrı pinler ve ayrıntılı tüketim kararını ADR-004'te
uygular.
