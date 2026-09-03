# ADR-0006 — Factor value kind and intended use

## Durum

Kabul edildi — 2026-08-27

## Bağlam

EPA Hub aynı workbook içinde toplam CO2e, yalnız CO2, CH4/N2O bileşenleri,
non-baseload avoided-emissions değerleri ve GWP characterization factor'ları yayınlar.
Bu değerleri tek bir sıradan emission-factor türünde toplamak yanlış eşleştirmeye ve
envanter hesabına yol açar.

## Karar

Canonical factor, sayının ne ifade ettiğini `factor_value_kind`, hangi hesapta
kullanılabileceğini `intended_use` ile ayrı taşır. Varsayılan matching yalnız
`co2e_total + inventory` kayıtlarına açıktır. Genel factor API diğer türleri saklamaya
ve filtreleyerek sunmaya devam eder.

IPCC entegrasyonuyla bu ayrım `gas_emission_factor` ve `calculation_parameter` değer
türlerini, ayrıca `calculation_input` kullanım amacını da kapsar. Bu kayıtlar toplam
CO2e faktörü olarak eşleştirilmez; versioned calculation recipe tarafından açıkça
seçilene kadar yalnız kaynak parametresi olarak sunulur.

## Sonuçlar

- EPA Tables 3–5 `non_co2_co2e` olarak kaybolmadan versiyonlanır.
- eGRID non-baseload değerleri `avoided_emissions` olur ve inventory eşleştirmesine girmez.
- EPA Tables 11–12 `characterization_factor` olur.
- Mevcut DEFRA kayıtları geriye uyumlu olarak `co2e_total + inventory` kabul edilir.
- IPCC gaz faktörleri tek başına toplam CO2e değildir; gaz ve source unit korunur.
- IPCC formül girdileri equation/worksheet bağlamıyla calculation parameter olarak saklanır.
