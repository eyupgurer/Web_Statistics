# YÖK İstatistikleri

Türkiye'deki yükseköğretim kurumlarına ait YÖK istatistiklerini toplayan,
normalize eden ve grafiklerle sunan bir web uygulaması.

Veriler [YÖK Yükseköğretim Bilgi Yönetim Sistemi](https://istatistik.yok.gov.tr)
üzerinden alınır, Excel tablolarından ayrıştırılıp MongoDB'ye yüklenir.

## Neler var

- **Üniversite listesi** — şehir, tür ve ada göre filtreleme
- **Üniversite detayı** — akademik unvan ve cinsiyet kırılımında öğretim elemanı sayıları
- **Karşılaştırma** — iki üniversiteyi yan yana grafiklerle kıyaslama
- **Şehir bazlı harita** — Türkiye haritası üzerinde öğretim elemanı dağılımı
- **Çok yıllı veri** — 2021-2022'den 2025-2026'ya

## Mimari

```
YÖK portalı (ZK Framework SPA)
      │  Playwright · yılda bir çalışır
      ▼
data/raw/*.xls              ham Excel      → .gitignore, repoya girmez
      │  xlrd ile ayrıştırma + doğrulama
      ▼
data/processed/*.ndjson.gz  normalize veri → repoda versiyonlanır
      │  seed
      ▼
MongoDB  ←  ASP.NET Core MVC uygulaması
```

Uygulama **çalışma anında YÖK'e istek atmaz.** YÖK verisi yılda bir yayımlandığı
için (2025-2026 → 27.03.2026) veri toplama ayrı bir pipeline olarak çalışır;
portal erişilemez olduğunda site çalışmaya devam eder.

Pipeline'ın ayrıntıları ve YÖK portalının neden tarayıcı otomasyonu gerektirdiği:
[`tools/yok-scraper/README.md`](tools/yok-scraper/README.md)

## Teknolojiler

| Katman | Teknoloji |
|---|---|
| Web | ASP.NET Core MVC (.NET 9) |
| Veritabanı | MongoDB 7 |
| Grafikler | Google Charts (GeoChart, BarChart, PieChart) |
| Arayüz | Bootstrap 5 |
| Veri pipeline | Python 3 · Playwright · xlrd |

## Kurulum

### Gereksinimler

- [.NET 9 SDK](https://dotnet.microsoft.com/download)
- [Docker](https://www.docker.com/) (MongoDB için)
- Python 3.11+ (yalnızca veriyi yeniden çekmek isterseniz)

### 1. MongoDB'yi başlatın

```bash
docker compose up -d
```

MongoDB `localhost:27017`, web tabanlı yönetim arayüzü (mongo-express)
`http://localhost:8081` adresinde çalışır.

### 2. Veriyi yükleyin

Repodaki işlenmiş veriyi MongoDB'ye aktarın:

```bash
cd tools/yok-scraper
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m yok_scraper seed
```

### 3. Uygulamayı çalıştırın

```bash
dotnet run
```

http://localhost:5220 adresinde açılır.

## Veriyi yeniden çekmek

Yalnızca YÖK yeni bir öğretim yılı yayımladığında gerekir:

```bash
cd tools/yok-scraper
./.venv/bin/python -m playwright install chromium
./.venv/bin/python -m yok_scraper scrape    # ham .xls indir
./.venv/bin/python -m yok_scraper parse     # normalize et
./.venv/bin/python -m yok_scraper seed      # MongoDB'ye yükle
```

## Proje yapısı

```
Controllers/         MVC controller'ları
Models/              Veri modelleri (Universite, Birim, SehirVeriViewModel)
Services/            IstatistikServisi — tüm veri erişiminin tek noktası
Views/               Razor görünümleri
wwwroot/             Statik dosyalar
data/processed/      Normalize edilmiş veri (repoda)
data/raw/            Ham Excel dosyaları (repoda değil)
tools/yok-scraper/   Python veri pipeline'ı
docker-compose.yml   MongoDB + mongo-express
```

## Veri kaynağı

Tüm veriler YÖK'ün kamuya açık Yükseköğretim İstatistikleri yayınlarından
alınmıştır. Veriler Resmî İstatistik Programı kapsamında yayımlanmaktadır.
Bu proje YÖK ile ilişkili değildir.
