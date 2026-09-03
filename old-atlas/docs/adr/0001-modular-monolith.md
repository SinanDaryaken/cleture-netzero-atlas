# ADR-0001: Modüler monolit ve ayrı process'ler

Durum: Kabul edildi

## Karar

V1 tek Python repository ve tek domain modeli kullanır. API, scheduler ve worker ayrı
process olarak deploy edilir; PostgreSQL, Redis ve MinIO ortak altyapıdır.

## Gerekçe

67 kaynağın asıl karmaşıklığı source/parsing/data-quality alanındadır. Erken servis
parçalama transaction, deployment ve contract koordinasyonunu büyütür. Port sınırları
ileride yoğun workload'ların ayrılmasına izin verir.
