namespace YokIstatistikWeb.Models
{
    /// <summary>
    /// Öğrenci, mezun ve yabancı uyruklu sayfaları aynı iskeleti paylaşıyor:
    /// filtre satırı, özet kartlar, kurum tablosu. Üçü için ayrı görünüm
    /// yazmak yerine ölçüm kolonları veriyle geliyor.
    /// </summary>
    public class KurumListesiViewModel
    {
        public string Baslik { get; set; } = "";
        public string Aciklama { get; set; } = "";
        public string Yil { get; set; } = "";
        public string YilGoster { get; set; } = "";

        public List<string> Sehirler { get; set; } = new();
        public List<string> Turler { get; set; } = new();
        public string? Arama { get; set; }
        public string? SeciliSehir { get; set; }
        public string? SeciliTur { get; set; }

        /// <summary>Tablodaki sayısal kolonların başlıkları.</summary>
        public List<string> OlcumBasliklari { get; set; } = new();

        public List<KurumSatiri> Satirlar { get; set; } = new();
        public List<OzetKart> Kartlar { get; set; } = new();

        public bool VeriVar => Satirlar.Count > 0;
    }

    public class KurumSatiri
    {
        public string Universite { get; set; } = "";
        public string Tur { get; set; } = "";
        public string Sehir { get; set; } = "";

        /// <summary>OlcumBasliklari ile aynı sırada.</summary>
        public List<int> Olcumler { get; set; } = new();

        /// <summary>Sıralama ve çubuk genişliği için kullanılan ana ölçüm.</summary>
        public int AnaOlcum { get; set; }
    }

    public class OzetKart
    {
        public string Etiket { get; set; } = "";
        public string Deger { get; set; } = "";
        public string? Alt { get; set; }
    }
}
