# ADR 0029: EEA viewer GHG canonical sınırı

## Durum

Kabul edildi — 28 Ağustos 2026.

## Bağlam

EMEP/EEA air pollutant emission inventory Guidebook 2023, ulusal hava-kirletici
envanterleri için resmî teknik rehberdir. EEA'nın factor viewer'ı Guidebook'taki seçilmiş
emission factor, abatement efficiency ve fuel-consumption kayıtlarını sunar; tam veri
tabanı değildir. Viewer ayrıca uyuşmazlıkta yayımlanmış chapter değerlerinin geçerli
olduğunu belirtir. 8 Temmuz 2026 tarihli viewer index'i 13.336 satır taşır. Bunların büyük
çoğunluğu NOx, NMVOC, PM, metal ve başka hava kirleticileridir; Atlas canonical gaz modeli
ise CO₂/CH₄/N₂O ve CO₂e semantiğini güvenli biçimde temsil eder.

## Karar

- Viewer API, `ID` artan sırası ve Elasticsearch `search_after` token'ıyla tam
  sayfalanır. Tüm sayfalarda exact total ve aynı index kimliği zorunludur.
- API cevaplarının volatile arama metadata'sı change detection'a katılmaz. ID sıralı
  `_source` kayıtlarının canonical JSON SHA-256 değeri revision olur; birleşik snapshot
  immutable raw asset olarak saklanır.
- Dataset edition'ı 2023, viewer snapshot kimliği ise index refresh tarihiyle ayrı
  tutulur. Faktör `reference_year=2023`; 2026 refresh tarihi ölçüm yılı gibi sunulmaz.
- Tek bir sayısal değeri ve source unit'i olan CO₂, CO₂-lube, CH₄ ve N₂O emission-factor
  satırları canonical olur. CO₂/CO₂-lube `CO2_ONLY`; CH₄/N₂O `GAS_EMISSION_FACTOR`
  olarak saklanır. Source değeri/birimi dönüştürülmez ve GWP uygulanmaz.
- Bu snapshot'ta 1.556 canonical factor vardır: 559 CO₂, 377 CO₂-lube, 121 CH₄ ve
  499 N₂O. Hepsi Guidebook'un Avrupa uygulama bağlamıyla continental geography taşır,
  fakat hiçbiri `CO2E_TOTAL` olmadığı için default-match'e girmez.
- Sayısal non-GHG emission-factor satırları ve abatement/fuel-consumption parametreleri
  canonical factor yapılmaz; toplam 11.469 source observation olarak korunur. Böylece
  yeni ve anlamı belirsiz bir air-pollutant factor türü core modele eklenmez.
- Boş, `NA`, `NC` veya tek bir Decimal değere indirgenemeyen 311 satır uydurma sıfırla
  doldurulmaz. Immutable raw ve parsed history'de kalır, factor/observation sayılmaz.
- Confidence interval, tier, NFR, technology, fuel, abatement, reference ve chapter URL
  satır provenance/methodology metadata'sında tutulur. Viewer değeri chapter'ın yerine
  geçen resmî üstün kaynak gibi sunulmaz.
- EEA'nın CC BY yeniden kullanım koşulları attribution ve anlamı bozmama şartıyla
  commercial/API/raw dağıtıma izin verir; satırdaki third-party referanslar korunur.

## Sonuçlar

Atlas EEA viewer'ının tam audit yüzeyini kaybetmeden, yalnız mevcut canonical GHG
modelinin açıkça temsil edebildiği gaz faktörlerini yayımlar. Hava kirleticileri yanlış
CO₂e faktörlerine dönüşmez, boş değerler sıfırlaştırılmaz ve viewer refresh'i Guidebook
edition/reference time ile karıştırılmaz. İleride Atlas ayrı bir air-pollutant domain
modeli kazanırsa raw ve source-observation history yeni mapping version'ıyla yeniden
işlenebilir; mevcut GHG factor history geriye dönük değiştirilmez.
