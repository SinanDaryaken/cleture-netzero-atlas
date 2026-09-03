# Cleture Atlas v1 mimarisi

## Modüler monolit, ayrı process sınırları

İlk faz tek Python codebase'i kullanır; API, scheduler ve worker ayrı process olarak
çalışır. Bu seçim domain kontratlarını erken sabitlerken dağıtık sistem operasyonunu
gereksiz yere büyütmez. PostgreSQL system of record, Redis iş koordinasyonu, MinIO ise
immutable raw ve ara artifact deposudur.

```text
FastAPI / Scheduler
        │
        ▼
 Postgres + Outbox ──► Redis queue ──► Stateless worker
        │                                  │
        │                                  ▼
        └──────────────────────────── Postgres state
                                           │
                                           ▼
                                     MinIO artifacts
```

## Katmanlar ve bağımlılık yönü

```text
apps → api/orchestration/ingestion → domain + ports ← infrastructure
sources/<code> → ingestion contracts + domain
```

- `domain`: source observation, curated factor, source, run, quality ve provenance
  kavramları.
- `ports`: database, queue, object storage, clock ve adapter kontratları.
- `ingestion`: manifest registry ve generic adapter tabanı.
- `orchestration`: sabit pipeline state machine, retry ve review kapıları.
- `infrastructure`: PostgreSQL, Redis ve S3/MinIO implementasyonları.
- `sources`: yalnız kaynağa özel manifest, parser, mapping, fixture ve testler.

## Güvenilirlik kuralları

1. Run, source + detected revision için idempotency key taşır.
2. Queue teslimatı at-least-once kabul edilir; step claim işlemi atomik olmalıdır.
3. Raw key checksum içerir ve var olan nesne overwrite edilmez.
4. Her step sonucu ve hata sınıfı ayrı kaydedilir.
5. Retry yalnız retryable altyapı hatalarında uygulanır.
6. Dataset/factor/mapping/parser sürümleri append-only tutulur.
7. `PUBLISHED` görünümü yalnız onaylanmış dataset version'larını okur.
8. Factor coğrafi kökeni ile uygulanabilir coğrafyaları ayrı tutulur; source country
   otomatik applicability değildir.
9. Factor değer türü ile kullanım amacı ayrı tutulur; varsayılan matching yalnız
   `co2e_total + inventory` kayıtlarını kullanır.
10. Geography matching exact → country-specific → country-modelled → regional →
    continental → global → proxy sırasını izler ve fallback'i response'ta açıklar.
11. Gaz emisyon faktörü, toplam CO2e ve calculation parameter aynı semantik tür değildir;
    yalnız `co2e_total + inventory` varsayılan matching'e girer.
12. Session-scoped veya volatile exportlarda raw checksum yanında deterministik veri
    fingerprint'i tutulur; değişiklik algılama paket metadata'sına bağlanmaz.
13. Source status (`valid`, `archived`, vb.) canonical publication statusuyla
    karıştırılmaz; archived source rows raw/parsed katmanda kalır ve version diff'te
    removal olarak izlenir.
14. Negatif değer otomatik veri hatası değildir. Kaynak semantiği avoided-emissions veya
    sequestration ise açık intended-use ile saklanır ve inventory matching'den çıkarılır.
15. Parsed numeric source observation ile kullanıcıya sunulan curated factor ayrı
    persistence katmanlarıdır. Activity data, emission result ve henüz normalize edilmemiş
    implied factor hücreleri `atlas_source_observations` içinde kalır; `atlas_factors`
    yalnız hesaplama ve matching sözleşmesini tamamlayan logical factor'ları taşır.
16. Düzenleyici bir kaynak base default ile yıl/işlem anında uygulanan katsayıyı ayrı
    tanımlıyorsa katsayı canonical factor'a gömülmez; calculation methodology ve legal
    provenance içinde açıkça taşınır.
17. Kaynak, CH₄/N₂O dönüşümünde olay tarihinde yürürlükte olan GWP sürümünü zorunlu
    tutuyorsa bileşen gaz factor'ı ingest sırasında CO₂e'ye çevrilmez; event-time GWP
    seçimi calculation katmanının açık sorumluluğudur.

Detaylı zorunlu sözleşmeler için [non-negotiables.md](non-negotiables.md), geography
kararı için [ADR-0005](adr/0005-geography-origin-applicability.md), factor semantiği
için [ADR-0006](adr/0006-factor-value-semantics.md) kullanılır.
Geographic coverage ve fallback kararı [ADR-0007](adr/0007-geographic-coverage-engine.md)
ile tanımlanır.
IPCC EFDB ingestion ve calculation-parameter kararı
[ADR-0008](adr/0008-ipcc-efdb-parameters.md) ile tanımlanır.
ADEME Base Carbone source/version/negative-value kararı
[ADR-0009](adr/0009-ademe-base-carbone.md) ile tanımlanır.
Source observation ve curated factor ayrımı
[ADR-0017](adr/0017-source-observation-factor-separation.md) ile tanımlanır.
GHG Protocol Cross-sector workbook gaz, conversion ve geography sınırları
[ADR-0020](adr/0020-ghg-protocol-cross-sector-workbook.md) ile tanımlanır.
EU CBAM default-values, benchmark ve regulatory-markup sınırları
[ADR-0021](adr/0021-cbam-default-values-benchmarks.md) ile tanımlanır.
Canada federal offset factor, event-time GWP ve protocol-parameter sınırları
[ADR-0022](adr/0022-canada-offset-emission-factors.md) ile tanımlanır.
ETKB Türkiye electricity inventory factor ve avoided-emissions grid-margin ayrımı
[ADR-0023](adr/0023-etkb-turkiye-electricity-factors.md) ile tanımlanır.

Unit ontology ve reciprocal factor-conversion kararı
[ADR-0030](adr/0030-unit-intelligence.md) ile; database-backed multilingual concepts,
PostgreSQL-first search ve calculation-profile policy kararı
[ADR-0031](adr/0031-semantic-search-profiles.md) ile tanımlanır.
Country-aware product recommendation projection ve fallback kararı
[ADR-0034](adr/0034-recommendation-serving-layer.md) ile tanımlanır.

## Intelligence sorgu akışı

```text
Published factors + observations
              │
              ├── Unit registry → exact/conditional/incompatible conversion
              ├── Canonical concepts → DB translations + synonyms
              └── Calculation profiles → search/calculation eligibility
                                      │
                                      ▼
                              PostgreSQL FTS/trigram
                                      │
                         catalog search
                              │
                              ▼
                  recommendation applicability projection
                              │
             country + profile + family fallback policy
                              │
                              ▼
                   recommendation + calculation plan
```

- `atlas_unit_definitions`, aliases ve factor-unit expressions original unit text'i
  değiştirmeden boyutsal sorgu katmanı oluşturur.
- `atlas_concepts`, `atlas_concept_labels` ve `atlas_factor_concepts` language-independent
  retrieval sağlar. YAML yalnız version-controlled seed'dir; kalıcı/runtime label yüzeyi
  PostgreSQL'dir.
- Search katalog/developer keşfidir. Product seçimi yalnız `/v1/recommendations` üzerinden
  yapılır; suggest/strict davranışı aynı versioned policy ve projection'ı kullanır.
- `atlas_factor_applicabilities` source fact'i değiştirmeyen serving metadata'sıdır.
- `atlas_sectors`, label ve category registry'leri ortak business-sector dilini;
  `atlas_factor_sector_assignments` ise her historical/current factor version için
  yeniden üretilebilir, source taxonomy'yi değiştirmeyen sektör projeksiyonunu sağlar.
  Bu sınır [ADR-0037](adr/0037-sector-registry-and-factor-projection.md) ile tanımlanır.
  Projection concept, role, scope, basis, boundary, qualifier ve fallback sınıfını taşır.
- Geography sırası ülkeye özgüdür. Ülke otorite override'ı bulunmayan ISO kodlarında generic
  exact-country → regional → global sırası çalışır; foreign proxy açık kabul gerektirir.
- Unit, concept, geography ve calculation policy registry version'ları response metadata ve
  audit kararlarında taşınır.
- `/explorer`, aynı process tarafından sunulan zero-build bir developer istemcisidir. Domain
  veya repository katmanına doğrudan erişmez; yalnız public API contract'larını compose eder.
  Facility ID çözümü ve activity × factor preview'ı UI orchestration olarak açıkça gösterilir;
  end-to-end calculation API'si varmış gibi sunulmaz.

## İlk veri akışı

```text
CHECK → FETCH → STORE_RAW → PARSE → NORMALIZE → VALIDATE
      → COMPARE → VERSION → PUBLISH
```

`CHECK` değişiklik bulmazsa kalan adımlar `SKIPPED` olur. `VALIDATE` veya `COMPARE`
review gerektirirse aday `VERSION` ile append-only olarak kaydedilir, review kaydı
açılır ve yalnız `PUBLISH` atlanır. Bu sayede reviewer gerçek dataset/factor version'ı
üzerinde karar verir. Beklenmeyen hata step'i `FAILED` yapar; orchestrator hatayı
retryable/non-retryable olarak sınıflandırır.
