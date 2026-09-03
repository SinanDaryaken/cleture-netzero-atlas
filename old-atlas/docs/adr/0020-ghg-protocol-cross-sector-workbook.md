# ADR-0020 — GHG Protocol Cross-sector workbook semantiği

## Durum

Kabul edildi — 28 Ağustos 2026.

## Bağlam

GHG Protocol Cross-sector Emission Factors v2.0; stationary combustion, mobile
combustion, purchased electricity, freight/public transport, yakıt ekonomisi ve unit
conversion değerlerini tek XLSX çalışma kitabında yayımlar. Bazı tablolar CO₂, CH₄ ve
N₂O bileşenlerini ayrı verir; bazı ulusal elektrik serileri yalnız CO₂ veya publisher
tarafından hesaplanmış CO₂e toplamı taşır. Bu ayrımları kaybetmek, kısmi gaz faktörlerini
yanlışlıkla tam inventory toplamı gibi eşleştirir.

## Karar

- Source-specific workbook kontratı `sources/ghg_protocol` altında kalır; yalnız 11
  beklenen sheet'i, v2.0 revision marker'ını ve Mart 2024 yayın işaretini kabul eder.
- CO₂ + CH₄ + N₂O bileşenleri workbook'un UK reverse-calculation notuyla tutarlı IPCC
  AR5 GWP100 (`CH4=28`, `N2O=265`) kullanılarak `CO2E_TOTAL` yapılır. Kaynak CO₂e toplamı
  yayımlıyorsa tekrar karakterizasyon uygulanmaz.
- Yalnız CO₂ yayımlayan kayıtlar `CO2_ONLY`, yalnız CH₄/N₂O yayımlayan kayıtlar
  `NON_CO2_CO2E` kalır. İkisi de default inventory matching'e girmez.
- Biogenic CO₂ `outside scopes + CALCULATION_INPUT` olarak saklanır; fossil inventory
  toplamına katılmaz.
- Numeric aralıklar için midpoint tahmin edilmez. Satır parsed provenance'da korunur,
  canonical factor üretmez ve exclusion metriğinde sayılır.
- Yakıt ekonomisi `TECHNICAL_PROPERTY`, unit matrisleri `CONVERSION_FACTOR` source
  observation'dır; emission-factor kataloğuna eklenmez.
- eGRID adı Atlas'ta tanımlıysa grid geography kullanılır. Publisher'ın `subregion
  unknown` kayıtları ülke ortalaması veya bilinen grid gibi gösterilmez; US parent'lı
  custom geography olarak kalır.
- Raw workbook repository'ye vendored edilmez; runtime resmî URL'den alınır ve immutable,
  content-addressed storage'a kaydedilir.
- Tool disclaimer ile genel terms-of-use arasındaki dağıtım kapsamı net olmadığı için
  commercial, redistribution, API ve raw-data izinleri manifestte `false` tutulur. Local
  reference publication owner approval ile yapılabilir; bu onay dış dağıtım hakkı vermez.

## Sonuçlar

Kısmi gaz faktörleri tam CO₂e inventory sonucu gibi eşleşmez, yardımcı conversion verisi
factor sayısını şişirmez ve her bileşen workbook sheet/table/row provenance'ına geri
izlenir. Publisher sheet veya version kontratını değiştirirse ingestion sessiz veri
bozulması yerine kalıcı hata verir ve parser version yeniden denetlenir.
