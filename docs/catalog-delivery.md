# Atlas katalog teslimi işletimi

`atlas:catalog:delivery` yalnız katalog provisioning/byte+semantic doğrulama komutudur.
Candidate intake, insan onayı, hesaplama veya yayın yapmaz. `atlas:catalog:lookup`
gerçek Atlas hedefinden exact teslim+katalog+version+SHA seçer; latest/live fallback yoktur.

## Güven ve sürümler

`resources/contracts/netzero-admin/delivery-v1` upstream çalışma ağacının exact
schema/manifest snapshot'ıdır. `PinnedDeliveryContracts::ROOTS` bağımsız güven köküdür.
Paketin taşıdığı şemalar bu pinlerle aynı olmalıdır; paket trust root seçemez.

| Alan | Bu teslimde değer |
| --- | --- |
| Delivery envelope | `netzero-atlas-delivery/v1` |
| Unit payload / descriptor | `unit-catalog-release/v2` / `atlas-catalog-snapshot/v2` |
| Unit tüketim sözleşmesi | `2.1.0` |
| Unit release | `netzero-units-2026-09-06-v2` |
| Candidate sözleşmesi | `2.0.0`, değiştirilmedi |

Sorted JSON ve candidate RFC8785 farklı sözleşmelerdir. Gelen byte'lar yeniden
serialize edilerek taşınmaz. Nested hash doğrulaması için tanımlanan sorted hash
preimage kullanılır. Unit definition hash'i `id`, `quantity_kind_id`, `sha256` hariç
ve `release_id` eklenmiş kaydı; conversion hash'i release ID, iki definition hash'i,
multiplier ve offset'i kapsar. Admin kaynakları `CreateUnitDefinitionVersion` ve
`PublishUnitCatalogRelease::buildConversionRows` ile karşılaştırılmıştır.

## Komutlar

Komutlar mevcut Atlas PHP runner'ı içinde, repository kökünde çalışır. Kaynak directory
komutu yalnız yerel preflight yapar; çıktıda `read_from=local_source_only` yazar:

```bash
php artisan atlas:catalog:delivery <independent-manifest-sha256> --source=/absolute/delivery/directory
```

Onaylı `atlas.storage.catalog_disk` S3 hedefi mevcut olmalıdır. Runtime driver,
endpoint ve bucket gizli değerler gösterilmeden doğrulanır. Bucket oluşturma komutun
işi değildir; hedef değişirse owner kararı tekrar alınır.

```bash
php artisan atlas:catalog:delivery <independent-manifest-sha256> --source=/absolute/delivery/directory --transfer
php artisan atlas:catalog:delivery <independent-manifest-sha256>
php artisan atlas:catalog:lookup <delivery-sha256> unit <release-version> <catalog-sha256>
php artisan atlas:catalog:lookup <delivery-sha256> intended_use <sha256:catalog-sha256> <catalog-sha256> --id=corporate_carbon_footprint
```

Nesneler `atlas-deliveries/sha256/<manifest-sha>/objects/sha256/<artifact-sha>` altında
exact saklanır. Logical isimler diske materyalize edilmez; manifest içindeki logical
descriptor/payload adları verified object bytes'a çözülür. Manifest son tamamlanma
işaretidir. `If-None-Match: *` desteği olmayan backend'de sessiz overwrite fallback yoktur.
Var olan farklı byte korunur ve hata verilir. Kesinti sonrası eksik nesneler aynı
komutla tamamlanabilir; bütün mevcut nesneler yine okunup doğrulanır. Sahte source path,
symlink, eksik marker, yanlış hash, schema veya descriptor bağı fail-closed reddedilir.

## Candidate loader seçimi

Yeni explicit CLI tüketicisi eski candidate akışını kendiliğinden repin etmez.
`CatalogSnapshotLoader` binding'i `ATLAS_CATALOG_DELIVERY_SHA256` tanımlandığında
delivery adapter'ını seçer. Her gereken katalog için `ATLAS_DELIVERY_<CATALOG>_VERSION`
ve `ATLAS_DELIVERY_<CATALOG>_SHA256` birlikte sağlanır; eksik pin hatadır. Bu seçim
test/işlem konfigürasyonunda yapılabilir. Mevcut V1 descriptor loader, delivery pin'i
tanımlanmadığında korunur; yeni loader'dan eski loader'a hata fallback'i yoktur.

Bu görev shared environment veya Atlas `.env` dosyasını değiştirmedi. Gerçek hedeften
beş katalog, delivery SHA ve katalog version/hash'leri açık verilen loader ile okundu.
Candidate build lisans/normalization/diğer review bağımlılıkları çözülmeden çalıştırılmadı.
Yeni taxonomy lookup `entry_sha256` bilgisini kapalı candidate hedef sözleşmesine eklemez.

## 2026-09-07 gerçek kanıt

Owner hedef kararından sonra private `atlas-catalogs` bucket'ı Atlas MinIO'da oluşturuldu.
Çalışan runner `cleture-netzero-atlas-php-1`, disk `atlas_catalogs`, endpoint
`http://minio:9000`. Bucket policy sorgusu anonim erişim policy'si olmadığını doğruladı.
Container lifecycle veya ortak environment değişmedi.

- Manifest: `38de9ae94013840926af3e6a223188cfabd05e1c12fc4990cf4c11513c2f408c`, 9404 byte.
- Artifact: 25, toplam 937372 byte; her biri hedeften yeniden okundu.
- Retry: aynı manifest ve bütün artifact byte'ları aynı.
- Loader: unit 181 definition/694 conversion; geography 250 ülke/81 il/973 ilçe;
  currency 21; taxonomy 9 node/2 link; intended-use 3.
- `kg=proposed`, `K=ambiguous`, `TR=proposed`; üç amaç `registered` fakat kullanım ve
  publish false. `resolution=null`, current approval false.

Dosya başına gerçek read-back ve bütün exact katalog pinleri
[kanıt kaydında](evidence/admin-atlas-step6-readback-2026-09-07.json).
Admin bulguları ve güncel onay kanalı talepleri
[inceleme raporunda](admin-atlas-step6-review.md).

## Test sınırı

Sentetik fixture'lar `tests/fixtures/atlas-delivery` altında; Python generator ve hash
oracle üretici PHP canonicalizer'ından bağımsızdır. Sentetik çözüm/publish bağlantıları
gerçek Admin onayı veya bilimsel yayın değildir. Bu fixture'lar production bucket'ına
yazılmaz. `tests/Integration/AtlasDeliveryStorageTest.php` gerçek MinIO'da yalnız rastgele
`atlas-delivery-test-*` bucket oluşturur ve kendisi temizler; DB kullanmaz.

Test çalıştırmaları owner talebiyle timestamp'li geçici loga alınır. Başarısız test
düzeltmeleri AGENTS.md uyarınca ayrıca istenir. Güncel sonuç ve açık kapılar CURRENT'tadır.
