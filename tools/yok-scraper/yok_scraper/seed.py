"""Normalize edilmiş NDJSON kayıtlarını MongoDB'ye yükler.

Koleksiyon adı ve belge şeması, mevcut ASP.NET uygulamasının beklediği
biçimle birebir aynı tutuluyor (Models/Universite.cs, Models/Birim.cs):

    YOI_ogretim_elemani_akademik_gorev_sayilari_{yil_slug}
    { universite, tur, sehir, yil, birimler: [ {birim, profesor_erkek, ...} ] }

Bu yüzden pipeline devreye girdiğinde çalışan sayfalar bozulmuyor.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from pymongo import MongoClient

from . import config

VARSAYILAN_URI = "mongodb://localhost:27017"
VARSAYILAN_DB = "YokIstatistikDB"

# Tablo kodu -> koleksiyon adı öneki.
# T028'in adı mevcut uygulamayla uyumlu kalsın diye korunuyor.
KOLEKSIYON_ONEKI = {
    "T028": "YOI_ogretim_elemani_akademik_gorev_sayilari",
    "T035": "YOI_yabanci_uyruklu_ogretim_elemani",
    "T012": "YOI_ogrenci_sayilari",
    "M005": "YOI_mezun_sayilari",
    "T107": "YOI_akademik_birim_sayilari",
}

# Uygulamanın filtrelediği alanlar. T107'de üniversite kırılımı yok.
INDEKSLER = ("sehir", "tur", "universite")


def koleksiyon_adi(tablo_kodu: str, donem: str) -> str:
    onek = KOLEKSIYON_ONEKI.get(tablo_kodu, f"YOI_{tablo_kodu.lower()}")
    return f"{onek}_{config.donem_to_slug(donem)}"


def ndjson_oku(yol: Path) -> list[dict]:
    """Düz veya gzip'li NDJSON dosyasını okur."""
    ac = gzip.open if yol.suffix == ".gz" else open
    with ac(yol, "rt", encoding="utf-8") as f:
        return [json.loads(satir) for satir in f if satir.strip()]


def yukle(
    yol: Path,
    tablo_kodu: str,
    donem: str,
    uri: str = VARSAYILAN_URI,
    db_adi: str = VARSAYILAN_DB,
) -> int:
    """Tek bir işlenmiş dosyayı ilgili koleksiyona yazar (idempotent: önce temizler)."""
    kayitlar = ndjson_oku(yol)
    if not kayitlar:
        print(f"  ! {yol.name} boş, atlanıyor")
        return 0

    istemci = MongoClient(uri, serverSelectionTimeoutMS=5000)
    koleksiyon = istemci[db_adi][koleksiyon_adi(tablo_kodu, donem)]

    # Tekrar çalıştırıldığında kopya oluşmasın diye koleksiyon sıfırlanıyor.
    koleksiyon.delete_many({})
    koleksiyon.insert_many(kayitlar)

    # Yalnızca kayıtlarda gerçekten bulunan alanlar indekslensin.
    ornek = kayitlar[0]
    for alan in INDEKSLER:
        if alan in ornek:
            koleksiyon.create_index(alan)

    istemci.close()
    print(f"  {koleksiyon.name}: {len(kayitlar)} belge")
    return len(kayitlar)


def tumunu_yukle(uri: str = VARSAYILAN_URI, db_adi: str = VARSAYILAN_DB) -> int:
    """data/processed altındaki tüm işlenmiş dosyaları yükler.

    Dosya adı kalıbı: {yil_slug}_{tablo_kodu}.ndjson.gz  (ör. 2025_2026_T028.ndjson.gz)
    """
    toplam = 0
    dosyalar = sorted(config.PROCESSED_DIR.glob("*.ndjson.gz"))
    if not dosyalar:
        print(f"! {config.PROCESSED_DIR} altında işlenmiş dosya yok. Önce 'parse' çalıştır.")
        return 0

    for dosya in dosyalar:
        govde = dosya.name.replace(".ndjson.gz", "")
        parcalar = govde.split("_")
        tablo_kodu = parcalar[-1]
        donem = f"{parcalar[0]}-{parcalar[1]}"
        toplam += yukle(dosya, tablo_kodu, donem, uri, db_adi)

    print(f"\nToplam {toplam} belge yüklendi -> {db_adi}")
    return toplam
