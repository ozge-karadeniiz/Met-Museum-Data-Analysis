<img width="700" height="466" alt="image" src="https://github.com/user-attachments/assets/eef13124-9f8d-428f-97b8-eeee2bfe4b4e" />




# The Met Museum Atlas: The Metropolitan Museum of Art Open Access Analytics

Bu proje, The Metropolitan Museum of Art (The Met) Açık Erişim koleksiyon verilerini kullanarak modern veri ambarı, boyutsal veri modelleme ve iş zekası süreçlerini bir araya getiren kapsamlı bir veri analitiği çalışmasıdır.

---

## 🇹🇷 Türkçe Proje Özeti

### Proje Hakkında
MET ATLAS, 5.000 yılı aşkın insanlık tarihine ve dünya kültür mirasına ait yüz binlerce sanat eserinin dijital verisini incelemektedir. Projenin temel amacı; müze koleksiyonunun tarihsel edinim süreçlerini, departmanlar ve coğrafi bölgeler arasındaki dağılımını, sanatçı demografisini ve eserlerin kamu malı (Public Domain) telifsiz erişilebilirlik oranlarını ortaya koymaktır.

### Veri Mimarisi ve Yöntem
* **Veri Depolama:** Ham veriler bulut tabanlı veri ambarı Google BigQuery üzerinde yapılandırılmıştır.
* **Veri Modelleme (dbt):** Ham tablolardaki tutarsızlıklar temizlenmiş; dbt aracılığıyla staging, intermediate ve marts katmanları oluşturularak analize hazır bir Yıldız Şeması (Star Schema) kurulmuştur. Veri kalitesi otomatik testlerle güvence altına alınmıştır.
* **Keşifçi Analiz ve Modelleme (Python):** Eserlerin yapım teknikleri, boyutları ve dönemleri arasındaki örüntüler Python kütüphaneleriyle incelenmiş ve kümeleme analizleri uygulanmıştır.
* **İş Zekası ve Raporlama (Power BI):** Elde edilen boyutsal modeller üzerinden küratörler, araştırmacılar ve yöneticiler için etkileşimli KPI panelleri tasarlanmıştır.

### Öne Çıkan Analiz Bulguları
* **Koleksiyon Büyümesi:** Müzenin belirli dönemlerde edindiği eser yoğunlukları ve bağış/satın alma trendleri haritalandırılmıştır.
* **Kültürel Temsil:** Departmanlar bazında farklı coğrafya ve uygarlıkların koleksiyon içindeki ağırlıkları ve dönem dağılımları karşılaştırılmıştır.
* **Açık Erişim:** Eserlerin telif durumları ve dijitalleştirilerek kamuya açılma oranları departman düzeyinde ölçülmüştür.
  
<img width="1548" height="993" alt="Screenshot_1" src="https://github.com/user-attachments/assets/7e2775d7-7635-4e4c-b21c-90669d4e6813" />
<img width="1541" height="986" alt="Screenshot_2" src="https://github.com/user-attachments/assets/c1c8de4b-5be9-412d-a721-c721a146bbee" />
<img width="1723" height="966" alt="Screenshot_3" src="https://github.com/user-attachments/assets/fccdb703-bdd6-4f87-877b-dce7b7fce774" />
<img width="1729" height="955" alt="Screenshot_4" src="https://github.com/user-attachments/assets/f07e0ae8-ac47-4ad1-849f-38a9c33ee47d" />

---

## 🇬🇧 English Project Overview

### About The Project
MET ATLAS is an end-to-end data analytics and dimensional modeling project built on The Metropolitan Museum of Art Open Access dataset. The project explores over 5,000 years of global cultural heritage, focusing on historical collection growth, curatorial department dynamics, geographic distribution, artist demographics, and public domain accessibility.

### Pipeline & Methodology
* **Cloud Warehouse:** Raw museum collections are structured within Google BigQuery.
* **Data Modeling (dbt):** Automated transformations and data cleansing are managed through dbt across staging, intermediate, and marts layers, resulting in an analytics-ready Star Schema verified by data quality tests.
* **Exploratory Analytics (Python):** Python is utilized for exploratory data analysis and unsupervised clustering to reveal hidden patterns across mediums, dimensions, and eras.
* **Visualization (Power BI):** Interactive dashboards provide executive and curatorial metrics, tracking acquisition timelines, collection diversity, and open-access statistics.

### Key Analytical Insights
* **Acquisition Patterns:** Mapping key eras of collection growth and acquisition dynamics across decades.
* **Geographic Balance:** Measuring the representation of diverse global civilizations and historical eras across departments.
* **Open Access Impact:** Quantifying digital accessibility and rights metadata across museum wings.

---

### 🙏 Teşekkür ve Kaynak / Acknowledgments
Bu çalışmada kullanılan veriler, kültürel mirası dünyayla paylaşan **The Metropolitan Museum of Art Open Access** girişimi tarafından sağlanmıştır. Değerli veri setini açık erişime sunan The Met ekibine teşekkür ederiz.

* **Veri Kaynağı / Data Source:** [The Met Open Access GitHub Repository](https://github.com/metmuseum/openaccess)
