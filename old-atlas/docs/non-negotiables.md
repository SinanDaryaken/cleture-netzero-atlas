# Cleture Atlas — Olmazsa Olmazlar

Bu sözleşmeler source adapter, canonical model, matching ve public API katmanlarında
korunur. Bir kaynak bunları açıkça sağlayamıyorsa değer tahmin edilmez; kayıt review
kuyruğuna alınır.

## Coğrafi köken ve uygulanabilirlik farklı kavramlardır

“Türkiye faktörleri” ile “Türkiye'de kullanılabilir faktörler” aynı küme değildir.
Bir factor'ın `TR` aramasında aday olması, Türkiye tarafından üretilmiş veya Türkiye'ye
özgü olduğu anlamına gelmez.

Her canonical factor aşağıdaki alanları ayrı taşır:

```text
origin_geography
applicable_geographies[]
geography_roles[]:
  role
  geography
  derivation
  source_field
  rule_version
  confidence
geography_level
geographic_specificity
geographic_fit_type:
  - country_specific
  - country_modelled
  - regional
  - continental
  - global
  - proxy
```

- `origin_geography`: factor'ın temsil ettiği veya source tarafından üretildiği
  coğrafya. Publisher'ın merkez adresi otomatik olarak origin sayılmaz.
- `applicable_geographies`: source metadata, metodoloji veya onaylanmış mapping ile
  factor'ın kullanılabildiği coğrafyalar.
- `geography_level`: factor'ın en spesifik applicability seviyesi.
- `geographic_specificity`: global=0 ile grid=6 arasındaki deterministik ayrıntı seviyesi.
- `geographic_fit_type`: applicability ilişkisinin niteliği. `proxy`, gerçek yerel veri
  yerine kullanılan ikame faktörü açıkça işaretler.
- `geography_roles`: coğrafyanın semantik görevini source field/rule provenance'iyle taşır.
  Market, production origin değildir; bilinmeyen origin `GLOBAL` olarak doldurulmaz.

Zorunlu kurallar:

1. Source country ile applicable country birbirinden türetilmez.
2. `GLOBAL`, “her ülkede yerel faktördür” anlamına gelmez.
3. Ülke araması sonuçları en az `country_specific`, `regional`, `global` ve `proxy`
   kırılımında raporlanabilir olmalıdır.
4. Matching önceliği varsayılan olarak country-specific → regional → global → proxy
   sırasını izler; metodoloji ve müşteri politikası bu sırayı açıkça değiştirebilir.
5. Geography mapping'leri versiyonlanır ve provenance içinde hangi mapping'in
   kullanıldığı tutulur.
6. Origin veya applicability bilinmiyorsa sistem değer uydurmaz. Source'un açıkça market
   veya applicability bildirdiği kayıt, bilinmeyen origin'i koruyarak publish edilebilir.
7. Matching sırası exact geography → country-specific → country-modelled → regional
   → continental → global → proxy olarak uygulanır.
8. Exact olmayan seçim açık `fallback_used` ve warning üretir.
9. Geographic fit skorları kod içinde sabitlenmez; versiyonlu Atlas geography
   configuration üzerinden yönetilir.
10. Ülke kimliği merkezî `atlas_countries.code` ISO alpha-2 değeridir. Çok dilli adlar,
    alpha-3 ve yaygın adlar kimlik yerine geçmez; approved `atlas_country_labels` üzerinden
    aynı koda çözülür.

## Factor kimliği ve varyantlar

Tek activity tek factor olmak zorunda değildir. Year, lifecycle boundary, methodology,
gas breakdown, unit ve source farklılıkları ayrı factor version veya varyantları
oluşturabilir. Sayımlar activity, logical factor, factor version ve applicability
boyutları belirtilmeden sunulmaz.

## Factor değeri ve kullanım amacı ayrı kavramlardır

Her sayısal kayıt doğrudan “toplam envanter CO2e faktörü” değildir. Canonical factor
aşağıdaki iki alanı zorunlu taşır:

```text
factor_value_kind:
  - co2e_total
  - co2_only
  - non_co2_co2e
  - gas_emission_factor
  - calculation_parameter
  - characterization_factor

intended_use:
  - inventory
  - calculation_input
  - avoided_emissions
  - characterization
```

Zorunlu kurallar:

1. Varsayılan factor matching yalnız `co2e_total + inventory` kayıtlarını aday alır.
2. CO2-only ve non-CO2 kayıtlar toplam CO2e gibi etiketlenmez veya sessizce birleştirilmez.
3. Avoided-emissions faktörleri inventory hesabında kullanılmaz.
4. GWP gibi characterization factor'ları aktivite emisyon faktörü değildir.
5. Farklı kullanım türleri aynı public listede bulunabilir; API tür ve amaç filtresi sunar.
6. Kaynak değerin türü açık değilse tahmin edilmez ve kayıt review'a alınır.
7. IPCC gibi çok-parametreli modellerde NCV, oxidation factor veya methane correction
   factor doğrudan CO2e faktörü gibi eşleştirilmez; `calculation_parameter +
   calculation_input` olarak denklem ve worksheet bağlamıyla saklanır.
8. Kaynak satırında serbest metin coğrafi koşul varsa bu değer otomatik global yapılmaz;
   onaylı geography mapping olmadan public coverage'a dahil edilmez.
9. `commercial_use` veya `api_distribution` açıkça onaylı değilse dataset otomatik
   publish edilemez ve review queue'da lisans sebebi üretir.
10. Negatif kaynak değerleri otomatik invalid sayılmaz; avoided-emissions veya carbon
    removal anlamı source metadata ile doğrulanır, açık intended-use taşır ve inventory
    matching'e girmez.
11. Source içindeki `valid`/`archived` statüsü Atlas dataset publication statüsünden
    ayrıdır. Archived satır raw/parsed history'de korunur; valid → archived geçişi factor
    history'de overwrite değil removal/version change olarak karşılaştırılır.
12. Yıllar arasında source schema değişirse parser kolonları pozisyona göre tahmin etmez.
    Exact schema validation fail eder; yeni parser version ve snapshot testiyle bilinçli
    reprocessing yapılır.
13. Elektrik residual mix yalnız tracking attribute kullanılmayan tüketim için seçilir;
    production mix, supplier mix ve residual mix birbirinin yerine kullanılmaz.
14. Kaynak doğrudan CO₂ yayımlıyorsa lifecycle veya toplam CO₂e kapsamı varsayılmaz.
    Supporting fuel-share ve radioactive-waste değerleri ayrı emission factor yapılmaz.

## Temporal ve bitemporal history

1. Yıllar kolonlara açılmaz; her annual release ayrı dataset version, her değer ayrı
   factor version olur.
2. `reference_year`, source `published_at`, `valid_from/valid_to` ve Atlas `retrieved_at`
   birbirinin yerine kullanılmaz.
3. Business validity (`valid_*`) ile system validity (`effective_*`) ayrı tutulur;
   bitiş sınırları exclusive kabul edilir.
4. Historical revision eski kaydı overwrite etmez. Eski version `superseded` olarak
   kapanır ve yeni version `supersedes_version_id` ile ona bağlanır.
5. Farklı reference year kayıtları aynı logical entity altında birlikte current olabilir;
   yalnız aynı temporal dilimin revision'ları birbirini supersede eder.
6. Atlas hem current truth hem de `known_at` ile as-known-at sorgusu sunmadan historical
   backfill tamamlanmış sayılmaz.
7. Kaynağın yayın modeli manifestte açıkça `yearly_release`,
   `lagged_yearly_release` veya `versioned_database` olarak tanımlanır. Yaşayan
   veritabanları için sentetik yıllık dataset oluşturulmaz.
8. Publication year ile reference year aynı kabul edilmez. Özellikle AIB gibi gecikmeli
   yayınlarda lag metadata'dır; factor'ın temsil ettiği yıl `reference_year` olarak
   korunur.
9. Historical ingestion kaynak için tercih edilen resmî makine-okunur asset'i kullanır;
   DEFRA'da flat file, EPA ve AIB'de mevcutsa Excel önceliklidir.
10. Annual source schema'sı yıllar boyunca sabit varsayılmaz. Manifest her reference year'i
    tam bir schema family'ye bağlar; kullanılan parser version dataset ve provenance'a
    kaydedilir.
11. Release-specific quality baseline olmadan farklı yıllar aynı row/table sayısıyla
    doğrulanmaz. Eski yılın doğal satır sayısı güncel yıl beklentisine göre anomaly sayılmaz.
12. Publisher'ın vermediği source ID, gerçek publisher ID gibi gösterilmez. Deterministik
    processing kimliği açıkça sentetik tutulur; qualifier değerler (`< 1`, `NA`) sıfıra
    çevrilmez.
13. Change detection source revision ile birlikte parser ve mapping sürümünü dikkate alır.
    Aynı immutable raw asset yeni processing sürümüyle yeniden işlenebilir.

## Environmental entity semantics

1. Her numeric source row `emission_factor` değildir. Atlas en az emission factor,
   implied emission factor, activity data, emission result, calculation parameter,
   reference value, LCA result, characterization result, EPD, conversion factor,
   technical property ve embodied-emission factor tiplerini ayırır.
2. Yalnız match-eligible emission/implied-emission factor kayıtları varsayılan factor
   matching'e girer; activity data, calculation parameter ve technical property girmez.
3. API time-series, yearly national submission, versioned database ve derived-data release
   aynı temporal model değildir. Publisher annual release üretmiyorsa sentetik yıl
   snapshot'ı oluşturulmaz.
4. Derived source, underlying publisher'ı sahiplenemez. `original_source` ve `derived_by`
   provenance boyunca ayrı korunur.

## Multi-asset raw releases

1. Bir dataset release birden fazla publisher dosyasından oluşuyorsa hiçbir member
   sessizce atlanmaz veya parse öncesi yeniden yazılmaz.
2. Tek raw-object sınırı gereken durumda deterministic acquisition bundle kullanılabilir;
   her original member byte-for-byte korunur ve URL, size, SHA256, role metadata'sı taşır.
3. Bundle provenance publisher ZIP'i gibi gösterilmez. Factor provenance bundle raw
   asset'ine bağlanırken original member filename, URL ve member checksum'unu ayrıca tutar.
4. Public result workbook lisansı, restricted background inventory lisansı anlamına
   gelmez. Örneğin AGRIBALYSE public sonuçları ingest edilir; ecoinvent LCI verisi ayrıca
   lisans olmadan ingest edilmez.

## National inventory submission time

1. UNFCCC submission yılı ile member workbook'un inventory `reference_year` değeri
   aynı alan değildir.
2. Sonraki submission geçmiş inventory yılını revize ederse eski factor version
   overwrite edilmez; system-time zincirinde supersede edilir.
3. CRF ve CRT schema family'leri aynı parser varsayımına zorlanmaz.
4. `started`, `awaiting_submission` ve benzeri source statüleri provenance'da korunur;
   insan onayı source statüsünü `submitted` diye yeniden yazmaz.
5. Historical submission'lar eskiden yeniye publish edilir. Aksi sıra, eski bir
   submission'ın daha yeni historical revision'ı current katmanda ezmesine yol açar.

## Observation count is not factor count

1. Raw/parsed observation, logical entity, temporal version ve curated emission factor
   sayıları ayrı metriklerdir; birbirinin yerine raporlanmaz.
2. `ACTIVITY_DATA` ve `EMISSION_RESULT` kayıtları factor API sayısına dahil edilmez.
3. `IMPLIED_EMISSION_FACTOR` source observation'ları unit/gas/boundary/category
   kurallarından geçmeden match-eligible factor olmaz.
4. Bir source'un tüm historical submission ve reference-year version'larının toplamı,
   kullanıcıya sunulan güncel factor sayısı olarak gösterilmez.
5. Coverage ve README metrikleri en az `observations`, `logical_entities`,
   `temporal_versions` ve `curated_factors` ayrımını açıkça belirtir.
6. Source-native numeric kayıtlar `atlas_source_observations` içinde dataset version ve
   raw asset provenance ile saklanır. Bu tablo public factor kataloğu değildir.
7. `atlas_factors` yalnız logical curated factor kimliği, `atlas_factor_versions` ise
   business/system-time değer tarihçesi taşır. Observation satırı burada yalnız açık,
   deterministik curation sözleşmesini tamamladıysa yer alabilir.
8. Curation sırasında kaynak unit, gas veya denominator belirsizse hedef sayıya ulaşmak
   için tahmin yapılmaz. Observation korunur, factor üretilmez ve exclusion metriği yazılır.

## Unit intelligence ve dönüşüm güvenliği

1. Unit dönüşümü çıplak `from/to/multiplier` tablosu değildir; canonical code, dimension,
   scale, offset, qualifier ve registry version taşır.
2. Activity quantity conversion ile factor denominator conversion ayrı işlemlerdir.
   `0.5 kgCO2e/kWh = 500 kgCO2e/MWh` reciprocal kuralı regression testidir.
3. Her dönüşüm `exact_conversion`, `conditional_conversion` veya `incompatible` olur.
4. Density, calorific value, load, occupancy veya exchange rate olmadan farklı dimension
   family'leri arasında değer üretilmez. Parametre source ve validity taşır.
5. Aynı fiziksel dimension farklı semantic qualifier anlamına gelmez. Net/gross CV,
   currency-year, product-specific mass ve transport-work qualifier'ları korunur.
6. UCUM referanstır; Atlas canonical code otoritedir. UCUM karşılığı olmayan domain unit'e
   sahte UCUM code atanmaz.
7. Original unit string overwrite edilmez. Parsed expression ayrı versioned tabloda tutulur.
8. İstenen activity unit'i parse edilemeyen veya incompatible olan factor strict resolve'a
   giremez.
9. Factor, activity ve source-observation katmanlarındaki her distinct raw unit expression
   versioned mapping tablosunda `mapped`, `dimensionless`, `ratio`, `index`,
   `calculation_parameter`, `source_unspecified` veya `source_native` disposition'larından
   tam birini taşır; sessiz `unparsed` boşluğu bırakılamaz.
10. `source_native` bir ifadenin canonical olarak dönüştürülebilir olduğu anlamına gelmez.
    Calculation-eligible factor havuzundaki her unit expression canonical `mapped` olmak
    zorundadır.

## Intelligence-first source freeze

1. `ATLAS_SOURCE_INGESTION_ENABLED` varsayılan olarak `false` kalır.
2. Freeze açıkken admin API, scheduler ve worker birlikte yeni source verisinin havuza
   girmesini engeller; yalnız UI seviyesinde gizlemek yeterli değildir.
3. Source ingestion ancak açık yönetişim kararı, güncellenmiş roadmap ve ilgili validation
   kapsamıyla yeniden açılabilir.
4. Mevcut raw/provenance/version geçmişi silinmez veya yeniden yazılmaz.

## Çok dilli concept ve search sözleşmesi

1. Translation factor/source text'in üzerine yazılmaz; `atlas_concept_labels` içinde
   canonical concept'e bağlanır.
2. Translation ve synonym ayrı `label_kind`; method, model, confidence, review status ve
   registry version alanlarıyla saklanır.
3. Machine translation draft'tır. Unreviewed label tek başına calculation resolve kararı
   oluşturamaz.
4. Domain synonym registry Atlas asset'idir; aynı concept her factor satırı için yeniden
   çevrilmez.
5. İlk production search PostgreSQL FTS + `pg_trgm` kullanır. OpenSearch/vector altyapısı
   benchmark ile gerekçelendirilmeden zorunlu dependency olamaz.
6. Her logical factor approved bir canonical concept mapping taşımadan intelligence
   altyapısı complete sayılmaz.
7. Hedef diller `en`, `tr`, `de`, `fr`, `es`, `ru`, `ar`'dır. Her canonical concept için
   her hedef dilde approved translation bulunmadan multilingual completeness geçmez.
8. Machine-generated draft'ın varlığı approved coverage değildir; bulk otomatik approval
   yasaktır. Review kararı reviewer, timestamp ve gerekçe/not audit'i taşır.
9. Unit, concept ve approved translation kapılarının birleşik sonucu `ready=true` olmadan
   NetZero dahil ürün entegrasyonlarına geçilemez.

## Calculation context ve profile policy

1. Atlas tek API sunar fakat tek, bağlamsız factor havuzu sunmaz.
2. `/v1/search` context; `/v1/match` ve `/v1/resolve` versioned calculation profile ister.
3. Search eligibility ile calculation eligibility farklı kararlardır. Metinsel eşleşme
   calculation kullanım izni anlamına gelmez.
4. Corporate carbon, LCA/PCF, CBAM ve freight entity family'leri profile allow-list olmadan
   birbirine karıştırılmaz.
5. Resolve yalnız published, quality/license kapılarından geçen, unit-compatible ve profile
   eligible kayıt döndürür; uygun aday yoksa `no_calculation_eligible_candidate` üretir.
6. Ranking deterministik, açıklanabilir ve policy/registry version'lıdır. Confidence skoru
   eligibility'nin yerine geçmez; LLM doğrudan factor seçemez.
7. Scope profile'larında factor methodology scope'u profile ile aynı olmak zorundadır;
   scope'u eksik kayıt `scope_unknown`, farklı kayıt `scope_denied` ile calculation dışı
   kalır.
