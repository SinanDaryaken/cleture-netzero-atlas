# ADEME Base Carbone source inventory

## Acquired release

- Source: ADEME Base Carbone
- Dataset ID: `base-carboner`
- Release: `23.6`
- Reported/exported rows: `18,616`
- Original file: `Base_Carbone_V23.6.csv`
- File size: `10,761,452` bytes
- Upstream MD5: `39583facdba0881a15f708693f25c793`
- Raw SHA-256: `01472bc24743c0265b649407508dfce896f15a5c11c0f612f6b47a5625b02653`
- Source data updated at: `2025-07-03T08:07:23Z`
- License: Licence Ouverte / Open Licence
- Raw object: `atlas-raw/sources/ademe/2026/09/03/01472bc24743c0265b649407508dfce896f15a5c11c0f612f6b47a5625b02653/Base_Carbone_V23.6.csv`

Bu kimlikler raw acquisition sırasında gerçek dosyanın boyutu, upstream MD5 değeri
ve Atlas SHA-256 değeri doğrulanarak elde edilmiştir. Aynı release ikinci kez
çalıştırıldığında yeni run veya raw nesne oluşturulmamıştır.

## Normalize öncesi profil

Bu profil raw CSV üzerinde salt-okunur olarak çıkarılmıştır; candidate veya canonical
kayıt sayısı değildir.

| Ölçüm | Değer |
| --- | ---: |
| CSV kolon sayısı | 67 |
| Export satırı | 18,616 |
| Geçerli emission-factor `Elément` satırı | 6,518 |
| Total değeri eksik geçerli satır | 0 |
| Birimi eksik geçerli satır | 0 |
| Negatif total değerli geçerli satır | 290 |
| Farklı source unit label | 69 |
| Farklı ana coğrafya sınıfı | 5 |
| Farklı sub-location label | 937 |

Geçerli faktör adaylarının ana coğrafya dağılımı:

- France continentale: 5,791
- Monde: 347
- Autre pays du monde: 168
- Outre-mer: 115
- Europe: 97

`Autre pays du monde` kayıtlarında 142 farklı Fransızca/İngilizce ülke label çifti
vardır. Yerel `base_netzero.countries` kataloğuyla yapılan yalnız analiz amaçlı
karşılaştırmada 127 İngilizce label doğrudan eşleşmiştir. Kalan 15 değer yazım
farkı, eski resmî ad veya politik/territorial belirsizlik içerir; örnekler
`Netherlands Antilles`, `FYR of Macedonia`, `Chinese Taipei`, `DPR of Korea (north)`
ve `Dem. Rep. of Congo` değerleridir.

Bu sonuç fuzzy eşlemenin otomatik kabul için yeterli olmadığını gösterir. NetZeroAdmin
snapshot'ı canonical UUID, ISO kodu, kullanılabilir localized name kanıtı, version ve
hash taşır; belirsiz veya eski coğrafyalar insan review'ına bırakılmalıdır.

## Parse aşaması kabul kriterleri

- 67 kolonun sırası ve orijinal adları parser sürümünün schema fingerprint'i olur.
- Bütün `Elément`, `Poste`, archived ve source-data satırları kayıpsız korunur.
- 6,518 geçerli factor element yeniden üretilemezse parse tamamlanmış sayılmaz.
- 69 source unit label dönüştürülmeden önce özgün biçimiyle envantere alınır.
- 290 negatif değer yalnız işaretine bakılarak avoided-emission sayılmaz.
- 168 dış ülke kaydı NetZeroAdmin canonical geography ID ve snapshot kanıtı olmadan
  publish-eligible olamaz.
- İlk NetZeroAdmin geography snapshot'ı 250 ülke ile yalnız Türkiye'nin 81 il/973
  ilçesini kapsar. Exact ISO/name ile tekil eşleşmeyen ADEME label'ları unresolved veya
  ambiguous kalır; source'a özel label ülke tahminiyle daraltılmaz.
- İlk published unit snapshot yalnız `g` ve `kg` içerir. `kgCO2e/kWh` gibi ADEME
  bileşik birimleri bu katalogdan türetilmez ve ek unit sözleşmesi gelene kadar
  unresolved kalır.

## Parsed observation sözleşmesi

- Parser version: `1.0.0`
- Schema version: `ademe.base-carbone.v23.6`
- Kaynak encoding: resmî snapshot için `Windows-1252`; UTF-8 ve UTF-8 BOM da kabul edilir.
- Artifact formatı: UTF-8 NDJSON
- Parsed row count: `18,616`
- Parsed artifact size: `43,842,388` bytes
- Parsed artifact SHA-256: `3f5369f9af3fdc3ff219aeff22f158b7baa61b2d948dc6ff64fdd1e6021e975d`
- Parsed artifact object: `atlas-processing/sources/ademe/releases/824d7d24c0220aac7605076016d355cc1f853468dc41a5573ea37dcd63f40b8e/parsed/1.0.0/3f5369f9af3fdc3ff219aeff22f158b7baa61b2d948dc6ff64fdd1e6021e975d.ndjson`
- Çalışma DB kapsamı: her kaynak kaydı için source record number, `Type Ligne`, element
  ID/type/status, row SHA-256 ve 67 özgün alan değeri
- İdempotency sınırı: raw asset ID + parser version

Gerçek V23.6 snapshot doğrulamasında parsed observation dağılımı 12.817 `Elément`,
5.799 `Poste`, 6.518 valid factor element, 3.282 valid factor post, 7.171 archived
kayıt ve 1.878 source-data kaydıdır. İkinci parse çağrısı aynı artifact'i kullanmış;
artifact, observation veya ingestion run sayısını artırmamıştır.

Element ID yalnız başına satır anahtarı değildir: aynı factor'ın `Elément` toplamı ve
birden fazla `Poste` decomposition satırı aynı ID'yi bilinçli olarak paylaşır. Duplicate
kontrolü bu nedenle yalnız `Valide générique` veya `Valide spécifique` durumundaki
`Facteur d'émission` türü `Elément` satırlarında uygulanır. Parsed katman normalization,
geography/unit mapping veya canonical publish yapmaz.

## ADEME normalization çekirdeği

Normalizer version `1.0.0`, yalnız ADEME `base-carboner` parsed observation
sözleşmesini kabul eder. Her geçerli factor `Elément` satırı source-neutral candidate
draft üretir; aynı element ID'li geçerli `Poste` satırları lifecycle component ve
ayrı provenance/evidence kaydı olarak adaya bağlanır. Source total, standart gaz
alanları ve ek gaz alanları decimal string olarak korunur; exponent açılımı dahil
canonical decimal dönüşümünde binary float kullanılmaz.

Unit, taxonomy, intended-use ve geography değerleri canonical snapshot olmadan
eşlenmiş sayılmaz. Özgün source değeriyle `unresolved` proposal üretilir ve target
`null` kalır. Negatif total aynen korunur, `source_unspecified` intended use değerini
değiştirmez ve metodoloji review bulgusu üretir.

`atlas:source:normalize ADEME` komutu latest parsed artifact'i object storage'dan
stream eder ve tamamını tüketirken beklenen satır sayısı ile SHA-256 değerini tekrar
doğrular. Normalization kimliği parsed artifact SHA-256, normalizer version ve pinned
candidate entity schema kimliğine bağlıdır. Aynı giriş tekrarlandığında yeni run,
artifact veya finding oluşturulmaz. Draft NDJSON `atlas-processing` içinde
content-addressed saklanır; normalized artifact metadata'sı ve review bulguları Atlas
çalışma DB'sine yazılır. Draft satırları package builder'ın RFC 8785 canonicalization
ve `record_sha256` adımından önceki ara sözleşmedir; candidate package veya Admin
teslimatı değildir.

## 2026-09-05 — Candidate build hazırlığı

Source-neutral validation, license evidence consumer, önceki paket diff'i ve kalıcı
review package pipeline'ı eklendi; `atlas:candidate:build` açık normalized artifact
kimliğiyle çalışır. ADEME'ye özel ikinci paket motoru oluşturulmadı. Gerçek ADEME
package build veya Admin teslimi bu fazda yapılmadı: exact katalog provision ve
source'a bağlı gerçek lisans kanıtı girdileri bekleniyor. Katalogdaki basit unit
tanımlarından ADEME compound factor dimension/applicability sonucu türetilmez.
Blocking/unresolved sonuçlar gizlenmez. Devam kapıları [CURRENT](../CURRENT.md) içindedir.

## 2026-09-07 — Exact katalog provisioning

Admin katalog-only teslimi gerçek Atlas MinIO `atlas-catalogs` bucket'ına alındı.
Manifest `38de9ae94013840926af3e6a223188cfabd05e1c12fc4990cf4c11513c2f408c`;
beş katalog ve 25 artifact exact byte/hash ile hedeften doğrulandı. Unit katalog artık
181 definition/694 conversion içeriyor; geography 250 ülke/81 il/973 ilçe, currency 21,
taxonomy 9 node/2 link ve intended-use üç explicit kayıt taşıyor.

Bu sonuç ADEME'nin 69 unit label'ının tümünün çözüldüğü anlamına gelmez. Örneğin
`K` birden çok quantity-kind hedefinde ambiguous kalır. Compound factor dimension,
applicability, lisans ve veri bazında kullanım kararı ayrı kapılardır. Gerçek ADEME
normalization yeniden üretilmedi veya candidate/publish yapılmadı. Çözüm teslimi
`resolution=null`; gerçek onaylı çözüm teslimi hâlâ açık bağımlılıktır.
[Exact pinler ve read-back](../evidence/admin-atlas-step6-readback-2026-09-07.json).

## 2026-09-07 — Güncel onay adapter'ı

Source-neutral Atlas current-approval adapter'ı ve sentetik altı tür kontrolleri
tamamlandı. Bu kod ADEME mapping veya kullanım hakkı üretmez; gerçek source grant,
approved-resolution teslimi, authority body şemaları ve finalization beklenir.
ADEME normalizer/candidate artefact'leri yeniden üretilmedi.
[İşletim ve kanıt sınırı](../current-approval.md).
