# NetZero Atlas agent çalışma sözleşmesi

## Ürün rolü

- NetZero Atlas, `moduler_netzero` platformunun çevresel veri tedarik ve hazırlama
  bileşenidir; bağımsız bir emisyon ürünü veya tenant uygulaması değildir.
- Atlas'ın görevi kaynak keşfi, fetch, immutable raw saklama, parse, normalize,
  canonical kavramlara eşleme, kalite/lisans doğrulama, sürüm karşılaştırma ve
  review'a hazır candidate dataset üretmektir.
- Canonical emisyon katalogları, birimler, formüller, belirsizlik kuralları ve
  publish kayıtlarının sahibi `cleture-netzero-admin` merkezi veritabanıdır.
- Atlas çalışma sırasında `moduler_netzero` merkezi DB'sini kullanmaz. Kendi
  çalışma DB'si ve object storage alanı yalnız ingestion run, raw asset, parsed
  observation, mapping kararı, validation sonucu ve candidate package için kullanılır.
- Atlas hiçbir tenant DB'ye bağlanmaz, tenant girdisi veya production hesap sonucu
  yazmaz ve tenant credential'ı taşımaz.

## Hafıza

- Nontrivial bir işe başlamadan önce `project=cleture-netzero-atlas`, en fazla 5 sonuç,
  narrative format ve en fazla 800 token ile tek bir `memory_recall` yap.
- Yalnızca kalıcı kararları, kolay türetilemeyen kısıtları ve çözülmüş gotcha'ları
  nedeni ve ilgili dosyalarıyla kaydet.
- Secret, kişisel veri, rutin anlatım ve geçici görev durumu kaydetme.
- Proje dışı hafıza araması ancak kullanıcı açıkça isterse yapılır.

## Codebase Memory

- Yapısal keşifte sıralama: `search_graph`, `trace_path`, `get_code_snippet`,
  `check_index_coverage`, gerektiğinde `query_graph` ve `get_architecture`.
- Her oturum başında proje ve index neslini doğrula.
- Varsayılan kanıt seviyesi Verify (Tier 2). Negatif veya exhaustive iddialarda
  kapsam coverage kontrolü ve raporlanan eksik aralıklarda doğrudan kaynak okuması yap.
- Büyük kod değişikliklerinden sonra index'in watcher tarafından yenilendiğini doğrula;
  gerekiyorsa açıkça re-index et.

## Laravel çalışma ortamı

- Uygulama koduna başlamadan önce proje PHP/Composer sürümlerini doğrula ve kurulu
  Laravel sürümüne uygun API kullan.
- Laravel Boost kurulmamışsa application değişikliğinden önce dev dependency olarak
  kur ve `boost:install` çalıştır. Üretilen framework yönergeleri bu ürün sözleşmesiyle
  birleştirilir; bu dosyadaki mimari ve veri sahipliği kararları ezilmez.
- Laravel kodu yazma, review veya refactor işlerinde repository'deki
  `laravel-best-practices` skill'i ve ilgili rule dosyaları uygulanır.
- Önce dar testler, ardından ilgili format/static analysis ve gerekli entegrasyon
  testleri çalıştırılır; yalnız mock/fake kanıtıyla external adapter tamamlanmış sayılmaz.

## Mimari sınırlar

- Hedef uygulama Laravel tabanlıdır. Domain kuralları `app/Domain` altında framework,
  Eloquent, HTTP client, queue ve source formatlarından bağımsız kalır; use-case
  orkestrasyonu `app/Application`, dış dünya adapter'ları `app/Infrastructure` altında
  tutulur.
- Orchestrator kaynak formatını bilmez; yalnızca adapter sözleşmesini yürütür.
- Raw nesneler immutable ve content-addressed saklanır.
- Pipeline sırası v1'de sabittir; genel amaçlı DAG engine eklenmez.
- Atlas canonical emisyon tablolarına doğrudan `INSERT`/`UPDATE` yapmaz. Hazır
  candidate dataset'i sürümlü manifest ve immutable paket olarak internal API/object
  storage sözleşmesiyle NetZeroAdmin ingestion sınırına teslim eder.
- Candidate manifest en az `schema_version`, source/release kimliği, paket URI'si,
  SHA-256, kayıt sayısı ve idempotency key taşır. Büyük dataset satır satır API ile
  gönderilmez; paket halinde staging/bulk import edilir.
- Candidate kabulü canonical publish değildir. NetZeroAdmin paketi doğrular,
  candidate/staging alana alır, önceki release ile diff üretir ve insan review'ına sunar.
- Publish yalnız NetZeroAdmin tarafından quality, lisans ve insan review kapılarından
  sonra yapılır. Kullanıcı ve calculation worker yalnız published, immutable ve
  açıkça sürümlenmiş calculation bundle tüketir.
- Validation hatası olan, coğrafyası eşlenemeyen, birimi/formülü geçersiz veya
  provenance'ı eksik aday publish edilemez; önce düzeltilir ya da reddedilir.
- Her source/faz tamamlandığında README, roadmap ve ilgili ADR/envanter tabloları önce
  güncellenir; doğrulamalar geçtikten sonra kullanıcı onayı beklenmeden değişiklikler
  commit edilir ve mevcut branch origin'e push edilir.
- Source'a özel kod `app/Infrastructure/Sources/<code>` altında kalır; domain veya
  orchestrator içine kaynak adıyla branch eklenmez.

## Sistem sınırları

- `cleture-netzero-admin` control plane'dir: canonical katalog ve migration sahibi,
  candidate inceleme/diff, birim-formül-belirsizlik yönetimi, review ve publish burada
  bulunur. Ağır source parse veya tenant hesaplama web request'i içinde çalışmaz.
- `Logi` ülke/il/ilçe ve kara-hava-deniz route/mesafe bilgisinin canonical sahibidir.
  Atlas yalnız kaynak coğrafyasını canonical Logi kimliğine eşlemek için Logi'yi
  kullanabilir; kullanıcı route hesabı ve route-point saklama Atlas'a eklenmez.
- Production tenant hesabının execution ve persistence sahibi calculation worker'dır.
  Worker published calculation bundle'ı kullanır ve sonuç ile immutable snapshot'ı
  yalnız ilgili tenant DB'ye yazar.
- Atlas candidate doğrulaması için aynı calculation contract'ına karşı fixture/golden
  test çalıştırabilir fakat ikinci bir production hesap motoru oluşturmaz.
- Frontend birim dönüşümü veya emisyon sonucunu kullanıcı deneyimi için önizleyebilir.
  Bu sonuç non-authoritative'dir, backend'e geri dönmesi zorunlu değildir ve rapor,
  doğrulama veya canonical toplam için kullanılmaz.
- API/Excel entegrasyonları frontend preview akışına bağımlı değildir. Backend request
  sınırı published factor erişimini, zorunlu parametreleri ve unit dimension
  uyumluluğunu doğrular; authoritative hesap gerekiyorsa idempotent worker task'ı üretir.

## Birim, formül ve belirsizlik sözleşmesi

- `UnitType` platform genelinde ortak merkezi referanstır; emisyon, su, CBAM, enerji ve
  diğer modüller aynı canonical unit kimliklerini kullanır. Modüle özel kullanım
  boolean kolonlarla değil ilişki/policy kayıtlarıyla modellenir.
- Birim yalnız label/code değildir; dimension, base unit, exact scale ve gerekiyorsa
  offset semantiği taşır. Bileşik faktör birimleri (`kgCO2e/kWh`, `kgCO2e/t.km`) dimension
  kontrolünden geçer.
- Hesap ve canonical dönüşüm binary float ile yapılmaz; decimal string/NUMERIC ve açık
  rounding politikası kullanılır. Dönüşüm bulunamaz veya dimension uyumsuzsa değer
  değiştirilmeden devam edilmez, işlem fail-closed olur.
- Kullanıcının original value/unit girdisi korunur; normalized value/unit ve kullanılan
  unit-definition sürümü hesap snapshot'ında ayrıca tutulur.
- Formüller serbest PHP/SQL/JavaScript veya `eval` edilecek metin değildir. İzin verilen
  operatörlere sahip typed AST/DSL olarak sürümlenir, publish öncesi parametre ve unit
  type-check yapılır. Yayınlanan formül değiştirilmez; değişiklik yeni sürüm üretir.
- Formül değerlendirme hatası emisyonu `0` yapmaz. `0` yalnız başarılı matematiksel
  sonucun gerçekten sıfır olması halinde yazılabilir.
- Belirsizlik activity input, factor ve resolver/model belirsizliği olarak ayrı
  provenance taşır. Kurallar input method, data source/quality, factor source,
  taxonomy, geography ve validity bağlamına göre sürümlü çözülür.
- Uygun belirsizlik kuralı yoksa sessiz `0` veya `1` varsayılmaz; sonuç `unknown`,
  warning ya da metodolojinin belirlediği blocking durum olur.

## Calculation bundle ve snapshot

- NetZeroAdmin publish aşamasında factor, formula, GWP, unit ve uncertainty rule
  sürümlerini immutable bir `calculation_bundle` altında sabitler ve hash'ler.
- Calculation task oluşturulurken bundle sürümü pin edilir; kuyruk beklerken yeni
  release yayınlansa bile task'ın hesap semantiği değişmez.
- Tenant snapshot en az original/resolved inputs, factor/formula/unit/uncertainty
  sürümleri, calculation bundle ve engine sürümü, Logi route kanıtı, ara adımlar, gaz
  sonuçları, toplam ve hesap zamanını taşır.
- Aynı input ve aynı bundle/engine sürümü deterministik olarak aynı sonucu üretmelidir.

## Bulk ve entegrasyon davranışı

- Büyük Excel/API akışları web request'i içinde parse veya calculate edilmez. Dosya
  object storage'a alınır; import batch, chunk validation ve calculation task'larıyla
  yürütülür.
- Interactive ve bulk calculation kuyrukları ayrılır; bir tenant'ın büyük import'u
  diğer tenant'ların interaktif işlerini bloke edemez. Tenant bazlı rate limit,
  concurrency ve backpressure uygulanır.
- Queue teslimatı at-least-once kabul edilir. Import ve calculation yazıları DB unique
  constraint/idempotency key ile tekrar çalıştırılabilir olur; yalnız queue uniqueness'e
  güvenilmez.
- Geçici network/rate-limit hataları kontrollü backoff ile retry edilir; validation,
  lisans, mapping veya dimension hataları kalıcı hata olarak retry edilmez.
