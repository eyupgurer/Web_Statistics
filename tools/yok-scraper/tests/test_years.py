from io import StringIO
import unittest

from yok_scraper.years import metinden_yillari_cikar, sonucu_raporla, yeni_yillari_bul


class YearsTests(unittest.TestCase):
    def test_portal_metninden_yillari_benzersiz_cikarir(self):
        metinler = [
            "2025-2026 Öğretim Yılı\n2024-2025 Öğretim Yılı",
            "2025-2026 Öğretim Yılı",
        ]

        self.assertEqual(["2024-2025", "2025-2026"], metinden_yillari_cikar(metinler))

    def test_yeni_yili_bulur(self):
        self.assertEqual(["2026-2027"], yeni_yillari_bul(["2025-2026", "2026-2027"]))

    def test_workflow_ciktisi_ve_cikis_kodu_kararlidir(self):
        cikti = StringIO()

        kod = sonucu_raporla(["2025-2026", "2026-2027"], cikti)

        self.assertEqual(2, kod)
        self.assertIn("YENI_YIL=2026-2027", cikti.getvalue())


if __name__ == "__main__":
    unittest.main()
