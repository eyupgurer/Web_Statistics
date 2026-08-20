"""Ham .xls dosyalarını uygulamanın beklediği belge şemasına dönüştürür.

YÖK dosyaları OLE2 formatında eski .xls (Excel 97-2003) — openpyxl bunu
okuyamaz, xlrd 2.x tam olarak bu formatı destekler.

Tablolar çok satırlı ve birleşik hücreli başlıklar taşıyor; bu yüzden
kolon eşlemesi sabit indekse değil, başlık satırlarının okunmasına dayanıyor.
"""

from __future__ import annotations

import gzip
import json
import re
from pathlib import Path

import xlrd

from . import config


# ---------------------------------------------------------------- inceleme

def incele(yol: Path, satir_sayisi: int = 25) -> None:
    """Bir .xls dosyasının sayfa ve başlık yapısını ekrana döker.

    Parser yazmadan/uyarlamadan önce gerçek düzeni görmek için.
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


# ---------------------------------------------------------------- T028

# Uygulamanın Birim modelindeki alan sırası (Models/Birim.cs).
# Her akademik unvan için erkek/kadın/toplam üçlüsü.
UNVAN_ALANLARI = [
    "profesor",
    "docent",
    "doktor_ogretim_uyesi",
    "ogretim_gorevlisi",
    "arastirma_gorevlisi",
    "toplam",
]


# T028 sayfa düzeni (2025-2026 dosyasında doğrulandı):
#   r0        başlık, r1 birleşik unvan başlıkları, r2 E/K/T satırı
#   r3        "TOPLAM / TOTAL" ülke geneli satırı  -> atlanır
#   r4..son-1 veri satırları
#   son satır "Resmi İstatistik Programı..." dipnotu -> atlanır
#
# Kolonlar: 0 ad | 1 tür | 2 şehir | 3..20 = 6 unvan x (E, K, T)
# Bir satırda tür kolonu doluysa ÜNİVERSİTE satırı, boşsa ona ait BİRİM satırı.
ILK_VERI_SATIRI = 4
AD_KOL, TUR_KOL, SEHIR_KOL = 0, 1, 2
ILK_SAYI_KOL = 3

DIPNOT_IZI = "Resmi İstatistik Programı"

# Ayrıştırma sırasında atlanan tekrar satırları (şeffaflık için raporlanır)
_TEKRARLAR: list[str] = []
TOPLAM_IZI = "TOPLAM"

# YÖK bazı birim satırlarının adını boş bırakıyor; veriyi kaybetmemek için etiketliyoruz.
ADSIZ_BIRIM = "(BİRİM ADI BELİRTİLMEMİŞ)"

# 2023-2024 ve öncesinde tür hücresi iki dilli geliyor ("DEVLET STATE",
# "VAKIF MYO FOUNDATION VOC. SCH."); 2024-2025'ten itibaren sade ("DEVLET").
# Yıllar arası karşılaştırma yapılabilsin diye tek biçime indirgiyoruz.
TUR_ONEKLERI = ("VAKIF MYO", "VAKIF", "DEVLET")


def _tur_normalize(ham: str) -> str:
    metin = _temiz(ham).upper()
    for onek in TUR_ONEKLERI:
        if metin.startswith(onek):
            return onek
    return metin


def _iki_dilli(deger) -> tuple[str, str]:
    """'ABDULLAH GÜL ÜNİVERSİTESİ\nABDULLAH GUL UNIVERSITY' -> (tr, en).

    YÖK tablolarında ad hücreleri Türkçe ve İngilizce adı satır sonuyla
    ayırarak tek hücrede tutuyor.
    """
    parcalar = [_temiz(p) for p in str(deger or "").split("\n") if _temiz(p)]
    if not parcalar:
        return "", ""
    return parcalar[0], (parcalar[1] if len(parcalar) > 1 else "")


def _sayilari_oku(sayfa, satir: int) -> dict:
    """3..20 arası kolonları unvan/cinsiyet alanlarına eşler."""
    degerler = {}
    kol = ILK_SAYI_KOL
    for unvan in UNVAN_ALANLARI:
        for cinsiyet in ("erkek", "kadin", "toplam"):
            degerler[f"{unvan}_{cinsiyet}"] = (
                _sayi(sayfa.cell_value(satir, kol)) if kol < sayfa.ncols else None
            )
            kol += 1
    return degerler


def ayristir_t028(yol: Path, donem: str) -> list[dict]:
    """T028'i uygulamanın Universite/Birim şemasına dönüştürür.

    Üniversite satırının kendi toplamları belgeye AYRICA yazılıyor
    (`toplam_toplam` vb. üst seviyede). YÖK'ün resmî rakamı bu satır: her iki
    doğrulanan yılda da üniversite satırlarının toplamı ülke geneli satırıyla
    birebir tutuyor. Birim satırlarının toplamı ise bazı yıllarda kaynaktaki
    tekrar/eksik kayıtlar yüzünden birkaç kişi sapabiliyor.
    """
    sayfa = xlrd.open_workbook(yol).sheet_by_index(0)
    universiteler: list[dict] = []
    aktif: dict | None = None

    for satir in range(ILK_VERI_SATIRI, sayfa.nrows):
        ham_ad = str(sayfa.cell_value(satir, AD_KOL) or "")
        if DIPNOT_IZI in ham_ad or ham_ad.strip().startswith(("*", "**")):
            continue

        ad_tr, ad_en = _iki_dilli(ham_ad)
        tur = _tur_normalize(sayfa.cell_value(satir, TUR_KOL))
        sayilar = _sayilari_oku(sayfa, satir)
        dolu = any(v for v in sayilar.values())

        if tur:  # üniversite satırı
            if ad_tr.startswith(TOPLAM_IZI):   # ülke geneli satırı
                continue
            aktif = {
                "universite": ad_tr,
                "universite_en": ad_en,
                "tur": tur,
                "sehir": _temiz(sayfa.cell_value(satir, SEHIR_KOL)),
                "yil": donem,
                "birimler": [],
            }
            # Üniversite satırının resmî toplamları belgenin üst seviyesinde.
            aktif.update(sayilar)
            universiteler.append(aktif)
            continue

        if aktif is None or (not ad_tr and not dolu):
            continue

        # YÖK bazı birim satırlarının adını boş bırakıyor ama sayılar gerçek
        # (2024-2025'te 2 satır, 18 kişi). Atlamak veriyi kaybetmek olurdu.
        birim = {
            "birim": ad_tr or ADSIZ_BIRIM,
            "birim_en": ad_en,
        }
        birim.update(sayilar)

        # Birebir tekrar eden satırlar (isim + 18 sayının tamamı aynı) kaynak
        # verideki hata; üniversite satırındaki resmî toplam bunları bir kez sayıyor.
        if birim in aktif["birimler"]:
            _TEKRARLAR.append(f"{aktif['universite']} / {birim['birim']}")
            continue

        aktif["birimler"].append(birim)

    return universiteler


def dogrula(yol: Path, universiteler: list[dict]) -> bool:
    """Üniversite toplamlarını dosyanın 'TOPLAM/TOTAL' satırıyla karşılaştırır.

    Yetkili katman üniversite satırları: ülke geneli satırıyla birebir tutuyorlar.
    Birim satırlarındaki sapmalar ayrıca uyarı olarak raporlanıyor.
    """
    sayfa = xlrd.open_workbook(yol).sheet_by_index(0)
    tamam = True

    for kol, alan in ((18, "toplam_erkek"), (19, "toplam_kadin"), (20, "toplam_toplam")):
        beklenen = _sayi(sayfa.cell_value(3, kol)) or 0
        hesaplanan = sum((u.get(alan) or 0) for u in universiteler)
        if beklenen != hesaplanan:
            print(f"    ! DOĞRULAMA HATASI {alan}: dosya={beklenen} hesap={hesaplanan}")
            tamam = False

    # Birim toplamı üniversite toplamını tutmayan kurumlar (kaynak veri kalitesi)
    for u in universiteler:
        birim_toplami = sum((b.get("toplam_toplam") or 0) for b in u["birimler"])
        resmi = u.get("toplam_toplam") or 0
        if birim_toplami != resmi:
            print(f"    · birim/üniversite sapması: {u['universite']} "
                  f"resmî={resmi} birimler={birim_toplami} ({birim_toplami - resmi:+d})")

    return tamam


def tumunu_ayristir() -> None:
    """data/raw altındaki ham dosyaları işleyip data/processed'e yazar."""
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    manifest_yolu = config.RAW_DIR / "manifest.json"
    if not manifest_yolu.exists():
        print(f"! Manifest yok: {manifest_yolu}. Önce 'scrape' calistir.")
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

        _TEKRARLAR.clear()
        kayitlar = AYRISTIRICILAR[tablo_kodu](kaynak, donem)

        if tablo_kodu == "T028" and not dogrula(kaynak, kayitlar):
            print(f"    ! {kaynak.name} doğrulamayı geçemedi, yine de yazılıyor")
        for tekrar in _TEKRARLAR:
            print(f"    · kaynakta tekrar eden birim atlandı: {tekrar}")

        hedef = config.PROCESSED_DIR / f"{config.donem_to_slug(donem)}_{tablo_kodu}.ndjson.gz"
        ndjson_yaz(kayitlar, hedef)
        islenen += 1

    print(f"\n{islenen} tablo işlendi -> {config.PROCESSED_DIR}")


def ndjson_yaz(kayitlar: list[dict], yol: Path) -> None:
    """Kayıtları gzip'li NDJSON olarak yazar (repoya giren biçim)."""
    yol.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(yol, "wt", encoding="utf-8") as f:
        for kayit in kayitlar:
            f.write(json.dumps(kayit, ensure_ascii=False) + "\n")
    print(f"  {yol.name}: {len(kayitlar)} kayıt, {yol.stat().st_size/1024:.0f} KB")


# Tablo kodu -> ayrıştırıcı. Yeni tablolar buraya eklenecek.
AYRISTIRICILAR = {
    "T028": ayristir_t028,
}
