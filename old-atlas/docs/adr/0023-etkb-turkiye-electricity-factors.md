# ADR-0023 — ETKB Türkiye elektrik factor sınırları

## Durum

Kabul edildi — 28 Ağustos 2026.

## Bağlam

ETKB EVÇED iki farklı elektrik yayını üretir. “Türkiye Elektrik Üretimi ve Elektrik
Tüketim Noktası Emisyon Faktörleri”, corporate inventory ve Kapsam 2 hesabında
kullanılabilen yıllık brüt üretim/tüketim yoğunluklarıdır. “Türkiye Ulusal Elektrik
Şebekesi Emisyon Faktörü” ise UNFCCC Tool07 ile hesaplanan operating/build/combined
margin değerlerini ve yenilenebilir proje kaynaklı kaçınılan emisyon hesabını kapsar;
şebekeden elektrik tüketen kuruluşların inventory factor'ı değildir.

## Karar

- Bu source fazı `sources/etkb` altında yalnız 2020–2023 üretim ve tüketim noktası annual
  PDF serisini ingest eder. Ulusal şebeke avoided-emissions marj serisi ayrı bir dataset
  sözleşmesi kurulmadan bu source'a eklenmez.
- Exact resmî PDF'ler content-addressed raw asset olarak saklanır. Parser; iki sayfa,
  `ETKB-EVÇED-FRM-042 Rev.01`, hesaplama dönemi/yayım tarihi/revizyonu, üç factor-table
  ve sabit 1 + 7 + 2 faaliyet satırı kontratını denetler.
- Her faaliyet için publisher'ın `tCO₂/MWh` ve `tCO₂-eşd./MWh` değerleri ayrı canonical
  version olur. CO₂ sütunu `CO2_ONLY` ve default-match ineligible; CO₂-eşdeğeri sütunu
  `CO2E_TOTAL` ve inventory default-match eligible'dır. CO₂ ile CO₂e farkından bileşen
  gaz veya GWP değeri tersine türetilmez.
- `t/MWh`, sayısal olarak eşdeğer `kg/kWh` birimine normalize edilir. Türkiye geneli ve
  yakıta göre üretim factor'ları brüt elektrik üretimi; iletim/dağıtım satırları ilgili
  bağlantı noktasına teslim edilen elektrik tüketimi boundary'sini taşır.
- Dört release, 80 temporal canonical version ve 20 logical seri oluşturur. Reference
  year ile PDF hesaplama yayım tarihi ayrıdır; 2020 rev.01 düzeltmesi overwrite edilmez,
  revision ve checksum provenance'da korunur.
- Kaynak Türkiye ülke-specific'tir. İletim/dağıtım bağlantı türü coğrafi bölge değildir;
  activity/source subcategory olarak tutulur.
- Bakanlık sayfası “tüm hakları saklıdır” der ve PDF açık yeniden-dağıtım lisansı vermez.
  Local reference publish attribution ile owner-approved olabilir; commercial, API,
  modified ve raw distribution ayrı yazılı izin olmadan açılmaz.

## Sonuçlar

Atlas Kapsam 2 tüketim yoğunluğunu proje bazlı avoided-emissions grid margin ile
karıştırmaz. Publisher'ın CO₂ ve CO₂e toplamları korunur, yapay gaz ayrıştırması yapılmaz.
Her factor yıllık PDF, page/table/row/column, calculation revision ve raw checksum'a geri
izlenebilir; external distribution lisans belirsizliği çözülene kadar kapalı kalır.
