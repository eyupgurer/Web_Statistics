"""YÖK portalındaki öğretim yılı listesini karşılaştırma yardımcıları."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import TextIO
import sys

from . import config


YIL_DESENI = re.compile(r"\b(20\d{2}-20\d{2})\s+Öğretim\s+Yılı\b", re.IGNORECASE)


def metinden_yillari_cikar(metinler: Iterable[str]) -> list[str]:
    """Görünür portal metninden benzersiz öğretim yıllarını çıkarır."""
    bulunan = {eslesme.group(1) for metin in metinler for eslesme in YIL_DESENI.finditer(metin)}
    return sorted(bulunan)


def yeni_yillari_bul(portal_yillari: Iterable[str]) -> list[str]:
    """Portalda olup yapılandırmada bulunmayan yılları döndürür."""
    return sorted(set(portal_yillari) - set(config.YEARS))


def sonucu_raporla(portal_yillari: Iterable[str], cikti: TextIO = sys.stdout) -> int:
    """Workflow'un okuyacağı kararlı çıktıyı üretir.

    Yeni yıl varsa 2, yoksa 0 döner. Workflow 2 kodunu özel olarak ele alır.
    """
    portal = sorted(set(portal_yillari))
    yeni = yeni_yillari_bul(portal)
    print(f"PORTAL_YILLARI={','.join(portal)}", file=cikti)
    if yeni:
        print(f"YENI_YIL={','.join(yeni)}", file=cikti)
        return 2
    print("Yeni öğretim yılı yok.", file=cikti)
    return 0
