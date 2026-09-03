# Cleture Atlas

Cleture Atlas; çevresel veriyi immutable raw katmanda saklayan, ortak modele normalize
eden, doğrulayan ve provenance bilgisiyle sunan bir Environmental Data Intelligence
Engine'dir. Canonical unit ontology, çok dilli concept registry ve calculation-profile
policy katmanı veriyi yalnız tutmak yerine güvenli biçimde aranabilir ve eşleştirilebilir
hale getirir.

Ana akış:

```text
Source → Detect → Fetch → Store Raw → Parse → Normalize → Validate
       → Compare → Version → Publish
```

## Çalışan source dikey dilimleri

Mevcut uygulama şunları içerir:

- kaynak manifestleri için doğrulanan Source Registry,
- sabit ve gözlemlenebilir dokuz adımlı pipeline çekirdeği,
- transactional outbox, Redis Streams dispatcher ve stateless worker,
- UTC cron scheduler ve PostgreSQL advisory source lock,
- content-addressed, versioning açık MinIO raw/processing katmanı,
- manifest-driven adapter factory ve gerçek DEFRA 2026 / EPA 2025 / IPCC EFDB /
  ADEME Base Carbone V23.6 / AIB Residual Mix 2025 / Ember yearly carbon-intensity /
  AGRIBALYSE 3.2 public LCA result / UNFCCC-TÜİK CRF-CRT / Open CEDA 2024–2025
  spend-based EEIO / GLEC Framework v3.2 audited PDF / GHG Protocol Cross-sector
  v2.0 audited XLSX / EU CBAM definitive default-values ve benchmark bundle /
  Canada GHG Offset Emission Factors and Reference Values Version 3.0 HTML / ETKB
  Türkiye electricity 2020–2023 annual PDF / ÖKOBAUDAT 2024-II CSV / WRAP Food &
  Drink Emission Factor Database v2.0 XLSX / CONCITO–2.-0 LCA The Big Climate
  Database v1.2 full-precision HTML bundle / Plastics Europe Mart 2026 Eco-profile
  PDF+ILCD package / Plastics Recyclers Europe 2015 audited impact-assessment PDF /
  EMEP/EEA Guidebook 2023 paginated JSON viewer parser'ları,
- source observation ile curated emission factor'ı ayıran provenance modeli,
- deterministik unit/taxonomy normalization ve quality/comparison gate,
- dataset/factor versioning ve manuel review/approve/reject akışı,
- published-only dataset/factor API'si ve Geographic Coverage Engine,
- PostgreSQL, Redis ve MinIO yerel geliştirme ortamı,
- ilk fazdaki DEFRA, EPA, IPCC, ADEME ve AIB kaynak kayıtları.

DEFRA, EPA, IPCC, ADEME, AIB, Ember, AGRIBALYSE, UNFCCC/TÜİK, Open CEDA, GLEC,
GHG Protocol, CBAM, Government of Canada, ETKB, ÖKOBAUDAT, WRAP, CONCITO, Plastics
Europe, Plastics Recyclers Europe ve EEA aktiftir.
IPCC EFDB'nin resmî XLSX exportu session-aware olarak alınır; worksheet
içeriğiyle change detection yapılır. IPCC gaz emisyon faktörleri ile formül girdisi olan
hesaplama parametreleri birbirinden ayrılır. Aynı fuel-combustion grubunda tam ve tekil
CO₂/CH₄/N₂O bileşenleri bulunan 217 grup ayrıca açık AR5 denklemi ve üç satırlı component
provenance ile canonical `co2e_total` üretir; eksik veya ambiguous grupta toplam uydurulmaz.
ADEME V23.6'nın Element/Poste ayrımı,
geography coverage'ı ve avoided-emissions semantiği korunur. İlk dataset version'ları
otomatik publish edilmez; admin review onayı bekler.

AIB residual mix değerleri yalnız direct CO₂ kapsamındadır. `co2_only` olarak saklanır,
CO₂e inventory matching'e otomatik girmez ve yalnız Guarantee of Origin iptal edilmemiş
elektrik tüketimi bağlamında kullanılır. AIB datasetleri owner review kararıyla local
reference stack'te published durumdadır; commercial/API distribution belirsizliği kayıtlı
kalır ve harici ticari dağıtımdan önce ayrı hukuk/lisans onayı gerekir.

Ember tek bir API time-series snapshot'ında 2020–2025 referans yıllarını taşır; Atlas
bunları sentetik annual release üretmeden ayrı temporal factor version'larına açar.
Kaynakta bulunan negatif net yoğunluk değeri emission factor diye sunulmaz;
`REFERENCE_VALUE` olarak korunur ve insan incelemesi ister. API anahtarı yalnız request
anında kullanılır, raw URL/provenance/hash içine yazılmaz.

ETKB/EVÇED'in resmî Türkiye Elektrik Üretimi ve Elektrik Tüketim Noktası Emisyon
Faktörleri serisi 2020–2023 arasındaki dört yıllık PDF olarak işlenir. Her release;
Türkiye geneli brüt üretim, yedi fosil yakıtlı üretim ve iletim/dağıtım bağlantılı tüketim
noktaları için publisher'ın ayrı CO₂ ve CO₂-eşdeğeri değerlerini taşır. Toplam 80
canonical version'ın 40'ı `CO2_ONLY`, 40'ı `CO2E_TOTAL`; yalnız CO₂e toplamları
varsayılan matching'e uygundur. `t/MWh` değerleri sayısal olarak eşdeğer `kg/kWh`
birimine çevrilir. Ayrı “Ulusal Elektrik Şebekesi Emisyon Faktörü” avoided-emissions
marj serisi bu inventory source'una karıştırılmaz. Dört release owner-approved/published,
2023 tekrar koşusu `NO_CHANGE` durumundadır. Bakanlık açık yeniden-dağıtım lisansı
vermediğinden external commercial/API/raw dağıtım izinleri kapalıdır.

AGRIBALYSE yıllık release gibi modellenmez. 3.2 public conventional, organic ve food
workbook'ları byte-for-byte korunan üç member'lı deterministic acquisition bundle olarak
arşivlenir. 2.901 climate-change sonucu `LCA_RESULT` olarak saklanır; klasik activity × EF
matching havuzuna otomatik düzleştirilmez. Public sonuç lisansı, ecoinvent background
inventory verisini ingest etme hakkı sayılmaz.

ÖKOBAUDAT 2024-II living/versioned database olarak modellenir; günlük güncel resmî CSV
exportu immutable snapshot halinde saklanır. 4.286 EPD/LCA veri setindeki 44.013 geçerli
EN 15804 modül-GWP toplamı `LCA_RESULT` olur ve klasik activity × EF matching havuzuna
girmez. Beyan miktarı bir birime normalize edilir; original quantity/unit, A1/A2 GWP
standardı, A2 biogenic/fossil/luluc bileşenleri, senaryo, EPD owner/registration ve
row/column provenance korunur. Publisher stokunda total GWP bulunmayan 700 satır ile
referans miktarı/birimi bulunmayan 6 satır canonical katmana alınmaz. 4.701 negatif LCA
sonucu, özellikle module D geri kazanım kredileri, negatif emission factor'a çevrilmez.
Source yalnız bina LCA'sı içindir; ürün LCA'sı hazırlamak için tasarlanmamıştır. Değişmemiş
verinin kaynak gösterilerek ücretsiz dağıtımına izin verildiğinden normalize edilmiş API
dağıtımı kapalıdır. Dataset owner-approved/published ve ikinci koşu `NO_CHANGE` durumundadır.

WRAP Food & Drink Emission Factor Database v2.0, workbook'un önerdiği HESTIA GWP100
katmanı ile 21 UK-relevant ürün sınıfı için hazırlanmış `refined` katmanı birlikte fakat
ayrı provenance ile işler. 722 HESTIA ve 418 refined kayıttan toplam 1.140
`LCA_RESULT` üretilir; geniş `full` alternatif havuzu aynı upstream kayıtları yeniden
saymamak için canonical katmana alınmaz. 1.006 sonuç ülke-modellemeli, 134 sonuç global;
sekiz negatif climate sonucu LCA semantiğiyle korunur ve hiçbir kayıt varsayılan
inventory matching'e girmez. CarbonWARM2 bir kurumsal/Scope 3 footprint faktör seti değil,
atık yönetimi seçeneklerini karşılaştıran relative-net metriktir; bu source'a karıştırılmaz.
WRAP koşulları UK dışı, commercial, hosted, türetilmiş ve yeniden dağıtılan kullanım için
özel izin gerektirdiğinden external API/raw dağıtımı kapalıdır. Local reference dataset
owner-approved/published ve ikinci koşu `NO_CHANGE` durumundadır.

CONCITO ve 2.-0 LCA'nın The Big Climate Database v1.2 yayını, DK/GB/FR/ES/NL
pazarlarının her birinde 540 food-at-retail ürünü taşır. Atlas, üç ondalığa yuvarlanan
index tablosunu factor değeri olarak kullanmaz; 2.700 resmî activity detail sayfasındaki
altı ondalıklı Total + Agriculture/iLUC/Processing/Packaging/Transport/Retail sonuçlarını
deterministic HTML bundle halinde arşivler. 18.900 ham sonuçtan 652 exact-zero stage
bileşeni çıkarıldı, 18.248 `LCA_RESULT` üretildi. Bunların 685'i lifecycle kredisi olan
negatif stage sonucudur; emission factor veya default-match adayı değildir. Pazar ülkesi
applicability'dir; uluslararası tedarik zincirinin origin'i olmadığı için origin geography
uydurulmaz. Bu ilişki source-backed `geography_roles.market` olarak saklanır; örneğin
`Ra00327-DK` Denmark pazarını ifade eder, muzun üretim menşeini değil. Dataset CC BY 4.0
altında owner-approved/published ve index fingerprint'li
ikinci koşu `NO_CHANGE` durumundadır.

Plastics Europe'un Mart 2026 Eco-profile yayını, resmî sayfada erişilebilen dört
paketteki 28 Avrupa üretim-ortalaması ürünü kapsar. Publisher PDF'lerindeki EF 3.1 / IPCC
2021 GWP100 sonuçları, aynı paketlerdeki 1 kg referans akışlı ILCD process UUID'leriyle
çapraz doğrulanır ve `LCA_RESULT` olarak saklanır; gömülü ecoinvent 3.11 inventory
exchange'leri dışarı açılmaz. Eski katalogdaki artık erişilemeyen sayfalar ve indirilemeyen
legacy paketler canonical kapsama alınmaz. Açık commercial/API/raw yeniden dağıtım lisansı
bulunmadığından external izinler kapalıdır. Dataset FAIL bulgusu olmadan doğrudan
owner-approved/published yapılmış, ikinci koşu `NO_CHANGE` sonuçlanmıştır.

Plastics Recyclers Europe'un 29 Mayıs 2015 tarihli EU-28 etki değerlendirmesi, sorted
plastic bale girişinden recycled pellet/flake çıkışına kadar sekiz reçine GHG sonucunu
taşır. PET bottle/fibre ile PE-HD/PE-LD sonuçları Wisard LCI tabanlıdır; PP, PS, PVC ve
“other resins” için 348 kgCO2e/t değeri publisher'ın açık PE-proxy varsayımıdır. Atlas bu
ayrımı kaybetmeden sekiz `LCA_RESULT` üretir. Koleksiyon, ayırma, taşıma, virgin-plastic
substitution, enerji geri kazanımı ve depolamaya ait 17 model girdisi factor yapılmadan
source observation olarak korunur. 2012 baseline verisi güncel Avrupa ortalaması gibi
sunulmaz ve hiçbir kayıt default-match havuzuna girmez. Açık yeniden dağıtım lisansı
bulunmadığından external izinler kapalıdır. Dataset FAIL bulgusu olmadan doğrudan
owner-approved/published yapılmış, ikinci koşu `NO_CHANGE` sonuçlanmıştır.

EMEP/EEA Guidebook 2023'ün resmî viewer'ı, 8 Temmuz 2026 tarihli index snapshot'ında
13.336 seçilmiş kayıt taşır. Atlas, ID sıralı `search_after` sayfalamasıyla tüm viewer'ı
deterministik JSON halinde arşivler. Sayısal CO₂, CO₂-lube, CH₄ ve N₂O satırlarından
1.556 gas-specific `EMISSION_FACTOR` üretilir: 936 `CO2_ONLY`, 620 component-gas
faktörü. Bunlar GWP uygulanmış CO₂e toplamı değildir ve default-match havuzuna girmez.
Sayısal fakat canonical GHG modeli dışında kalan 11.469 hava-kirletici, abatement ve
fuel-consumption satırı source observation olarak; değeri boş/NA/NC olan 311 satır ise
immutable raw ve parsed katmanda korunur. Viewer seçilmiş bir kolaylık katmanıdır;
uyuşmazlıkta Guidebook chapter'ı esas alınır. EEA'nın CC BY yeniden kullanım koşulları
attribution ile açık tutulur. Dataset FAIL bulgusu olmadan doğrudan owner-approved/
published yapılmış, ikinci koşu `NO_CHANGE` sonuçlanmıştır.

UNFCCC/TÜİK 2020–2026 national inventory submission'ları CRF (2020–2023) ve CRT
(2024–2026) parser family'leriyle ayrı işlenir. Yedi immutable ZIP içindeki 224 workbook,
1990–2024 inventory yıllarından toplam 297.590 typed observation üretti: activity data,
implied emission factor ve emission result birbirine karıştırılmaz. Submission yılı ile
inventory `reference_year` ayrıdır; daha yeni submission'ın historical revision'ı eskisini
overwrite etmek yerine supersede eder. 2024 `started`, 2025 `awaiting_submission`
statüsüyle owner-approved/published olsa da bu source statüleri provenance'da korunur.
Bu 297.590 kayıt `atlas_source_observations` katmanında dataset/raw-asset provenance ile
korunur; emission-factor sayısı değildir. `atlas_factors` yalnız deterministic unit,
gas, GWP ve activity curation sözleşmesini tamamlayan Türkiye-specific logical factor'ları
tutar. 2025 submission / 2023 inventory kesitindeki 471 implied-EF hücresi 224 activity
grubu oluşturur; 222 grup güvenli `kgCO2e/activity_unit` factor'a dönüşür. Activity unit'i
kaynakta belirsiz olan iki wildfire grubu observation olarak korunur fakat factor/matching
kataloğuna alınmaz. Yedi submission'ın güncel processing sürümleri 44.783 curated factor
version üretir; en yeni 2026 submission'ı içinde 7.259 current temporal factor, tarihsel
aktivite kataloğunda 233 logical factor ve son 2024 inventory yılında 222 factor vardır.
Böylece hedef sayıya ulaşmak için tahmin yapılmaz. Aynı 2026 arşivinin tekrar çalıştırılması
`NO_CHANGE` sonuçlanır.

GHG Protocol Cross-sector Emission Factors v2.0 çalışma kitabı sheet ve yayın marker'ları
denetlenen source-specific parser ile işlenir. Stationary combustion, mobile fuel/distance,
US eGRID ve beş ulusal elektrik serisi ile freight/public transport tablolarından 875
canonical emission factor üretilir. Bunların 606'sı tam `CO2E_TOTAL` inventory factor,
58'i `CO2_ONLY`, 211'i `NON_CO2_CO2E` kaydıdır. Workbook'taki üç aralık değerli satıra
uydurma orta nokta atanmaz. Yakıt ekonomisi ve unit conversion matrisleri factor kataloğuna
sokulmadan 158 `TECHNICAL_PROPERTY` / `CONVERSION_FACTOR` source observation olarak
saklanır. Gaz bileşenleri workbook ile tutarlı IPCC AR5 GWP100 kullanılarak birleştirilir;
biogenic CO₂ outside-scopes calculation input olarak kalır. Genel kullanım koşulları ile
tool disclaimer arasındaki yeniden dağıtım belirsizliği nedeniyle external commercial,
API ve raw distribution izinleri kapalıdır; local reference dataset owner-approved ve
published durumdadır. İkinci koşu `NO_CHANGE` sonuçlanır.

EU CBAM definitive-regime kaynağı, Komisyonun 10 Ağustos 2026'da yayımladığı düzeltilmiş
default-values workbook'u ile benchmark workbook'unu iki member'lı deterministic bundle
olarak arşivler. Ülke, “Other Countries and Territories” ve Annex IV ayrımı korunarak
11.170 `EMBODIED_EMISSION_FACTOR` üretilir; 2.465 Column A `BMg*` / Column B `BMg`
benchmark değeri factor yapılmadan `CALCULATION_PARAMETER` source observation olarak
saklanır. `tCO2e/tonne` ile `kgCO2e/kg` sayısal olarak eşdeğerdir. Publisher'ın total
sütunu kullanılır; yuvarlanmış direct ve indirect bileşenler yeniden toplanmaz. Yasal
2026/2027/2028+ markup base değere gömülmez, methodology'de açık hesaplama girdisi olarak
kalır. XLSX dosyaları bilgilendirme amaçlıdır; bağlayıcı değer ve kurallar ilgili EU
Implementing Regulation metinleridir.

Government of Canada kaynağı, Environment and Climate Change Canada'nın 24 Ekim 2025
tarihli Version 3.0 “Emission factors and reference values” HTML yayınını immutable raw
asset olarak arşivler. 24 resmî tablodan 2023–2026 geçerlilik dilimlerini koruyan 399
`EMISSION_FACTOR` üretilir: 144 `CO2_ONLY`, 216 bileşen-gaz faktörü ve 39 elektrik
tüketimi `CO2E_TOTAL` faktörü. Yalnız son grup varsayılan inventory matching'e uygundur.
CH₄/N₂O değerleri, azaltımın gerçekleştiği anda yürürlükte olan Greenhouse Gas Pollution
Pricing Act Schedule 3 GWP değerini gerektirdiğinden ingest sırasında CO₂e'ye çevrilmez.
Orman yönetimi ve sığır enterik metan protokollerindeki 45 referans/hesaplama parametresi
factor kataloğuna sokulmadan source observation olarak korunur. Dataset quality gate'i
temiz geçti, owner-approved/published yapıldı ve publish sonrası koşu `NO_CHANGE`
sonuçlandı. Contains information licensed under the Open Government Licence – Canada.

Open CEDA 2024 ve 2025 producer-price USD workbook'ları ayrı yearly release olarak
işlenir. 2024 matrisi 59.200 country-modelled, 400 Rest of World proxy factor ve 4.236
hesaplama parametresi; 2025 matrisi bunlara ek olarak 8.400 regional fallback factor ve
toplam 4.784 hesaplama parametresi taşır. Exchange rate, purchaser/producer conversion
ve sector price index tabloları emission factor yapılmaz; `source_observation` olarak
korunur. Harcama önce
model base-year USD producer price'a dönüştürülmeden CEDA factor'ıyla çarpılamaz. Rest of
World satırı açık `proxy`, regional average satırları ise yalnız source country-region
mapping'inde listelenen ülkelere uygulanabilir `regional` factor olarak işaretlenir. Aynı
2025 release'inin tekrar çalıştırılması `NO_CHANGE` sonuçlanır ve duplicate version üretmez.

GLEC Framework v3.2'nin resmî 183 sayfalık PDF yayını koordinatları denetlenmiş tablo
kontratıyla işlenir. Module 1'den 102 WTW yakıt/enerji taşıyıcı factor'ı, Module 2'den
375 end-user WTW taşıma ve hub yoğunluğu, Module 3'ten 44 AR6 GWP100 characterization
sonucu üretilir. TTW/WTT bileşenleri ayrı toplam factor gibi çoğaltılmaz; methodology
detayında korunur. Değeri bulunmayan R-717 canonical katmandan çıkarılır. Soğutucu charge
ve leakage varsayımları 6 `CALCULATION_PARAMETER` source observation olarak saklanır.
Toplam 521 canonical version'ın 477'si inventory matching için uygundur. Source yayınının
ticari/API yeniden dağıtım hakkı açık olmadığı için bu izin manifestte kısıtlı kalır;
owner review sonrası local reference stack'te published durumdadır. İkinci koşu
`NO_CHANGE` sonuçlanır.

## Güncel geliştirme önceliği

Yeni source ingestion kuyruğu kapatılmıştır; mevcut veri havuzu intelligence ürünleşmesi
için yeterli kabul edilir. Cornerstone/USEEIO ve Cloud Carbon Footprint planlı source
listesinden çıkarılmıştır. Güncel sıra: unit envanteri ve dönüşüm kapsamı → canonical
concept kapsamı → EN/TR/DE/FR/ES/RU/AR çeviri review'ları → completeness gate → ürün
entegrasyonlarıdır. Completeness gate yeşil olmadan NetZero dahil hiçbir ürün
entegrasyonuna geçilmez.

Bu karar runtime seviyesinde de uygulanır: `ATLAS_SOURCE_INGESTION_ENABLED` varsayılan
olarak `false` değerindedir. Bu durumda scheduler yeni run üretmez, worker eski source-run
mesajlarından veri yazmaz ve admin source-run endpoint'i `409` döner. Bayrağın açılması
yalnız açık bir ürün/yönetişim kararıyla yapılabilir.

Completeness backfill'i factor, activity ve source-observation katmanlarındaki 966/966
distinct raw unit expression'ı açık bir disposition ile kaydeder. Factor version
ifadelerinin 294.669'u canonical unit'e mapped; 17'si ratio, 1.329'u source-native olarak
sınıflandırılmıştır. Current calculation-eligible factor havuzunda mapped olmayan unit
ifadesi yoktur. 171.005/171.005 logical factor 486 canonical concept'e bağlıdır.
EN/TR/DE/FR/ES/RU/AR dillerinin her birinde 486/486 tercih edilen label approved durumundadır;
OpenAI üretimi, koşullu Sol QA ve owner-delegated audit 30 Ağustos 2026'da tamamlandı.
Intelligence, recommendation ve sector kapılarının birleşik `/ready` sonucu `true` değerindedir.

## Source integration coverage

Bu matris publisher release/reference-year ingestion kapsamını gösterir; factor'ın kendi
geçerlilik yılıyla karıştırılmamalıdır.

- `✅`: Resmî dataset Atlas pipeline'ında gerçekten ingest edildi.
- `↔`: Kaynak annual release üretmeyen living/versioned database olarak entegre edildi;
  sentetik yıllık snapshot oluşturulmaz.
- `PDF`: Resmî yayın mevcut, denetlenmiş PDF parser henüz tamamlanmadı.
- `○`: Publisher bu yıl için dataset yayımlamadı.
- `—`: Henüz entegre edilmedi.

| EF Source | Model | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 | Source |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| ADEME | Versioned DB | ↔ | ↔ | ↔ | ↔ | ↔ | ↔ | ↔ | ✅ |
| Agribalyse | Versioned DB | ↔ | ↔ | ↔ | ↔ | ↔ | ↔ | ↔ | ✅ |
| AIB | Lagged yearly | PDF | PDF | ✅ | ✅ | ✅ | ✅ | ○ | ✅ |
| AusLCI | — | — | — | — | — | — | — | — | — |
| BAFA | — | — | — | — | — | — | — | — | — |
| BEIS / DEFRA / DESNZ / NAEI | Yearly | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| CAEP | — | — | — | — | — | — | — | — | — |
| CBAM | Definitive legal values | ○ | ○ | ○ | ○ | ○ | ○ | ✅ | ✅ |
| Cloud Carbon Footprint (CCF) | — | — | — | — | — | — | — | — | — |
| Circular Ecology | — | — | — | — | — | — | — | — | — |
| Climate TRACE | — | — | — | — | — | — | — | — | — |
| Climatiq | — | — | — | — | — | — | — | — | — |
| CLP Group | — | — | — | — | — | — | — | — | — |
| CO2 Emissiefactoren | — | — | — | — | — | — | — | — | — |
| CO2 Emissiefactoren Belgium | — | — | — | — | — | — | — | — | — |
| CONCITO + 2.-0 LCA | Versioned DB | ↔ | ↔ | ↔ | ↔ | ↔ | ↔ | ↔ | ✅ |
| Cornerstone / USEEIO | — | — | — | — | — | — | — | — | — |
| Covenant of Mayors / JRC | — | — | — | — | — | — | — | — | — |
| Climate Transparency (CT) | — | — | — | — | — | — | — | — | — |
| Danish Energy Agency | — | — | — | — | — | — | — | — | — |
| DEWA | — | — | — | — | — | — | — | — | — |
| DISER / DCCEEW | — | — | — | — | — | — | — | — | — |
| DiXi Group – Green Transition Office | — | — | — | — | — | — | — | — | — |
| EEA | Versioned DB | ↔ | ↔ | ↔ | ↔ | ↔ | ↔ | ↔ | ✅ |
| EEI | — | — | — | — | — | — | — | — | — |
| Electricity Info | — | — | — | — | — | — | — | — | — |
| EMA | — | — | — | — | — | — | — | — | — |
| Ember | API time series | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ○ | ✅ |
| Energiföretagen Sverige | — | — | — | — | — | — | — | — | — |
| EPA | Yearly | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ○ | ✅ |
| EPPO | — | — | — | — | — | — | — | — | — |
| ETKB / Türkiye Electricity | Yearly PDF | ✅ | ✅ | ✅ | ✅ | ○ | ○ | ○ | ✅ |
| GEMIS | — | — | — | — | — | — | — | — | — |
| GHG Protocol | Versioned workbook | ↔ | ↔ | ↔ | ↔ | ↔ | ↔ | ↔ | ✅ |
| GLEC | Versioned publication | ↔ | ↔ | ↔ | ↔ | ↔ | ↔ | ↔ | ✅ |
| Google | — | — | — | — | — | — | — | — | — |
| Government of Canada | Versioned regulatory doc | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| Government of India – CEA | — | — | — | — | — | — | — | — | — |
| Green-e | — | — | — | — | — | — | — | — | — |
| Greenview | — | — | — | — | — | — | — | — | — |
| HKEI | — | — | — | — | — | — | — | — | — |
| ICM Database | — | — | — | — | — | — | — | — | — |
| IGES | — | — | — | — | — | — | — | — | — |
| IPCC | Versioned DB | ↔ | ↔ | ↔ | ↔ | ↔ | ↔ | ↔ | ✅ |
| ISPRA | — | — | — | — | — | — | — | — | — |
| Market Economics Limited | — | — | — | — | — | — | — | — | — |
| MfE | — | — | — | — | — | — | — | — | — |
| MITECO | — | — | — | — | — | — | — | — | — |
| Netherlands Enterprise Agency (RVO) | — | — | — | — | — | — | — | — | — |
| NVE | — | — | — | — | — | — | — | — | — |
| ÖKOBAUDAT | Versioned DB | ↔ | ↔ | ↔ | ↔ | ↔ | ↔ | ↔ | ✅ |
| OpenIO-Canada | — | — | — | — | — | — | — | — | — |
| PCAF | — | — | — | — | — | — | — | — | — |
| Plastics Europe | Versioned publication | — | — | — | — | — | — | ✅ | ✅ |
| Plastics Recyclers Europe | Historical publication (2015) | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ✅ |
| SEFR | — | — | — | — | — | — | — | — | — |
| SEMARNAT | — | — | — | — | — | — | — | — | — |
| Shiseido | — | — | — | — | — | — | — | — | — |
| Smart Freight Centre India | — | — | — | — | — | — | — | — | — |
| Statistics Finland | — | — | — | — | — | — | — | — | — |
| STC-Nestra | — | — | — | — | — | — | — | — | — |
| UBA | — | — | — | — | — | — | — | — | — |
| UBA Austria | — | — | — | — | — | — | — | — | — |
| UNECE | — | — | — | — | — | — | — | — | — |
| UNEP | — | — | — | — | — | — | — | — | — |
| UNFCCC / Turkish Statistical Institute | Yearly submission | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Watershed / CEDA | Yearly release | — | — | — | — | ✅ | ✅ | ○ | ✅ |
| WRAP | Versioned DB | ↔ | ↔ | ↔ | ↔ | ↔ | ↔ | ↔ | ✅ |

## Kümülatif veri envanteri

Aşağıdaki sayılar 28 Ağustos 2026 itibarıyla canlı Atlas veritabanından alınmıştır.
`Canonical version`, rejected olmayan tüm dataset version'larındaki factor version
toplamıdır; unique logical veya yalnız current factor sayısı değildir. `LCA result` ve
`Karakterizasyon` kendi canonical entity type'larını, `EF` yalnız
`entity_type=emission_factor`, `Embodied EF` yalnız
`entity_type=embodied_emission_factor` kayıtlarını sayar. Source observation'lar factor
değildir.

| Source | Canonical version | EF | Embodied EF | LCA result | Karakterizasyon | Referans değer | Source observation |
|---|---:|---:|---:|---:|---:|---:|---:|
| ADEME | 6.356 | 6.356 | 0 | 0 | 0 | 0 | 0 |
| AGRIBALYSE | 2.901 | 0 | 0 | 2.901 | 0 | 0 | 0 |
| AIB | 158 | 158 | 0 | 0 | 0 | 0 | 0 |
| Canada | 399 | 399 | 0 | 0 | 0 | 0 | 45 |
| CBAM | 11.170 | 0 | 11.170 | 0 | 0 | 0 | 2.465 |
| CONCITO + 2.-0 LCA | 18.248 | 0 | 0 | 18.248 | 0 | 0 | 0 |
| DEFRA / DESNZ | 20.442 | 20.442 | 0 | 0 | 0 | 0 | 0 |
| EEA | 1.556 | 1.556 | 0 | 0 | 0 | 0 | 11.469 |
| Ember | 1.208 | 1.207 | 0 | 0 | 0 | 1 | 0 |
| EPA | 4.434 | 4.434 | 0 | 0 | 0 | 0 | 0 |
| ETKB | 80 | 80 | 0 | 0 | 0 | 0 | 0 |
| GHG Protocol | 875 | 875 | 0 | 0 | 0 | 0 | 158 |
| GLEC | 521 | 477 | 0 | 0 | 44 | 0 | 6 |
| IPCC | 8.018 | 8.018 | 0 | 0 | 0 | 0 | 0 |
| ÖKOBAUDAT | 44.013 | 0 | 0 | 44.013 | 0 | 0 | 0 |
| Open CEDA | 127.600 | 127.600 | 0 | 0 | 0 | 0 | 9.020 |
| Plastics Europe | 28 | 0 | 0 | 28 | 0 | 0 | 0 |
| Plastics Recyclers Europe | 8 | 0 | 0 | 8 | 0 | 0 | 17 |
| UNFCCC / TÜİK | 44.783 | 44.783 | 0 | 0 | 0 | 0 | 595.180 |
| WRAP | 1.140 | 0 | 0 | 1.140 | 0 | 0 | 0 |
| **Toplam** | **293.938** | **216.385** | **11.170** | **66.338** | **44** | **1** | **618.360** |

Kullanım bağlamı sütunları source manifestindeki beyanı canonical version sayısına
uygular; aynı kayıt birden fazla bağlamda yer alabilir ve sütunlar toplanamaz.

| Source | PCF | LCA | Corporate carbon | Scope 3 | Freight / logistics | Regulatory / CBAM | Offset / protocol |
|---|---:|---:|---:|---:|---:|---:|---:|
| ADEME | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| AGRIBALYSE | 2.901 | 2.901 | 0 | 0 | 0 | 0 | 0 |
| AIB | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Canada | 0 | 0 | 399 | 0 | 0 | 0 | 399 |
| CBAM | 11.170 | 0 | 0 | 0 | 0 | 11.170 | 0 |
| CONCITO + 2.-0 LCA | 18.248 | 18.248 | 18.248 | 18.248 | 0 | 0 | 0 |
| DEFRA / DESNZ | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| EEA | 1.556 | 0 | 1.556 | 0 | 0 | 0 | 0 |
| Ember | 1.208 | 1.208 | 1.208 | 0 | 0 | 0 | 0 |
| EPA | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| ETKB | 80 | 0 | 80 | 0 | 0 | 0 | 0 |
| GHG Protocol | 0 | 0 | 875 | 875 | 875 | 0 | 0 |
| GLEC | 0 | 0 | 521 | 521 | 521 | 0 | 0 |
| IPCC | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| ÖKOBAUDAT | 0 | 44.013 | 0 | 0 | 0 | 0 | 0 |
| Open CEDA | 0 | 0 | 127.600 | 127.600 | 0 | 0 | 0 |
| Plastics Europe | 28 | 28 | 28 | 28 | 0 | 0 | 0 |
| Plastics Recyclers Europe | 8 | 8 | 8 | 8 | 0 | 0 | 0 |
| UNFCCC / TÜİK | 0 | 0 | 44.783 | 0 | 0 | 0 | 0 |
| WRAP | 1.140 | 1.140 | 1.140 | 1.140 | 0 | 0 | 0 |
| **Toplam bağlam kapsamı** | **36.339** | **67.546** | **196.446** | **148.420** | **1.396** | **11.170** | **399** |

Coğrafi sütunlar aynı canonical version toplamının birbirini dışlayan applicability
kırılımıdır. `Country`, `country_specific + country_modelled`; `Region`,
`regional + continental` değerlerini birleştirir.

| Source | Country | Region / continent | Global | Proxy |
|---|---:|---:|---:|---:|
| ADEME | 5.797 | 212 | 347 | 0 |
| AGRIBALYSE | 2.899 | 1 | 0 | 1 |
| AIB | 158 | 0 | 0 | 0 |
| Canada | 395 | 0 | 0 | 4 |
| CBAM | 10.650 | 0 | 0 | 520 |
| CONCITO + 2.-0 LCA | 18.248 | 0 | 0 | 0 |
| DEFRA / DESNZ | 20.442 | 0 | 0 | 0 |
| EEA | 0 | 1.556 | 0 | 0 |
| Ember | 1.118 | 84 | 6 | 0 |
| EPA | 3.583 | 376 | 454 | 21 |
| ETKB | 80 | 0 | 0 | 0 |
| GHG Protocol | 402 | 324 | 149 | 0 |
| GLEC | 69 | 140 | 312 | 0 |
| IPCC | 0 | 0 | 8.018 | 0 |
| ÖKOBAUDAT | 14.897 | 27.541 | 1.575 | 0 |
| Open CEDA | 118.400 | 8.400 | 0 | 800 |
| Plastics Europe | 0 | 28 | 0 | 0 |
| Plastics Recyclers Europe | 0 | 8 | 0 | 0 |
| UNFCCC / TÜİK | 44.783 | 0 | 0 | 0 |
| WRAP | 1.006 | 0 | 134 | 0 |
| **Toplam** | **242.927** | **38.670** | **10.995** | **1.346** |

CBAM'ın kendi ürün ve geography-fit kırılımı aşağıdadır. `Other` ve `Annex IV` değerleri
country-specific gibi gösterilmez; ikisi de açık proxy'dir. Benchmark sütunu factor
toplamına dahil değildir.

| CBAM sektörü | Canonical factor | Country-modelled | Other proxy | Annex IV proxy | Benchmark observation |
|---|---:|---:|---:|---:|---:|
| Cement | 345 | 329 | 8 | 8 | 18 |
| Fertilisers | 2.443 | 2.389 | 27 | 27 | 56 |
| Iron and steel | 6.629 | 6.229 | 200 | 200 | 2.210 |
| Aluminium | 1.656 | 1.608 | 24 | 24 | 179 |
| Hydrogen | 97 | 95 | 1 | 1 | 2 |
| **Toplam** | **11.170** | **10.650** | **260** | **260** | **2.465** |

Canada Version 3.0'ın ayrı factor-family chart'ı aşağıdadır. `2023–2024` tek bir iki
yıllık geçerlilik dilimidir; yıllar ayrı release değildir. CH₄ ve N₂O sütunları event-time
GWP uygulanmamış bileşen-gaz factor'larını, elektrik satırı ise doğrudan CO₂e toplamını
temsil eder.

| Canada faktör ailesi | Entity / değer türü | 2023–2024 | 2025 | 2026 | Canonical factor |
|---|---|---:|---:|---:|---:|
| Natural gas — CO₂ | EF / `CO2_ONLY` | 23 | 23 | 23 | 69 |
| Natural gas — CH₄ ve N₂O | EF / component gas | 16 | 22 | 22 | 60 |
| Natural gas liquids | EF / CO₂ + component gas | 12 | 12 | 12 | 36 |
| Refined petroleum products | EF / CO₂ + component gas | 63 | 63 | 63 | 189 |
| Provincial electricity consumption | EF / `CO2E_TOTAL` | 13 | 13 | 13 | 39 |
| Biogas combustion — N₂O | EF / component gas | 2 | 2 | 2 | 6 |
| **Toplam** | **399 EF** | **129** | **135** | **135** | **399** |

| Canada ek kırılımı | Country / province exact | Proxy | Factor değil: source observation |
|---|---:|---:|---:|
| Canonical geography fit | 395 | 4 | 0 |
| Improved Forest Management protocol values | 0 | 0 | 14 |
| Beef Cattle protocol parameters | 0 | 0 | 31 |
| **Toplam** | **395** | **4** | **45** |

ETKB yıllık PDF serisinin ayrı factor-family chart'ı aşağıdadır. Her source satırı CO₂
ve publisher-reported CO₂e olmak üzere iki canonical version üretir; dolayısıyla factor
toplamı source faaliyet satırının iki katıdır.

| ETKB faktör ailesi | 2020 | 2021 | 2022 | 2023 | Canonical version |
|---|---:|---:|---:|---:|---:|
| Türkiye geneli brüt elektrik üretimi | 2 | 2 | 2 | 2 | 8 |
| Yakıta göre elektrik üretimi — 7 yakıt | 14 | 14 | 14 | 14 | 56 |
| İletim/dağıtım tüketim noktası | 4 | 4 | 4 | 4 | 16 |
| **Toplam** | **20** | **20** | **20** | **20** | **80** |

| ETKB yıl kırılımı | Üretim CO₂e (kgCO₂e/kWh) | İletim tüketim CO₂e | Dağıtım tüketim CO₂e | `CO2_ONLY` | `CO2E_TOTAL` |
|---|---:|---:|---:|---:|---:|
| 2020 | 0,420 | 0,427 | 0,462 | 10 | 10 |
| 2021 | 0,439 | 0,445 | 0,479 | 10 | 10 |
| 2022 | 0,442 | 0,445 | 0,478 | 10 | 10 |
| 2023 | 0,434 | 0,436 | 0,469 | 10 | 10 |
| **Toplam factor** | — | — | — | **40** | **40** |

ÖKOBAUDAT 2024-II'nin ayrı LCA chart'ları aşağıdadır. Her canonical kayıt tek bir
ürün/veri seti + scenario + EN 15804 lifecycle module için publisher'ın toplam GWP
sonucudur. Negatif değerler başta module D olmak üzere LCA kredileridir; inventory EF
veya default-match adayı değildir.

| ÖKOBAUDAT lifecycle module | Açıklama | LCA result | Negatif sonuç |
|---|---|---:|---:|
| A1 | Hammadde temini | 469 | 56 |
| A2 | Hammadde taşımacılığı | 469 | 0 |
| A3 | Üretim | 469 | 33 |
| A1–A3 | Birleştirilmiş ürün aşaması | 3.808 | 186 |
| A4 | Şantiyeye taşımacılık | 2.903 | 0 |
| A5 | Kurulum | 2.962 | 0 |
| B1 | Kullanım | 2.154 | 338 |
| B2 | Bakım | 1.990 | 0 |
| B3 | Onarım | 1.723 | 4 |
| B4 | Değiştirme | 1.674 | 0 |
| B5 | Yenileme | 1.678 | 1 |
| B6 | Operasyonel enerji | 2.019 | 3 |
| B7 | Operasyonel su | 1.799 | 0 |
| C1 | Söküm/yıkım | 3.578 | 0 |
| C2 | Atık taşımacılığı | 4.021 | 0 |
| C3 | Atık işleme | 4.143 | 62 |
| C4 | Bertaraf | 3.818 | 26 |
| D | Sistem sınırı dışı fayda/yük | 4.336 | 3.992 |
| **Toplam** | **4.286 data set / 44.013 module-scenario sonucu** | **44.013** | **4.701** |

| ÖKOBAUDAT standardı | Canonical / LCA | Country | Region / continent | Global | Default-match |
|---|---:|---:|---:|---:|---:|
| EN 15804+A1 | 61 | 61 | 0 | 0 | 0 |
| EN 15804+A2 | 43.952 | 14.836 | 27.541 | 1.575 | 0 |
| **Toplam** | **44.013** | **14.897** | **27.541** | **1.575** | **0** |

| ÖKOBAUDAT data set türü | Module-scenario LCA result |
|---|---:|
| Specific dataset | 13.648 |
| Average dataset | 27.539 |
| Generic dataset | 2.140 |
| Template dataset | 481 |
| Representative dataset | 205 |
| **Toplam** | **44.013** |

WRAP v2.0'ın ayrı LCA chart'ları aşağıdadır. HESTIA yalnız IPCC 2021 GWP100 sonuçlarını,
`refined` ise WRAP'ın UK relevance ve veri kalitesi ölçütleriyle küratörlediği katmanı
gösterir. `full` tablosu ve CarbonWARM2 bu 1.140 canonical sonuca dahil değildir.

| WRAP veri katmanı | Canonical / LCA | Country-modelled | Global | kg FU | litre FU | Negatif | Default-match |
|---|---:|---:|---:|---:|---:|---:|---:|
| HESTIA GWP100 | 722 | 642 | 80 | 722 | 0 | 7 | 0 |
| Curated refined | 418 | 364 | 54 | 408 | 10 | 1 | 0 |
| **Toplam** | **1.140** | **1.006** | **134** | **1.130** | **10** | **8** | **0** |

| WRAP lifecycle stage | HESTIA GWP100 | Refined | Toplam |
|---|---:|---:|---:|
| Cradle to Farm Gate | 80 | 87 | 167 |
| Farm input | 297 | 0 | 297 |
| Farm | 345 | 9 | 354 |
| Feed | 0 | 9 | 9 |
| Land Use Change | 0 | 12 | 12 |
| Processing | 0 | 71 | 71 |
| Packaging | 0 | 71 | 71 |
| Transport | 0 | 71 | 71 |
| Cradle to Processing Gate + Transport | 0 | 88 | 88 |
| **Toplam** | **722** | **418** | **1.140** |

| WRAP upstream database | LCA result |
|---|---:|
| HESTIA | 642 |
| HESTIA multi-ingredient | 80 |
| AGRIBALYSE ready-to-eat | 176 |
| Foodsteps | 150 |
| GLEAM | 35 |
| Frankowska et al. | 20 |
| Poore & Nemecek | 16 |
| HCC | 12 |
| GFLI | 6 |
| AGRIBALYSE cradle-to-farm-gate | 3 |
| **Toplam** | **1.140** |

CONCITO / 2.-0 LCA v1.2'nin ayrı LCA chart'ları aşağıdadır. Her activity bir ürün ×
retail-market ülkesidir. Total sonuçlar her zaman korunur; exact-zero stage hücreleri
factor değildir. Negatif değerler consequential LCA kredi sonuçlarıdır.

| The Big Climate Database sonucu | Ham hücre | Canonical LCA | Exact-zero dışlanan | Negatif |
|---|---:|---:|---:|---:|
| Total | 2.700 | 2.700 | 0 | 0 |
| Agriculture | 2.700 | 2.575 | 125 | 0 |
| iLUC | 2.700 | 2.700 | 0 | 308 |
| Processing / other | 2.700 | 2.213 | 487 | 350 |
| Packaging | 2.700 | 2.680 | 20 | 23 |
| Transport | 2.700 | 2.690 | 10 | 4 |
| Retail | 2.700 | 2.690 | 10 | 0 |
| **Toplam** | **18.900** | **18.248** | **652** | **685** |

| CONCITO retail pazarı | Ürün / Total sonucu | Tüm stage LCA | Negatif | Geography fit | Default-match |
|---|---:|---:|---:|---|---:|
| Denmark (DK) | 540 | 3.649 | 141 | Country-modelled | 0 |
| Spain (ES) | 540 | 3.649 | 129 | Country-modelled | 0 |
| France (FR) | 540 | 3.649 | 118 | Country-modelled | 0 |
| Great Britain (GB) | 540 | 3.649 | 143 | Country-modelled | 0 |
| Netherlands (NL) | 540 | 3.652 | 154 | Country-modelled | 0 |
| **Toplam** | **2.700** | **18.248** | **685** | **Country-modelled** | **0** |

| CONCITO ürün kategorisi | LCA result |
|---|---:|
| Meat/poultry/other animals | 2.620 |
| Fruits/vegetables/nuts/seeds prepared/processed | 2.586 |
| Prepared/preserved foods | 2.545 |
| Seafood | 1.795 |
| Vegetables | 1.691 |
| Bread/bakery products | 1.395 |
| Beverages | 1.125 |
| Seasonings/preservatives/extracts | 1.091 |
| Milk/butter/cream/yoghurts/cheese/eggs/substitutes | 1.070 |
| Fruits — unprepared/unprocessed | 795 |
| Cereal/grain/pulse products | 750 |
| Confectionery/sugar sweetening products | 450 |
| Oils/fats edible | 125 |
| Candy/sugar products | 105 |
| Milk/eggs/substitute products | 70 |
| Fruit/vegetable products | 35 |
| **Toplam** | **18.248** |

Plastics Europe Mart 2026 Eco-profile sonuçlarının ayrı LCA chart'ı aşağıdadır. Her satır
publisher'ın cradle-to-gate, Avrupa üretim-ortalaması ve 1 kg ürün fonksiyonel birimiyle
yayımladığı bir GWP100 sonucudur; klasik inventory default-match havuzuna girmez.

| Plastics Europe ürün ailesi | LCA result | PCF | Scope 3 | Region / continent | 1 kg functional unit | GWP100 aralığı (kgCO2e/kg) | Default-match |
|---|---:|---:|---:|---:|---:|---:|---:|
| Polyolefin resins | 4 | 4 | 4 | 4 | 4 | 1,92–2,16 | 0 |
| Vinyl chloride and PVC resins | 3 | 3 | 3 | 3 | 3 | 1,64–2,45 | 0 |
| Steam cracker products and aromatics | 14 | 14 | 14 | 14 | 14 | 1,25–2,08 | 0 |
| Refinery feedstocks | 7 | 7 | 7 | 7 | 7 | 0,69–1,17 | 0 |
| **Toplam** | **28** | **28** | **28** | **28** | **28** | **0,69–2,45** | **0** |

| Paket / rapor | Publisher GWP100 sonuçları (kgCO2e/kg) |
|---|---|
| PE and PP | HDPE 2,16; LDPE 2,16; LLDPE 2,12; PP 1,92 |
| CVM and PVC | VCM 1,64; S-PVC 2,08; E-PVC 2,45 |
| Steam cracker | Ethylene 1,82; propylene 1,78; butadiene 1,95; pyrolysis gasoline 1,32; hydrogen 1,77; ethylene oxide 2,08; MEG 1,60; DEG 1,87; TEG 1,98 |
| Steam cracker aromatics | Benzene 1,86; toluene 1,39; o-xylene 1,77; p-xylene 1,75; mixed xylenes 1,25 |
| Refinery | Naphtha 0,72; atmospheric gas oil 0,69; FCC propylene 1,17; reformate 0,91; propane/butane 1,05; diesel 0,99; petrol 0,99 |

Plastics Recyclers Europe 2015 sonuçlarının ayrı chart'ları aşağıdadır. Raporun kendi
ifadesiyle değerler EU-28 impact-assessment modeline aittir; current market average
değildir. `Documented`, upstream Wisard LCI değerini; `PE proxy`, PE değerinin başka
reçineye publisher tarafından taşındığını gösterir.

| Recycled plastic çıkışı | LCA result | Değer temeli | kgCO2e/kg output | PCF | Scope 3 | Region | Default-match |
|---|---:|---|---:|---:|---:|---:|---:|
| PET bottle-grade | 1 | Documented | 0,510 | 1 | 1 | 1 | 0 |
| PET fibre-grade | 1 | Documented | 0,280 | 1 | 1 | 1 | 0 |
| PE-HD | 1 | Documented | 0,348 | 1 | 1 | 1 | 0 |
| PE-LD | 1 | Documented | 0,348 | 1 | 1 | 1 | 0 |
| PP | 1 | PE proxy | 0,348 | 1 | 1 | 1 | 0 |
| PS | 1 | PE proxy | 0,348 | 1 | 1 | 1 | 0 |
| PVC | 1 | PE proxy | 0,348 | 1 | 1 | 1 | 0 |
| Other plastic resins | 1 | PE proxy | 0,348 | 1 | 1 | 1 | 0 |
| **Toplam** | **8** | **4 documented / 4 proxy** | **0,280–0,510** | **8** | **8** | **8** | **0** |

| PRE model girdisi | Source observation | Canonical factor | Semantik |
|---|---:|---:|---|
| Collection / sorting / transport | 4 | 0 | Direct process-model input |
| Virgin plastic substitution | 8 | 0 | Avoided-emission calculation input |
| Incineration / RDF energy recovery | 4 | 0 | 2 direct + 2 avoided input |
| Landfill operations | 1 | 0 | Direct process-model input |
| **Toplam** | **17** | **0** | **Factor kataloğu dışında** |

EMEP/EEA Guidebook 2023 viewer'ının ayrı ingestion chart'ları aşağıdadır. `Raw / parsed`
viewer'daki tüm seçilmiş satırları, `Source observation` sayısal fakat Atlas'ın güvenli
GHG canonical sınırı dışında kalan kayıtları gösterir. Viewer'ın kendi uyarısı gereği
uyuşmazlıkta ilgili Guidebook chapter'ı esas alınır.

| EEA viewer kayıt türü | Raw / parsed | Canonical EF | Source observation | Raw/parsed-only |
|---|---:|---:|---:|---:|
| Tier 1 emission factor | 2.185 | 74 | 2.094 | 17 |
| Tier 2 emission factor | 10.509 | 1.482 | 8.733 | 294 |
| Tier 2 abatement efficiency | 480 | 0 | 480 | 0 |
| Tier 1 fuel consumption | 10 | 0 | 10 | 0 |
| Tier 2 fuel consumption | 152 | 0 | 152 | 0 |
| **Toplam** | **13.336** | **1.556** | **11.469** | **311** |

| EEA canonical gaz etiketi | Viewer satırı | Canonical EF | Değer türü | Geography | Default-match |
|---|---:|---:|---|---|---:|
| CO₂ | 583 | 559 | `CO2_ONLY` | Europe / continental | 0 |
| CO₂ lube | 377 | 377 | `CO2_ONLY` | Europe / continental | 0 |
| CH₄ | 145 | 121 | Component gas EF | Europe / continental | 0 |
| N₂O | 523 | 499 | Component gas EF | Europe / continental | 0 |
| **Toplam** | **1.628** | **1.556** | **936 CO₂-only / 620 gas EF** | **1.556** | **0** |

## Geliştirme

```bash
cp .env.example .env
uv sync --all-groups
docker compose up -d
uv run pytest
docker compose ps --all
```

OpenAI terminology üretimi için gerçek anahtar yalnız git dışındaki `.env` veya deployment
secret store'a yazılır:

```dotenv
ATLAS_OPENAI_API_KEY=
ATLAS_OPENAI_ORGANIZATION=
ATLAS_OPENAI_PROJECT=
ATLAS_TRANSLATION_PROVIDER=openai
ATLAS_TRANSLATION_TARGET_LANGUAGE=tr
ATLAS_TRANSLATION_BATCH_SIZE=50
ATLAS_OPENAI_TRANSLATION_MODEL=gpt-5.6-terra
ATLAS_OPENAI_QA_MODEL=gpt-5.6-sol
ATLAS_OPENAI_BATCH_ENABLED=true
ATLAS_MULTILINGUAL_RESOLVER_V2=true
```

Anahtar health veya audit payload'ında döndürülmez; `/health` yalnız provider'ın configured
durumunu ve model adlarını gösterir. Terminoloji üretimi en fazla 50 konseptlik operasyonel
job'lara bölünür ve insan onayı gelene kadar `draft` kalır. Admin endpoint'i asenkron Batch API
için `execution_mode=batch`, doğrudan 50-konsept Responses API grupları için
`execution_mode=responses` kabul eder. Explorer, Batch dosyalarına erişemeyen proje anahtarlarıyla
da çalışabilmek için Responses gruplarını kullanır. Aktif bir job içindeki concept yeni bir
`only_missing=true` çağrısında tekrar gönderilmez.

Atlas host portları diğer Cleture projeleriyle çakışmaması için ayrı bir bloktadır:

| Servis | Host port | Container port |
|---|---:|---:|
| API | 48080 | 48080 |
| PostgreSQL | 45432 | 5432 |
| Redis | 46379 | 6379 |
| MinIO API | 49000 | 9000 |
| MinIO Console | 49001 | 9001 |

Host portları `.env` içindeki `ATLAS_*_HOST_PORT` değişkenleriyle override edilebilir.

API:

```text
GET /health
GET /explorer
GET /explorer/catalog
GET /v1/sources
GET /v1/sources/{code}
GET /v1/sources/{code}/coverage
GET /v1/datasets
GET /v1/datasets/{dataset_id}
GET /v1/datasets/{dataset_id}/versions
GET /v1/factors
GET /v1/factors/{factor_id}
GET /v1/factors/{factor_id}/versions
GET /v1/countries?language=tr
GET /v1/geographies
GET /v1/geographies/{country}/coverage
GET /v1/units
GET /v1/units/{code}
GET /v1/contexts
GET /v1/contexts/{context}/profiles
GET /v1/profiles/{profile}/rules
GET /v1/scope3/categories
GET /v1/concepts
POST /v1/concepts/resolve
POST /v1/convert
POST /v1/search
POST /v1/recommendations
GET  /v1/explorer/concepts/resolve
POST /v1/explorer/compatibility
POST /v1/explorer/calculate
POST /v1/explorer/compare
POST /v1/explorer/regression/run

POST /v1/admin/sources/{code}/runs
GET  /v1/admin/runs/{run_id}
GET  /v1/admin/reviews
POST /v1/admin/reviews/{review_id}/approve
POST /v1/admin/reviews/{review_id}/reject
GET  /v1/admin/units/inventory
GET  /v1/admin/intelligence/coverage
POST /v1/admin/intelligence/rebuild
POST /v1/admin/concepts/{concept_code}/labels
GET  /v1/admin/translations
PATCH /v1/admin/translations/{label_id}
POST /v1/admin/translations/{label_id}/{decision}
GET  /v1/admin/translation-jobs
POST /v1/admin/translation-jobs
POST /v1/admin/translation-jobs/{job_id}/sync
GET  /v1/admin/translation-glossary
POST /v1/admin/translation-glossary
```

`http://localhost:48080/explorer` adresindeki Atlas Explorer, global
facility/country/year/context/profile çubuğunun altında tek bir Search çalışma alanı sunar.
Alt alan 25/25/50 oranında Text/Quantity/Unit input'u, dikey search sonuçları ve kendi içinde
iki kolona bölünen seçili factor detayından oluşur. Arayüz yeni factor seçim veya conversion
kuralları tanımlamaz; versioned `/v1/recommendations`, `/v1/explorer/compatibility` ve
`/v1/explorer/calculate` sözleşmelerini çağırır. Dünya geneline dağılmış 20 başlangıç facility
seçeneği vardır; country override listesi sabit bir UI listesi değil, merkezî
`/v1/countries` ISO registry'sindeki desteklenen ülke kodlarından üretilir. Country kimliği
ISO alpha-2'dir; alpha-3/numeric kodlar ile EN/TR/DE/FR/ES/IT/PT/RU/AR/FA/JA/ZH adları ve
onaylı yaygın adlar ayrı, review-status taşıyan label kayıtlarıdır. `banana DK`,
`banana Denmark` ve `banana Danimarka` aynı `DK` filtresine çözülür. Facility, country,
context ve profile
Search isteğinin eligibility girdileridir. Sonuç seçildiğinde desteklenen input unit'leri factor paydasından
`/v1/explorer/compatibility` ile türetilir ve `/v1/explorer/calculate` conversion ile final
sonucu server-side üretip detay panelinde gösterir. Sağ compatibility paneli unit registry
chip'lerini dökmek yerine input unit selector sunar; parameterized seçimde gerekli parameter
value/unit alanları açılır. Conditional conversion açık parametre ve
unit provenance'i olmadan hesaplanmaz; ancak eksik parameter factor'ı recommendation adaylığından
çıkarmaz. Örneğin `100 m³` natural gas girdisi `kgCO₂e/GJ` factor'ını önerebilir, seçimden
sonra calorific value ister ve yalnız bu değer sağlanınca hesaplar. İlk activity unit selector'ı
`/v1/units` registry'sini başlangıçta bir kez yükler ve bütün unit'leri dimension'a göre gruplar.
Profile, context, facility veya query değişimi selector'ı yeniden üretmez; seçilmiş unit sabit
kalır ve yalnız Search aday havuzu yeni context'e göre yeniden değerlendirilir. Örneğin GB / Scope 3 / `domestic` için
`passenger` seçilebilir; Atlas `passenger.km` factor'ını elemez, `distance` parametresi ister ve
`2 passenger × 500 km = 1.000 passenger.km` olarak normalize eder. TR context'inde GB'ye özel
DEFRA faktörü `accept_proxy=true` olmadan sunulmaz.

Masthead'deki **Factor catalog**, recommendation akışından ayrı bir source-faithful kayıt
inceleme yüzeyidir. `http://localhost:48080/explorer/catalog` altında source, ortak sektör,
sektör alt kategorisi ve GHG scope
seçilebilir; yazıldıkça server-side text filtresi factor adı, ID, source factor ID, taxonomy,
activity type ve factor unit üzerinde çalışır. Aynı sorgu onaylı çok dilli concept label ve
eşanlamlılarında da çözülür; çözümlenen concept'e bağlı kayıtlar kaynak adı farklı dilde olsa
bile ham text sonuçlarıyla birlikte listelenir ve arayüz uygulanan concept'i filtre çipinde
gösterir. Liste yalnız yayımlanmış emission,
implied-emission, embodied-emission factor ve source-faithful `LCA_RESULT` kayıtlarını kapsar;
calculation parameter/technical-property satırlarını veya calculation profile eligibility ve
runtime license kapılarını uygulamaz. Böylece AGRIBALYSE, The Big Climate Database, ÖKOBAUDAT,
Plastics Europe, Plastics Recyclers Europe ve WRAP gibi LCA-native kaynaklar da aynı katalogda
görünür. Bir kayıt seçildiğinde value/unit,
classification, temporal alanlar, geographies, gas breakdown, methodology details, provenance,
version history ve source registry tanımı birlikte gösterilir. Inspector ayrıca faktör, source
ve sürüm cevaplarının ham JSON'unu korur; böylece sistemde kayıtlı hiçbir alan özet görünüm
nedeniyle kaybolmaz. Scope'u publisher tarafından boş bırakılmış national inventory implied
combustion kayıtları katalogda açıkça `Scope 1 · inferred`, diğerleri `Unspecified` görünür.
Birden fazla reference year bulunan sonuç setinde kayıt sayılı yıl düğmeleri alt filtre olarak
görünür; yıl seçimi listeyi anında daraltır, `All` seçimi bütün yüklenmiş yılları geri getirir.
Catalog ve ana Explorer panel tipografisi normal desktop okuma mesafesinde 10 px altına düşmez;
factor adları, değerleri ve karar açıklamaları daha büyük görsel hiyerarşi kullanır.

Ortak sektör filtresi source taxonomy'yi değiştirmez. On iş sektörü ve yanlış pozitifleri
önleyen `Cross-sector / General`, versioned `atlas_sectors` registry'sinde tutulur; bütün
historical/current factor version'lar `atlas_factor_sector_assignments` ile eksiksiz
projekte edilir. Open CEDA ekonomik faaliyet kodları ile ADEME, LCA ve inventory taxonomy
root'ları aynı source-neutral crosswalk'ta sınıflanır. `GET /v1/sectors` canlı dağılımı,
`GET /v1/factors?sector=energy&category=electricity` katalog filtresini verir;
`atlas-sectors-check` eksik veya stale projeksiyonda non-zero döner.

Masthead'deki **Test Lab** mevcut Search yüzeyini değiştirmeden aynı canlı sözleşmeleri dört
deney görünümünde çalıştırır:

- **Live pipeline:** aktif Explorer girdisini language detection → canonical concept →
  context/profile → candidate gates → geography → unit path → factor selection → calculation
  zincirinde gösterir; her adımın ham verisi ile request/response kontratı açılabilir.
- **Regression suite:** temel conversion/semantic vakalarına ek olarak 20 tesisin her birinde
  Scope 1 doğal gaz ve Scope 2 location elektrik seçimini gerçek recommendation endpoint'inden
  doğrular. Kategori 1/3/4/5/6/9/12 Scope 3 yolları, freight/waste yön belirsizliği ve açık
  coverage gap'leriyle birlikte toplam 68 canonical senaryo kalıcı run olarak çalışır.
- **Language matrix:** EN/TR/DE/FR/ES/RU/AR ifadelerini düzenlenebilir alanlardan aynı canonical
  concept beklentisine karşı `/v1/concepts/resolve` ile ölçer.
- **System coverage:** admin anahtarıyla factor/concept/unit coverage kapılarını ve her dil için
  approved/draft/missing dağılımını gösterir; buradan mevcut terminology review ekranına geçilir.

Test Lab fixture sonucu taklit etmez ve browser içinde ayrı ranking kuralı uygulamaz. Bu nedenle
örneğin henüz ülke politikası bulunmayan US Scope 2 electricity senaryosu kırmızı görünür; bu,
arayüz hatası değil recommendation coverage açığı olarak gözlemlenir.

`/v1/search` geography verildiğinde repository sorgusunu istenen ülke, tanımlı parent/proxy
coğrafyalar ve global fallback ile sınırlar; calculation profile'ın entity type, factor kind ve
intended use kapıları candidate limitinden önce uygulanır. Scope engine'de doğrulanır; national
inventory boundary taşıyan energy total-CO₂e kayıtlarında kaynak scope'u boşsa Scope 1 türetilir. `SemanticSearchEngine`
aynı kapsamı yeniden doğrular ve exact ülke adaylarını fallback'lerden önce sıralar. Normal
API/Explorer sonucu yalnız geçerli adayları döndürür; scope, factor kind, activity concept veya
unit uyumsuzluğu gibi hard-deny kayıtları Advanced Debug'da da seçim listesine girmez.
Yayımlanmış katalog Search sırasında ikinci bir runtime license kırılımına tabi tutulmaz ve
Search payload'ına license eligibility alanı eklenmez; license kapısı ingestion/review/publish
sınırında uygulanır. Exact canonical concept eşleşmesi lexical FTS kanalını kapatmaz; böylece
`diesel → energy.diesel` çözümü, daha geniş `stationary_combustion` concept'ine bağlı
`Gas/Diesel oil2` factor'ını kaçırmaz. Slash ve noktalama FTS öncesinde token separator'a çevrilir.
IPCC kaynaklı bir GHG Protocol faktörü görünür sonuç setine girerse uygun canonical IPCC
primary factor da recommendation alternatiflerinde tutulur.

`/v1/search` katalog/developer keşfidir. Product seçimi `/v1/recommendations` ile yapılır;
`mode=suggest` açık varsayım üretebilir, `mode=strict` eksik qualifier için `needs_input`
döndürür. Her istek versioned `calculation_profile`, inline facility country ve activity
quantity/unit taşır. Translation ve synonym'ler
`atlas_concept_labels`, factor-concept ilişkileri `atlas_factor_concepts` tablolarında
kalıcıdır; original source/factor text overwrite edilmez.

Recommendation policy tek bir TR sırası değildir. Ranking anahtarı country + calculation
profile + factor family'dir: TR için ETKB, US için EPA, GB için DEFRA gibi declarative national
authority override'ları vardır. Override tanımlanmamış ISO ülkelerinde exact-country → regional
→ global generic sırası çalışır. Foreign-country proxy yalnız `accept_proxy=true` ile döner.
Serving metadata `atlas_factor_applicabilities` projection'ında tutulur; source factor satırları
policy rebuild sırasında değiştirilmez.

Scope 3 profili GHG Protocol kategori `1..15` sözleşmesini zorunlu kılar. Kategori, serbest metin
etiketi değil request, intent, applicability ve trace boyunca taşınan doğrulanmış bir alandır.
Strict mode kategoriyi her zaman ister; suggest mode yalnız family tek kategoriye gidiyorsa
varsayım yapar. Road freight için 4/9, waste için 5/12 ayrımı kullanıcıdan alınır; waste ayrıca
material+treatment, business travel ise haul qualifier'ı olmadan faktör seçmez. Çalışan ve eksik
kategori yolları `GET /v1/scope3/categories` üzerinden aynı versioned policy'den yayımlanır;
Scope 1/2 faktörleri Scope 3 gibi yeniden etiketlenmez.

Scope 1 yakıt aileleri benzin, motorin ve doğal gazı canonical concept üzerinden çok dilli
çözer. Örneğin `Gasoline`, `Petrol`, `Benzin`, `Essence`, `Gasolina`, `Бензин` ve `بنزين`
aynı `energy.gasoline` concept'ine gider; litre cinsinden GHG Protocol stationary motor-gasoline
factor'ı doğrudan hesaplanabilir. Aviation gasoline, biogasoline ve E85 aynı aileye sessizce
karıştırılmaz.

Intelligence completeness işlemleri idempotent CLI'larla da yürütülür:

```text
atlas-intelligence-rebuild
atlas-intelligence-translate
atlas-intelligence-check
atlas-recommendation-rebuild
atlas-recommendation-check
atlas-recommendation-ensure
```

`atlas-intelligence-check`, unit inventory, calculation-eligible unit, factor-concept ve
approved target-language coverage kapılarının tamamı geçmedikçe non-zero exit code döner.
Machine translation yalnız draft üretir; translation review endpoint'i reviewer, karar,
zaman ve not audit'ini saklar.

Canonical English curation ve TR → DE/FR/ES → RU/AR rollout'u contextual OpenAI translation
job'larıyla yürütülür. `gpt-5.6-terra` ana üretimi yapar; uyarı, tekrar veya unchanged-language
QA sinyali taşıyan kayıtlar `gpt-5.6-sol` ile yeniden değerlendirilir. Preferred term,
synonym ve abbreviation ayrı kayıtlar olarak saklanır. Reviewer Explorer Advanced Debug
içindeki Terminology panelinden taslağı düzenleyebilir, approve/reject edebilir, batch'i sync
edebilir ve glossary yönetebilir. Eski Argos kayıtları offline fallback taslağıdır ve insan
onayı olmadan runtime index'e girmez.

Search ve Recommendation aynı approved terminology havuzunu kullanan Unicode-safe resolver'a
bağlıdır. Resolver non-Latin sorguyu boş ASCII string'e çevirmeden script, dil, exact preferred,
alias, phrase-token, transliteration ve fuzzy kanallarını sıralar; tek genel ortak token concept
seçmek için yeterli değildir. Ambiguous strict recommendation sessiz seçim yerine `needs_input`
döndürür. Runtime aramada OpenAI çağrısı yapılmaz.

`GET /v1/factors` içindeki `geography` filtresi uygulanabilir coğrafyayı,
`origin_geography` ise factor kökenini filtreler. Bu iki anlam birbirinin yerine
kullanılmaz.

Factor history bitemporal tutulur. Varsayılan sorgu her reference-year/validity diliminin
current version'ını döndürür. Belirli bir tarihte Atlas'ın bildiği version için:

```http
GET /v1/factors?reference_year=2022&mode=as_known_at&known_at=2024-12-31T23:59:59Z
GET /v1/factors/{factor_id}?reference_year=2022&mode=current
```

`valid_from/valid_to` kaynak geçerliliğini, `effective_from/effective_to` Atlas system
history'sini temsil eder; historical revision eski version'ı overwrite etmez.
Recommendation serving aynı logical factor'ın yıllı sürümlerinden reporting year'e en yakınını
seçer; eşit uzaklıkta geçmiş yılı tercih eder. Kaynağın reference year yayınlamadığı metodoloji
default'ları yıllıkmış gibi etiketlenmez ve Explorer'da açıkça `UNDATED` görünür.

`country` filtresi Geography Coverage Engine üzerinden country-specific, modelled,
regional, continental, global ve onaylı proxy adaylarını kapsar. Exact olmayan match
sonucu `fallback_used=true`, geographic fit skoru ve açık warning döndürür. Fit skorları
`atlas/geography/defaults.yaml` üzerinden versiyonlu olarak yönetilir.

Admin endpoint'leri `X-Atlas-Admin-Key` header'ı ister. Yerel varsayılan yalnız
geliştirme içindir; local dışındaki ortamlarda `ATLAS_ADMIN_API_KEY` zorunludur.

Detaylı plan için [docs/roadmap.md](docs/roadmap.md), sınırlar için
[docs/non-negotiables.md](docs/non-negotiables.md) ve ürün çağrı sözleşmeleri için
[docs/product-integration.md](docs/product-integration.md) kullanılır; mimari ayrıntılar
[docs/architecture.md](docs/architecture.md) dosyasındadır.
