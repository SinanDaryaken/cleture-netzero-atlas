# NetZero Atlas

Atlas kaynak verisini alır, özgün dosyayı saklar, kaynak motoruyla parse/normalize eder ve birim/ülke eşleştirmeleriyle doğrudan Admin gelen faktörler alanına yazar.

## Çalışan akış

ADEME → acquire → parse → normalize → unit/geo → moduler_netzero → Admin inceleme

Platform komutu: cleture-netzero-atlas artisan atlas:source:prepare-admin ADEME

Kaynak satırları, alt gazlar, yaşam döngüsü bileşenleri, açık GWP/formül/PCI-PCS bilgileri ve kanıtları korunur. Kaynakta olmayan bilimsel bilgi uydurulmaz. Aynı kaynak kimliğiyle tekrar aktarım yeni kopya üretmez; Admin kararları ve düzenlemeleri korunur.

Paket üretme, Worker üzerinden taşıma, katalog teslimi ve karşılıklı onay sorgulama kaldırılmıştır. Acquire/parse/normalize/inspect komutları kaynak incelemesi için kalır. Candidate isimli kalan sınıflar ve sabit JSON sözleşmeleri mevcut normalizasyon dosyalarının biçim/kimlik uyumunu korur; paket aktarımını etkinleştirmez.

Merkezi şema sahibi Admin'dir. Kaynak işleme kayıtları Atlas DB'sinde, gelen faktörler merkezi DB'de tutulur. Admin onayı ve hesap tanımları Atlas tarafından değiştirilmez.

## Doğrulama

Servis durumunu cleture-netzero-atlas status ile kontrol edin. Testleri platform PHP runner'ıyla çalıştırın. Testler izole SQLite belleği ve sahte depolama kullanır; gerçek aktarım komutu geliştirme veritabanına yazar.

old-atlas/ salt-okunur referanstır. Eski paket/delivery ADR ve kanıtları tarihsel kayıttır; güncel çalışma yolu yukarıdaki doğrudan akıştır.
