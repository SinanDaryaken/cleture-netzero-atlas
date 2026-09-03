# ADR 0027: Plastics Europe Eco-profile LCIA sınırı

## Durum

Kabul edildi — 28 Ağustos 2026.

## Bağlam

Plastics Europe Eco-profiles kataloğundaki birçok eski ürün sayfası ve indirme bağlantısı
artık çalışmıyor. Mart 2026 güncellemesinde ise ana sayfadan doğrulanabilen dört ZIP paket
erişilebilir durumdadır: PE/PP, CVM/PVC, steam cracker ve refinery. Paketler publisher
PDF'leri ile ILCD XML inventory process'lerini birlikte taşır. PDF'ler EF 3.1 / IPCC 2021
GWP100 sonuçlarını, XML'ler process UUID'sini ve 1 kg referans akışını sağlar. XML inventory
exchange'leri ecoinvent 3.11 background verisine dayanır; yayın sayfası bunların ticari,
hosted API veya yeniden dağıtım kullanımına açık bir lisans vermez.

## Karar

- Yalnız resmî ana sayfada çalışan ve doğrulanabilen dört Mart 2026 paketi ingest edilir.
- Publisher'ın PDF'de verdiği 28 climate-change toplamı canonical `LCA_RESULT` olur.
- ILCD XML yalnız process kimliği, isim ve 1 kg referans akışını doğrulamak için kullanılır;
  inventory exchange'lerinden Atlas içinde yeniden LCIA hesaplanmaz ve exchange'ler API'de
  sunulmaz.
- Sonuçlar Europe continental, cradle-to-gate, `kgCO2e/kg`, EF 3.1 / IPCC 2021 GWP100 ve
  characterization kullanım semantiğiyle tutulur; default inventory matching kapalıdır.
- PE/PP için 2024 referans yılı ve 2024–2029 geçerliliği, diğer paketler için 2023 referans
  yılı ve 2023–2028 geçerliliği publisher yayınından korunur.
- Erişilemeyen eski sayfalar, indirilemeyen legacy paketler ve açık lisans beyanı olmayan
  başka arşiv kopyaları kapsam dışıdır; değer veya satır sayısı tahmin edilmez.
- Açık commercial/API/raw yeniden dağıtım izni bulunana kadar bu izinler manifestte kapalı
  kalır.

## Sonuçlar

Atlas yalnız bugün yeniden üretilebilen, publisher tarafından yayımlanmış 28 sonucu taşır.
PDF sonucu ile XML referans akışı arasındaki çapraz kontrol provenance kalitesini artırır;
ancak embedded inventory'nin kendisi Atlas'ın dağıtılabilir veri yüzeyine dönüşmez. Eski
katalog sayfaları tekrar erişilebilir olursa yeni paketler ayrı bir kaynak kapsamı ve lisans
incelemesiyle eklenebilir; mevcut 2026 snapshot'ı geriye dönük değiştirilmez.
