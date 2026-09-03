# ADR-0035: OpenAI tabanlı contextual terminology ve ortak multilingual resolver

## Durum

Kabul edildi — 2026-08-29.

## Bağlam

Taxonomy code'dan üretilen English adlar ve yalnız kısa label üzerinde çalışan Argos
çevirileri çevresel veri terminolojisini güvenilir şekilde aktarmıyordu. Search ve
Recommendation farklı term listeleri kullandığı için aynı ERP activity metni farklı
canonical concept'lere gidebiliyor, Latin olmayan metin ASCII normalizasyonunda boşalarak
yanlış ilk family'ye düşebiliyordu.

## Karar

- 485 concept önce context, factor örnekleri ve taxonomy yolu kullanılarak English preferred
  term/definition review'una girer; sonra TR → DE/FR/ES → RU/AR çevrilir.
- OpenAI Responses API Structured Outputs şema garantili çıktı üretir. Batch API toplu üretim,
  `gpt-5.6-terra` ana model, `gpt-5.6-sol` yalnız QA uyarılı kayıtların ikinci geçişidir.
- Provider işi en fazla 50 concept içerir. Asenkron Batch API'ye ek olarak project key'in Batch
  input file'ına erişemediği ortamlarda 50-concept doğrudan Responses grupları kullanılabilir.
  Aktif job içindeki concept yeniden gönderilmez; tamamlanmış Responses çıktısı persistence veya
  QA kesintisinden sonra response ID ile idempotent yeniden ingest edilebilir.
- Model çıktıları preferred, synonym ve abbreviation kayıtlarına ayrılır; provider, model,
  prompt/glossary version, QA flags ve supersession audit'i saklanır.
- Aynı concept içindeki canonical, synonym ve abbreviation değerleri normalize edildikten sonra
  tekilleştirilir; preferred canonical kayıt daha düşük öncelikli alias tarafından ezilemez.
- Sol QA kotası veya erişimi kesilirse başarılı Terra çıktısı kaybedilmez. QA hatası audit
  sayacına yazılır ve kayıt insan review'unda kalır.
- Model çıktısı yalnız draft'tır. İnsan approve etmeden Search veya Recommendation index'ine
  girmez. Argos yalnız offline fallback draft üretir.
- API anahtarı environment secret'tır; raw key hiçbir response, audit veya log alanında
  gösterilmez. Müşteri transaction/facility verisi translation provider'a gönderilmez.
- Runtime concept resolution yereldir. Unicode NFKC, script/language detection, approved terms,
  transliteration ve kontrollü fuzzy eşleşme kullanılır; runtime OpenAI çağrısı yapılmaz ve
  tek genel token concept seçmez.
- Search ve Recommendation aynı DB-backed resolver sonucunu kullanır. Strict ambiguous sonuç
  `needs_input` döndürür.

## Sonuçlar

Çeviri üretimi toplu ve yeniden çalıştırılabilir, yayın ise denetlenebilir hale gelir. Original
factor/source text immutable kalır. Kalite artışı API latency veya OpenAI availability'sine
bağlanmaz; provider yalnız offline intelligence üretim aşamasındadır.
