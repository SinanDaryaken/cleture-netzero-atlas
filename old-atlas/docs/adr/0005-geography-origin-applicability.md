# ADR-0005: Geography origin ve applicability ayrımı

Durum: Kabul edildi

## Karar

Canonical factor modelindeki tek `geography` alanı kaldırılır. Yerine
`origin_geography`, `applicable_geographies` ve `geography_type` alanları kullanılır.
Public country filtresi applicability üzerinde çalışır; origin filtresi ayrıca sunulur.

`geography_type` değerleri `country_specific`, `regional`, `global` ve `proxy` ile
sınırlıdır. Matching ve sonuç özetleri bu sınıfları kaybetmeden taşır.

## Gerekçe

Bir factor'ın belirli bir ülkede kullanılabilir olması, o ülkenin resmi veya yerel
factor'ı olduğu anlamına gelmez. Global, bölgesel ve proxy dataset'ler aynı country
aramasında aday olabilir. Tek geography alanı bu ayrımı gizleyerek factor sayısını,
kaynak kalitesini ve matching güvenini yanlış anlatır.

## Sonuçlar

- Source adapter applicability iddiasını kanıtlayan metadata veya mapping sağlamalıdır.
- Bilinmeyen geography otomatik olarak source country ya da `GLOBAL` yapılmaz.
- API ve analytics, “ülkeye özgü” ile “ülkede uygulanabilir” sayımlarını ayrı sunabilir.
- Eski tek geography kayıtları açık migration kuralı olmadan sessizce dönüştürülmez.
