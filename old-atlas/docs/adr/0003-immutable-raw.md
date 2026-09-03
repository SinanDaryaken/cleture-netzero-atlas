# ADR-0003: Content-addressed immutable raw storage

Durum: Kabul edildi

## Karar

Raw artifact anahtarı source kodu, UTC indirme tarihi ve SHA256 içerir. Aynı checksum'a
sahip payload aynı logical object'e karşılık gelir; nesne overwrite edilmez. Metadata
ayrı, versioned bir kayıt olarak tutulur.

## Gerekçe

Bu model audit ve deterministik reprocessing'i korur; source'un aynı isimli dosyayı
sessizce değiştirmesi halinde geçmiş verinin kaybolmasını engeller.
