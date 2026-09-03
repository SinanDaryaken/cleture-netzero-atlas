# ADR-0002: V1 için sabit pipeline

Durum: Kabul edildi

## Karar

V1 pipeline sırası dokuz adımdır ve genel amaçlı DAG desteklenmez. Orchestrator kaynak
detayını bilmez; her adımı `AtlasSourceAdapter` sözleşmesi üzerinden çağırır.

## Gerekçe

Sabit sıra; idempotency, retry, audit ve partial retry semantiğini açık tutar. İlk beş
kaynak bu modelin yetersizliğini göstermeden DAG esnekliği eklenmeyecektir.
