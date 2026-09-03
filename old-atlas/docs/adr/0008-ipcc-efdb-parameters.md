# ADR-0008 — IPCC EFDB export ve hesaplama parametreleri

## Durum

Kabul edildi — 2026-08-27; canonical CO₂e toplam kararı 2026-08-28'de eklendi.

## Bağlam

IPCC EFDB yalnız tek adımda `EF × tüketim` ile kullanılabilecek CO2e faktörleri içermez.
Gaz bazlı emisyon faktörlerinin yanında net calorific value, oxidation factor, methane
correction factor ve bir worksheet denkleminde birlikte kullanılan başka parametreler
bulunur. Web uygulamasındaki XLS export ayrıca session-scoped geçici tablo kullanır ve
aynı veri için volatile paket metadata'sı üretir.

## Karar

- Atlas resmî EFDB sonuç tablosunu session-aware POST export ile indirir ve original
  XLSX paketini immutable raw katmanda tutar.
- Change detection raw paket hash'iyle değil, deterministik worksheet XML fingerprint'iyle
  yapılır.
- Doğrudan gaz faktörleri `gas_emission_factor` veya `co2_only`; formül girdileri
  `calculation_parameter + calculation_input` olarak saklanır.
- Kaynağın equation, worksheet, technology, conditions, fuel ve source reference alanları
  methodology/provenance içinde korunur. Kaynak denklemi otomatik executable koda çevrilmez.
- Yalnız coğrafi koşulu boş olan IPCC default kayıtları ilk sürümde global normalize edilir.
  Bölgesel serbest metinler onaylı mapping olmadan global kabul edilmez.
- Tekil gaz ve parameter kayıtları toplam CO₂e adayı sayılmaz. Ancak fuel-combustion
  (`1.A`) içinde aynı guideline/category/fuel/default/technology/condition grubunda tam ve
  tekil CO₂ + CH₄ + N₂O üçlüsü varsa Atlas bu üçlüyü canonical `co2e_total` olarak ayrıca
  üretir.
- Bileşenler ortak activity paydasına normalize edilir ve toplam açıkça
  `CO2 + CH4 × 28 + N2O × 265` (IPCC AR5 GWP100) olarak türetilir. Bunun publisher-reported
  total olmadığı methodology'de işaretlenir; üç source row component provenance olarak
  korunur.
- Eksik, birden çok anlamlı veya unit'i güvenle normalize edilemeyen grupta toplam üretilmez.
  Bu durumlar ayrı normalizasyon metrikleri olarak raporlanır.

## Sonuçlar

Atlas çok-parametreli IPCC hesaplarını veri kaybı olmadan temsil edebilir; ilerideki
calculation recipe engine bu versioned parametreleri açık input kontratlarıyla bağlayabilir.
Resmî 27.566 satırlık snapshot'ta bu kural 217 calculation-eligible canonical toplam üretir;
bunların sekizi Natural Gas/NGL kategori gruplarıdır. Yanlış global coverage, eksik bileşenden
uydurulan toplam ve yanlış tek-faktör eşleştirmesi engellenir.
