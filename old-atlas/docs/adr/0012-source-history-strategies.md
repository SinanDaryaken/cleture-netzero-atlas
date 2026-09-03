# ADR-0012 — Kaynak geçmişi stratejileri

## Durum

Kabul edildi — 2026-08-28

## Bağlam

İlk beş Atlas kaynağı aynı yayın modelini kullanmaz. DEFRA ve EPA yıllık release,
AIB bir sonraki takvim yılında önceki referans yılını yayımlayan gecikmeli yıllık
release, IPCC EFDB ve ADEME Base Empreinte ise yaşayan ve zaman içinde revize edilen
veritabanlarıdır. Hepsine `2020.xlsx ... 2026.xlsx` varsayımı uygulamak sahte dataset
versiyonları ve yanlış referans yılları üretir.

## Karar

Her source manifest zorunlu bir `history` sözleşmesi taşır:

- `yearly_release`: DEFRA 2020–2026 ve EPA 2020–2025.
- `lagged_yearly_release`: AIB 2020–2025; `publication_lag_years: 1` yayın takvimi
  bilgisidir, datasetin `reference_year` değerini değiştirmez.
- `versioned_database`: IPCC EFDB ve ADEME. Bunlarda sentetik yıllık release veya
  yıllık eksik-coverage kaydı oluşturulmaz; her değişen export/API snapshot'ı checksum,
  retrieve zamanı ve source revision ile versiyonlanır.

Yıllık kaynaklar kapalı bir referans yılı aralığı ve mümkünse resmî release sayfaları
tanımlar. Preferred asset, DEFRA için otomatik işlemeye ayrılmış flat file; EPA ve AIB
için Excel'dir. Yaşayan veritabanları kayıt ve snapshot endpoint'lerini tanımlar.

## Sonuçlar

Scheduler yalnız son release'i kontrol edebilir; backfill ise manifestte izin verilen
belirli bir `reference_year` hedefleyebilir. Kaynakların tarihsel completeness hesabı
yalnız yıllık stratejilerde beklenen yıl kümesine göre yapılır. AIB yayın yılı ile
referans yılı ayrılır. IPCC ve ADEME için annual dosya varmış gibi kayıt üretilmez.
