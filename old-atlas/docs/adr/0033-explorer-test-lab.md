# ADR 0033 — Explorer & Test Lab API orchestration boundary

## Durum

Kabul edildi — 2026-08-28.

## Bağlam

Atlas'ın search, profile-gated factor matching, strict resolve, unit conversion ve
Explorer-scoped final calculation yüzeyleri mevcuttur. Geliştiricilerin facility, context,
activity, factor, conversion ve result zincirini tek yerde çalıştırıp kararları incelemesi
gerekir. Backend henüz first-class facility resolution ve saved regression case
persistence'a sahip değildir.

## Karar

Explorer, `GET /explorer` altında FastAPI ile birlikte sunulan zero-build bir developer UI
olacaktır. İlk çalışma yüzeyi tab navigasyonu kullanmaz: global facility/context/profile
çubuğunun altında 25/25/50 oranında activity input, dikey search sonuçları ve iki kolonlu
seçili factor detayı bulunur. Arayüz bu aşamada public `/v1/search` ile Explorer-scoped
`/v1/explorer/compatibility` ve `/v1/explorer/calculate` contract'larını çağırır;
domain/repository katmanına doğrudan erişmez ve core calculation mantığını kopyalamaz.
Match/Resolve/Compare/regression endpoint'leri backend contract olarak korunur fakat bu ilk
sadeleştirilmiş Explorer yüzeyine bağlanmaz.

Facility ID → geography mapping halen açık client orchestration step'idir. Explorer bu sınırı
dünya geneline dağılmış 20 demo facility ile görünür kılar; country override seçeneklerini
`/v1/countries` ISO registry'sinden dinamik yükler. Facility/country, context ve calculation
profile Search request'inin ortak eligibility sözleşmesidir. Kullanıcı Text/Quantity/Unit
girdisini verir; context-aware search sonucundan seçilen factor için compatibility server
tarafından üretilir ve normalized activity × factor sonucu `/v1/explorer/calculate` içinde
hesaplanıp detay kolonunda önizlenir. İlk Unit select hard-coded değildir; `/v1/units`
registry'sini başlangıçta bir kez yükler, bütün seçenekleri dimension'a göre gruplar ve mevcut
seçimi profile/context/facility/query değişimlerinde korur. Profile değişimi unit DOM'unu yeniden
kurmaz. Compatibility registry'si uzun bir unit chip listesi
olarak sunulmaz; kullanıcı seçili factor için input unit'i tek select'ten seçer. Direct
conversion anında çalışır, parameterized conversion gerekli parametre value/unit alanlarını
açar. Parameter eksikliği factor ranking'i reddetmez; seçim sonrası calculation response'u
required parameter ile bloke olur.
Conditional conversion, required parameter değeri, uyumlu unit'i ve source provenance'i
verilmeden sonuç üretmez. Reviewed parameter bulunmadığında default değer uydurulmaz.
Passenger count bir passenger-distance factor'ına doğrudan eşit sayılmaz. `passenger →
passenger.km` conditional yolu `distance` parametresi ve mesafe unit'i ister; örneğin iki
passenger ve 500 km, 1.000 passenger.km üretir.

Canonical multilingual/geography/context/unit senaryoları server runner ile yürütülür.
Foreign-country PCF/LCA kaydı ancak request'in açık proxy izni varsa calculation pool'a girer;
karar düşük geography score ve görünür warning taşır.

Search geography yalnız sonuç sunumunda filtrelenmez. Repository candidate query'si requested
country, versioned ancestor/proxy kodları ve global fallback ile sınırlandırılır; search engine
aynı uygunluğu yeniden değerlendirir ve exact country sonucunu fallback önünde sıralar. Normal
API/UI response hard-deny context/profile/activity/unit adaylarını içermez; Advanced Debug da
bu kayıtları seçilebilir factor listesine geri eklemez. Yayımlanmış katalog runtime Search'te
ayrı bir license kararına veya response alanına bölünmez; bu kapı publish öncesinde kalır.
Exact concept eşleşmesi lexical FTS'i short-circuit etmez; concept ilişkisi daha genel bir
üst kavrama bağlı factor'lar isim eşleşmesiyle aday havuzuna girmeye devam eder. Slash ve diğer
noktalama işaretleri FTS token separator'ı olarak normalize edilir. Resolve yalnız
calculation-eligible aday seçer; örneğin CBAM profile'ında inventory elektrik faktörü uygun
CBAM embodied factor yerine dönmez ve uygun aday yoksa `no_calculation_eligible_candidate`
üretir.

Reporting year, source'un bire bir release yılı olmak zorunda değildir. En fazla beş yıllık
gecikme taşıyan ve data quality'si açıkça `official annual` olan kayıt temporal olarak tam
uyumlu kabul edilir; modelled kaynaklar aynı istisnayı almaz. Böylece en güncel resmî ETKB
CO₂e tüketim değeri, daha yeni modelled ülke grid serisinden source authority nedeniyle önce
gelebilir; gecikme sınırı aşıldığında temporal ceza yeniden uygulanır.

Saved test case UI'si bu sadeleştirme aşamasında yüzeyden kaldırılmıştır. Paylaşılan regression
repository, review state'leri ve CI runner daha sonra ayrı bir versioned contract olarak ele
alınacaktır.

Source-faithful katalog incelemesi recommendation yüzeyinin bir modu değildir. Masthead'deki
ayrı `GET /explorer/catalog` ekranı public `GET /v1/factors` sözleşmesini source, scope ve text
filtreleriyle kullanır; yayımlanmış emission, implied-emission ve embodied-emission factor
türlerinin yanında publisher tarafından LCA sonucu olarak yayımlanmış `LCA_RESULT` kayıtlarını
da listeler. Bu ayrım source-faithful AGRIBALYSE, CONCITO, ÖKOBAUDAT, Plastics Europe,
Plastics Recyclers Europe ve WRAP içeriklerinin faktör kataloğunda görünmesini sağlar;
calculation parameter ve technical-property satırları kapsam dışıdır. Bu yüzey calculation
profile eligibility/ranking çalıştırmaz. Seçim
sonrası exact factor, factor version history ve source registry tanımı paralel alınır; özet
alanların yanında ham cevaplar da gösterilerek normalized kaydın bütün alanları korunur.
Publisher scope'u bulunmayan `national_inventory_implied_factor` boundary kayıtları Scope 1
olarak türetilir, diğer boş scope'lar `Unspecified` kalır. Katalog runtime license gate
uygulamaz; yayımlanmış kayıt zaten ingestion quality/review/license kapılarından geçmiştir.
Birden çok reference year görüldüğünde yüklenmiş kayıtların yıl dağılımı seçilebilir alt filtre
olarak korunur; bu filtre source/scope/text sorgusunu değiştirmez. Explorer ve Catalog evidence
panellerinde bilgi yoğunluğu 7–9 px mikro tipografiyle sağlanmaz; okunabilirlik için normal
metinler en az 10 px, factor adları ve kritik kararlar daha büyük hiyerarşi kullanır.

## Sonuçlar

- UI gerçek engine davranışını gözlemler; proxy seçimi backend contract'ında açık opt-in'dir.
- Atlas'ın domain ve source sınırları değişmez.
- Persisted facility resolution ve reviewed parameter catalog eksikleri görünür kalır.
- Browser-local regression state'i ekipler arası kalıcı test kanıtı sayılmaz.
- Catalog source kayıtlarını olduğu gibi inceletir; ürün için “en doğru factor” seçimi halen
  versioned recommendation policy sorumluluğudur.
