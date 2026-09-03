# Uygulama yol haritası

## Güncel ürün önceliği

Yeni source ingestion durdurulmuştur. Cornerstone/USEEIO ve Cloud Carbon Footprint dahil
kalan source kuyruğu kapalıdır. Atlas mevcut havuz üzerinden Environmental Data
Intelligence Engine olarak geliştirilir: unit ontology → conversion → semantic concepts →
multilingual indexing → context-aware search → recommendation serving → product integration.
Freeze, varsayılan `ATLAS_SOURCE_INGESTION_ENABLED=false` ayarıyla admin API, scheduler ve
worker katmanlarında uygulanır. Unit, concept ve approved translation completeness
kapıları birlikte yeşil olmadan NetZero dahil ürün entegrasyonlarına geçilmez.

## Faz 0 — Çekirdek kontratlar (tamamlandı)

- Repository ve toolchain
- Source Registry manifest şeması
- Canonical factor/provenance modelleri
- Adapter ve altyapı portları
- Sabit pipeline engine ve state modeli
- Quality gate v0
- API sağlık ve source discovery yüzeyi
- PostgreSQL/Redis/MinIO geliştirme ortamı

Çıkış kriteri: network veya database olmadan kontrat testleri geçer.

## Faz 1 — DEFRA uçtan uca dikey dilim

- SQLAlchemy modelleri ve Alembic başlangıç migration'ı
- Transactional outbox, Redis dispatcher ve worker claim/lock
- MinIO content-addressed immutable raw store
- HTTP/Excel generic adapter
- DEFRA gerçek check/fetch/parser/mapping akışı
- Dataset/factor versioning, provenance ve review persistence
- Published-only factor API

Durum: Tamamlandı. 2026 revised DEFRA flat file ile gerçek stack doğrulaması:
8.740 parsed row, 2.622 canonical factor, 6.528 provenance kaydı ve ilk-dataset
manuel review kapısı. Aynı release'in ikinci run'ı `NO_CHANGE` ile sonuçlanır.

Çıkış kriteri: aynı DEFRA dosyasını iki kez çalıştırmak duplicate üretmez; factor'dan
orijinal workbook/sheet/row'a geri izleme yapılır.

## Faz 2 — Beş kaynakla mimari doğrulama

- EPA adapter/parser'ı ve manifest-driven adapter factory (Faz 2A tamamlandı)
- IPCC adapter/parser, calculation-parameter ve güvenli canonical CO₂e semantiği
  (Faz 2C tamamlandı)
- ADEME Base Carbone adapter/parser ve source semantiği (Faz 2D tamamlandı)
- AIB residual mix adapter/parser ve direct-CO2 semantiği (Faz 2E tamamlandı)
- API, HTML/Playwright/PDF gibi gereken generic adapter tipleri
- Taxonomy v1, geography ve unit registry
- Dataset diff: added/removed/changed/unchanged
- Review aksiyonları: approve/reject/remap/reprocess
- Origin/applicability geography mapping'lerinin kaynak bazında doğrulanması
- Geographic Coverage Engine, configurable fallback skorları ve coverage API (Faz 2B tamamlandı)

Çıkış kriteri: beş farklı yapı tek canonical model ve tek published API'de birleşir.

EPA Faz 2A doğrulaması: resmî 2025 Hub workbook içindeki 12 tablo 641 canonical
adaya dönüştürüldü. 352 kayıt varsayılan inventory matching için uygun; 189 non-CO2,
10 CO2-only, 28 avoided-emissions ve 62 characterization kaydı türleri karıştırılmadan
saklandı. İlk dataset manuel review bekler; aynı release'in ikinci run'ı `NO_CHANGE`
olur ve duplicate dataset version üretmez.

Geographic Coverage Faz 2B doğrulaması: origin/applicability yanında geography level,
specificity ve fit type canonical/DB/API boyunca taşınır. Source declared coverage,
ülke coverage matrix, country-aware factor filtresi ve `/v1/match` geography fallback
notice ile sunulur. Skorlar versiyonlu geography configuration'dan yüklenir.

IPCC Faz 2C doğrulaması: resmî EFDB web uygulamasındaki session-scoped export 27.566
satır olarak arşivlenip parse edilir. Coğrafi koşulu boş, numeric ve taxonomy'si bilinen
8.018 IPCC default kaydı korunur: 5.676 gaz emisyon faktörü ve 2.342 hesaplama
parametresi. Bunlara ek olarak aynı fuel-combustion grubundaki tekil CO₂/CH₄/N₂O
üçlülerinden 217 izlenebilir AR5 canonical `co2e_total` üretilir; toplam normalized factor
sayısı 8.235'tir. Eksik/ambiguous/unsupported-unit gruplarında toplam uydurulmaz. Serbest
metin bölgesel koşullu 10.885 kayıt global sayılmaz; onaylı geography
mapping bekler. Worksheet fingerprint aynı verinin volatile XLSX metadata nedeniyle
yeniden ingest edilmesini engeller.

ADEME Faz 2D doğrulaması: resmî Data Fair `base-carboner` V23.6 CSV'sindeki 18.616
satır immutable arşivlenir; 6.356 valid element canonical factor'a dönüştürülür.
5.797 country-specific, 115 regional, 97 continental ve 347 global kayıt geography
semantiğiyle ayrılır. 290 negatif değer avoided-emissions olarak default matching'den
çıkarılır. Henüz onaylı ISO eşlemesi olmayan 162 başka-ülke kaydı global yapılmaz ve
review sebebi üretir. Element/Poste ayrımı ve lifecycle decomposition source row'larıyla
korunur; metadata fingerprint'i katalog güncellemelerini veri değişikliği saymaz.

AIB Faz 2E doğrulaması: resmî 2025 / Version 1.0 workbook'undaki 34 ülke satırı üç
sheet arasında doğrulanır; residual mix bulunan 31 ülke country-specific canonical
factor'a dönüştürülür. AT, CH ve NL full disclosure nedeniyle factor üretmeden parsed
history'de korunur. Kaynağın doğrudan CO₂ değeri `co2_only` olarak saklanır ve toplam
CO₂e matching'e girmez. Commercial/API redistribution hakkı açık olmadığı için ilk
dataset license ve initial-dataset review kapılarında bekler.

## Faz 3 — Operasyon ve ölçek

- Bitemporal dataset/factor history ve current/as-known-at API (Faz 3A tamamlandı)
- Source history stratejileri ve resmî release katalogları (Faz 3B tamamlandı)
- Hedef reference-year backfill run'ları ve persisted historical coverage (Faz 3C tamamlandı)
- DEFRA 2020–2026, EPA 2020–2025 ve AIB 2022–2025 schema family parser'ları
  (Faz 3D tamamlandı)
- AIB 2020–2021 report/PDF backfill parser'ı
- Rate limit, dead-letter işlemleri ve operasyon dashboard'u
- RBAC, API key, audit log ve secret isolation
- Source health/freshness metrikleri ve dashboard
- Source SDK generator (`atlas source:create`)
- 67 kaynağa kontrollü genişleme

## Faz 4 — İkinci kaynak genişleme paketi

- Canonical environmental entity type ayrımı (Faz 4A tamamlandı)
- Ember yearly carbon-intensity API time series (Faz 4B tamamlandı)
- UNFCCC / TÜİK CRF ve CRT yearly national submissions (Faz 4D tamamlandı)
- AGRIBALYSE versioned agriculture/food LCA sonuçları (Faz 4C tamamlandı)
- Open CEDA yearly spend-based EEIO factor ve hesaplama parametreleri (Faz 4F tamamlandı)
- GLEC Framework v3.2 freight/logistics factor'ları (Faz 4G tamamlandı)
- GHG Protocol Cross-sector v2.0 factor'ları (Faz 4H tamamlandı)
- EU CBAM definitive default-values ve benchmarkları (Faz 4I tamamlandı)
- Government of Canada Offset Emission Factors Version 3.0 (Faz 4J tamamlandı)
- ETKB Türkiye electricity annual emission factors (Faz 4K tamamlandı)
- ÖKOBAUDAT versioned ILCD+EPD lifecycle-module kayıtları (Faz 4L tamamlandı)
- WRAP Food & Drink Scope 3 secondary LCA sonuçları (Faz 4M tamamlandı)
- CONCITO / 2.-0 LCA The Big Climate Database food-at-retail sonuçları
  (Faz 4N tamamlandı)
- Plastics Europe March 2026 Eco-profile LCA sonuçları (Faz 4O tamamlandı)
- Plastics Recyclers Europe recycled-plastics impact-assessment sonuçları
  (Faz 4P tamamlandı)
- EMEP/EEA Guidebook 2023 selected emission-factor viewer (Faz 4Q tamamlandı)
- Cloud Carbon Footprint release-versioned usage/embodied coefficients

Ember Faz 4B doğrulaması: resmî API'den 2020–2025 arasındaki 1.210 satır tek
immutable JSON snapshot olarak arşivlendi. Null değeri olan 2 satır parsed history'de
korunup canonical katmandan çıkarıldı; 1.207 emission factor ile 1 negatif reference
value üretildi. Negatif değer default matching'e girmedi ve review sebebi oldu. İkinci
run canonical payload hash'i üzerinden `NO_CHANGE` sonuçlandı; API anahtarı raw asset
URL'sine veya provenance'a taşınmadı.

AGRIBALYSE Faz 4C doğrulaması: resmî 3.2 conventional, organic ve food public
workbook'ları tek deterministic acquisition bundle içinde immutable arşivlendi. 217
conventional, 226 organic ve 2.458 food kaydından toplam 2.901 `LCA_RESULT` üretildi.
On negatif climate-change sonucu source semantiğiyle korunup review sebebi oldu; hiçbir
LCA sonucu klasik emission-factor matching havuzuna otomatik sokulmadı. Aynı üç member
checksum'ıyla ikinci koşu `NO_CHANGE` sonuçlandı.

UNFCCC/TÜİK Faz 4D doğrulaması: 2020–2026 arasındaki yedi resmî CRF/CRT ZIP
immutable olarak arşivlendi; 29'dan 35'e çıkan toplam 224 workbook, submission-time ve
inventory reference-time ayrımıyla parse edildi. 2020–2023 legacy CRF parser `0.1.0`,
2024–2026 CRT/ETF parser `0.2.0` ile işlendi. Toplam 297.590 typed kaydın 95.611'i
implied emission factor, 77.096'sı activity data ve 124.883'ü emission result olarak
saklandı. Faz 4E'de bu kayıtlar `atlas_source_observations` katmanına taşındı;
`atlas_factors` artık source observation deposu değildir. CRF parser `0.2.0`, CRT parser
`0.3.0` ve curation mapping `0.2.0` ile gas component, GWP ve unit dönüşümlerinden geçen
CO2e factor'lar ayrı version zinciri olarak üretilir. Unit/denominator belirsizliği olan
kayıt observation history'de korunur ancak matching kataloğuna alınmaz. Sıralı 2020–2026
backfill sonucu current processing katmanında 297.590 source observation, toplam 44.783
curated factor version ve en yeni submission'da 7.259 current temporal factor oluştu.
Tarihsel aktivite kataloğu 233 logical factor, son 2024 inventory kesiti 222 factor taşır;
2026 tekrar koşusu `NO_CHANGE` sonucunu verdi.

Open CEDA Faz 4F doğrulaması: resmî 2024 ve 2025 XLSX release'leri exact workbook
fingerprint'leriyle parse edildi. 2024 release'i 59.200 country-modelled, 400 Rest of World
proxy factor ve 4.236 hesaplama parametresi; 2025 release'i bunlara ek 8.400 regional
fallback factor ve toplam 4.784 hesaplama parametresi üretti. Exchange rate,
purchaser/producer conversion
ve sector price index tabloları factor kataloğuna sokulmadan source observation olarak
saklandı. Her hücrenin workbook, sheet, row, column ve sector-code provenance'ı korunur;
release year ile model base year birbirinden ayrıdır. Aynı 2025 release'inin ikinci run'ı
`NO_CHANGE` sonuçlandı ve duplicate dataset version üretmedi.

GLEC Faz 4G doğrulaması: resmî Framework v3.2 PDF'nin 183 sayfalık yayın kontratı
denetlendi. Module 1'den 102 WTW fuel/energy carrier factor'ı, Module 2'den 375 end-user
WTW transport/hub intensity ve Module 3'ten 44 AR6 GWP100 characterization sonucu
üretildi. Altı refrigerant charge/leakage varsayımı calculation-parameter observation
olarak ayrıldı; R-717 değeri olmadığı için canonical katmana alınmadı. Toplam 521
canonical version'ın 477'si inventory matching için uygundur. Geography kırılımı 69
country-specific, 41 regional, 99 continental ve 312 global kayıttır. İlk adaydaki
specificity uyumsuzluğu quality gate tarafından reddedildi; mapping `0.1.1` ile düzeltildi,
yeniden doğrulanan dataset owner-approved/published yapıldı ve ikinci run `NO_CHANGE`
sonuçlandı.

GHG Protocol Faz 4H doğrulaması: resmî Cross-sector Emission Factors v2.0 XLSX
workbook'unun 11-sheet yayın kontratı ve Mart 2024 version marker'ları denetlendi.
Stationary combustion, mobile fuel/distance, US eGRID, China/Taiwan/Brazil/Thailand/UK
electricity, freight ve public transport tablolarından 878 factor satırı parse edildi.
Aralık değer taşıyan üç satır midpoint uydurulmadan canonical katmandan çıkarıldı;
kalan 875 factor'ın 606'sı `CO2E_TOTAL`, 58'i `CO2_ONLY`, 211'i `NON_CO2_CO2E` oldu.
Yakıt ekonomisi ve conversion matrislerinden 158 source observation üretildi. Bilinen
eGRID bölgeleri Atlas grid kodlarına, `subregion unknown` kayıtları açık custom bölgelere
bağlandı. Dataset quality gate'i geçti, lisans/initial-dataset review'u owner-approved
olarak published yapıldı ve ikinci koşu `NO_CHANGE` sonuçlandı.

CBAM Faz 4I doğrulaması: resmî düzeltilmiş default-values ve benchmark XLSX dosyaları
tek deterministic acquisition bundle içinde immutable arşivlendi. 121 ülke sheet'i,
“Other Countries and Territories” ve Annex IV içinden toplam 11.170 definitive base
default `EMBODIED_EMISSION_FACTOR` üretildi; 10.650 kayıt country-modelled, 520 kayıt
açık proxy'dir. Cement 345, fertilisers 2.443, iron and steel 6.629, aluminium 1.656 ve
hydrogen 97 factor taşır. Benchmark workbook'undaki 661 Column A `BMg*` ve 1.804 Column B
`BMg` değeri toplam 2.465 calculation-parameter observation olarak ayrıldı. Yıllık legal
markup factor'a gömülmedi; EU legal acts bağlayıcı, workbook'lar informational kabul
edildi. Dataset quality gate'i geçti, owner-approved/published yapıldı ve aynı bundle'ın
ikinci koşusu `NO_CHANGE` sonuçlandı.

Government of Canada Faz 4J doğrulaması: ECCC'nin resmî 24 Ekim 2025 tarihli Version
3.0 HTML yayını 24 data-table kontratıyla denetlendi ve immutable raw asset olarak
arşivlendi. 2023–2026 geçerlilik dilimlerinden 399 canonical emission factor üretildi:
144 `CO2_ONLY`, 216 CH₄/N₂O component-gas ve 39 provincial electricity `CO2E_TOTAL`.
Yalnız elektrik toplamları default matching'e açıldı. Schedule 3 GWP'nin azaltımın
gerçekleştiği tarihteki sürümü gerektiğinden component gazlar ingest sırasında CO₂e'ye
çevrilmedi. Orman yönetimi protokolünden 14 reference value ve sığır enterik metan
protokolünden 31 calculation parameter, toplam 45 source observation olarak ayrıldı.
395 factor Canada/province exact, dört “Other provinces and territories” kaydı açık
proxy'dir. Dataset quality gate'i bulgusuz geçti, owner-approved/published yapıldı ve
publish sonrası koşu `NO_CHANGE` sonuçlandı.

ETKB Faz 4K doğrulaması: EVÇED'in resmî 2020–2023 Türkiye Elektrik Üretimi ve
Elektrik Tüketim Noktası Emisyon Faktörleri bilgi formları, iki sayfa ve üç factor-table
kontratına sahip dört annual PDF olarak immutable arşivlendi. Her release Türkiye geneli
brüt üretim, yedi yakıt türü ve iki bağlantı noktasındaki tüketim için 10 faaliyet satırı;
publisher'ın ayrı CO₂/CO₂e sütunlarıyla 20 canonical version üretti. Toplam 80 version'ın
40'ı `CO2_ONLY`, 40'ı `CO2E_TOTAL` ve default-match eligible'dır; 20 logical seri dört
reference year boyunca korunur. `tCO₂/MWh` ile `kgCO₂/kWh` sayısal eşdeğerliği uygulanır.
Ulusal şebeke avoided-emissions marjları bu inventory serisine karıştırılmaz. Dört release
validation FAIL olmadan owner-approved/published yapıldı; lisans review'u nedeniyle
external distribution kapalı kaldı ve publish sonrası 2023 koşusu `NO_CHANGE` sonuçlandı.

ÖKOBAUDAT Faz 4L doğrulaması: BMWSB/BBSR'nin resmî 2024-II data-stock CSV exportu
ISO-8859-1/semicolon şema kontratıyla immutable arşivlendi. 44.719 module-scenario
satırından publisher total GWP değeri olan ve pozitif beyan miktarı/birimi bulunan 44.013
satır `LCA_RESULT` olarak normalize edildi; 4.286 data set, 61 EN 15804+A1 ve 43.952
EN 15804+A2 sonucu taşır. A2 biogenic/fossil/luluc bileşenleri yeniden toplanmadan
methodology ayrıntısında korunur. 700 total-GWP'siz ve 6 referanssız satır canonical
katmandan çıkarıldı. 4.701 negatif LCA sonucu, çoğunluğu module D sistem-sınırı dışı
krediler olmak üzere source semantiğiyle tutuldu; hiçbir kayıt inventory default-match
havuzuna girmedi. Geography kırılımı 14.897 country-modelled, 27.541 regional/continental
ve 1.575 global kayıttır. Değişmemiş verinin kaynak gösterilerek ücretsiz dağıtımına izin
veren kullanım koşulu normalize API çıktısına genişletilmedi; license review'u owner
tarafından onaylanarak dataset published yapıldı ve ikinci koşu `NO_CHANGE` sonuçlandı.

WRAP Faz 4M doğrulaması: resmî Food & Drink Emission Factor Database v2.0 XLSX
workbook'u, beklenen sheet/header kontratı ve IPCC 2021 GWP100 marker'ıyla immutable
arşivlendi. Workbook'un önerilen HESTIA katmanındaki 722 GWP100 sonucu ile 21 UK-relevant
ürün sınıfı için hazırlanmış curated refined katmandaki 418 sonuç, toplam 1.140
`LCA_RESULT` üretti. Geniş `full` katmanı aynı upstream alternatifleri tekrar saymamak
için canonical scope dışında bırakıldı. Geography kırılımı 1.006 country-modelled ve
134 global; fonksiyonel birim kırılımı 1.130 kg ve 10 litredir. Yedi HESTIA ve bir refined
negatif sonuç source LCA semantiğiyle korunup hiçbir kayıt default-match havuzuna girmedi.
CarbonWARM2 relative-net waste-treatment comparison metric olduğu ve kurumsal/Scope 3
footprint faktörü olmadığı için bu source'a karıştırılmadı. WRAP terms kapsamındaki UK
dışı/commercial/hosted/derivative/redistribution kısıtları manifestte external API/raw
dağıtımını kapalı tutar. License ve negatif-LCA review'u owner-approved, dataset published;
ikinci workbook koşusu `NO_CHANGE` sonuçlandı.

CONCITO Faz 4N doğrulaması: The Big Climate Database v1.2'nin resmî index'i 2.700
activity kimliğini — DK, ES, FR, GB ve NL pazarlarının her birinde 540 ürün — doğruladı.
Index'teki üç ondalıklı gösterim factor değeri yapılmadı; 2.700 activity detail sayfası
altı ondalıklı sonuçlarıyla deterministic HTML acquisition bundle içinde immutable
arşivlendi. Her activity için Total, Agriculture, iLUC, Processing/Other, Packaging,
Transport ve Retail olmak üzere 18.900 ham sonuç parse edildi. 652 exact-zero stage
bileşeni canonical katmandan çıkarıldı; 18.248 `LCA_RESULT` üretildi. Bunların 2.700'ü
ürünün cradle-to-retail Total sonucu, 685'i consequential lifecycle kredi semantiği
taşıyan negatif stage sonucudur. Tüm kayıtlar retail pazarına göre country-modelled
applicability taşır; uluslararası supply-chain origin'i pazar ülkesiyle doldurulmaz.
`tCO2e/t` sayısal eşdeğer `kgCO2e/kg` olarak normalize edilir ve hiçbir kayıt inventory
default-match havuzuna girmez. CC BY 4.0 lisansı commercial/API/raw dağıtıma attribution
ve değişiklik bildirimiyle izin verir. Origin-missing ve negatif-LCA review gerekçeleri
owner-approved, dataset published; index SHA-256 üzerinden ikinci koşu `NO_CHANGE`
sonuçlandı.

Plastics Europe Faz 4O doğrulaması: resmî Eco-profiles sayfasında erişilebilen Mart 2026
PE/PP, CVM/PVC, steam-cracker ve refinery paketleri deterministic acquisition bundle
halinde immutable arşivlendi. Beş publisher PDF'indeki EF 3.1 / IPCC 2021 GWP100 özetleri,
28 ILCD process UUID'si ve 1 kg referans akışıyla çapraz doğrulandı. Dört polyolefin, üç
VCM/PVC, 14 steam-cracker/aromatics ve yedi refinery sonucu olmak üzere 28 continental
`LCA_RESULT` üretildi; değer aralığı 0,69–2,45 kgCO2e/kg'dır ve hiçbir kayıt inventory
default-match havuzuna girmez. Eski katalogdaki artık çalışmayan sayfalar ve indirilemeyen
legacy paketler canonical kapsama alınmadı. Açık commercial/API/raw yeniden dağıtım
lisansı bulunmadığından external izinler kapalı tutuldu. Quality gate FAIL üretmedi;
dataset doğrudan owner-approved/published yapıldı ve ikinci koşu `NO_CHANGE` sonuçlandı.

Plastics Recyclers Europe Faz 4P doğrulaması: PRE'nin resmî publications sayfasındaki
29 Mayıs 2015 tarihli, 54 sayfalık EU-28 impact-assessment PDF'i immutable arşivlendi.
Table 28'deki PET bottle/fibre, PE-HD, PE-LD, PP, PS, PVC ve other-resins olmak üzere
sekiz recycling-output GHG sonucu `LCA_RESULT` yapıldı. İlk dört sonuç Wisard LCI tabanlı;
son dört sonuç publisher'ın PE ile eşitlik varsayımıdır ve bu proxy semantiği kaybedilmez.
Değerler 0,280–0,510 kgCO2e/kg output aralığındadır. Koleksiyon, sorting, taşıma, eski
virgin-plastic substitution, incineration/RDF ve landfill için raporda kullanılan 17
değer calculation-parameter source observation olarak ayrıldı; canonical factor veya
kaçınılan-emisyon toplamı yapılmadı. 2012 model baseline'ı current Avrupa ortalaması gibi
sunulmaz, hiçbir sonuç default-match havuzuna girmez. Açık commercial/API/raw lisansı
olmadığından external izinler kapalıdır. Quality gate FAIL üretmedi; dataset doğrudan
owner-approved/published yapıldı ve ikinci koşu `NO_CHANGE` sonuçlandı.

EEA Faz 4Q doğrulaması: EMEP/EEA Guidebook 2023'ün resmî viewer API'sindeki 8 Temmuz
2026 index'i, ID sıralı `search_after` sayfalamasıyla üç çağrıda tam 13.336 kayıt olarak
deterministik JSON snapshot'a dönüştürüldü. Viewer'ın seçilmiş bir alt küme olduğu ve
uyuşmazlıkta chapter değerlerinin geçerli olduğu provenance/methodology katmanında açıkça
korundu. Sayısal CO₂, CO₂-lube, CH₄ ve N₂O satırlarından 1.556 continental
`EMISSION_FACTOR` üretildi: 936 `CO2_ONLY`, 620 GWP uygulanmamış component-gas factor.
11.469 sayısal non-GHG emission-factor, abatement-efficiency ve fuel-consumption satırı
source observation'a ayrıldı; boş/NA/NC ya da tek bir sayıya indirgenemeyen 311 satır
raw ve parsed katmanda kaldı. Hava kirleticileri CO₂e gibi kanonikleştirilmedi ve 1.556
factor'ın hiçbiri default-match'e açılmadı. CC BY attribution koşulları manifestte açıkça
kaydedildi. Pre-publication audit'te hatalı excluded-row metriği taşıyan ilk candidate
reject edildi; mapping `0.1.1` ile üretilen düzeltilmiş candidate `excluded_row_count=311`
ve sıfır FAIL ile doğrudan owner-approved/published yapıldı. İkinci koşu canonical data
SHA-256 üzerinden `NO_CHANGE` sonuçlandı.

## Faz 5 — Environmental Data Intelligence Engine

- Faz 5A, intelligence-first governance ve unit inventory: tamamlandı. Yeni source kuyruğu
  kapatıldı; 296.015 factor version, 326 factor unit, 193 activity unit ve 447 observation
  unit envanteri çıkarıldı.
- Faz 5B, canonical unit ontology: tamamlandı. Versioned unit definitions, aliases,
  dimensions, semantic qualifiers, optional UCUM code ve factor-unit expression tabloları
  eklendi. Registry 1.2.0 completeness backfill'inde üç katmandaki 966/966 distinct raw
  unit açık disposition aldı. Factor version ifadelerinin 294.669'u mapped, 17'si ratio,
  1.329'u source-native'dir; current calculation-eligible havuzda mapped olmayan unit
  yoktur.
- Faz 5C, conversion engine: tamamlandı. Activity ve factor denominator conversion yolları
  ayrıldı; exact/conditional/incompatible sonuçları, provenance-bearing bridge parametreleri
  ve `/v1/convert` sunuldu.
- Faz 5D, semantic concepts ve multilingual registry: tamamlandı. 171.005/171.005 logical
  factor 486 canonical concept'e bağlıdır. EN/TR/DE/FR/ES/RU/AR dillerinin her birinde
  486/486 tercih edilen label owner-delegated audit ile approved'dur. Original source/factor
  text değişmez; approval her etiketin reviewer kimliği, zamanı ve notunu taşır.
- Faz 5E, PostgreSQL-first search: tamamlandı. `pg_trgm`, FTS/trigram index'leri,
  database concept-label sorgusu ve context-aware `/v1/search` eklendi. OpenSearch/vector
  zorunlu değildir.
- Faz 5F, profile-gated match/resolve: tamamlandı. Corporate carbon, LCA, PCF, CBAM ve
  freight profile policy'leri; search/calculation eligibility ayrımı; profile-aware
  `/v1/match` ve strict `/v1/resolve` sözleşmeleri eklendi.
- Faz 5G, operasyon: tamamlandı. Unit inventory endpoint'i, idempotent bulk intelligence
  rebuild CLI/admin endpoint'i, policy/registry version metadata'sı ve API contract testleri
  eklendi.
- Faz 5H, completeness ve translation review: tamamlandı. Unit inventory,
  calculation-eligible unit, factor-concept ve approved
  target-language coverage ayrı kapılardır. Coverage API/CLI, translation review listesi,
  approve/reject audit'i ve iki idempotent migration eklendi. Son kapı yalnız tüm hedef
  dillerde approved coverage sıfır eksik verdi; birleşik `/ready` kapısı `true` oldu.
- Faz 5I, recommendation serving: tamamlandı. Dokuz öncelikli factor family için rebuildable
  applicability projection, country/profile/family fallback policy, jurisdiction-specific
  authority order ve `/v1/recommendations` eklendi. `/v1/match` ile `/v1/resolve` kaldırıldı;
  `/v1/search` katalog keşfi olarak kaldı. License runtime selection kırılımı değildir. Benzin
  çok dilli `energy.gasoline` concept'iyle stationary motor-gasoline factor'larına bağlanır;
  jet/aviation ve bio yakıtlar aynı aileye alınmaz. Yıllı logical factor serilerinde reporting
  year'e en yakın version seçilir, eşit uzaklıkta geçmiş yıl kazanır; kaynağın yıl vermediği
  metodoloji default'u `UNDATED` olarak korunur.
- Faz 5J, contextual multilingual terminology: tamamlandı. OpenAI Responses Structured
  Outputs ve Batch job yönetimi,
  Terra üretim/Sol koşullu QA, glossary, preferred/synonym/abbreviation provenance'i,
  English curation ve Explorer review paneli eklendi. Search ile Recommendation aynı
  Unicode-safe approved-term resolver'ı kullanır; runtime OpenAI çağrısı yapmaz. Yayın sırası
  EN curation → TR → DE/FR/ES → RU/AR'dır ve her dil insan onayı tamamlanmadan ready sayılmaz.
  Operasyonel üretim en fazla 50 konseptlik gruplara bölünür; Batch ve doğrudan Responses
  modları, aktif-job duplicate koruması ve response-ID recovery uygulanmıştır. 486 concept'in
  tamamı EN curation ve TR/DE/FR/ES/RU/AR terminology rollout'una dahildir; tercih edilen terim,
  gerçek arama eşanlamlıları ve kısaltmalar ayrı provenance taşır. Provider
  Batch dosya/organization uyuşmazlığında tamamlanmış grupları koruyan `only_missing` doğrudan
  Responses fallback'i kullanıldı. 30 Ağustos 2026'da owner'ın açık yetkilendirmesiyle
  `codex-on-behalf-of-owner` reviewer audit'i yazıldı; her dilde 486 approved preferred label,
  sıfır draft preferred label doğrulandı.

Çıkış kriteri: yanlış entity family veya incompatible unit strict recommendation tarafından
reddedilir; factor denominator dönüşümü reciprocal uygulanır; translation/synonym'ler
PostgreSQL'de versioned ve review-status taşıyarak saklanır; `atlas-intelligence-check`
`ready=true` ve sıfır eksikle tamamlanır. Kriter 30 Ağustos 2026'da canlı veride sağlandı.

## Faz 6 — Explorer & Test Lab

- Faz 6E, ortak sektör registry'si ve katalog filtresi: tamamlandı. On kullanıcı sektörü,
  kontrollü alt kategoriler ve `Cross-sector / General` first-class PostgreSQL registry
  olarak eklendi. Bütün historical/current factor version'lar source taxonomy bozulmadan
  deterministik olarak backfill edildi; yeni ingest aynı versioned policy'yi uygular.
  Public sector API, Factor Catalog sector/category filtreleri, inspector metadata'sı,
  admin rebuild/coverage ve CLI readiness kapısı birlikte çalışır.

- Faz 6A, developer test surface: tamamlandı. `/explorer` altında zero-build, FastAPI-served
  tek Search çalışma alanı bulunur. Global facility/context/profile barı korunur; alt alan
  25/25/50 oranında input, dikey sonuç listesi ve iki kolonlu seçili factor detayına ayrılır.
  Eski altı tablı çalışma alanı kaldırılmıştır. Masthead'den açılan yeni Test Lab mevcut sade
  çalışma alanını bozmadan live pipeline, dokuz senaryolu regression pack, yedi dilli canonical
  concept matrix ve admin-gated intelligence coverage yüzeylerini aynı gerçek API kontratlarıyla
  çalıştırır. Pipeline her stage'in ham verisini ve request/response flight recorder'ını gösterir;
  suite başarısız ülke/policy coverage'ını saklamaz.
- Faz 6A public ve Explorer API'lerini compose eder. Recommendation multilingual canonical concept
  expansion uygular; foreign PCF/LCA adayı yalnız explicit `allow_geographic_proxy` ile ve
  warning/fallback score taşıyarak seçilebilir. `Buğday → agriculture.wheat → Blé` zinciri
  gerçek AGRIBALYSE verisi üzerinde doğrulandı. Explorer global context bar'ı 20 demo facility
  ve `/v1/countries` tarafından sağlanan tüm ISO country kodlarını sunar; facility/country/
  context/profile bütün uygun deney endpoint'lerine taşınır.
- Faz 6B, canonical server regression runner: tamamlandı. 68 canonical case
  `/v1/explorer/regression/run` ile PASS/CHANGED/FAIL olarak çalışır ve her koşu/result kalıcıdır.
  History/detail API'leri ile admin approve/reject audit'i eklendi. Public CI canlı suite'i
  zorunlu çalıştırır; lisanslı resmî artifact manifesti ayrı self-hosted workflow'dadır.
  Suite'in 40 global baseline vakası, 20 facility için Scope 1 doğal gazda ülke veya `GLOBAL`
  sabit yanma fallback'ini ve Scope 2 elektrikte exact ülke faktörünü gerçek recommendation
  kontratıyla doğrular; scope/coğrafya/`kgCO2e` hesap sonucu birlikte geçmeden suite geçmez.
  Ek on Scope 3 vakası 15-kategori policy kataloğunu, kategori 1/3/4/5/6/9/12 yollarını,
  upstream/downstream freight belirsizliğini ve unsupported kategori gap'ini canlı projection
  üzerinde korur.
- Faz 6C, end-to-end calculate ve product-input contract: tamamlandı. Factor-first UI,
  `/v1/explorer/compatibility`, server-side `/v1/explorer/calculate` ve context/geography/unit
  `/v1/explorer/compare` tamamlandı. Compatibility panelinde direct/parameterized unit'ler
  tek selector'dan seçilir; gerekli manual parameter value/unit alınarak conversion çalıştırılır.
  İlk activity unit listesi `/v1/units` registry'sinden başlangıçta bir kez yüklenir, bütün
  seçenekler dimension'a göre gruplanır ve profile/context/facility/query değişiminde yeniden
  yaratılmaz. Profile yalnız factor eligibility ve ranking'i değiştirir.
  `passenger → passenger.km` yolu distance parametresi ister ve DEFRA domestic-flight Scope 3
  akışı gerçek katalog üzerinde doğrulanmıştır.
  Parameter unit dimensional olarak validate/scale edilir;
  reviewed recommendation yoksa hesap bloke kalır. Conditional path bulunan factor parameter
  eksikken de ranked aday kalır; parameter seçimden sonra istenir. Explorer'ın 20 başlangıç
  facility kaydı PostgreSQL registry ve `/v1/facilities` API'sine taşındı; recommendation
  `facility_id` çözer ve country uyuşmazlığını reddeder. Dated/provenance-bearing conversion
  parameter catalog draft → approve/reject kapısı taşır ve yalnız approved kayıtlar hesaplamaya
  girer. `/health` liveness, `/ready` product gate'tir; sector/recommendation ensure ve birleşik
  readiness CLI/compose kontrolleri deployment image'ına dahildir.
- Faz 6D, Search geography/context isolation: tamamlandı. Geography aday havuzuna repository
  seviyesinde uygulanır; entity/factor-kind/intended-use prefilter'ları ve engine scope kapısı
  çalışır. Engine exact ülkeyi global fallback önünde sıralar; hard-deny context/profile,
  activity ve incompatible-unit sonuçlarını normal/Advanced Debug seçim listesinden çıkarır.
  Runtime license kırılımı/payload alanı yoktur; publish kapısı authoritative sınırdır. Exact
  concept match lexical FTS'i kapatmaz ve punctuation token separator olarak normalize edilir;
  bu sayede TR Scope 1 diesel araması UNFCCC toplamlarıyla GHG Protocol/IPCC-derived toplamı
  birlikte bulur. Resolve strict eligible sonuç üretir. Türkiye Scope 2 elektrik araması ve
  CBAM/Electricity isolation canonical regression içinde korunur.
- Faz 6E, source-faithful Factor Catalog: tamamlandı. `/explorer/catalog` recommendation
  yüzeyinden ayrıdır; source, GHG scope ve anlık server-side text filtresiyle yayımlanmış
  emission/implied/embodied factor ailesini ve LCA-native kaynakların `LCA_RESULT` kayıtlarını
  listeler. Calculation parameter/technical property satırları bu yüzeye girmez. Seçilen kaydın tüm normalized factor alanları, methodology,
  gases, geographies, provenance, version history, source registry definition ve ham API
  payload'ları tek inspector'da açılır. National inventory implied combustion scope'u açıkça
  Scope 1 olarak türetilir; diğer publisher-unspecified kayıtlar ayrı filtrelenebilir. Çok
  yıllı sonuçlar kayıt sayılı, seçilebilir year alt filtresi sunar; Catalog ve ana Explorer
  panellerinin tipografi ölçeği normal desktop kullanımında okunabilir hale getirilmiştir.
  Instant text search ham factor alanlarını ve approved çok dilli concept label/eşanlamlı
  eşleşmelerini OR semantiğiyle birleştirir; kaynak metni çevrilmeden farklı dildeki arama
  ilgili concept'e bağlı yayımlanmış kayıtları bulur ve uygulanan concept UI'da görünürdür.
- Faz 6F, semantic geography ve merkezî country registry: tamamlandı. 249 ISO-3166 ülke
  alpha-2 kimliği altında alpha-3/numeric kodlarıyla saklanır; EN/TR/DE/FR/ES/IT/PT/RU/AR/
  FA/JA/ZH adları ile doğrulanmış alias'lar ayrı, approved label kayıtlarıdır. Explorer ülke
  selector'ı `/v1/countries` kullanır; Catalog ve Search serbest metindeki çok dilli ülke
  adını aynı registry üzerinden structured geography filtresine dönüştürür. CONCITO retail
  country değerleri production origin yapılmaz, source-backed `market` rolüyle tutulur;
  WRAP origin ve applicability rolleri ayrı projekte edilir. Published 18.248 CONCITO ve
  1.140 WRAP factor version geri doldurulmuştur. Null origin UI'da `GLOBAL` gösterilmez.
- Faz 6G, kategori-aware Scope 3 contract: tamamlandı. GHG Protocol kategorileri 1–15 versioned
  recommendation policy içinde direction, method, required input, availability ve compatible
  family metadata'sıyla tanımlandı. Scope 3 request/intent/applicability/trace kategori taşır;
  strict mod explicit seçim ister, suggest yalnız tek-anlamlı family için assumption kaydederek
  çıkarım yapar. Freight 4/9 ve waste 5/12 ayrımları tahmin edilmez. Explorer kategori seçicisi
  ve `/v1/scope3/categories` public contract'ı aynı policy'yi kullanır; Scope 1/2 factor'ları
  Scope 3 olarak yeniden etiketlenmez.

## Bilinçli olarak ertelenenler

- Genel amaçlı DAG engine
- OpenSearch ve zorunlu vector store
- Otomatik AI publish
- Canonical suite dışında kullanıcı tanımlı regression case authoring
- Microservice ayrıştırması
