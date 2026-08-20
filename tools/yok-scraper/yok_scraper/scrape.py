"""YÖK istatistik portalından ham .xls dosyalarını indirir.

Portal ZK Framework ile yazılmış, tamamen stateful bir SPA:
  - URL hiçbir tıklamada değişmiyor, deep-link yok
  - İndirme ikonları href'siz <img> elemanları; tıklama sunucuya zkau POST'u atıyor
  - Sunucu dosyayı o oturum için üretip tek kullanımlık bir adresten sunuyor

Bu yüzden requests/httpx ile çekmek mümkün değil; gerçek tarayıcı şart.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PWTimeout, sync_playwright

from . import config


@dataclass
class IndirilenTablo:
    """Tek bir Excel tablosunun indirme kaydı."""

    donem: str          # "2025-2026"
    sekme: str          # "ÖĞRETİM ELEMANLARI"
    baslik: str         # "ÖĞRETİM ELEMANLARININ AKADEMİK GÖREVLERİNE GÖRE SAYILARI"
    tablo_kodu: str     # "T028"
    dosya_adi: str      # "2026_T028.xls"
    boyut: int


def _zk_bekle(page: Page, saniye: float = 1.0) -> None:
    """ZK'nın asenkron güncellemesinin oturmasını bekler.

    ZK 'Bekleyiniz...' göstergesini kaldırdıktan sonra bile DOM bir süre
    yerleşiyor; networkidle tek başına yetmiyor.
    """
    try:
        page.wait_for_load_state("networkidle", timeout=config.NAV_TIMEOUT_MS)
    except PWTimeout:
        pass
    page.wait_for_timeout(int(saniye * 1000))


def _menu_ac(page: Page, metin: str) -> None:
    """Üst menüden verilen metne sahip öğeyi tıklar."""
    page.get_by_text(metin, exact=False).first.click()
    _zk_bekle(page, 0.6)


def yil_sayfasina_git(page: Page, donem: str) -> None:
    """'Yükseköğretim İstatistikleri' menüsünden ilgili öğretim yılını açar."""
    _menu_ac(page, "Yükseköğretim İstatistikleri")
    page.get_by_text(f"{donem} Öğretim Yılı", exact=False).first.click()
    _zk_bekle(page, 2.0)


def _gorunur_xls_ikonlari(page: Page) -> list[dict]:
    """Aktif sekmedeki görünür Excel ikonlarını satır başlığıyla birlikte döner.

    ZK sekmeleri tembel yükleniyor: sekmeye tıklanmadan o panelin ikonları
    DOM'a hiç girmiyor, girenler de gizliyken 0x0 boyutta oluyor. Bu yüzden
    görünürlük (width > 0) üzerinden filtreliyoruz.
    """
    return page.evaluate(
        """() => {
            const out = [];
            document.querySelectorAll('img[src*="xls"]').forEach((im, i) => {
                const r = im.getBoundingClientRect();
                if (r.width > 0) {
                    const row = im.closest('tr') || im.parentElement;
                    out.push({
                        id: im.id,
                        baslik: (row ? row.innerText : '').trim(),
                    });
                }
            });
            return out;
        }"""
    )


def _tablo_kodu(dosya_adi: str) -> str:
    """'2026_T028.xls' -> 'T028'. Beklenmedik adlarda dosya adına düşer."""
    govde = Path(dosya_adi).stem
    ham = govde.split("_")[-1] if "_" in govde else govde
    return config.normalize_tablo_kodu(ham)


def sekme_indir(page: Page, donem: str, sekme: str, hedef: Path) -> list[IndirilenTablo]:
    """Bir sekmedeki tüm Excel tablolarını indirir."""
    kayitlar: list[IndirilenTablo] = []

    try:
        page.get_by_text(sekme, exact=True).first.click()
    except PWTimeout:
        print(f"    ! '{sekme}' sekmesi bulunamadı, atlanıyor")
        return kayitlar
    _zk_bekle(page, 1.5)

    ikonlar = _gorunur_xls_ikonlari(page)
    print(f"    {sekme}: {len(ikonlar)} tablo")

    for sira, ikon in enumerate(ikonlar, 1):
        baslik = ikon["baslik"][:90].replace("\n", " ")
        try:
            with page.expect_download(timeout=config.DOWNLOAD_TIMEOUT_MS) as indirme:
                page.locator(f"#{ikon['id']}").click()
            dl = indirme.value
            dosya_adi = dl.suggested_filename
            yol = hedef / dosya_adi
            dl.save_as(yol)
            boyut = yol.stat().st_size

            kayitlar.append(
                IndirilenTablo(
                    donem=donem,
                    sekme=sekme,
                    baslik=baslik,
                    tablo_kodu=_tablo_kodu(dosya_adi),
                    dosya_adi=dosya_adi,
                    boyut=boyut,
                )
            )
            print(f"      [{sira}/{len(ikonlar)}] {dosya_adi:20s} {boyut/1024:7.0f} KB  {baslik[:50]}")
        except PWTimeout:
            print(f"      [{sira}/{len(ikonlar)}] ZAMAN AŞIMI: {baslik[:60]}")
        except Exception as hata:                      # noqa: BLE001
            print(f"      [{sira}/{len(ikonlar)}] HATA ({type(hata).__name__}): {baslik[:50]}")

        time.sleep(config.POLITE_DELAY_S)

    return kayitlar


def yil_indir(page: Page, donem: str) -> list[IndirilenTablo]:
    """Bir öğretim yılının tüm sekmelerindeki tabloları indirir."""
    hedef = config.RAW_DIR / config.donem_to_slug(donem)
    hedef.mkdir(parents=True, exist_ok=True)

    print(f"\n=== {donem} ===")
    yil_sayfasina_git(page, donem)

    kayitlar: list[IndirilenTablo] = []
    for sekme in config.TABS:
        kayitlar.extend(sekme_indir(page, donem, sekme, hedef))
    return kayitlar


def _portali_ac(sayfa: Page, deneme: int = 3) -> bool:
    """Portalı açar, geçici ağ hatalarında yeniden dener.

    Uzun çekimlerde tek bir anlık DNS/bağlantı hatası bütün işi kaybettirmemeli.
    """
    for sira in range(1, deneme + 1):
        try:
            sayfa.goto(config.BASE_URL, wait_until="domcontentloaded")
            _zk_bekle(sayfa, 2.5)
            return True
        except Exception as hata:                      # noqa: BLE001
            print(f"    portal açılamadı ({sira}/{deneme}): {type(hata).__name__}")
            if sira < deneme:
                time.sleep(5 * sira)
    return False


def _tarayici_baslat(p, headless: bool):
    """Playwright'ın kendi Chromium'unu, yoksa sistemdeki Chrome'u kullanır.

    `playwright install chromium` her ortamda çalışmayabiliyor (kurumsal ağ,
    indirme hatası). Sistemde Chrome varsa onunla devam etmek pipeline'ı
    klonlayan herkes için daha dayanıklı kılıyor.
    """
    try:
        return p.chromium.launch(headless=headless)
    except Exception as hata:                          # noqa: BLE001
        print(f"  ! Gömülü Chromium açılamadı ({type(hata).__name__}), sistem Chrome'u deneniyor")
        return p.chromium.launch(headless=headless, channel="chrome")


def calistir(donemler: list[str] | None = None, headless: bool = True) -> list[IndirilenTablo]:
    """Verilen öğretim yıllarını indirir ve manifest yazar."""
    donemler = donemler or config.YEARS
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    tum_kayitlar: list[IndirilenTablo] = []

    with sync_playwright() as p:
        tarayici = _tarayici_baslat(p, headless)
        sayfa = tarayici.new_page(accept_downloads=True)
        sayfa.set_default_timeout(config.NAV_TIMEOUT_MS)

        for donem in donemler:
            # Her yıl için temiz oturum: ZK'nın desktop state'i sekme geçişlerinde
            # birikip tembel yüklenen panelleri karıştırabiliyor.
            #
            # Navigasyon da yeniden denemeli: geçici bir ad çözümleme hatası
            # (ERR_NAME_NOT_RESOLVED) uzun süren bir çekimi baştan öldürmemeli.
            if not _portali_ac(sayfa):
                print(f"  ! {donem} atlandı: portal açılamadı")
                continue
            try:
                tum_kayitlar.extend(yil_indir(sayfa, donem))
            except Exception as hata:                  # noqa: BLE001
                print(f"  ! {donem} indirilemedi ({type(hata).__name__}: {hata})")

        tarayici.close()

    # Manifest birleştiriliyor: tek tek yıl çekildiğinde önceki yılların
    # kaydı silinmemeli, yoksa 'parse' onları görmez.
    manifest = config.RAW_DIR / "manifest.json"
    mevcut: list[dict] = []
    if manifest.exists():
        try:
            mevcut = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("  ! mevcut manifest okunamadı, yeniden oluşturuluyor")

    # Bu çalıştırmada yenilenen dönemlerin eski kayıtları düşürülüyor
    yenilenen = {k.donem for k in tum_kayitlar}
    birlesik = [k for k in mevcut if k.get("donem") not in yenilenen]
    birlesik.extend(asdict(k) for k in tum_kayitlar)
    birlesik.sort(key=lambda k: (k.get("donem", ""), k.get("tablo_kodu", "")))

    manifest.write_text(
        json.dumps(birlesik, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    toplam_mb = sum(k.boyut for k in tum_kayitlar) / 1024 / 1024
    print(f"\n{len(tum_kayitlar)} dosya, {toplam_mb:.1f} MB -> {config.RAW_DIR}")
    print(f"Manifest toplam {len(birlesik)} kayıt "
          f"({len({k.get('donem') for k in birlesik})} öğretim yılı)")
    print(f"Manifest: {manifest}")
    return tum_kayitlar
