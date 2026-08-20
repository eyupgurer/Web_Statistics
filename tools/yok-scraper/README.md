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

# Portalda yeni bir öğretim yılı çıktı mı (yeni yıl varsa çıkış kodu 2)
./.venv/bin/python -m yok_scraper years
```

### Deterministik çıktı

`parse` çıktısı bayt bayt tekrarlanabilir olmak zorunda: gzip varsayılan olarak
başlığa yazma zamanını ve dosya adını gömüyor, bu yüzden aynı veri iki kez
işlendiğinde dosyalar farklı çıkıyordu. Zamanlanmış iş akışı da bunu "veri
değişti" sanıp her çalıştığında boş bir pull request açardı. `mtime=0` ve
`filename=""` ile her iki alan da devre dışı.

## Kapsam

Portalda **13 öğretim yılı** (2013-2014 → 2025-2026) ve yıl başına ~40 Excel
tablosu var; `config.YEARS` bunların tamamını kapsıyor. Yeni bir yıl
yayımlandığında `years` komutu haber veriyor.

Uygulamanın gösterdiği yıl listesi elle tutulmuyor: MongoDB'deki koleksiyon
adlarından okunuyor, yani `seed` çalıştığında menüde kendiliğinden beliriyor.

| Sekme | Tablo sayısı |
|---|---|
| ÖZET TABLOLAR | 8 |
| ÖĞRENCİ SAYILARI | 11 |
| ÖĞRETİM ELEMANLARI | 6 |
| MEZUN SAYILARI | 13 |

## Ayrıştırıcılar

Her tablonun kendi sayfa düzeni var, bu yüzden ayrıştırıcılar tablo kodu bazında
yazılıyor (`parse.AYRISTIRICILAR`).

| Kod | Tablo | Koleksiyon |
|---|---|---|
| `T028` | Öğretim elemanlarının akademik görevlerine göre sayıları | `YOI_ogretim_elemani_akademik_gorev_sayilari` |
| `T035` | Yabancı uyruklu öğretim elemanları | `YOI_yabanci_uyruklu_ogretim_elemani` |
| `T012` | Önlisans ve lisans düzeyinde öğrenci sayıları | `YOI_ogrenci_sayilari` |
| `M005` | Mezun sayıları | `YOI_mezun_sayilari` |
| `T107` | Türlerine göre akademik birim sayıları | `YOI_akademik_birim_sayilari` |

Portalda yıl başına ~42 tablo var; yukarıdakiler menüdeki dört veri grubunu
karşılayanlar. Yeni bir tablo eklemek için: `inspect` ile düzeni gör →
plan tanımla → `AYRISTIRICILAR` sözlüğüne ekle.

### Ortak yürüyüş

`T028`, `T035`, `T012` ve `M005` aynı "üniversite + birim" düzenini paylaşıyor:
tür kolonu dolu olan satır yeni bir kurum başlatır, boş olanlar ona ait birimdir.
Değişen tek şey kolon yerleşimi, o da `TabloPlani` ile tanımlanıyor. `T107`
üniversite kırılımı taşımadığı için ayrı bir ayrıştırıcı kullanıyor.

### Otomatik düzen çözümleme

Kolon indeksleri sabit yazılmıyor. Ayrıştırıcı önce `E | K | T` başlık satırını
bulup plandaki indeksleri gerçek dosyaya göre kaydırıyor. Buna ihtiyaç var:
2021-2022'nin `T35` dosyasında fazladan bir ilçe kolonu var ve başlıklar bir
satır aşağıda — aynı tablonun diğer yıllarındaki düzenden farklı. Sabit indeksle
okunsaydı sessizce yanlış kolonlar alınırdı.

### Doğrulama

Her ayrıştırma sonucu dosyanın **kendi "TOPLAM / TOTAL" satırıyla**
karşılaştırılıyor. Sapma iki şekilde raporlanıyor:

- **`! DOĞRULAMA HATASI`** — sapma %0,01'den büyük. Kolon kayması ya da yanlış
  satır okuma anlamına gelir, ayrıştırıcı bozulmuştur.
- **`· kaynak toplamı tutmuyor`** — sapma birkaç kişilik. Kaynak dosyanın kendi
  aritmetiği tutmuyor demektir; ayrıştırıcı sadıktır.

İkisini ayırmak, gerçek bir ayrıştırma hatasının kaynak gürültüsünde
kaybolmaması için.

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

**Adı boş kurumlar.** `M005`'te alfabetik listenin sonunda adı yazılmamış
kurumlar var (2025-2026'da 8 adet). Sayıları gerçek; `(KURUM ADI BELİRTİLMEMİŞ) N`
etiketiyle korunuyorlar.

**Ulusal toplamın tutmadığı yıl.** 2024-2025 `M005` dosyasında YÖK'ün kendi
ulusal toplamı, parçalarının toplamından 3 kişi eksik. Her üniversite bloğu
kendi içinde tutarlı; tutarsızlık kaynağın kendisinde.

**Şehri boş kurum.** `İZMİR KONAK MESLEK YÜKSEKOKULU` (2025-2026, 116 kişi)
kaynakta şehirsiz geliyor. Ad içinde il adı geçse de tahmin yürütülmüyor;
şehir bazlı haritada bu kurum yer almıyor.

**Değişen tablo kodları.** YÖK 2024-2025'ten itibaren tablo kodlarını üç haneye
sıfırla doldurmaya başladı (`T28` → `T028`, `M1` → `M001`). Kodlar
`config.normalize_tablo_kodu` ile tek biçime indirgeniyor.

**İki dilli tür hücresi.** 2023-2024 ve öncesinde üniversite türü hücresi
`DEVLET STATE` / `VAKIF MYO FOUNDATION VOC. SCH.` biçiminde iki dilli geliyor;
sonraki yıllarda sade. Yıllar arası karşılaştırma için Türkçe kısma indirgeniyor.
