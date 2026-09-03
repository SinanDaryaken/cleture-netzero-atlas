# ADR-0032: Intelligence completeness ve translation review kapıları

## Durum

Kabul edildi — 2026-08-28.

## Bağlam

Unit parser'ın yalnız tanıdığı ifadeleri raporlaması, concept seed'lerinin küçük bir alt
kümeyle sınırlı kalması veya machine translation draft'larının mevcut olması altyapının
eksiksiz olduğunu göstermez. Ürün entegrasyonu bu kısmi durumlarda başlarsa hesaplama
havuzu, arama dili ve review durumu arasında sessiz boşluklar oluşur.

## Karar

- Factor, activity ve source-observation katmanlarındaki her distinct raw unit expression
  registry-version'lı ve content-addressed bir mapping/disposition kaydı taşır.
- Calculation-eligible factor unit'leri yalnız canonical `mapped` durumunda hazır sayılır;
  `source_native`, `ratio` veya başka bir disposition kullanılabilirlik beyanı değildir.
- Her logical factor approved bir canonical concept mapping taşır.
- Hedef diller `en`, `tr`, `de`, `fr`, `es`, `ru`, `ar` olarak registry'de versiyonlanır.
- Machine translation yalnız draft üretir. Approval/rejection reviewer, timestamp ve not
  ile audit edilir; otomatik toplu approval yapılmaz.
- Readiness bu kapıların conjunction'ıdır. API ve CLI aynı sonucu üretir; herhangi bir
  eksikte CLI non-zero exit code döner.
- NetZero ve diğer ürün entegrasyonları readiness `true` olmadan başlatılmaz.

## Doğrulanan başlangıç durumu

2026-08-28 completeness backfill'i üç unit katmanında 966/966 distinct ifadeyi
sınıflandırdı. 171.005/171.005 logical factor 483 concept'e bağlandı. Tüm hedef dillerde
label satırı mevcut olsa da English dışındaki machine-generated label'lar review
tamamlanana kadar draft kaldığı için readiness bilinçli olarak `false` durumundadır.

## Sonuçlar

Eksik kapsam ile içerik kalitesi birbirinden ayrılır: kayıtların varlığı coverage'ı,
approved review ise production readiness'i temsil eder. Altyapı boşlukları ölçülebilir ve
CI'da fail-fast olur; insan dil incelemesi teknik kapılar atlanarak otomatikleştirilemez.
