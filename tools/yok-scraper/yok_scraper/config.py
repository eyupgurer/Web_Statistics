"""Pipeline yapılandırması.

YÖK istatistik portalı (https://istatistik.yok.gov.tr) ZK Framework tabanlı,
oturuma bağlı bir SPA. Statik indirme URL'i yok: her dosya, sunucuda o oturum
için üretilip /zkau/view/{desktopId}/dwnmed-N/{uuid}/{yil}_T{NNN}.xls
biçiminde tek kullanımlık bir adresten sunuluyor. Bu yüzden indirme adımı
tarayıcı otomasyonu (Playwright) ile yapılmak zorunda.
"""

from pathlib import Path

BASE_URL = "https://istatistik.yok.gov.tr/"

# Depo kökü: tools/yok-scraper/yok_scraper/config.py -> üç seviye yukarısı
REPO_ROOT = Path(__file__).resolve().parents[3]

# Ham .xls dosyaları (~yıl başına 38 dosya / ~35 MB). .gitignore'da: repoya girmez.
RAW_DIR = REPO_ROOT / "data" / "raw"

# Normalize edilmiş, sıkıştırılmış çıktı. Repoya giren tek veri katmanı bu.
PROCESSED_DIR = REPO_ROOT / "data" / "processed"

# Portalda "Yükseköğretim İstatistikleri" menüsündeki öğretim yılları.
# Menü etiketi "2025-2026 Öğretim Yılı", indirilen dosya adı ise "2026_T028.xls":
# dosya adındaki yıl, öğretim yılının BİTİŞ yılı.
#
# Portalda mevcut olan tüm yıllar. Yeni bir yıl yayımlandığında
# `python -m yok_scraper years` bunu bildiriyor.
YEARS = [
    "2013-2014", "2014-2015", "2015-2016", "2016-2017", "2017-2018",
    "2018-2019", "2019-2020", "2020-2021", "2021-2022", "2022-2023",
    "2023-2024", "2024-2025", "2025-2026",
]

ALL_YEARS = YEARS

# Yıl sayfasındaki sekmeler. BÜLTEN sekmesi Excel değil PDF sunduğu için dışarıda.
TABS = [
    "ÖZET TABLOLAR",
    "ÖĞRENCİ SAYILARI",
    "ÖĞRETİM ELEMANLARI",
    "MEZUN SAYILARI",
]

# ZK sunucusu dosyayı istek anında ürettiği için indirme uzun sürebiliyor.
DOWNLOAD_TIMEOUT_MS = 120_000
NAV_TIMEOUT_MS = 60_000

# Ardışık indirmeler arası bekleme (saniye). Kamu sunucusunu yormamak için.
POLITE_DELAY_S = 1.5


def donem_to_dosya_yili(donem: str) -> int:
    """'2025-2026' -> 2026 (indirilen dosya adında kullanılan yıl)."""
    return int(donem.split("-")[1])


def donem_to_slug(donem: str) -> str:
    """'2025-2026' -> '2025_2026' (MongoDB koleksiyon adı biçimi)."""
    return donem.replace("-", "_")


def normalize_tablo_kodu(kod: str) -> str:
    """Tablo kodunu kanonik biçime getirir: 'T28' -> 'T028', 'M1' -> 'M001'.

    YÖK 2024-2025 öğretim yılından itibaren tablo kodlarını üç haneye sıfırla
    doldurmaya başladı; öncesinde dolgusuz kullanıyordu (2024_T28.xls ama
    2025_T028.xls). Aynı tablo iki farklı kodla görünmesin diye tek biçime
    indirgiyoruz.
    """
    import re

    eslesme = re.match(r"^([A-Za-zÇĞİÖŞÜçğıöşü]+)(\d+)$", kod.strip())
    if not eslesme:
        return kod.strip().upper()
    onek, sayi = eslesme.groups()
    return f"{onek.upper()}{int(sayi):03d}"
