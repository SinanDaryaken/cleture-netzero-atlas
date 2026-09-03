# ADR-0009 — ADEME Base Carbone ingestion ve source semantiği

## Durum

Kabul edildi — 2026-08-27

## Bağlam

Base Empreinte portalının Base Carbone® içeriği ADEME Open Data üzerindeki Data Fair
dataset'i olarak yayımlanır. Dataset metadata'sı version, file checksum, row count,
license ve original-file URL'sini ayrı taşır. V23.6 export'u CP1252, noktalı virgül
ayraçlıdır; `Elément` toplamları ile `Poste` lifecycle/gas ayrışımları aynı dosyadadır.
Negatif değerlerin bir bölümü veri hatası değil, depolama veya avoided-emissions
semantiğidir. Coğrafya alanı France, overseas, Europe, world ve 140 farklı ülke etiketi
içerebilir.

## Karar

- Resmî `base-carboner` Data Fair metadata API'si source contract'tır; original CSV
  değişmeden immutable raw katmana alınır.
- Change detection portal `updatedAt` değerini kullanmaz. Dataset id, original filename,
  MD5, size, row count ve `dataUpdatedAt` birleşiminden deterministik revision üretilir.
- Parser V23.6'nın 67 kolonunu exact schema olarak doğrular. Yıllar arasında kolon yapısı
  değişirse mevcut parser sessizce tahmin yürütmez; yeni parser version gerekir.
- Yalnız valid `Elément + Facteur d'émission` kayıtları canonical factor olur. Archived
  kayıtlar raw/parsed katmanda korunur; valid bir factor'ın archived olması sonraki
  dataset comparison'da removal olarak görünür.
- `Poste` kayıtları toplam factor'ın methodology decomposition alanında source row ile
  korunur. Gaz kolonları kaynakta CO2e contribution olduğundan raw gas mass gibi
  etiketlenmez.
- Negatif toplamlar `avoided_emissions` olarak ayrılır ve default inventory matching'e
  girmez.
- France, French overseas, Europe ve world mapping'leri açık yapılır. Onaylı ISO mapping'i
  olmayan diğer ülke etiketleri global/proxy yapılmaz; dışarıda bırakılır ve review
  sebebi üretir.
- Licence Ouverte hakları manifestte commercial use, redistribution, modification,
  API ve raw distribution için açık; attribution zorunlu olarak kaydedilir.

## Sonuçlar

ADEME version değişimleri source dosyasına bağlı ve tekrar üretilebilir olur. Total,
lifecycle decomposition, negative avoided-emissions ve geography coverage birbirine
karışmaz. V23.6'da mapping bekleyen 162 factor coverage sayımlarını şişirmez; ISO katalog
genişletmesi ayrı, gözlemlenebilir bir iş olarak kalır.
