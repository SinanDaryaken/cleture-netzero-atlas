# ADR 0028: PRE tarihsel recycling-model sınırı

## Durum

Kabul edildi — 28 Ağustos 2026.

## Bağlam

Plastics Recyclers Europe'un resmî publications sayfası güncel bir açık recycled-resin
factor veritabanı yayımlamıyor. Yeniden üretilebilir sayısal yayın, 29 Mayıs 2015 tarihli
“Increased EU Plastics Recycling Targets” etki değerlendirmesidir. Rapor EU-28 için 2012
baseline'ını 2020 ve 2025 senaryolarına taşır. Table 28, sorted plastic bales girişinden
recycled pellet/flake çıkışına sekiz doğrudan GHG sonucu verir. PET bottle/fibre ile PE-HD
ve PE-LD değerleri Wisard LCI verisine dayanır; PP, PS, PVC ve other-resins değerleri PE
geri dönüşüm değerine eşit kabul edilmiş açık publisher varsayımlarıdır. Aynı raporun
başka bölümleri plastik atık zincirine ait model girdileri ve PlasticsEurope 2014 virgin
plastic substitution değerleri taşır.

## Karar

- Table 28'deki sekiz recycling-output sonucu `LCA_RESULT` olarak ingest edilir.
- Kaynak birimi `kgCO2e/t output`, sayısal eşdeğer `kgCO2e/kg output` birimine çevrilir.
- Sonuçlar EU28 regional, mechanical-recycling, sorted-bales-to-pellets/flakes ve 2012
  baseline semantiği taşır; 2012–2025 validity yalnız raporun model ufkunu gösterir.
- PET bottle/fibre ve PE-HD/PE-LD `documented`; PP, PS, PVC ve other-resins
  `proxy_from_pe` olarak işaretlenir. Proxy değerler ölçülmüş veya güncel ortalama gibi
  sunulmaz.
- Koleksiyon, sorting, iki transport, sekiz virgin-plastic substitution, dört
  incineration/RDF ve bir landfill değeri — toplam 17 — `CALCULATION_PARAMETER` source
  observation olarak korunur; canonical factor'a veya negatif avoided-emission sonucuna
  dönüştürülmez.
- Table 29'daki PlasticsEurope 2014 virgin değerleri PRE factor sayısına eklenmez; bunlar
  yalnız PRE modelinin historical substitution girdileridir.
- Hiçbir kayıt default inventory matching'e açılmaz.
- Açık commercial/API/raw yeniden dağıtım izni bulunana kadar external izinler manifestte
  kapalı kalır.

## Sonuçlar

Atlas PRE'nin yayımladığı recycling-output sonuçlarını kaynak sınırı ve belirsizliğiyle
korur, fakat eski senaryo modelini current European recyclate database gibi göstermez.
Model girdilerinin source observation'a ayrılması duplicate virgin-plastic factor ve
yanlış negatif kredi üretimini engeller. PRE ileride güncel, açık ve ürün-bazlı bir veri
seti yayımlarsa yeni snapshot ayrı version/mapping ile ingest edilir; 2015 history geriye
dönük değiştirilmez.
