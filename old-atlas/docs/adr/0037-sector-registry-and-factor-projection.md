# ADR-0037 — Merkezi sektör registry'si ve factor sektör projeksiyonu

## Durum

Kabul edildi — 2026-08-30

## Bağlam

Atlas kaynak kayıtlarını source-faithful biçimde korurken her kaynak farklı kategori
dili kullanır. ADEME kategori yolları, Open CEDA ekonomik sektör kodları, LCA ürün
sınıfları ve inventory taxonomy'leri aynı iş filtresinde doğrudan karşılaştırılamaz.
Source taxonomy'yi yeniden yazmak provenance kaybına; yalnız factor adıyla sektör
tahmini yapmak ise sessiz yanlış sınıflandırmaya yol açar.

## Karar

- İş sektörleri `atlas_sectors`, çok dilli adları `atlas_sector_labels`, kontrollü alt
  kategorileri `atlas_sector_categories` içinde versioned registry olarak tutulur.
- Her factor version için tam bir adet primary `atlas_factor_sector_assignments` kaydı
  üretilir. Bu kayıt source fact değil, yeniden üretilebilir serving projeksiyonudur.
- İlk registry on iş sektörünü kapsar: Consumer Goods and Services; Materials and
  Manufacturing; Energy; Restaurants and Accommodation; Transport; Buildings and
  Infrastructure; Agriculture/Hunting/Forestry/Fishing; Land Use; Waste; Water.
- Refrigerant, methodology ve gerçekten sektörler arası kayıtları yanlış bir iş
  sektörüne zorlamamak için `Cross-sector / General` ayrı bir kontrollü sınıftır.
- Crosswalk kaynak adına göre branch etmez. Canonical taxonomy root'u ve Open CEDA'nın
  taxonomy içinde korunan ekonomik faaliyet kodu kullanılır. Source taxonomy, category
  ve raw payload değiştirilmez.
- Deterministik kurallar `approved`, tam eşleşmeler yüzde 100 confidence taşır. Bilinmeyen
  taxonomy sessizce başka sektöre atanmaz; `cross_sector/general`, düşük confidence ve
  açık fallback rule ile görünür.
- Migration bütün historical/current factor version'ları backfill eder. Yeni ingest aynı
  policy ile assignment üretir. Coverage kapısı factor version sayısı ile assignment
  sayısının eşitliğini ve mapping version güncelliğini zorunlu tutar.

## Sonuçlar

`GET /v1/sectors` sektör ve kategori dağılımını, `GET /v1/factors?sector=&category=`
source-faithful katalog filtresini sağlar. Admin rebuild/coverage uçları ve CLI komutları
policy değişikliklerini operasyonel olarak yeniden üretir. Recommendation family,
calculation context ve GHG scope bu sektörden ayrı kalır; sektör bunların yerine geçmez.
