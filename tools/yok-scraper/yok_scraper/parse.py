"""Ham .xls dosyalarını uygulamanın beklediği belge şemasına dönüştürür.

YÖK dosyaları OLE2 formatında eski .xls (Excel 97-2003) — openpyxl bunu
okuyamaz, xlrd 2.x tam olarak bu formatı destekler.

Tablolar çok satırlı ve birleşik hücreli başlıklar taşıyor; kolon eşlemesi
sabit indekse değil, her tablo için doğrulanmış bir plana dayanıyor.
"""

from __future__ import annotations

import gzip
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import xlrd

from . import config


# ---------------------------------------------------------------- inceleme

def incele(yol: Path, satir_sayisi: int = 25) -> None:
    """Bir .xls dosyasının sayfa ve başlık yapısını ekrana döker.

    Yeni bir ayrıştırıcı yazmadan önce gerçek düzeni görmek için.
    """
    kitap = xlrd.open_workbook(yol, formatting_info=False)
    print(f"Dosya   : {yol.name}  ({yol.stat().st_size/1024:.0f} KB)")
    print(f"Sayfalar: {kitap.sheet_names()}")

    for sayfa in kitap.sheets():
        print(f"\n--- '{sayfa.name}'  {sayfa.nrows} satır x {sayfa.ncols} kolon ---")
        if sayfa.merged_cells:
            print(f"Birleşik hücre sayısı: {len(sayfa.merged_cells)} (ilk 8: {sayfa.merged_cells[:8]})")
        for r in range(min(satir_sayisi, sayfa.nrows)):
            hucreler = []
            for c in range(min(sayfa.ncols, 24)):
                d = sayfa.cell_value(r, c)
                if isinstance(d, float) and d.is_integer():
                    d = int(d)
                metin = str(d).strip().replace("\n", " ")
                hucreler.append(metin[:18] if metin else "·")
            print(f"  r{r:<3} | " + " | ".join(hucreler))


# ---------------------------------------------------------------- yardımcılar

DIPNOT_IZLERI = ("Resmi İstatistik Programı", "Üniversitenin Yurtiçi", "İlgili akademik birim")
TOPLAM_IZI = "TOPLAM"
ADSIZ_BIRIM = "(BİRİM ADI BELİRTİLMEMİŞ)"

# 2023-2024 ve öncesinde tür hücresi iki dilli geliyor ("DEVLET STATE",
# "VAKIF MYO FOUNDATION VOC. SCH."); 2024-2025'ten itibaren sade ("DEVLET").
TUR_ONEKLERI = ("VAKIF MYO", "VAKIF", "DEVLET")

# Ayrıştırma sırasında atlanan tekrar satırları (şeffaflık için raporlanır)
_TEKRARLAR: list[str] = []


def _sayi(deger) -> int | None:
    """Hücreyi tam sayıya çevirir; boş/anlamsızsa None döner."""
    if deger is None or deger == "":
        return None
    if isinstance(deger, (int, float)):
        return int(deger)
    metin = str(deger).strip().replace(".", "").replace(",", "").replace(" ", "")
    if not metin or metin in {"-", "·"}:
        return None
    try:
        return int(metin)
    except ValueError:
        return None


def _temiz(deger) -> str:
    return re.sub(r"\s+", " ", str(deger or "")).strip()


def _iki_dilli(deger) -> tuple[str, str]:
    """'ABDULLAH GÜL ÜNİVERSİTESİ\\nABDULLAH GUL UNIVERSITY' -> (tr, en).

    Ad hücreleri Türkçe ve İngilizce adı satır sonuyla ayırarak tek hücrede
    tutuyor.
    """
    parcalar = [_temiz(p) for p in str(deger or "").split("\n") if _temiz(p)]
    if not parcalar:
        return "", ""
    return parcalar[0], (parcalar[1] if len(parcalar) > 1 else "")


def _tur_normalize(ham: str) -> str:
    metin = _temiz(ham).upper()
    for onek in TUR_ONEKLERI:
        if metin.startswith(onek):
            return onek
    return metin


def _dipnot_mu(ham_ad: str) -> bool:
    return any(iz in ham_ad for iz in DIPNOT_IZLERI) or ham_ad.strip().startswith("*")


# ---------------------------------------------------------------- kolon planı

@dataclass
class Olcum:
    """Bir E/K/T üçlüsünün alan öneki ve başladığı kolon."""
    onek: str
    kolon: int


@dataclass
class TabloPlani:
    """Bir tablonun kolon düzeni.

    Bütün 'üniversite + birim' tabloları aynı yürüyüşü paylaşıyor: tür kolonu
    dolu olan satır yeni bir üniversite başlatır, boş olanlar ona ait birimdir.
    Değişen tek şey kolon yerleşimi.
    """
    ad_kolonu: int = 0
    tur_kolonu: int = 1
    sehir_kolonu: int = 2
    olcumler: list[Olcum] = field(default_factory=list)
    ilk_veri_satiri: int = 4
    ulke_toplami_satiri: int = 3
    # Birim satırında ilçe bilgisi taşıyan tablolar (T012) için
    ilce_kolonu: int | None = None
    # Birim adının ayrı bir kolonda olduğu tablolar (M005) için
    birim_adi_kolonu: int | None = None


ADSIZ_KURUM = "(KURUM ADI BELİRTİLMEMİŞ)"


def duzeni_coz(sayfa, plan: TabloPlani) -> TabloPlani:
    """Plandaki indeksleri gerçek dosyaya göre kaydırır.

    YÖK'ün sayfa düzeni yıldan yıla kayabiliyor: 2021-2022'nin T35 dosyasında
    fazladan bir ilçe kolonu var ve başlıklar bir satır aşağıda, aynı tablonun
    diğer yıllarındaki düzenden farklı. Sabit indeks yazmak yerine 'E | K | T'
    başlık satırını bulup kaymayı hesaplıyoruz; böylece düzen yine değişirse
    ayrıştırıcı sessizce yanlış kolonu okumuyor.
    """
    ekt_satiri = ilk_sayi_kolonu = None
    for r in range(min(8, sayfa.nrows)):
        for c in range(min(10, sayfa.ncols - 2)):
            if (_temiz(sayfa.cell_value(r, c)) == "E"
                    and _temiz(sayfa.cell_value(r, c + 1)) == "K"
                    and _temiz(sayfa.cell_value(r, c + 2)).startswith("T")):
                ekt_satiri, ilk_sayi_kolonu = r, c
                break
        if ekt_satiri is not None:
            break

    if ekt_satiri is None:      # başlık bulunamadı: plan olduğu gibi kullanılır
        return plan

    kayma = ilk_sayi_kolonu - plan.olcumler[0].kolon
    return TabloPlani(
        ad_kolonu=plan.ad_kolonu,
        tur_kolonu=plan.tur_kolonu,
        sehir_kolonu=plan.sehir_kolonu,
        olcumler=[Olcum(o.onek, o.kolon + kayma) for o in plan.olcumler],
        ilk_veri_satiri=ekt_satiri + 2,
        ulke_toplami_satiri=ekt_satiri + 1,
        ilce_kolonu=None if plan.ilce_kolonu is None else plan.ilce_kolonu + kayma,
        birim_adi_kolonu=None if plan.birim_adi_kolonu is None else plan.birim_adi_kolonu + kayma,
    )


def _olcumleri_oku(sayfa, satir: int, plan: TabloPlani) -> dict:
    """Plandaki her ölçümü erkek/kadın/toplam alanlarına eşler."""
    degerler: dict = {}
    for olcum in plan.olcumler:
        for kayma, cinsiyet in enumerate(("erkek", "kadin", "toplam")):
            kolon = olcum.kolon + kayma
            degerler[f"{olcum.onek}_{cinsiyet}"] = (
                _sayi(sayfa.cell_value(satir, kolon)) if kolon < sayfa.ncols else None
            )
    return degerler


def universite_bloklari(yol: Path, donem: str, plan: TabloPlani) -> list[dict]:
    """'Üniversite + birim' düzenindeki tabloları ortak biçimde ayrıştırır.

    Üniversite satırının kendi toplamları belgenin üst seviyesine yazılıyor.
    YÖK'ün resmî rakamı bu satır: üniversite satırlarının toplamı ülke geneli
    satırıyla birebir tutuyor. Birim satırlarının toplamı ise kaynaktaki
    tekrar/eksik kayıtlar yüzünden bazı yıllarda birkaç kişi sapabiliyor.
    """
    sayfa = xlrd.open_workbook(yol).sheet_by_index(0)
    plan = duzeni_coz(sayfa, plan)
    universiteler: list[dict] = []
    aktif: dict | None = None
    adsiz_sayaci = 0

    for satir in range(plan.ilk_veri_satiri, sayfa.nrows):
        ham_ad = str(sayfa.cell_value(satir, plan.ad_kolonu) or "")
        if _dipnot_mu(ham_ad):
            continue

        ad_tr, ad_en = _iki_dilli(ham_ad)
        tur = _tur_normalize(sayfa.cell_value(satir, plan.tur_kolonu))
        sayilar = _olcumleri_oku(sayfa, satir, plan)
        dolu = any(v for v in sayilar.values())

        if tur:  # üniversite satırı
            if ad_tr.startswith(TOPLAM_IZI):     # ülke geneli satırı
                continue
            if not ad_tr:
                # Kaynakta adı boş bırakılmış kurumlar var (2025-2026 M005'te 8
                # adet). Sayıları gerçek; atmak yerine ayırt edilebilir bir
                # etiketle korunuyorlar.
                adsiz_sayaci += 1
                ad_tr = f"{ADSIZ_KURUM} {adsiz_sayaci}"

            aktif = {
                "universite": ad_tr,
                "universite_en": ad_en,
                "tur": tur,
                "sehir": _temiz(sayfa.cell_value(satir, plan.sehir_kolonu)),
                "yil": donem,
                "birimler": [],
            }
            aktif.update(sayilar)
            universiteler.append(aktif)
            continue

        if aktif is None:
            continue

        # Birim adı ayrı kolonda olabiliyor (M005: birim TÜRÜ ayrı kolonda)
        if plan.birim_adi_kolonu is not None:
            birim_tr, birim_en = _iki_dilli(sayfa.cell_value(satir, plan.birim_adi_kolonu))
        else:
            birim_tr, birim_en = ad_tr, ad_en

        if not birim_tr and not dolu:
            continue
        if birim_tr.startswith(TOPLAM_IZI):      # blok içi ara toplam
            continue

        # YÖK bazı birim satırlarının adını boş bırakıyor ama sayılar gerçek
        # (2024-2025 T028'te 2 satır, 18 kişi). Atmak veri kaybı olurdu.
        birim = {"birim": birim_tr or ADSIZ_BIRIM, "birim_en": birim_en}
        if plan.ilce_kolonu is not None:
            birim["ilce"] = _temiz(sayfa.cell_value(satir, plan.ilce_kolonu))
        birim.update(sayilar)

        # Birebir tekrar eden satırlar kaynak verideki hata; üniversite
        # satırındaki resmî toplam bunları bir kez sayıyor.
        if birim in aktif["birimler"]:
            _TEKRARLAR.append(f"{aktif['universite']} / {birim['birim']}")
            continue

        aktif["birimler"].append(birim)

    return universiteler


# ---------------------------------------------------------------- tablo planları

# T028 / T035: 6 unvan x (E, K, T), kolon 3'ten başlıyor
UNVAN_PLANI = TabloPlani(olcumler=[
    Olcum("profesor", 3),
    Olcum("docent", 6),
    Olcum("doktor_ogretim_uyesi", 9),
    Olcum("ogretim_gorevlisi", 12),
    Olcum("arastirma_gorevlisi", 15),
    Olcum("toplam", 18),
])

# T012: ilçe kolon 3'te, yeni kayıt 4'ten, toplam öğrenci 7'den
OGRENCI_PLANI = TabloPlani(
    ilce_kolonu=3,
    olcumler=[Olcum("yeni_kayit", 4), Olcum("toplam", 7)],
)

# M005: birim TÜRÜ kolon 3'te, tek ölçüm kolon 4'ten.
# Ülke geneli bloğu r2-r5 arasında, üniversiteler r6'dan başlıyor.
MEZUN_PLANI = TabloPlani(
    birim_adi_kolonu=3,
    olcumler=[Olcum("toplam", 4)],
    ilk_veri_satiri=2,
    ulke_toplami_satiri=2,
)


def ayristir_unvan(yol: Path, donem: str) -> list[dict]:
    """T028 (tüm öğretim elemanları) ve T035 (yabancı uyruklu) — aynı düzen."""
    return universite_bloklari(yol, donem, UNVAN_PLANI)


def ayristir_ogrenci(yol: Path, donem: str) -> list[dict]:
    """T012 — önlisans ve lisans düzeyinde öğrenci sayıları."""
    return universite_bloklari(yol, donem, OGRENCI_PLANI)


def ayristir_mezun(yol: Path, donem: str) -> list[dict]:
    """M005 — mezun sayıları, üniversite ve birim türü kırılımında."""
    return universite_bloklari(yol, donem, MEZUN_PLANI)


def ayristir_birim_sayilari(yol: Path, donem: str) -> list[dict]:
    """T107 — türlerine göre akademik birim sayıları.

    Üniversite kırılımı yok: birim türü satırlarda, üniversite türü
    kolonlarda olan küçük bir çapraz tablo.
    """
    sayfa = xlrd.open_workbook(yol).sheet_by_index(0)
    turler = [("devlet", 1), ("vakif", 3), ("vakif_myo", 5), ("toplam", 7)]
    kayitlar: list[dict] = []

    for satir in range(3, sayfa.nrows):
        ham_ad = str(sayfa.cell_value(satir, 0) or "")
        if _dipnot_mu(ham_ad):
            continue
        ad_tr, ad_en = _iki_dilli(ham_ad)
        if not ad_tr:
            continue

        kayit = {"birim_turu": ad_tr, "birim_turu_en": ad_en, "yil": donem}
        for onek, kolon in turler:
            kayit[f"{onek}_aktif"] = _sayi(sayfa.cell_value(satir, kolon))
            kayit[f"{onek}_pasif"] = _sayi(sayfa.cell_value(satir, kolon + 1))
        kayitlar.append(kayit)

    return kayitlar


# Tablo kodu -> (ayrıştırıcı, açıklama)
AYRISTIRICILAR = {
    "T028": (ayristir_unvan,          "Öğretim elemanları — akademik görevlere göre"),
    "T035": (ayristir_unvan,          "Yabancı uyruklu öğretim elemanları"),
    "T012": (ayristir_ogrenci,        "Önlisans ve lisans öğrenci sayıları"),
    "M005": (ayristir_mezun,          "Mezun sayıları"),
    "T107": (ayristir_birim_sayilari, "Türlerine göre akademik birim sayıları"),
}


# ---------------------------------------------------------------- doğrulama

def dogrula(yol: Path, kayitlar: list[dict], plan: TabloPlani) -> bool:
    """Üniversite toplamlarını dosyanın 'TOPLAM/TOTAL' satırıyla karşılaştırır.

    Kaynak dosyanın düzeni değişir de kolonlar kayarsa, sessizce yanlış veri
    üretmek yerine burada yakalanır.
    """
    sayfa = xlrd.open_workbook(yol).sheet_by_index(0)
    plan = duzeni_coz(sayfa, plan)
    tamam = True
    son_olcum = plan.olcumler[-1]

    for kayma, cinsiyet in enumerate(("erkek", "kadin", "toplam")):
        alan = f"{son_olcum.onek}_{cinsiyet}"
        beklenen = _sayi(sayfa.cell_value(plan.ulke_toplami_satiri, son_olcum.kolon + kayma)) or 0
        hesaplanan = sum((k.get(alan) or 0) for k in kayitlar)
        if beklenen == hesaplanan:
            continue

        fark = hesaplanan - beklenen
        # Kolon kayması ya da yanlış satır okuma büyük sapma üretir; kaynak
        # dosyanın kendi aritmetik tutarsızlığı ise birkaç kişilik olur.
        # İkisini ayırmak, gerçek bir ayrıştırma hatasını gürültüde kaybetmemek için.
        oran = abs(fark) / beklenen if beklenen else 1.0
        if oran < 0.0001:
            print(f"    · kaynak toplamı tutmuyor {alan}: dosya={beklenen} "
                  f"parçaların toplamı={hesaplanan} ({fark:+d})")
        else:
            print(f"    ! DOĞRULAMA HATASI {alan}: dosya={beklenen} hesap={hesaplanan} ({fark:+d})")
            tamam = False

    return tamam


PLANLAR = {
    "T028": UNVAN_PLANI, "T035": UNVAN_PLANI,
    "T012": OGRENCI_PLANI, "M005": MEZUN_PLANI,
}


# ---------------------------------------------------------------- çıktı

def ndjson_yaz(kayitlar: list[dict], yol: Path) -> None:
    """Kayıtları gzip'li NDJSON olarak yazar (repoya giren biçim).

    Çıktı DETERMİNİSTİK olmak zorunda. gzip varsayılan olarak başlığa hem
    yazma zamanını hem de dosya adını gömüyor; aynı veri iki kez işlendiğinde
    dosyalar bayt bayt farklı çıkıyordu. Zamanlanmış iş akışı bunu "veri
    değişti" sanıp her çalıştığında boş bir pull request açardı.

    mtime=0 zaman damgasını, filename="" ise ad alanını devre dışı bırakıyor.
    """
    yol.parent.mkdir(parents=True, exist_ok=True)
    govde = "".join(json.dumps(k, ensure_ascii=False) + "\n" for k in kayitlar).encode("utf-8")

    with open(yol, "wb") as ham:
        with gzip.GzipFile(filename="", mode="wb", fileobj=ham, mtime=0) as f:
            f.write(govde)

    print(f"  {yol.name}: {len(kayitlar)} kayıt, {yol.stat().st_size/1024:.0f} KB")


def tumunu_ayristir() -> None:
    """data/raw altındaki ham dosyaları işleyip data/processed'e yazar."""
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    manifest_yolu = config.RAW_DIR / "manifest.json"
    if not manifest_yolu.exists():
        print(f"! Manifest yok: {manifest_yolu}. Önce 'scrape' çalıştır.")
        return

    manifest = json.loads(manifest_yolu.read_text(encoding="utf-8"))
    islenen = 0

    for kayit in manifest:
        tablo_kodu = config.normalize_tablo_kodu(kayit["tablo_kodu"])
        donem = kayit["donem"]
        kaynak = config.RAW_DIR / config.donem_to_slug(donem) / kayit["dosya_adi"]

        if tablo_kodu not in AYRISTIRICILAR:
            continue   # bu tablo için henüz ayrıştırıcı yazılmadı
        if not kaynak.exists():
            print(f"  ! bulunamadı: {kaynak}")
            continue

        ayristirici, _ = AYRISTIRICILAR[tablo_kodu]
        _TEKRARLAR.clear()
        kayitlar = ayristirici(kaynak, donem)

        if (plan := PLANLAR.get(tablo_kodu)) is not None and not dogrula(kaynak, kayitlar, plan):
            print(f"    ! {kaynak.name} doğrulamayı geçemedi, yine de yazılıyor")
        for tekrar in _TEKRARLAR:
            print(f"    · kaynakta tekrar eden birim atlandı: {tekrar}")

        hedef = config.PROCESSED_DIR / f"{config.donem_to_slug(donem)}_{tablo_kodu}.ndjson.gz"
        ndjson_yaz(kayitlar, hedef)
        islenen += 1

    print(f"\n{islenen} tablo işlendi -> {config.PROCESSED_DIR}")
