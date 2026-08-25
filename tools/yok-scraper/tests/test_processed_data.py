import gzip
import json
from pathlib import Path
import unittest


class ProcessedDataTests(unittest.TestCase):
    def test_tum_arsivler_gecerli_ndjson_icerir(self):
        veri_dizini = Path(__file__).resolve().parents[3] / "data" / "processed"
        arsivler = sorted(veri_dizini.glob("*.ndjson.gz"))
        self.assertEqual(124, len(arsivler))

        belge_sayisi = 0
        for arsiv in arsivler:
            with gzip.open(arsiv, "rt", encoding="utf-8") as akim:
                for satir_no, satir in enumerate(akim, 1):
                    try:
                        kayit = json.loads(satir)
                    except json.JSONDecodeError as hata:
                        self.fail(f"{arsiv.name}:{satir_no} geçersiz JSON: {hata}")
                    self.assertIsInstance(kayit, dict)
                    belge_sayisi += 1

        self.assertEqual(50_437, belge_sayisi)


if __name__ == "__main__":
    unittest.main()
