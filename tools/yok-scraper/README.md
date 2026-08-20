# YÖK Veri Pipeline'ı

YÖK Yükseköğretim İstatistikleri portalından ham Excel tablolarını indirir,
normalize eder ve MongoDB'ye yükler.

## Neden tarayıcı otomasyonu?

[istatistik.yok.gov.tr](https://istatistik.yok.gov.tr) **ZK Framework** ile yazılmış,
tamamen sunucu durumlu (stateful) bir SPA. Pratikte şu anlama geliyor:

- **URL hiçbir tıklamada değişmiyor.** Deep-link, kalıcı rapor adresi yok.
- **İndirme ikonları `href` taşımıyor.** `<img id="qUzPr4" src="/images/xls.png">` gibi
  çıplak elemanlar; tıklama sunucuya bir `zkau` POST'u gönderiyor.
- **Dosya istek anında üretiliyor** ve yalnızca o oturuma ait, tek kullanımlık bir
  adresten sunuluyor:
  `/zkau/view/{desktopId}/dwnmed-N/{uuid}/2026_T028.xls`
- **Component ID'leri her oturumda değişiyor** (`iHBPg6` → `qUzPr4`), bu yüzden
  sabit seçici yazılamıyor; ikonlar her çalıştırmada yeniden keşfediliyor.
- Statik adres denemeleri (`/files/`, `/dosyalar/`, `/yuksekogretimIstatistikleri/…`)
  hepsi **404** döndü.

Sonuç: `requests`/`httpx` ile çekmek mümkün değil. Playwright zorunlu.

## Veri akışı

```
YÖK portalı (ZK SPA)
      │  Playwright · yılda bir veya elle tetiklenir
      ▼
data/raw/{yil}/*.xls          ~yıl başına 38 dosya   → .gitignore, repoya GİRMEZ
      │  xlrd ile ayrıştırma + doğrulama
      ▼
data/processed/*.ndjson.gz    ~birkaç MB             → repoya GİRER, versiyonlanır
      │  seed
      ▼
MongoDB                       → web uygulaması yalnızca buradan okur
```

Uygulama **çalışma anında YÖK'e hiç gitmiyor.** Veri yılda bir yayımlandığı için
(2025-2026 → 27.03.2026) canlı çekmenin bir faydası yok; portal düştüğünde site
çalışmaya devam ediyor.

## Kurulum

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m playwright install chromium
```

`playwright install` başarısız olursa (kurumsal ağ, indirme hatası) scraper
sistemde kurulu Google Chrome'a otomatik düşüyor — ek kurulum gerekmiyor.

## Kullanım

```bash
# Tüm yapılandırılmış yılları indir (config.YEARS)
./.venv/bin/python -m yok_scraper scrape

# Tek yıl
./.venv/bin/python -m yok_scraper scrape --yil 2025-2026

# Tarayıcıyı görünür çalıştır (hata ayıklama)
./.venv/bin/python -m yok_scraper scrape --headed

# Bir Excel'in sayfa/başlık yapısını dök (yeni ayrıştırıcı yazarken)
./.venv/bin/python -m yok_scraper inspect ../../data/raw/2025_2026/2026_T028.xls

# Ham .xls -> normalize NDJSON
./.venv/bin/python -m yok_scraper parse

# İşlenmiş veriyi MongoDB'ye yükle
./.venv/bin/python -m yok_scraper seed
```

## Kapsam

Portalda **13 öğretim yılı** (2013-2014 → 2025-2026) ve yıl başına **38 Excel
tablosu** var. `config.YEARS` şu an 5 yılla sınırlı; genişletmek için
`config.ALL_YEARS` listesinden doldurulabilir.

| Sekme | Tablo sayısı |
|---|---|
| ÖZET TABLOLAR | 8 |
| ÖĞRENCİ SAYILARI | 11 |
| ÖĞRETİM ELEMANLARI | 6 |
| MEZUN SAYILARI | 13 |

## Ayrıştırıcılar

Her tablonun kendi sayfa düzeni var, bu yüzden ayrıştırıcılar tablo kodu bazında
yazılıyor (`parse.AYRISTIRICILAR`).

| Kod | Tablo | Durum |
|---|---|---|
| `T028` | Öğretim elemanlarının akademik görevlerine göre sayıları | ✅ hazır |

Yeni bir tablo eklemek için: `inspect` ile düzeni gör → `ayristir_TNNN()` yaz →
`AYRISTIRICILAR` sözlüğüne ekle.

### Doğrulama

`T028` ayrıştırıcısı sonucu dosyanın **kendi "TOPLAM / TOTAL" satırıyla**
karşılaştırıyor. Kaynak dosyanın düzeni değişir de kolonlar kayarsa, sessizce
yanlış veri üretmek yerine hata veriyor.

### Bilinen kaynak veri sorunu

YÖK dosyalarında birebir tekrar eden birim satırları var (2025-2026'da 1 adet:
*Sakarya Uygulamalı Bilimler / Denizcilik MYO* — isim ve 18 sayının tamamı aynı).
Üniversite satırındaki resmi toplam bunları bir kez saydığı için ayrıştırıcı da
birebir kopyaları atlıyor ve atladığını raporluyor. Aynı isimli **ama farklı
sayılara sahip** satırlar (ör. *Kapadokya / İnsan ve Toplum Bilimleri Fakültesi*)
meşru kabul edilip korunuyor.

**Adı boş birim satırları.** Bazı üniversitelerin son birim satırında ad hücresi
boş ama sayılar gerçek (2024-2025'te 2 satır, 18 kişi). Bu satırlar atılmıyor,
`(BİRİM ADI BELİRTİLMEMİŞ)` etiketiyle korunuyor.

**Şehri boş kurum.** `İZMİR KONAK MESLEK YÜKSEKOKULU` (2025-2026, 116 kişi)
kaynakta şehirsiz geliyor. Ad içinde il adı geçse de tahmin yürütülmüyor;
şehir bazlı haritada bu kurum yer almıyor.

**Değişen tablo kodları.** YÖK 2024-2025'ten itibaren tablo kodlarını üç haneye
sıfırla doldurmaya başladı (`T28` → `T028`, `M1` → `M001`). Kodlar
`config.normalize_tablo_kodu` ile tek biçime indirgeniyor.

**İki dilli tür hücresi.** 2023-2024 ve öncesinde üniversite türü hücresi
`DEVLET STATE` / `VAKIF MYO FOUNDATION VOC. SCH.` biçiminde iki dilli geliyor;
sonraki yıllarda sade. Yıllar arası karşılaştırma için Türkçe kısma indirgeniyor.
