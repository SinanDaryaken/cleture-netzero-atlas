# Atlas product integration contract

NetZero dahil hiçbir consumer bu sözleşmeye, Atlas intelligence completeness endpoint'i
`ready=true` dönmeden bağlanamaz. Readiness; tüm raw unit ifadelerinin açık disposition
almasını, calculation-eligible unit'lerin canonical mapped olmasını, tüm factor'ların
approved concept mapping taşımasını ve `en/tr/de/fr/es/ru/ar` label coverage'ının approved
olmasını birlikte gerektirir. Draft translation coverage bu önkoşulu karşılamaz.

Atlas consumers never read the complete factor pool and select a calculation record on
their own. Every product owns a fixed calculation profile and uses
`POST /v1/recommendations`. `/v1/search` is catalog/developer discovery; it is not a product
calculation decision.

| Product capability | Profile | Endpoint |
|---|---|---|
| Corporate Scope 1 | `corporate_carbon.ghg_protocol.scope1` | `POST /v1/recommendations` |
| Scope 2 location | `corporate_carbon.ghg_protocol.scope2_location` | `POST /v1/recommendations` |
| Scope 3 | `corporate_carbon.ghg_protocol.scope3` | `POST /v1/recommendations` |
| LCA | `lca.iso14040` | `POST /v1/recommendations` |
| PCF | `pcf.iso14067` | `POST /v1/recommendations` |
| CBAM | `cbam.eu_definitive` | `POST /v1/recommendations` |
| Freight | `freight.glec` | `POST /v1/recommendations` |

Example strict request:

```json
{
  "mode": "strict",
  "context": "corporate_carbon",
  "year": 2025,
  "calculation_profile": "corporate_carbon.ghg_protocol.scope1",
  "facility_context": {"facility_id": "FAC-001", "country": "TR"},
  "activity": {"text": "natural gas", "quantity": 100, "unit": "m3"},
  "accept_proxy": false
}
```

Consumers persist the returned factor/version identity, policy version, unit conversion
status, geographic tier, ordered rank dimensions, assumptions and calculation trace.
`conversion_parameter_required` and `needs_input` stop calculation. A foreign-country factor
is returned only after `accept_proxy=true`; that acceptance is part of the audit.

`facility_id` verilmişse Atlas kaydı `/v1/facilities` registry'sinden çözer ve request country
ile uyuşmazlığı reddeder. Conditional conversion için request'te açık parametre yoksa yalnız
`approved`, aktif ve hesap tarihine uygun `/v1/conversion-parameters` kayıtları kullanılabilir;
facility kaydı country ve global kayıtlardan önce gelir. Draft/rejected parametre hesaplamaya
giremez.

`GET /health` yalnız process liveness'tır. Product deployment kapısı `GET /ready` veya
`atlas-readiness-check` olmalıdır; intelligence, recommendation ve sector kapılarından herhangi
biri eksikse 503/non-zero döner.

Warm-cache local acceptance budgetleri `/v1/search` için p95 400 ms,
`/v1/recommendations` için 750 ms ve `/v1/convert` için 50 ms'dir. Product endpoint'i katalog
taramak yerine family-scoped serving projection'ı okur.

## Explorer & Test Lab

`GET /explorer` production consumer değildir; yukarıdaki public contract'ları aynı origin'de
çalıştıran developer test surface'idir. Calculate içinde önce context-aware factor bulunup
seçilir; activity formu ancak `/v1/explorer/compatibility` factor paydasına göre desteklenen
unit'leri döndürdükten sonra açılır. Search formundaki ilk unit seçenekleri `/v1/units`
registry'sinden tek seferde yüklenir ve dimension'a göre gruplanır. Profile/context/facility/query
değişimleri unit selector'ını yeniden yaratmaz. `/v1/explorer/calculate` normalization ve final sonucu
server-side üretir. Conditional conversion response'u required parameter döndürdüğünde,
uyumlu parameter unit'i ve provenance sağlanana kadar calculation/result bloke kalır; bu eksik
parameter factor'ın recommendation adaylığını bloke etmez. Hard-deny context, activity ve
incompatible-unit kayıtları Advanced Debug dahil factor listesinde gösterilmez. Published
catalog için Search runtime'ında ayrıca license eligibility kırılımı uygulanmaz.
`passenger` girdisi `passenger.km` denominator'ına distance parametresiyle normalize edilir;
GB / Scope 3 / DEFRA domestic-flight senaryosunda `2 passenger` tek başına hesaplanmaz, mesafe
verildiğinde hesaplanır. TR gibi farklı geography'de GB faktörü explicit proxy olmadan aday olmaz.
Compare'ın context, geography ve unit lens'leri `/v1/explorer/compare`; canonical 68 case ise
`/v1/explorer/regression/run` üzerinden yürür ve her koşu kalıcı bir `run_id` üretir.
`/v1/explorer/regression/runs` geçmişi, run detail sonuçları; admin approve/reject endpoint'i
review audit'ini verir. Explorer'ın 20 başlangıç facility kaydı `/v1/facilities` üzerinden gelir;
country override seçenekleri `/v1/countries` ISO registry'sinden yüklenir. Facility/country,
context ve profile ilgili bütün test isteklerinde açıkça taşınır. Recommendation geography filtresi
repository aday havuzunu requested country + izinli fallback kapsamına indirir; UI normal
modda yalnız calculation-eligible sonuçları gösterir.

Suite'in 40 baseline vakası 20 facility'nin her biri için `100 m3 Natural gas` Scope 1 ve
`100 kWh Electricity` Scope 2 location isteğini gerçek recommendation endpoint'i üzerinden
çalıştırır. Doğal gazda yalnız facility ülkesi veya `GLOBAL` sabit yanma fallback'i; elektrikte
yalnız exact facility-country factor kabul edilir. Her vakada scope, hesaplanmış `kgCO2e` sonucu
ve güvenli coğrafya birlikte doğrulanır.

## Scope 3 category contract

Scope 3 recommendation istekleri `activity.scope3_category` alanında GHG Protocol kategori
numarasını (`1..15`) taşır. `GET /v1/scope3/categories` her kategorinin upstream/downstream
yönünü, yöntemlerini, zorunlu girdilerini, mevcut coverage durumunu ve desteklenen factor
family'lerini döndürür. Aynı katalog Scope 3 profile rules response'una da eklenir.

Strict mod kategoriyi her zaman ister. Suggest mod yalnız family tek bir kategoriye gidiyorsa
kategoriyi açık assumption ile çıkarır. Freight için kategori 4/9, waste için 5/12 ayrımı
kullanıcıdan gelmeden seçim yapılmaz. Explicit kategori ile activity family uyuşmazsa ranking
başlamadan `family_category_mismatch` üretilir. Scope 1 combustion veya Scope 2 generation
factor'ları Scope 3 diye yeniden etiketlenmez; kategori 3 yalnız published/projected Scope 3 WTT
factor'larını kabul eder. Unsupported kategoriler `/v1/scope3/categories` içinde açık coverage
gap olarak görünür.

Kategori 5 ve 12 için waste material ile treatment, kategori 6 için travel distance class
zorunlu structured qualifier'dır. Bu alanlar eksikken Atlas rastgele bir material veya haul
factor'ı seçmez; `needs_input` döndürür. Explorer ilgili kategori seçildiğinde bu girdileri açar.

Canonical suite'in ek Scope 3 vakaları kategori kataloğunu, 1/3/4/5/6/9/12 çalışan yollarını,
freight direction belirsizliğini ve kategori 15 coverage gap'ini gerçek recommendation
projection'ında doğrular.

Canonical suite server-owned, versioned ve CI tarafından çalıştırılır. Lisanslı source snapshot
testleri `config/official-snapshots.yaml` manifesti ve `atlas-official-snapshots-check` ile ayrı
self-hosted CI kapısında doğrulanır; artifact'ler Git'e veya public runner'a kopyalanmaz.
