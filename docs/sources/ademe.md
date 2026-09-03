# ADEME Base Carbone source inventory

## Acquired release

- Source: ADEME Base Carbone
- Dataset ID: `base-carboner`
- Release: `23.6`
- Reported/exported rows: `18,616`
- Original file: `Base_Carbone_V23.6.csv`
- File size: `10,761,452` bytes
- Upstream MD5: `39583facdba0881a15f708693f25c793`
- Raw SHA-256: `01472bc24743c0265b649407508dfce896f15a5c11c0f612f6b47a5625b02653`
- Source data updated at: `2025-07-03T08:07:23Z`
- License: Licence Ouverte / Open Licence
- Raw object: `atlas-raw/sources/ademe/2026/09/03/01472bc24743c0265b649407508dfce896f15a5c11c0f612f6b47a5625b02653/Base_Carbone_V23.6.csv`

Bu kimlikler raw acquisition sırasında gerçek dosyanın boyutu, upstream MD5 değeri
ve Atlas SHA-256 değeri doğrulanarak elde edilmiştir. Aynı release ikinci kez
çalıştırıldığında yeni run veya raw nesne oluşturulmamıştır.

## Normalize öncesi profil

Bu profil raw CSV üzerinde salt-okunur olarak çıkarılmıştır; candidate veya canonical
kayıt sayısı değildir.

| Ölçüm | Değer |
| --- | ---: |
| CSV kolon sayısı | 67 |
| Export satırı | 18,616 |
| Geçerli emission-factor `Elément` satırı | 6,518 |
| Total değeri eksik geçerli satır | 0 |
| Birimi eksik geçerli satır | 0 |
| Negatif total değerli geçerli satır | 290 |
| Farklı source unit label | 69 |
| Farklı ana coğrafya sınıfı | 5 |
| Farklı sub-location label | 937 |

Geçerli faktör adaylarının ana coğrafya dağılımı:

- France continentale: 5,791
- Monde: 347
- Autre pays du monde: 168
- Outre-mer: 115
- Europe: 97

`Autre pays du monde` kayıtlarında 142 farklı Fransızca/İngilizce ülke label çifti
vardır. Yerel `base_netzero.countries` kataloğuyla yapılan yalnız analiz amaçlı
karşılaştırmada 127 İngilizce label doğrudan eşleşmiştir. Kalan 15 değer yazım
farkı, eski resmî ad veya politik/territorial belirsizlik içerir; örnekler
`Netherlands Antilles`, `FYR of Macedonia`, `Chinese Taipei`, `DPR of Korea (north)`
ve `Dem. Rep. of Congo` değerleridir.

Bu sonuç fuzzy eşlemenin otomatik kabul için yeterli olmadığını gösterir. Logi lookup
sözleşmesi ISO kodu, alias kanıtı ve katalog sürümü döndürmeli; belirsiz veya eski
coğrafyalar insan review'ına bırakılmalıdır.

## Parse aşaması kabul kriterleri

- 67 kolonun sırası ve orijinal adları parser sürümünün schema fingerprint'i olur.
- Bütün `Elément`, `Poste`, archived ve source-data satırları kayıpsız korunur.
- 6,518 geçerli factor element yeniden üretilemezse parse tamamlanmış sayılmaz.
- 69 source unit label dönüştürülmeden önce özgün biçimiyle envantere alınır.
- 290 negatif değer yalnız işaretine bakılarak avoided-emission sayılmaz.
- 168 dış ülke kaydı Logi canonical ID olmadan publish-eligible olamaz.
