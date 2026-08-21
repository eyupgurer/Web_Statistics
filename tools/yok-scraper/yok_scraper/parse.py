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
from dataclasses import dataclass, field, replace
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


# Türkçe harflerin URL karşılıkları. str.lower() işe yaramıyor: "İ".lower()
# birleşik noktalı "i̇" üretiyor ve slug'a görünmez bir karakter sızdırıyor.
TR_HARFLER = str.maketrans({
    "İ": "i", "I": "i", "ı": "i", "Ğ": "g", "ğ": "g", "Ü": "u", "ü": "u",
    "Ş": "s", "ş": "s", "Ö": "o", "ö": "o", "Ç": "c", "ç": "c", "Â": "a", "â": "a",
})


def slug_uret(ad: str) -> str:
    """'HACETTEPE ÜNİVERSİTESİ' -> 'hacettepe-universitesi'.

    Kurum linkleri kalıcı olmalı. Önceden URL'de MongoDB'nin ObjectId'si vardı
    ve veri her yeniden yüklendiğinde yeni id üretildiği için paylaşılan
    linkler ölüyordu. Slug addan türediği için sabit kalıyor.
    """
    metin = _temiz(ad).translate(TR_HARFLER).lower()
    metin = re.sub(r"[^a-z0-9]+", "-", metin)
    return metin.strip("-")[:80]


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

    # Üniversite satırını neyin belirlediği. YÖK iki farklı yazım kullanıyor:
    #   "tur"  -> birim satırlarında tür hücresi boş (2018-2019 sonrası T28)
    #   "ilce" -> tür her satırda dolu, üniversiteyi ilçenin BOŞ olması ayırıyor
    # Dosyadan otomatik belirleniyor; sabit yazmak yıllar arasında kırılıyor.
    universite_belirteci: str = "tur"

    # Her ölçüm grubunun başlığında geçmesi GEREKEN anahtar kelime.
    # Aritmetik doğrulama kolon kaymasını yakalar ama tablonun ANLAMI
    # değiştiğinde sessiz kalır: 2018 unvan reformundan önceki dosyalarda
    # 8 unvan grubu var (Yardımcı Doçent, Okutman, Uzman, Çevirici) ve
    # altıncı grup "Toplam" değil "Uzman". Başlık kontrolü bunu yakalıyor.
    baslik_anahtarlari: list[str] = field(default_factory=list)


ADSIZ_KURUM = "(KURUM ADI BELİRTİLMEMİŞ)"


class TabloDuzeniDegisti(Exception):
    """Dosyanın anlamı beklenenden farklı: kolonlar aynı yerde ama başka şeyi sayıyor."""


def _basliklari_dogrula(sayfa, ekt_satiri: int, ilk_kolon: int, plan: TabloPlani) -> None:
    """Ölçüm gruplarının başlıklarının beklenenle uyuştuğunu kontrol eder.

    Aritmetik doğrulama tek başına yetmiyor: yanlış kolon okunduğunda dosyanın
    kendi toplam satırı da aynı yanlış kolondan geldiği için sapma çıkmıyor.
    2016-2017 T28'de altıncı grup "Toplam" değil "Uzman"; kontrol olmadan
    veritabanına 'toplam_toplam = 47' gibi anlamsız değerler yazılıyordu.
    """
    if not plan.baslik_anahtarlari:
        return

    # Grup başlıkları E/K/T satırının hemen üstünde, birleşik hücrede duruyor.
    ustsatir = ekt_satiri - 1
    if ustsatir < 0:
        return

    basliklar = [(_temiz(sayfa.cell_value(ustsatir, c)).upper(), c)
                 for c in range(ilk_kolon, sayfa.ncols)
                 if _temiz(sayfa.cell_value(ustsatir, c))]

    for sira, anahtar in enumerate(plan.baslik_anahtarlari):
        if sira >= len(basliklar):
            raise TabloDuzeniDegisti(
                f"{sira + 1}. ölçüm grubu yok (beklenen: {anahtar})")
        bulunan = basliklar[sira][0]
        if anahtar.upper() not in bulunan:
            raise TabloDuzeniDegisti(
                f"{sira + 1}. grup '{bulunan[:34]}' — beklenen '{anahtar}'. "
                f"Bu dosyanın tablo düzeni farklı, ayrıştırıcı uymuyor.")


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

    _basliklari_dogrula(sayfa, ekt_satiri, ilk_sayi_kolonu, plan)

    # Ölçüm grupları arasında boş kolon olabiliyor (2017-2018 T12: 11 kolon,
    # ikinci grup 7'de değil 8'de başlıyor). Sabit ofset yerine satırdaki
    # bütün E/K/T üçlüleri bulunup ölçümlerle sırayla eşleniyor.
    ucluler = []
    c = ilk_sayi_kolonu
    while c + 2 < sayfa.ncols:
        if (_temiz(sayfa.cell_value(ekt_satiri, c)) == "E"
                and _temiz(sayfa.cell_value(ekt_satiri, c + 1)) == "K"
                and _temiz(sayfa.cell_value(ekt_satiri, c + 2)).startswith("T")):
            ucluler.append(c)
            c += 3
        else:
            c += 1

    kayma = ilk_sayi_kolonu - plan.olcumler[0].kolon

    # İlçe kolonu başlıktan bulunuyor (E/K/T satırında ya da bir üstünde).
    # Bazı dosyalarda kolon var ama başlığı boş (2017-2018 T35); o durumda
    # ilk sayı kolonundan hemen önceki kolon ayırt edici oluyor.
    ilce_kolonu = plan.ilce_kolonu + kayma if plan.ilce_kolonu is not None else None
    for r in (ekt_satiri, ekt_satiri - 1):
        if r < 0:
            continue
        for c in range(ilk_sayi_kolonu):
            if "İLÇE" in _temiz(sayfa.cell_value(r, c)).upper():
                ilce_kolonu = c
                break
    if ilce_kolonu is None and ilk_sayi_kolonu >= 1:
        ilce_kolonu = ilk_sayi_kolonu - 1

    # Hangi yazım kullanılıyor? Veri satırlarının çoğunda tür doluysa,
    # tür kolonu üniversiteyi ayırt etmiyor demektir.
    ilk_veri = ekt_satiri + 2
    ornek = range(ilk_veri, min(ilk_veri + 40, sayfa.nrows))
    dolu = sum(1 for r in ornek
               if _temiz(sayfa.cell_value(r, plan.tur_kolonu)))
    toplam_ornek = max(len(list(ornek)), 1)
    # Aday kolon gerçekten ayırt edici mi: hem boş hem dolu değerler taşımalı.
    # Yoksa (ör. şehir kolonu) her satırı üniversite sanardık.
    ayirt_edici = False
    if ilce_kolonu is not None:
        degerler = [bool(_temiz(sayfa.cell_value(r, ilce_kolonu))) for r in ornek]
        ayirt_edici = any(degerler) and not all(degerler)

    tur_ayirt_ediyor = dolu / toplam_ornek <= 0.6

    if not tur_ayirt_ediyor and not ayirt_edici:
        # Ne tür ne ilçe kolonu üniversiteyi birimden ayırıyor (2018-2019 T22'de
        # ikisi de her satırda dolu). Geriye yalnızca ada bakmak kalıyor ki o da
        # güvenilmez: İzmir Yüksek Teknoloji ENSTİTÜSÜ bir üniversite, Fen
        # Bilimleri ENSTİTÜSÜ ise ona bağlı birim. Tahmin edip yanlış veri
        # üretmektense dosyayı reddediyoruz.
        raise TabloDuzeniDegisti(
            "üniversite satırı ayırt edilemiyor: tür ve ilçe kolonları her "
            "satırda dolu, ayırt edici bir kolon yok")

    belirtec = "ilce" if (not tur_ayirt_ediyor and ayirt_edici) else "tur"

    # Üçlü sayısı yetiyorsa doğrudan onlarla eşle; yetmiyorsa eski kaydırma
    # davranışına düş (ör. başlık satırı beklenenden farklıysa).
    if len(ucluler) >= len(plan.olcumler):
        olcumler = [Olcum(o.onek, ucluler[i]) for i, o in enumerate(plan.olcumler)]
    else:
        olcumler = [Olcum(o.onek, o.kolon + kayma) for o in plan.olcumler]

    return TabloPlani(
        universite_belirteci=belirtec,
        baslik_anahtarlari=plan.baslik_anahtarlari,
        ad_kolonu=plan.ad_kolonu,
        tur_kolonu=plan.tur_kolonu,
        sehir_kolonu=plan.sehir_kolonu,
        olcumler=olcumler,
        ilk_veri_satiri=ekt_satiri + 2,
        ulke_toplami_satiri=ekt_satiri + 1,
        ilce_kolonu=ilce_kolonu,
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

        if plan.universite_belirteci == "ilce":
            # Tür her satırda dolu; üniversiteyi ilçenin boş olması ayırıyor.
            ilce = _temiz(sayfa.cell_value(satir, plan.ilce_kolonu)) if plan.ilce_kolonu is not None else ""
            universite_satiri = bool(tur) and not ilce
        else:
            universite_satiri = bool(tur)

        if universite_satiri:
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
                "slug": slug_uret(ad_tr),
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


# ---------------------------------------------------------------- düz tablolar

@dataclass
class DuzTabloPlani:
    """Satırları üniversite değil KATEGORİ olan tablolar (ülke, eğitim alanı).

    Bu tablolarda tür/il/ilçe kolonu yok; ad kolonundan sonra doğrudan
    ölçümler geliyor.
    """
    kategori_adi: str = "kategori"
    # Birden fazla kimlik kolonu taşıyan denormalize tablolar için
    # (T105: üniversite / birim / program). Boşsa kategori_adi + kolon 0.
    kimlik_kolonlari: list[tuple[str, int]] = field(default_factory=list)
    olcumler: list[Olcum] = field(default_factory=list)
    baslik_anahtarlari: list[str] = field(default_factory=list)
    # Eğitim alanı tablolarında satırlar hiyerarşik (geniş alan > dar alan >
    # ayrıntılı alan) ve seviye Excel'in girinti biçiminde saklı. Okunmazsa
    # üç seviye toplanıp gerçek toplamın üç katı çıkıyor.
    hiyerarsik: bool = False


def ayristir_duz_tablo(yol: Path, donem: str, plan: DuzTabloPlani) -> list[dict]:
    """Kategori satırlı tabloları ayrıştırır."""
    # Girinti seviyesi yalnızca biçim bilgisiyle okunabiliyor.
    try:
        kitap = xlrd.open_workbook(yol, formatting_info=plan.hiyerarsik)
    except Exception:                                  # noqa: BLE001
        kitap = xlrd.open_workbook(yol)
        plan = replace(plan, hiyerarsik=False)
    sayfa = kitap.sheet_by_index(0)

    # E/K/T satırını ve üçlüleri bul (üniversite tablolarıyla aynı mantık)
    ekt_satiri = ilk_kolon = None
    for r in range(min(8, sayfa.nrows)):
        for c in range(min(6, sayfa.ncols - 2)):
            if (_temiz(sayfa.cell_value(r, c)) == "E"
                    and _temiz(sayfa.cell_value(r, c + 1)) == "K"
                    and _temiz(sayfa.cell_value(r, c + 2)).startswith("T")):
                ekt_satiri, ilk_kolon = r, c
                break
        if ekt_satiri is not None:
            break
    if ekt_satiri is None:
        raise TabloDuzeniDegisti("E | K | T başlık satırı bulunamadı")

    _basliklari_dogrula(sayfa, ekt_satiri, ilk_kolon, plan)

    ucluler = []
    c = ilk_kolon
    while c + 2 < sayfa.ncols:
        if (_temiz(sayfa.cell_value(ekt_satiri, c)) == "E"
                and _temiz(sayfa.cell_value(ekt_satiri, c + 1)) == "K"
                and _temiz(sayfa.cell_value(ekt_satiri, c + 2)).startswith("T")):
            ucluler.append(c); c += 3
        else:
            c += 1
    if len(ucluler) < len(plan.olcumler):
        raise TabloDuzeniDegisti(
            f"{len(plan.olcumler)} ölçüm grubu bekleniyordu, {len(ucluler)} bulundu")

    kayitlar: list[dict] = []
    for satir in range(ekt_satiri + 2, sayfa.nrows):
        ham = str(sayfa.cell_value(satir, 0) or "")
        if _dipnot_mu(ham):
            continue
        ad_tr, ad_en = _iki_dilli(ham)
        if not ad_tr or ad_tr.startswith(TOPLAM_IZI):
            continue

        if plan.kimlik_kolonlari:
            kayit = {"yil": donem}
            for alan, kolon in plan.kimlik_kolonlari:
                kayit[alan] = _iki_dilli(sayfa.cell_value(satir, kolon))[0]
            if not kayit.get(plan.kimlik_kolonlari[0][0]):
                continue
        else:
            kayit = {
                plan.kategori_adi: ad_tr,
                f"{plan.kategori_adi}_en": ad_en,
                "yil": donem,
            }
        if plan.hiyerarsik:
            xf = kitap.xf_list[sayfa.cell_xf_index(satir, 0)]
            kayit["seviye"] = xf.alignment.indent_level // 2

        for i, olcum in enumerate(plan.olcumler):
            kol = ucluler[i]
            for kayma, cinsiyet in enumerate(("erkek", "kadin", "toplam")):
                kayit[f"{olcum.onek}_{cinsiyet}"] = (
                    _sayi(sayfa.cell_value(satir, kol + kayma))
                    if kol + kayma < sayfa.ncols else None)
        kayitlar.append(kayit)

    return kayitlar


# ---------------------------------------------------------------- tablo planları

# T028 / T035: 6 unvan x (E, K, T), kolon 3'ten başlıyor
UNVAN_PLANI = TabloPlani(
    baslik_anahtarlari=["PROFESÖR", "DOÇENT", "DOKTOR", "ÖĞRETİM GÖREVLİSİ",
                        "ARAŞTIRMA", "TOPLAM"],
    olcumler=[
    Olcum("profesor", 3),
    Olcum("docent", 6),
    Olcum("doktor_ogretim_uyesi", 9),
    Olcum("ogretim_gorevlisi", 12),
    Olcum("arastirma_gorevlisi", 15),
    Olcum("toplam", 18),
])

# T012: ilçe kolon 3'te, yeni kayıt 4'ten, toplam öğrenci 7'den
OGRENCI_PLANI = TabloPlani(
    baslik_anahtarlari=["YENİ KAYIT", "TOPLAM"],
    ilce_kolonu=3,
    olcumler=[Olcum("yeni_kayit", 4), Olcum("toplam", 7)],
)

# M005: birim TÜRÜ kolon 3'te, tek ölçüm kolon 4'ten.
# Ülke geneli bloğu r2-r5 arasında, üniversiteler r6'dan başlıyor.
MEZUN_PLANI = TabloPlani(
    baslik_anahtarlari=[],   # M005'te grup başlığı yok, tek ölçüm
    birim_adi_kolonu=3,
    olcumler=[Olcum("toplam", 4)],
    ilk_veri_satiri=2,
    ulke_toplami_satiri=2,
)


# T022: lisansüstü öğrenci. İki blok (yeni kayıt / toplam öğrenci), her biri
# yüksek lisans + doktora + toplam. 13. kolonda bloklar arası boşluk var;
# ölçümler E/K/T üçlülerinden eşlendiği için sorun olmuyor.
LISANSUSTU_PLANI = TabloPlani(
    baslik_anahtarlari=["YÜKSEK LİSANS", "DOKTORA", "TOPLAM",
                        "YÜKSEK LİSANS", "DOKTORA", "TOPLAM"],
    ilce_kolonu=3,
    olcumler=[
        Olcum("yeni_kayit_yuksek_lisans", 4),
        Olcum("yeni_kayit_doktora", 7),
        Olcum("yeni_kayit", 10),
        Olcum("yuksek_lisans", 14),
        Olcum("doktora", 17),
        Olcum("toplam", 20),
    ],
)


def ayristir_lisansustu(yol: Path, donem: str) -> list[dict]:
    """T022 — enstitülere göre yüksek lisans ve doktora öğrenci sayıları."""
    return universite_bloklari(yol, donem, LISANSUSTU_PLANI)


# T102: öğrenci sayıları il ve ilçelere göre. Ölçüm grupları T007 ile
# birebir aynı (öğrenim düzeyi x öğretim türü); fark, satırların yaş değil
# üniversite+birim olması. Birim satırındaki şehir kolonu ilçeyi taşıyor.
IL_ILCE_OGRENCI_PLANI = TabloPlani(
    baslik_anahtarlari=["ÖRGÜN", "İKİNCİ", "UZAKTAN", "AÇIK",
                        "ÖRGÜN", "İKİNCİ", "UZAKTAN", "AÇIK",
                        "ÖRGÜN", "İKİNCİ", "UZAKTAN",
                        "ÖRGÜN"],
    olcumler=[
        Olcum("onlisans_orgun", 3),       Olcum("onlisans_ikinci", 6),
        Olcum("onlisans_uzaktan", 9),     Olcum("onlisans_acik", 12),
        Olcum("lisans_orgun", 16),        Olcum("lisans_ikinci", 19),
        Olcum("lisans_uzaktan", 22),      Olcum("lisans_acik", 25),
        Olcum("yuksek_lisans_orgun", 29), Olcum("yuksek_lisans_ikinci", 32),
        Olcum("yuksek_lisans_uzaktan", 35),
        Olcum("doktora_orgun", 39),
        Olcum("toplam", 43),
    ],
)


def ayristir_il_ilce_ogrenci(yol: Path, donem: str) -> list[dict]:
    """T102 — öğrenci sayıları, il/ilçe ve öğretim türü kırılımında."""
    return universite_bloklari(yol, donem, IL_ILCE_OGRENCI_PLANI)


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
            # Eski yılların dosyalarında kolon sayısı daha az olabiliyor.
            kayit[f"{onek}_aktif"] = (
                _sayi(sayfa.cell_value(satir, kolon)) if kolon < sayfa.ncols else None)
            kayit[f"{onek}_pasif"] = (
                _sayi(sayfa.cell_value(satir, kolon + 1)) if kolon + 1 < sayfa.ncols else None)
        kayitlar.append(kayit)

    return kayitlar


# T201: yabancı uyruklu öğretim elemanları, uyruğa göre. Satır = ülke.
UYRUK_PLANI = DuzTabloPlani(
    kategori_adi="ulke",
    baslik_anahtarlari=["PROFESÖR", "DOÇENT", "DOKTOR", "ÖĞRETİM GÖREVLİSİ",
                        "ARAŞTIRMA", "TOPLAM"],
    olcumler=[Olcum("profesor", 1), Olcum("docent", 4),
              Olcum("doktor_ogretim_uyesi", 7), Olcum("ogretim_gorevlisi", 10),
              Olcum("arastirma_gorevlisi", 13), Olcum("toplam", 16)],
)

# T017 / T019: eğitim ve öğretim alanına göre öğrenci sayıları.
# Satırlar hiyerarşik: geniş alan (seviye 0) > dar alan (1) > ayrıntılı (2).
EGITIM_ALANI_PLANI = DuzTabloPlani(
    kategori_adi="alan",
    baslik_anahtarlari=["YENİ KAYIT", "TOPLAM"],
    olcumler=[Olcum("yeni_kayit", 1), Olcum("toplam", 5)],
    hiyerarsik=True,
)


# T007: yaş gruplarına göre öğrenci. Üç katmanlı başlık:
#   r1 öğrenim düzeyi · r2 öğretim türü · r3 E/K/T
# Öğretim türü (örgün / ikinci / uzaktan / açık öğretim) başka hiçbir
# tabloda yok; öğrenci sayısındaki dalgalanmanın hangi türden geldiğini
# ancak bu gösteriyor.
YAS_PLANI = DuzTabloPlani(
    kategori_adi="yas",
    # 13 ölçüm grubu var ama öğretim türü satırında 12 başlık: sonuncusu
    # (genel TOPLAM) tür taşımıyor, etiketi bir üst satırda duruyor.
    baslik_anahtarlari=["ÖRGÜN", "İKİNCİ", "UZAKTAN", "AÇIK",
                        "ÖRGÜN", "İKİNCİ", "UZAKTAN", "AÇIK",
                        "ÖRGÜN", "İKİNCİ", "UZAKTAN",
                        "ÖRGÜN"],
    olcumler=[
        Olcum("onlisans_orgun", 1),      Olcum("onlisans_ikinci", 4),
        Olcum("onlisans_uzaktan", 7),    Olcum("onlisans_acik", 10),
        Olcum("lisans_orgun", 13),       Olcum("lisans_ikinci", 16),
        Olcum("lisans_uzaktan", 19),     Olcum("lisans_acik", 22),
        Olcum("yuksek_lisans_orgun", 25), Olcum("yuksek_lisans_ikinci", 28),
        Olcum("yuksek_lisans_uzaktan", 31),
        Olcum("doktora_orgun", 34),
        Olcum("toplam", 37),
    ],
)


def ayristir_yas(yol: Path, donem: str) -> list[dict]:
    """T007 — yaş gruplarına göre öğrenci, öğrenim düzeyi ve öğretim türü kırılımında."""
    return ayristir_duz_tablo(yol, donem, YAS_PLANI)


# T003: eğitim birimlerine göre öğrenci VE öğretim elemanı. Satırlar
# üniversite değil BİRİM TÜRÜ (fakülte, meslek yüksekokulu, enstitü…).
# İki veri grubunu yan yana veren tek tablo; birim türü bazında öğretim
# elemanı başına öğrenci oranı buradan çıkıyor.
BIRIM_TURU_PLANI = DuzTabloPlani(
    kategori_adi="birim_turu",
    # T017/T019 gibi hiyerarşik: girinti 2 = birim türü (FAKÜLTE),
    # girinti 4 = tek tek birim adları. Her seviye ayrı ayrı ülke toplamına
    # eşit; seviyeler toplanmamalı.
    hiyerarsik=True,
    baslik_anahtarlari=["YENİ KAYIT", "OKUYAN", "YENİ KAYIT", "OKUYAN",
                        "YENİ KAYIT", "OKUYAN",
                        "PROFESÖR", "DOÇENT", "DOKTOR", "ÖĞRETİM GÖREVLİSİ",
                        "ARAŞTIRMA", "TOPLAM"],
    olcumler=[
        Olcum("onlisans_lisans_yeni_kayit", 2), Olcum("onlisans_lisans", 5),
        Olcum("yuksek_lisans_yeni_kayit", 8),   Olcum("yuksek_lisans", 11),
        Olcum("doktora_yeni_kayit", 14),        Olcum("doktora", 17),
        Olcum("profesor", 21),                  Olcum("docent", 24),
        Olcum("doktor_ogretim_uyesi", 27),      Olcum("ogretim_gorevlisi", 30),
        Olcum("arastirma_gorevlisi", 33),       Olcum("ogretim_elemani", 36),
    ],
)


def ayristir_birim_turu(yol: Path, donem: str) -> list[dict]:
    """T003 — eğitim birimlerine göre öğrenci ve öğretim elemanı sayıları."""
    return ayristir_duz_tablo(yol, donem, BIRIM_TURU_PLANI)


def ayristir_uyruk(yol: Path, donem: str) -> list[dict]:
    """T201 — yabancı uyruklu öğretim elemanları, uyruğuna göre."""
    return ayristir_duz_tablo(yol, donem, UYRUK_PLANI)


def ayristir_egitim_alani(yol: Path, donem: str) -> list[dict]:
    """T017 (lisans) ve T019 (önlisans) — eğitim alanına göre öğrenci."""
    return ayristir_duz_tablo(yol, donem, EGITIM_ALANI_PLANI)


# T105: öğrenim düzeyi ve birimlere göre öğrenci sayıları, PROGRAM düzeyinde.
# Hiyerarşik değil, denormalize düz tablo: her satır bir program, üniversite
# ve birim adı her satırda tekrarlıyor. Tüm satırların toplamı ülke geneline
# eşit, çift sayım yok. Ölçüm grupları T007/T102 ile aynı.
PROGRAM_PLANI = DuzTabloPlani(
    kimlik_kolonlari=[("universite", 0), ("birim", 1), ("program", 2)],
    baslik_anahtarlari=["ÖRGÜN", "İKİNCİ", "UZAKTAN", "AÇIK",
                        "ÖRGÜN", "İKİNCİ", "UZAKTAN", "AÇIK",
                        "ÖRGÜN", "İKİNCİ", "UZAKTAN",
                        "ÖRGÜN"],
    olcumler=[
        Olcum("onlisans_orgun", 3),       Olcum("onlisans_ikinci", 6),
        Olcum("onlisans_uzaktan", 9),     Olcum("onlisans_acik", 12),
        Olcum("lisans_orgun", 16),        Olcum("lisans_ikinci", 19),
        Olcum("lisans_uzaktan", 22),      Olcum("lisans_acik", 25),
        Olcum("yuksek_lisans_orgun", 29), Olcum("yuksek_lisans_ikinci", 32),
        Olcum("yuksek_lisans_uzaktan", 35),
        Olcum("doktora_orgun", 39),
        Olcum("toplam", 43),
    ],
)


def ayristir_program(yol: Path, donem: str) -> list[dict]:
    """T105 — program düzeyinde öğrenci sayıları."""
    return ayristir_duz_tablo(yol, donem, PROGRAM_PLANI)


# Tablo kodu -> (ayrıştırıcı, açıklama)
AYRISTIRICILAR = {
    "T028": (ayristir_unvan,          "Öğretim elemanları — akademik görevlere göre"),
    "T035": (ayristir_unvan,          "Yabancı uyruklu öğretim elemanları"),
    "T012": (ayristir_ogrenci,        "Önlisans ve lisans öğrenci sayıları"),
    "M005": (ayristir_mezun,          "Mezun sayıları"),
    "T107": (ayristir_birim_sayilari, "Türlerine göre akademik birim sayıları"),
    "T022": (ayristir_lisansustu,     "Lisansüstü öğrenci sayıları"),
    "T201": (ayristir_uyruk,          "Yabancı uyruklu öğretim elemanları — uyruğa göre"),
    "T017": (ayristir_egitim_alani,   "Lisans öğrenci — eğitim alanına göre"),
    "T019": (ayristir_egitim_alani,   "Önlisans öğrenci — eğitim alanına göre"),
    "T007": (ayristir_yas,            "Öğrenci — yaş, öğrenim düzeyi ve öğretim türü"),
    "T102": (ayristir_il_ilce_ogrenci, "Öğrenci — il/ilçe ve öğretim türü"),
    "T003": (ayristir_birim_turu,     "Birim türüne göre öğrenci ve öğretim elemanı"),
    "T105": (ayristir_program,        "Program düzeyinde öğrenci sayıları"),
}

# Yalnızca en güncel yıl için işlenen tablolar. T105 yılda ~1,2 MB sıkıştırılmış
# veri üretiyor ve gzip git'te delta sıkışmadığı için her güncellemede tamamı
# geçmişe kalıcı ekleniyor. Program düzeyinde geçmiş seriye ihtiyaç yok;
# zaman serisi zaten üniversite düzeyinde mevcut.
SON_YIL_TABLOLARI = {"T105"}


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
        # Küçük mutlak sapmalar kaynak gürültüsü; oransal eşik tek başına
        # küçük toplamlarda (ör. 3.121 kişilik yabancı uyruklu tablosu)
        # birkaç kişiyi ayrıştırma hatası gibi gösteriyordu.
        oran = abs(fark) / beklenen if beklenen else 1.0
        if abs(fark) <= 10 or oran < 0.001:
            print(f"    · kaynak toplamı tutmuyor {alan}: dosya={beklenen} "
                  f"parçaların toplamı={hesaplanan} ({fark:+d})")
        else:
            print(f"    ! DOĞRULAMA HATASI {alan}: dosya={beklenen} hesap={hesaplanan} ({fark:+d})")
            tamam = False

    return tamam


PLANLAR = {
    "T028": UNVAN_PLANI, "T035": UNVAN_PLANI,
    "T012": OGRENCI_PLANI, "M005": MEZUN_PLANI,
    "T022": LISANSUSTU_PLANI,
    "T102": IL_ILCE_OGRENCI_PLANI,
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
    en_guncel_donem = max((k.get("donem", "") for k in manifest), default="")
    islenen = 0
    basarisiz: list[tuple[str, str, str]] = []

    for kayit in manifest:
        tablo_kodu = config.normalize_tablo_kodu(kayit["tablo_kodu"])
        donem = kayit["donem"]
        kaynak = config.RAW_DIR / config.donem_to_slug(donem) / kayit["dosya_adi"]

        if tablo_kodu not in AYRISTIRICILAR:
            continue   # bu tablo için henüz ayrıştırıcı yazılmadı
        if tablo_kodu in SON_YIL_TABLOLARI and donem != en_guncel_donem:
            continue
        if not kaynak.exists():
            print(f"  ! bulunamadı: {kaynak}")
            continue

        ayristirici, _ = AYRISTIRICILAR[tablo_kodu]
        _TEKRARLAR.clear()
        try:
            kayitlar = ayristirici(kaynak, donem)
        except Exception as hata:                      # noqa: BLE001
            # Tek bir bozuk dosya on üç yıllık işi durdurmamalı; hangi dosyada
            # ne olduğu raporlanıp devam ediliyor.
            basarisiz.append((donem, tablo_kodu, f"{type(hata).__name__}: {hata}"))
            print(f"    ! {kaynak.name} ayrıştırılamadı ({type(hata).__name__}: {hata})")
            continue

        if (plan := PLANLAR.get(tablo_kodu)) is not None and not dogrula(kaynak, kayitlar, plan):
            print(f"    ! {kaynak.name} doğrulamayı geçemedi, yine de yazılıyor")
        for tekrar in _TEKRARLAR:
            print(f"    · kaynakta tekrar eden birim atlandı: {tekrar}")

        hedef = config.PROCESSED_DIR / f"{config.donem_to_slug(donem)}_{tablo_kodu}.ndjson.gz"
        ndjson_yaz(kayitlar, hedef)
        islenen += 1

    print(f"\n{islenen} tablo işlendi -> {config.PROCESSED_DIR}")
    if basarisiz:
        print(f"\n{len(basarisiz)} tablo ayrıştırılamadı:")
        for donem, kod, sebep in basarisiz:
            print(f"  {donem} {kod}: {sebep}")
