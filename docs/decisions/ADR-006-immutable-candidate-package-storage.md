# ADR-006: Immutable candidate package storage ve idempotent ledger

- Durum: Kabul edildi
- Tarih: 2026-09-05

## Bağlam

Deterministik V2 package builder geçici ZIP artifact'i ve canonical sidecar manifest
üretir. Bu çıktının process-local geçici dosyada kalması, aynı release tekrar
çalıştırıldığında yeni package kayıtları oluşması veya var olan object storage
nesnesinin yalnız adına güvenilmesi immutable ingestion sözleşmesini karşılamaz.

## Karar

- Candidate ZIP `sha256/<archive_sha256>.zip`, canonical manifest ise
  `manifests/sha256/<manifest_sha256>.json` anahtarında `atlas_candidates` diskine
  yazılır. Source code, release adı veya zaman object key üretimine katılmaz.
- Var olan nesne sessizce doğru kabul edilmez. Archive ve manifest her kullanımda
  exact byte size ve stream SHA-256 ile tekrar doğrulanır. Uyuşmazlık fallback veya
  overwrite yerine fail-closed hatadır.
- Object storage yazısı stream ile yapılır. Archive bütünü uygulama belleğine alınmaz;
  manifest zaten bounded canonical sidecar byte dizisidir.
- Atlas çalışma DB'sindeki `candidate_packages` tablosu package UUID, source release,
  producer ingestion run, önceki package, idempotency key, archive/manifest storage
  kimlikleri ve count özetlerini saklar. Canonical kayıt veya publish state'i tutmaz.
- Idempotency key veritabanında unique'tir. Aynı key yeniden geldiğinde package ID,
  source/release/run bağlantıları ve bütün immutable storage kimlikleri birebir aynı
  olmak zorundadır; farklı olguya çözülürse işlem reddedilir.
- Previous-package self-reference constraint'i PostgreSQL'in creation ordering
  davranışı nedeniyle primary table oluşturulduktan sonra ayrı schema adımında eklenir.
- Object storage ve SQL tek transaction değildir. Content-addressed yazı önce yapılır,
  ardından kısa DB transaction'ında ledger kaydı oluşturulur. DB kaydı başarısız olursa
  kalan nesne immutable ve hash-adresli orphan'dır; başka bir package verisini ezmez ve
  sonraki aynı girişte doğrulanarak tekrar kullanılabilir.

## Sonuçlar

Package persistence tekrar çalıştırılabilir ve byte kimliğiyle doğrulanabilir hale
gelmiştir. Bu kayıt NetZeroAdmin kabulü veya canonical publish değildir. Validation
kapıları geçmeden package teslimata uygun sayılmaz; canlı delivery hâlâ Admin V2 intake
ve Worker durable staging koordinasyonunu bekler.
