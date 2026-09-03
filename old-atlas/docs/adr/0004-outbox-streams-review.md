# ADR-0004: Transactional outbox, Redis Streams ve publish review kapısı

Durum: Kabul edildi

## Karar

Run talebi ve outbox olayı PostgreSQL içinde aynı transaction'da oluşturulur.
Dispatcher pending outbox kayıtlarını Redis Stream'e taşır; stateless worker consumer
group ile at-least-once teslim alır ve source bazında PostgreSQL advisory lock kullanır.

İlk dataset ve kalite/comparison anomalileri önce append-only dataset/factor version
olarak kaydedilir. Review kaydı onaylanana kadar `PUBLISH` çalışmaz ve public API bu
version'ı göstermez.

## Gerekçe

Outbox, veritabanı run state'i ile queue dispatch arasındaki kayıp-event boşluğunu
kapatır. Redis Streams consumer group yatay worker ölçeklemesini ve stale job reclaim'i
sağlar. Version-before-review yaklaşımı reviewer'a sabit ve tamamen provenance'lı bir
aday sunarken şüpheli verinin production API'ye sızmasını engeller.
