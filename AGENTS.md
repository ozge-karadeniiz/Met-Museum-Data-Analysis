# MET Atlas — Ajan çalışma rehberi

Bu dosya repo, Trello ve BigQuery bağlamını bir araya getirir. Kullanıcının güncel
talimatları önceliklidir. İşin kapsamını koru; bir kartın varlığı sonraki aşamaları
başlatma yetkisi vermez. Kullanıcıyla Türkçe, kısa ve açık iletişim kur.

## Proje ve kaynaklar

Proje, The Metropolitan Museum of Art açık erişim koleksiyonunu temizlemek,
modellemek ve koleksiyonun dağılımını etkileşimli raporlarla incelemek içindir.
Temel konular departman, dönem, kültür, malzeme, edinim, kamu malı durumu,
galeri bilgisi ve sanatçı temsiliyetidir.

- Repo: <https://github.com/ozge-karadeniiz/Met-Museum-Data-Analysis>
- Ana iş panosu: [MET Atlas: Sanatın Veriyle Keşfi](https://trello.com/b/uFg0jEX1)
- Diğer pano: [MetProject](https://trello.com/b/8dRKvB7I). Şablon/örnek kartlar
  içerir; bunları MET projesinin gerçek gereksinimleri olarak yorumlama.
- [Proje özeti](https://trello.com/c/fjuBJqq0)
- [Teknoloji planı](https://trello.com/c/J2JdnSBG)
- [Metrik sözlüğü](https://trello.com/c/ErQ8JLfb)
- [Hipotezler](https://trello.com/c/JumY1SB7)

Planlanan akış: MET CSV → BigQuery ham veri → dbt staging/mart → Colab/Python
analizleri ve ML → Power BI ve Data Studio raporları. Raporlar aynı filtrelerde
aynı KPI tanımlarını ve sonuçlarını kullanmalıdır.

## BigQuery bağlantısı

- Google Cloud proje kimliği: **`the-met-open-access`**.
- BigQuery için doğrudan **`gcloud` ve `bq` kullan; BigQuery MCP kullanma**.
- Komutlarda projeyi açıkça belirt. Farklı bir projeye kendiliğinden geçme.
- Kurulu araç ve oturumu önce kontrol et; çalışan bağlantıyı gereksiz yere
  yeniden kurma veya yeni bir Google giriş akışı başlatma.
- Kimlik bilgilerini, tokenları ve yerel hesap bilgilerini repoya yazma.

2026-10-09 tarihinde CLI üzerinden doğrulanan kaynaklar:

| Kaynak | Tür | Bölge | Not |
| --- | --- | --- | --- |
| `the-met-open-access.met_data.met_objects` | Tablo | EU | Ham veri; 484.956 kayıt, 54 sütun |
| `the-met-open-access.met_data.stg_met_objects` | View | EU | Temizlenmiş staging katmanı |
| `the-met-open-access.met_data.mart_met_objects` | Tablo | EU | Analiz martı; 484.956 kayıt |
| `the-met-open-access.dbt_ozge` | Dataset | US | Ayrı dataset; `met_data` ile aynı bölge değildir |

Bu sayılar bir anlık doğrulama kaydıdır; yeni veri yüklenirse tekrar doğrula.
View metadatasındaki `numRows=0`, view'in boş olduğu anlamına gelmez.
`met_data` sorgularında EU bölgesini kullan. EU ve US kaynaklarını aynı sorguda
birleştirebileceğini varsayma; dbt hedef dataset/bölgesini çalıştırmadan doğrula.

Bağlantı ve metadata kontrolü için PowerShell komutları:

```powershell
gcloud auth list
gcloud config get-value project
bq --headless=true --project_id=the-met-open-access ls --datasets=true
bq --headless=true --project_id=the-met-open-access ls the-met-open-access:met_data
bq --headless=true --project_id=the-met-open-access show the-met-open-access:met_data.met_objects
```

Gerekirse tablo taramayan bir sorguyla bağlantıyı doğrula:

```powershell
bq --headless=true --project_id=the-met-open-access --location=EU query --use_legacy_sql=false --maximum_bytes_billed=0 'SELECT 1 AS connection_ok'
```

Sorguları mümkün olduğunca tam nitelikli tablo adlarıyla yaz. Maliyetli sorgudan
önce `--dry_run` ile tarama tahminini kontrol et ve uygun bir
`--maximum_bytes_billed` sınırı kullan. Ham tabloyu koru; istenen dönüşümleri
dbt modellerinde veya ayrı çıktılarda yap. Genel bir rehberdeki örnek dataset
oluşturma/yükleme/silme adımlarını bu projede kendiliğinden çalıştırma.

## Repo yapısı ve dbt

- `dbt_project.yml`: dbt proje adı hâlâ `my_new_project`, profil adı `default`.
  Bunlar mevcut ayarlardır; sırf şablon isimleri olduğu için değiştirme.
- `models/staging/stg_met_objects.sql`: ham tabloyu doğrudan
  `the-met-open-access.met_data.met_objects` üzerinden okur. Henüz `source()`
  kullanmaz. Cast, boş değer temizliği ve varsayılan etiketler bu katmandadır.
- `models/staging/schema.yml`: staging açıklamaları ve generic testler.
- `models/marts/mart_met_objects.sql`: `ref('stg_met_objects')` üzerinden okur;
  `materialized='table'` tanımlıdır. Dönem/sıralama, edinim/bağışçı,
  sanatçı demografisi ve eser türü/malzeme alanlarını türetir.
- `models/marts/schema.yml`: mart açıklamaları ve generic testler.
- `tests/assert_object_id_is_positive.sql`: staging içinde `object_id <= 0`
  kayıtlarını yakalayan singular test.
- `analyses/`, `macros/`, `seeds/`, `snapshots/`: mevcut dbt klasörleri.

Repoda `profiles.yml` yoktur. `dbt debug`/`dbt build` öncesinde yerel profilin
`default` adıyla, doğru proje, hedef dataset ve bölgeyle yapılandırıldığını
doğrula. `gcloud auth login` ile Application Default Credentials aynı şey
değildir; bq bağlantısının çalışması dbt/Colab ADC erişiminin de hazır olduğunu
kanıtlamaz. İlgili iş gerektiğinde ayrıca kontrol et.

## Veri ve metrik kuralları

- Eser düzeyi anahtar `object_id`'dir. Çok değerli sanatçı/etiket alanları
  açıldığında eser sayılarını `COUNT(DISTINCT object_id)` ile koru.
- NULL, boş metin ve yalnız boşluk içeren metinleri eksik kabul et. Staging'in
  `Unknown`, `Untitled`, `Anonymous / Unknown` gibi etiketleri eksikliği
  doldurur; veri kalitesi ölçerken bu dönüşümü hesaba kat.
- Oranları aynı filtre ve açık paydalarla hesapla. Hesaplanamayan oranı sıfır
  olarak gösterme; NULL/hesaplanamıyor durumunu koru.
- Departman payının paydası, departman filtresi dışında aynı filtreleri
  taşıyan tüm departmanlardaki eser sayısıdır.
- `is_on_view`, mevcut modelde galeri numarası doluluğundan türetilir.
  Boş galeri numarası eserin depoda olduğunu kanıtlamaz; `In Storage` etiketi
  modelin varsayılan metnidir. Grafik ve hipotezlerde bu sınırlamayı belirt.
- MÖ yıllarını koru. Ters tarih aralıklarını ve sıfır yıl kayıtlarını tarih
  hesaplarından önce incele. Metrik kartındaki 205 ters aralık ve 1.444 sıfır
  yıl bulgusunu güncel veride doğrulamadan sabit sonuç olarak kullanma.
- `AccessionYear` hem yıl hem tam tarih içerebilir. Staging'deki mevcut
  `SAFE_CAST(... AS INT64)` işleminin tam tarihleri kaybedebileceğini dikkate al.
- Bir eserde birden fazla sanatçı olabilir. Eser ve sanatçı sayımlarını
  ayır; isim/kimlik eşleşmesini doğrula.
- Edinim, bağışçı, dönem ve cinsiyet kategorileri türetilmiş kurallardır;
  kategorileri örnek ham kayıtlarla kontrol et. Model veya Trello açıklamasını
  doğrulanmış analitik sonuç gibi sunma.

## Trello planı ve analiz kapsamı

İş öncesinde ilgili MET Atlas kartını ve gerekli bağımlılıklarını kontrol et.
Trello'daki `Done` listesi veya tamamlandı bayrağı tek başına teslimat kanıtı
değildir; repo ve canlı BigQuery ile karşılaştır. Örneğin 07 numaralı kartta
planlanan `mart_met_kpis` ve köprü tabloları bu doğrulama sırasında repoda ve
`met_data` tablo listesinde bulunmuyordu.

2026-10-09 anlık planında metrik sözlüğü (03) devam ediyor; Power BI raporu
(08) ve ML adımları (10–12) To-Do'da, iki rapora ML ekleme (13) ve uçtan uca
sunum/doğrulama (14) Backlog'da. Yeni işe başlarken güncel kart durumunu oku.

Hipotezler: eski/yeni eserlerin kamu malı oranı, highlight eserlerde galeri
bilgisi, bağış/satın alma, alan bazında eksiklik, departmana göre galeri
bilgisi ve döneme göre malzeme kullanımı. Test edilmiş sonucu ve sınırlamalarını
ham hipotezden ayır; Colab çıktılarının repoda bulunduğunu varsayma.

ML hedefi `Department` sınıflandırmasıdır. Trello'nun 10–12 numaralı kartlarına
göre özellikler başlık, malzeme ve eser türü metinleridir. `Department`,
`Object_ID`, `Gallery_Number` ve `Credit_Line` özelliklere alınmaz. Sabit seed,
ayrı holdout ve mümkün olduğunca sanatçı gruplarını ayıran bölme kullan;
çoklu sanatçı/nadir sınıf kurallarını belgele. Dummy baseline ile TF-IDF +
Logistic Regression'ı macro-F1, accuracy, sınıf bazlı sonuçlar ve confusion
matrix üzerinden karşılaştır. Holdout değerlendirmesi ve tüm veri tahminlerini
ayır; ayrı tahmin tablosunda `object_id`, `predicted_department`, model sürümü
ve skor tanımı bulunsun. Yeniden çalıştırma tekrar kayıt üretmemelidir.

## Değişiklik ve doğrulama

- İstenen işi tamamlayan en küçük değişikliği yap; başka kişilerin
  değişikliklerini geri alma. Windows'ta native PowerShell kullan.
- SQL/model değişikliğinde ilgili schema açıklamalarını/testleri güncelle.
  Uygun dbt ortamı hazırsa `dbt debug`, ilgili model ve aşağı akış için
  `dbt build --select stg_met_objects+` çalıştır. Tam proje doğrulaması
  istendiğinde `dbt build` kullan. Bu komutlar hedef dataset'e yazar;
  yalnız yetkilendirilmiş modelleme/doğrulama işi kapsamında çalıştır.
- Başarılı kontrolleri yeni değişiklik veya çözülmemiş risk olmadan tekrarlama.
  Yalnız dokümantasyon değişikliği için bulutta dbt build çalıştırma;
  kaynaklarla tutarlılık ve `git diff --check` yeterlidir.
- Token, credential JSON, yerel profil, ham veri indirmeleri ve geçici
  kurulum dosyalarını commit etme. `target/`, `dbt_packages/`, `logs/`
  gibi üretilmiş çıktıları kaynak kodundan ayrı tut.
- Trello'ya yorum/mesaj yazmak, paylaşmak veya başka kişilere bildirim
  göndermek için açık kullanıcı talimatı gerekir.
- Yalnız ilgili dosyaları stage et. Kullanıcı aksi belirtmedikçe yeni dallarda
  `codex/` önekini kullan; commit/push/PR işlemlerini istenen kapsamda yap.
- Sonuçta neyin değiştiğini, hangi kontrollerin geçtiğini ve varsa gerçek
  engeli kısa biçimde bildir. Planlanan işleri tamamlanmış gibi gösterme.
