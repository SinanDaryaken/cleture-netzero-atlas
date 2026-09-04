# NetZero Atlas

NetZero Atlas, `moduler_netzero` platformunun çevresel veri tedarik ve hazırlama
bileşenidir. Kaynak keşfi, immutable raw saklama, parse, normalize, canonical
kavramlara eşleme, kalite ve lisans doğrulama, sürüm karşılaştırma ve review'a
hazır candidate dataset üretiminden sorumludur.

Atlas canonical katalogları doğrudan yayımlamaz, tenant veritabanlarına bağlanmaz
ve production hesap sonucu saklamaz. Candidate paketlerin review ve publish sahibi
`cleture-netzero-admin` uygulamasıdır.

## Yerel altyapı

- PostgreSQL: ortak `laravel-dev-postgres` servisi, `atlas_netzero` veritabanı
- Redis: ortak `laravel-dev-redis` servisi
- Object storage: Atlas instance'ına özel MinIO
- Private bucket'lar: `atlas-raw`, `atlas-processing`, `atlas-candidates`
- MinIO API: `127.0.0.1:49000`
- MinIO Console: `127.0.0.1:49001`

Laravel bağlantı örnekleri `.env.example` içinde, yerel Docker servis tanımı ise
`laravel-dev-platform/instances/cleture-netzero-atlas` altında tutulur. Secret
değerler Git'e eklenmez.

## Kod sınırları

- Framework bağımsız domain kuralları: `app/Domain`
- Use-case orkestrasyonu: `app/Application`
- Veritabanı, queue, HTTP ve source adapter'ları: `app/Infrastructure`
- Source'a özel kod: `app/Infrastructure/Sources/<code>`

`old-atlas` yalnızca analiz ve kontrollü taşıma için referans snapshot'tır. Yeni
uygulamanın çalışma zamanı veya mimari kaynağı değildir.

## ADEME pilotu

İlk source pilotu ADEME Base Carbone'dur. Kaynağın güncel release metadata'sı veri
indirilmeden ve persist edilmeden incelenebilir:

```bash
php artisan atlas:source:inspect ADEME
```

Komut dataset kimliği, finalized durumu, dosya kimliği, satır sayısı ve açık lisans
sözleşmesini fail-closed doğrular. Raw acquisition, parse, normalization ve candidate
package aşamaları [roadmap](docs/roadmap.md) içinde ayrı kapılar olarak izlenir.
Acquired release ve normalize öncesi gerçek veri profili
[ADEME source inventory](docs/sources/ademe.md) içinde bulunur.

Coğrafya eşlemesi Atlas içinde sahiplenilmez. Ülke/il/ilçe eşlemesi Logi canonical
kimliklerine dayanacaktır; mevcut entegrasyon sınırı
[ADR-001](docs/decisions/ADR-001-logi-geography-boundary.md) içinde açıklanmıştır.
ADEME'ye özgü normalization ile bütün kaynakların kullanacağı ortak candidate package
altyapısının sorumluluk ayrımı ve pinlenmiş NetZeroAdmin sözleşme kapısı
[ADR-003](docs/decisions/ADR-003-normalization-and-candidate-contract-boundary.md)
içinde tanımlanmıştır.

Doğrulanan release'in orijinal dosyası MD5 ve SHA-256 kontrolünden geçirilerek
content-addressed biçimde `atlas-raw` alanına alınabilir:

```bash
php artisan migrate
php artisan atlas:source:acquire ADEME
```

Acquisition komutu yalnız Atlas çalışma DB'sindeki source/release/run/raw asset
kayıtlarını ve MinIO raw nesnesini oluşturur. Parse, normalize, candidate veya
canonical publish işlemi yapmaz; aynı release yeniden çalıştırıldığında mevcut raw
nesneyi döndürür.

Acquired raw release, source'a özel ve sürümlü parser sözleşmesiyle kayıpsız parsed
observation'lara dönüştürülebilir:

```bash
php artisan atlas:source:parse ADEME
```

ADEME V23.6 parser'ı noktalı virgülle ayrılmış 67 kolonun adını ve sırasını SHA-256
fingerprint ile doğrular; UTF-8 BOM'u kabul eder ve resmî Windows-1252 exportu için
açık fallback uygular. Bütün `Elément`, `Poste`, archived ve source-data kayıtları
özgün alan değerleri korunarak Atlas çalışma DB'sine ve content-addressed NDJSON
artifact olarak `atlas-processing` alanına yazılır. Şema kayması, satır sayısı farkı,
geçersiz decimal ve duplicate geçerli factor `Elément` kimliği işlemi fail-closed
sonlandırır. Aynı raw checksum ve parser sürümü yeniden çalıştırıldığında mevcut
parsed artifact kullanılır. Ayrıntılı sözleşme [ADR-002](docs/decisions/ADR-002-ademe-parsed-observation-contract.md)
içinde açıklanmıştır.

Latest parsed artifact, ADEME'ye özel normalizer ile source-neutral candidate draft'a
dönüştürülebilir:

```bash
php artisan migrate
php artisan atlas:source:normalize ADEME
```

Komut parsed artifact'in satır sayısını ve SHA-256 değerini yeniden doğrular. Geçerli
`Elément` satırlarını candidate draft, ilişkili `Poste` ve gaz değerlerini component,
negatif toplamları ise review finding olarak üretir. Unit, taxonomy, intended-use ve
geography eşlemeleri canonical snapshot gelene kadar `unresolved` kalır. Draft NDJSON
content-addressed olarak `atlas-processing` alanına yazılır; run ve finding kayıtları
Atlas çalışma DB'sinde tutulur. Bu çıktı henüz `record_sha256` eklenmiş candidate package
değildir ve Admin'e gönderilmez.

## Backlog

Public, kayıtsız ve snapshot'sız hesaplama arayüzü ayrı bir geliştirme hattıdır:
[GitHub Issue #1](https://github.com/SinanDaryaken/cleture-netzero-atlas/issues/1).
