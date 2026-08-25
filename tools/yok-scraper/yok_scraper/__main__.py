"""YÖK veri pipeline'ı komut satırı arayüzü.

Kullanım:
    python -m yok_scraper years                  # yeni öğretim yılı var mı kontrol et
    python -m yok_scraper scrape                 # tüm yapılandırılmış yılları indir
    python -m yok_scraper scrape --yil 2025-2026 # tek yıl
    python -m yok_scraper scrape --headed        # tarayıcıyı görünür çalıştır (hata ayıklama)
    python -m yok_scraper inspect <dosya.xls>    # bir Excel'in yapısını dök
    python -m yok_scraper parse                  # ham .xls -> data/processed/*.ndjson.gz
    python -m yok_scraper seed                   # işlenmiş veriyi MongoDB'ye yükle
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config


def main(argv: list[str] | None = None) -> int:
    ayristirici = argparse.ArgumentParser(
        prog="yok_scraper",
        description="YÖK Yükseköğretim İstatistikleri veri pipeline'ı",
    )
    alt = ayristirici.add_subparsers(dest="komut", required=True)

    alt.add_parser("years", help="Portalda yeni öğretim yılı var mı kontrol et")

    p_scrape = alt.add_parser("scrape", help="Portaldan ham .xls dosyalarını indir")
    p_scrape.add_argument("--yil", action="append", help="Öğretim yılı, ör. 2025-2026 (birden çok kez verilebilir)")
    p_scrape.add_argument("--headed", action="store_true", help="Tarayıcıyı görünür çalıştır")

    p_inspect = alt.add_parser("inspect", help="Bir .xls dosyasının sayfa/başlık yapısını dök")
    p_inspect.add_argument("dosya", type=Path)
    p_inspect.add_argument("--satir", type=int, default=25, help="Kaç satır gösterilsin")

    alt.add_parser("parse", help="Ham .xls -> normalize NDJSON")

    p_seed = alt.add_parser("seed", help="İşlenmiş veriyi MongoDB'ye yükle")
    p_seed.add_argument("--uri", default="mongodb://localhost:27017")
    p_seed.add_argument("--db", default="YokIstatistikDB")

    args = ayristirici.parse_args(argv)

    if args.komut == "years":
        from .scrape import portaldaki_yillari_oku
        from .years import sonucu_raporla

        return sonucu_raporla(portaldaki_yillari_oku())

    if args.komut == "scrape":
        from .scrape import calistir

        calistir(donemler=args.yil or config.YEARS, headless=not args.headed)
        return 0

    if args.komut == "inspect":
        from .parse import incele

        incele(args.dosya, satir_sayisi=args.satir)
        return 0

    if args.komut == "parse":
        from .parse import tumunu_ayristir

        tumunu_ayristir()
        return 0

    if args.komut == "seed":
        from .seed import tumunu_yukle

        tumunu_yukle(uri=args.uri, db_adi=args.db)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
