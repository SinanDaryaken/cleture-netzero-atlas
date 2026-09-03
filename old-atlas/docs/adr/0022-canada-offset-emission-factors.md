# ADR-0022 — Canada offset emission factor ve protokol parametresi semantiği

## Durum

Kabul edildi — 28 Ağustos 2026.

## Bağlam

Environment and Climate Change Canada, federal Greenhouse Gas Offset Credit System
protokollerinde kullanılacak emission factor ve reference value'ları versioned bir HTML
belgesinde yayımlar. Version 3.0, genel natural gas, petroleum, electricity ve biogas
factor'larının 2023–2026 geçerlilik dilimlerini; ayrıca belirli forestry ve beef-cattle
protokollerinin formül girdilerini içerir. CH₄/N₂O hesaplarında kullanılacak GWP, sabit
bir workbook metadatası değil, azaltımın gerçekleştiği anda Greenhouse Gas Pollution
Pricing Act Schedule 3'te yürürlükte olan değerdir.

## Karar

- Source-specific HTML kontratı `sources/canada` altında kalır. Resmî Version 3.0 sayfası
  repository'ye vendored edilmez; exact response immutable, content-addressed raw asset
  olarak saklanır.
- Change detection sayfanın volatile shell/navigation metadata'sına değil; version marker,
  publication date ve 24 data table'ın caption/header/cell içeriğinden üretilen stabil
  SHA-256 revision'a bağlanır.
- Tables 1–6 içindeki 399 numeric değer `EMISSION_FACTOR + INVENTORY` olarak saklanır.
  `valid_from`/`valid_to` source'un 2023–2024, 2025 ve 2026 dilimlerini aynen korur;
  Version 3.0 için sentetik annual release üretilmez.
- Source'un doğrudan gCO₂e/kWh verdiği 39 provincial electricity değeri
  `CO2E_TOTAL` ve default-match eligible'dır. 144 CO₂ kaydı `CO2_ONLY`; 216 CH₄/N₂O
  kaydı `GAS_EMISSION_FACTOR` olur ve varsayılan CO₂e matching'e girmez.
- CH₄/N₂O factor'larına ingest-time GWP uygulanmaz. İlgili offset calculation, event-time
  Schedule 3 GWP sürümünü seçmekle sorumludur; Atlas bu koşulu methodology/provenance'da
  açıkça taşır.
- Province/territory factor'ları ISO 3166-2 kodlu exact geography'dir. “Other provinces
  and territories” satırları belirli bir province gibi gösterilmez;
  `CA_OTHER_PROVINCES_TERRITORIES` custom origin ve açık `proxy` fit taşır.
- Tables 7–8 içindeki forestry değerleri `REFERENCE_VALUE`, Tables 9–12 içindeki
  beef-cattle formül girdileri `CALCULATION_PARAMETER` source observation olarak
  saklanır. Bu 45 kayıt canonical emission factor toplamına dahil edilmez.
- Open Government Licence – Canada yeniden kullanım, değişiklik ve ticari dağıtıma
  attribution ile izin verir. Manifest, zorunlu attribution metnini, third-party/official
  marks istisnasını ve endorsement yasağını kaydeder.

## Sonuçlar

Atlas resmî CO₂e elektrik yoğunluklarını, gaz-bileşeni factor'larını ve protokol formül
girdilerini birbirine karıştırmaz. Event-time GWP'nin yanlış veya iki kez uygulanması
önlenir. Her kayıt HTML table/row/column koordinatına, raw checksum'a ve Version 3.0
yayınına geri izlenebilir; province exact coverage ile catch-all proxy açıkça ayrılır.
