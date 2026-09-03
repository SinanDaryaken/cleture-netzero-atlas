# ADR-001: Logi coğrafya sahipliği ve Atlas eşleme sınırı

- Durum: Kabul edildi
- Tarih: 2026-09-03

## Bağlam

ADEME Base Carbone kayıtları ülke, bölge, kıta ve global uygulanabilirlik ifadeleri
taşır. Atlas bu ifadeleri canonical coğrafya kimliklerine eşlemeli, fakat canonical
coğrafya kataloğunun sahibi değildir.

`cleture-logi` repository'sinin mevcut migration ve API sözleşmesinde yalnız
`air_ports` ve `sea_ports` domain'leri vardır. Bu kayıtlar ISO 3166-1 alpha-2 ülke
kodu taşır; ülke, il ve ilçe için stable canonical kimlik veya versioned lookup API
sunulmaz.

Yerel PostgreSQL incelemesinde ülke/il/ilçe verisinin `base_netzero` veritabanında
bulunduğu görülmüştür. Atlas'ın bu veritabanını çalışma zamanında sorgulaması ürün
sınırını ve veri sahipliğini ihlal eder.

ADEME V23.6 içindeki 142 farklı dış-ülke label çiftinin 127 tanesi mevcut
`base_netzero.countries` İngilizce adıyla doğrudan eşleşmektedir. Kalan 15 label eski
ülke adı, yazım farkı veya politik/territorial belirsizlik taşır. Bu veri Logi için
iyi bir başlangıç kaynağıdır, fakat yalnız isim eşitliği canonical eşleme kanıtı
değildir.

## Karar

- Atlas `base_netzero`, `moduler_netzero` veya tenant veritabanlarına coğrafya
  eşlemesi için bağlanmayacak.
- ADEME source discovery, raw acquisition ve parse işleri coğrafya servisinden
  bağımsız ilerleyecek.
- Coğrafya normalizasyonu `source label -> Logi canonical geography id` biçiminde
  sürümlü bir resolver sözleşmesine bağlanacak.
- Logi canonical ülke/il/ilçe lookup veya versioned snapshot sunana kadar yalnız
  açık kaynak semantiğine sahip `GLOBAL` ve `EUROPE` gibi değerler sınıflandırılacak;
  ülke eşlemesi gerektiren kayıtlar silinmeden `review_required` kalacak.
- Logi verisinin Atlas'a kopyalanması kalıcı çözüm değildir. Gerekirse Atlas yalnız
  eşleme anında kullanılan Logi kimliği, katalog sürümü ve kanıtı saklar.

## Sonuçlar

- ADEME pilotinin ilk dilimi coğrafya bağımlılığı olmadan release metadata'sını
  doğrulayabilir.
- Ülke eşlemesinin tamamlanması için Logi'ye stable country/province/district
  kimlikleri ve ISO/name lookup sözleşmesi eklenmesi gerekir.
- Mevcut `base_netzero` verisi Logi'yi başlangıçta beslemek için ayrı, kontrollü ve
  kullanıcı tarafından onaylanmış bir migration işi olarak değerlendirilebilir.
