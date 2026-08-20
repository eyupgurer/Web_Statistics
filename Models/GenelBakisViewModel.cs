namespace YokIstatistikWeb.Models
{
    /// <summary>Ana sayfanın ihtiyaç duyduğu özet veriler.</summary>
    public class GenelBakisViewModel
    {
        public string Yil { get; set; } = "";
        public string YilGoster { get; set; } = "";

        public int ToplamKurum { get; set; }
        public int ToplamOgretimElemani { get; set; }
        public int ToplamErkek { get; set; }
        public int ToplamKadin { get; set; }

        public double KadinOrani =>
            ToplamOgretimElemani > 0 ? (double)ToplamKadin / ToplamOgretimElemani * 100 : 0;

        public int KurumBasinaOrtalama =>
            ToplamKurum > 0 ? (int)Math.Round((double)ToplamOgretimElemani / ToplamKurum) : 0;

        // Öğrenci sayıları iki ayrı tablodan geliyor: T012 (önlisans+lisans)
        // ve T022 (yüksek lisans + doktora).
        public int OnlisansLisansOgrenci { get; set; }
        public int YuksekLisans { get; set; }
        public int Doktora { get; set; }

        public int ToplamOgrenci => OnlisansLisansOgrenci + YuksekLisans + Doktora;
        public bool OgrenciVar => ToplamOgrenci > 0;

        public List<TurDagilimi> Turler { get; set; } = new();
        public List<UnvanDagilimi> Unvanlar { get; set; } = new();

        public bool VeriVar => ToplamKurum > 0;
    }

    public class TurDagilimi
    {
        public string Ad { get; set; } = "";
        public int KurumSayisi { get; set; }
        public int KisiSayisi { get; set; }
        public string Renk { get; set; } = "";

        /// <summary>Çubuk genişliği. Çok küçük paylar CSS'te taban genişlikle görünür kalıyor.</summary>
        public double Oran { get; set; }
    }

    public class UnvanDagilimi
    {
        public string Ad { get; set; } = "";
        public int Erkek { get; set; }
        public int Kadin { get; set; }
        public int Toplam => Erkek + Kadin;

        public double ErkekOrani => Toplam > 0 ? (double)Erkek / Toplam * 100 : 0;
        public double KadinOrani => Toplam > 0 ? (double)Kadin / Toplam * 100 : 0;
    }
}
