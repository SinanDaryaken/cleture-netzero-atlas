# Candidate build işletim sözleşmesi

## Ön koşullar ve plan

Atlas migration'ları, PHP ZIP ve PDO SQLite extension'ları gereklidir. SQLite yalnız
geçici disk tabanlı diff indeksidir; çalışma kayıtları Atlas DB'sinde kalır. Admin
ve tenant DB bağlantısı kurulmaz. Katalogların exact descriptor/payload byte'ları
`atlas_catalogs` diskinde bulunmalıdır. `.env.example` katalog ve policy pinlerini gösterir.
Katalog veya policy değişiminde path ve hash birlikte açıkça güncellenir; fallback yoktur.

`atlas:candidate:build` yerel JSON planı alır. Aşağıdaki yer tutucular gerçek kanıtla
doldurulur; source/release/raw/pipeline alanları plan üzerinden override edilemez:

```json
{
  "schema_version": "atlas-candidate-build/v1",
  "normalized_artifact_id": "<Atlas normalized_artifacts UUID>",
  "publisher": {"name": "<kanıtlanmış yayıncı>", "identifier": null, "homepage": null},
  "license_descriptor_path": "licenses/sha256/<descriptor SHA-256>.json",
  "license_descriptor_sha256": "<descriptor SHA-256>",
  "previous_package_id": null
}
```

İlk release için previous_package_id açıkça null'dır. Sonraki karşılaştırmada Atlas
ledger'ındaki aynı source/dataset paket UUID'si verilir; otomatik latest seçilmez.
Önceki manifest ve ZIP exact hash/size, V2 schema ve entity checksum kapılarından geçer.

## Lisans kanıtı

Atlas processing diskinde immutable terim byte'ları ve descriptor bulunmalıdır.
Bu bir hak/lisans üretme mekanizması değildir; gerçek source kanıtının tüketicisidir.
Test lisansları production input değildir. Descriptor örnek şekli:

```json
{
  "schema_version": "atlas-license-evidence/v1",
  "source": {"code": "<source>", "dataset_id": "<dataset>", "release_revision_sha256": "<revision hash>"},
  "license": {
    "identifier": "<license identifier>", "name": "<discovery ile aynı lisans adı>",
    "terms_sha256": "<exact terms SHA-256>", "attribution": "<required attribution>",
    "source_uri": "https://<official-license-location>", "retrieved_at": "<RFC3339 timestamp>"
  },
  "terms_object_key": "licenses/sha256/<exact terms SHA-256>.terms",
  "terms_size_bytes": 123
}
```

Descriptor'ın exact byte hash'i dosya anahtarına ve plana yazılır. Terms boyutu örnek
değildir: gerçek byte sayısı girilir. Lisans identifier/name/attribution açıkça sağlanır;
discovery'deki bir başlıktan kullanım hakkı türetilmez. Acquisition/provision işlemi bu
komutun dışındadır. Lisans uygunluğunun son review/publish kararı Admin'e aittir.

## Sonuç ve kapılar

- Exit 0: review candidate paketi saklandı veya aynı paket yeniden kullanıldı; publish değildir.
- Exit 2: schema-valid entity'lerde paket bütünlüğü hatası; findings ve validation receipt
  saklandı, paket oluşturulmadı.
- Exit 1: eksik/bozuk girdi, schema/checksum/adapter hatası; hata çıktısı incelenir.
  Preflight veya entity schema hatasında semantic validation kaydı oluşmayabilir.

Referans bütünlüğü, raw provenance hash/locator/pointer, primary component tutarlılığı
ve yanlış katalog hedefi paket bloklayıcıdır. Eksik unit/geography/taxonomy/intended-use,
doğrulanamayan dimension/formula ve temporal kalite sorunları açık bulgulardır; blocking
adayların review paketinde bulunması publish edilebilir oldukları anlamına gelmez.
Bu paketlerin canlı intake kabul politikası Admin tarafından henüz açılmamıştır.

Provenance kontrolü field pointer'ın varlığı ve raw asset bağıdır; raw hücrelerden
değeri yeniden hesaplama veya bütün alanlar için semantik kanıt kapsamı sertifikası değildir.
Root pointer kaba provenance olarak review bulgusu üretir. Compound-unit applicability,
formula ve taxonomy sahip sözleşmeleri olmadan Atlas canonical kural icat etmez.

Validation receipt entity/findings hash'leri, kataloglar, lisans, raw kanıt, normalized
artifact kimliği ve policy ile sabitlenir. Package builder receipt eşleşmesini zorunlu
tutar ve ZIP öncesinde member byte'larını yeniden doğrular. Release kilidi altında
internal idempotency key için package UUID, producer run ve generated_at bir kez ayrılır.
Aynı ZIP farklı lisans/pipeline manifestlerinde kullanılabilir; archive key unique değildir.

S3 storage versioning Enabled olmalı; producer doğrulanmış ZIP VersionId receipt'inden
sonra manifest üretir. `atlas.candidate_ingress` logical profildir, yerel disk adı değildir.
Wire idempotency key Admin semantic fingerprint v1'dir; Atlas internal full identity
anahtarından ayrıdır. Raw asset set hash'i yalnız sıralı dört transport descriptor alanını
içerir; provenance URI/zaman alanları korunur. [ADR-010](decisions/ADR-010-versioned-candidate-transport.md).

## Doğrulama

Varsayılan suite Unit/Feature testlerini içerir. Gerçek PostgreSQL/MinIO testi ayrıca
`tests/Integration/CandidatePackagePipelineTest.php` ile çağrılır; yalnız
`atlas_validation_test_*` adlı ayrılmış DB'yi kabul eder. Migration reset yapar: hiçbir
uygulama DB'sine yöneltilmez. Rastgele test bucket'ını kendi temizler. İki bağımsız PHP
süreci eşzamanlı üretim yapar; retry, önceki paket diff'i ve latest değişse de pin'in
korunması kontrol edilir. Test bucket'ı versioning açar, sürümler/delete marker'lar temizlenir.
Bu gerçek MinIO testi son transport diliminde çalıştırılmadı; yalnız ilgili local/SDK/socket
testleri çalıştırıldı. [Güncel kabul kanıtı](candidate-versioned-acceptance.md).
Testler kullanıcı talebiyle çalıştırılır ve timestamp'li geçici loga alınır.
