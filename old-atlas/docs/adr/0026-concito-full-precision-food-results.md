# ADR-0026 — CONCITO full-precision food-at-retail LCA sonuçları

## Durum

Kabul edildi — 28 Ağustos 2026.

## Bağlam

CONCITO ve 2.-0 LCA'nın The Big Climate Database v1.2 web yayını; Denmark, Great
Britain, France, Spain ve Netherlands retail pazarlarının her birinde 540 food product
için cradle-to-retail climate results sunar. Index tablosu Total ve altı lifecycle stage
değerini üç ondalıkla gösterirken her activity detail sayfası aynı değerleri altı
ondalıkla yayımlar. Index değerlerini ingest etmek kaynak hassasiyetini gereksiz yere
kaybettirir.

Metodoloji tipik olarak 1 kg food at retail reference flow kullanır; çalışma bunu bir
functional unit olarak tanımlamaz. ISO 14040/44 çerçevesini belgelenen istisnalarla,
consequential LCA yaklaşımını, EXIOBASE hybrid background sistemini ve IPCC 2013 GWP100
characterisation factor'larını kullanır. Pazar ülkesi sonucun applicability'sidir; ürünün
uluslararası supply-chain production origin'i değildir.

## Karar

- `sources/concito` index HTML'ini fingerprint olarak alır. Yalnız fingerprint değiştiğinde
  2.700 resmî activity detail sayfasını indirir ve index + detail HTML'lerini deterministic
  ZIP bundle içinde content-addressed raw snapshot olarak saklar. Değişmeyen ikinci koşu
  detail crawl yapmaz.
- Parser her pazarda 540, toplam 2.700 benzersiz activity ID ve activity başına yedi exact
  result bekler. Ürün, kategori, ülke ve ID index/detail arasında çapraz doğrulanır.
- Total, Agriculture, iLUC, Processing/Other, Packaging, Transport ve Retail değerleri
  ayrı izlenebilir LCA results'tır. Exact-zero stage bileşenleri factor yapılmaz; Total
  sonuçları sıfır olsa bile ürün-result kontratı olarak korunur.
- Sonuçlar `LCA_RESULT`, `CO2E_TOTAL`, `CHARACTERIZATION` olarak modellenir. Negatif
  consequential stage kredileri korunur; avoided-emission veya inventory factor'a
  çevrilmez. Hiçbir sonuç default matching'e girmez.
- Publisher'ın `t CO2e/t` değeri sayısal eşdeğer `kgCO2e/kg` birimine açılır. Original
  birim ve activity detail member provenance'da tutulur.
- Retail market ISO country geography'si country-modelled applicability'dir. Origin
  geography bilinmediğinde boş kalır; market country production origin olarak uydurulmaz.
- Dataset sitesinin beyan ettiği CC BY 4.0 uygulanır: commercial use, redistribution,
  adaptation, API ve raw distribution attribution, license link ve modification notice
  şartıyla açıktır; endorsement ima edilmez.

## Sonuçlar

18.900 ham activity-stage sonucunun 652 exact-zero bileşeni çıkarıldı ve 18.248 canonical
LCA result üretildi. 685 negatif stage sonucu review sebebidir. Beş pazarın her biri 540
Total result; tüm dataset 18.248 country-modelled result taşır. Dataset review gerekçeleri
owner-approved olarak published ve aynı index fingerprint'inin ikinci koşusu
`NO_CHANGE` sonucundadır.
