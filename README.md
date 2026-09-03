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

## Backlog

Public, kayıtsız ve snapshot'sız hesaplama arayüzü ayrı bir geliştirme hattıdır:
[GitHub Issue #1](https://github.com/SinanDaryaken/cleture-netzero-atlas/issues/1).
