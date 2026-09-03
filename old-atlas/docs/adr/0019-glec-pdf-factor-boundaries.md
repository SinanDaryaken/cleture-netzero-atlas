# ADR-0019 — GLEC PDF ingestion ve factor sınırları

## Durum

Kabul edildi — 28 Ağustos 2026.

## Bağlam

GLEC Framework v3.2, yakıtların WTT/TTW/WTW değerlerini, taşıma ve hub yoğunluklarını,
soğutucu GWP100 değerlerini ve soğutucu kayıp varsayımlarını aynı PDF yayını içinde
sunuyor. Bu değerlerin tümünü sıradan emission factor olarak düzleştirmek lifecycle
bileşenlerini çift sayar ve characterization sonuçlarını inventory matching'e sokar.
Yayın, eğitim/non-profit çoğaltmaya atıfla izin verir; ticari kullanım için yazılı izin
ister.

## Karar

- Source-specific PDF koordinat kontratı `sources/glec` altında kalır ve yalnız resmî
  183 sayfalık v3.2 düzenini kabul eder.
- Fuel ve transport/hub tablolarında yalnız son kullanıcı WTW toplamı canonical emission
  factor olur. WTT, TTW, base WTW ve aggregate değerleri methodology detayında korunur.
- Non-container sea factor'larında kaynak tablonun son kullanıcıya yönelik %15 distance
  adjustment uygulanmış WTW değeri kullanılır; adjustment açıkça provenance'da tutulur.
- Refrigerant GWP100 değerleri `CHARACTERIZATION_RESULT` ve characterization intended-use
  ile saklanır; default inventory matching'e girmez.
- Refrigerant charge/leakage varsayımları `CALCULATION_PARAMETER` source observation'dır.
  Numeric GWP değeri olmayan R-717 parsed history'de korunur fakat canonical factor olmaz.
- PDF raw dosyası repository'ye vendored edilmez; runtime resmî versioned URL'den indirir,
  immutable raw storage'a content-addressed kaydeder.
- Manifest commercial/API/raw distribution izinlerini `false` tutar. Local reference
  publication owner review ile onaylanabilir; bu onay harici ticari yeniden dağıtım hakkı
  vermez.

## Sonuçlar

Atlas aynı lifecycle toplamını bileşenleri nedeniyle çoğaltmaz; lojistik inventory,
characterization ve hesaplama parametresi semantiği ayrık kalır. PDF layout değişiklikleri
sessiz veri bozulması yerine kalıcı ingestion hatası üretir. Yeni GLEC yayını geldiğinde
page/marker/table kontratı yeniden denetlenmeli ve parser version yükseltilmelidir.
