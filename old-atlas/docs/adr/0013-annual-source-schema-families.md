# ADR-0013 — Yıllık kaynak schema family'leri

## Durum

Kabul edildi — 2026-08-28

## Bağlam

Aynı annual source'un workbook sözleşmesi yıllar arasında sabit değildir. DEFRA 2020–2022
flat file'larında source `ID` yoktur ve 2021/2022 dosyaları legacy XLS'tir; 2023–2026
dosyaları ID içeren XLSX sözleşmesine geçmiştir. EPA elektrik grid ve GWP tablolarının
kolonları 2023/2024 döneminde değişmiştir. AIB 2022–2024 calculation workbook'ları ile
2025 workbook'u aynı residual-mix bilgisini farklı header biçimleriyle sunar.

## Karar

- Source manifest `history.schemas` altında her referans yılını tam bir kez kapsayan
  schema family'leri tanımlar.
- Her family adı, parser semver'i, dosya formatı, yıl aralığı ve implementation durumu
  taşır. Aynı parser kodu birden fazla family'yi okuyabilir; family adı source contract'ı,
  parser semver ise çalışan kodu tanımlar.
- Backfill isteği implementation'ı olmayan family için queue'ya alınmadan reddedilir.
- Kullanılan parser semver run context'e alınır ve dataset version ile satır provenance'a
  yazılır; manifestin yalnız “latest parser” alanına güvenilmez.
- Quality baseline source-wide tek sayı olmak zorunda değildir. `release_expectations`
  her yıl için expected row/factor/table sayılarını ayrı tutar.
- DEFRA legacy satırlarında olmayan source ID uydurma bir publisher ID olarak sunulmaz.
  Alanlardan deterministik `legacy_*` processing ID ve yıllar arası semantic logical key
  üretilir. `< 1` gibi qualifier değerler sıfıra çevrilmez.
- AIB 2022–2025 direct residual CO₂ değerleri doğrudan yıllık `Residual Mixes` sheet'inden
  okunur. Production/supplier mix veya sonraki workbook'lardaki karşılaştırma tablosu
  residual factor yerine kullanılmaz.

## Sonuçlar

Bir parser güncellemesi eski raw assetleri aynı schema family ve yeni parser semver ile
yeniden işleyebilir. Dataset processing uniqueness checksum + parser version + mapping
version üzerinden korunur. Yıllar arasında schema drift normal bir source versioning olayı
olarak gözlemlenir; sessiz kolon kayması veya güncel parser ile eski dosyayı zorla okuma
engellenir.
