namespace YokIstatistikWeb.Models
{
    /// <summary>
    /// Yıllar arası karşılaştırma. Tek yıla bakmak yerine eğilimi görmek için:
    /// öğretim elemanı, öğrenci ve mezun sayılarının yıllara göre seyri.
    /// </summary>
    public class ZamanSerisiViewModel
    {
        public List<YilOzeti> Yillar { get; set; } = new();

        public bool VeriVar => Yillar.Count > 0;

        /// <summary>Grafiklerde eğilim çizebilmek için en az iki yıl gerekiyor.</summary>
        public bool TrendCizilebilir => Yillar.Count > 1;

        public YilOzeti? Ilk => Yillar.FirstOrDefault();
        public YilOzeti? Son => Yillar.LastOrDefault();

        /// <summary>İki uç yıl arasındaki yüzde değişim. Veri yoksa null.</summary>
        public double? Degisim(Func<YilOzeti, int> secici)
        {
            if (Ilk is null || Son is null) return null;
            var bas = secici(Ilk);
            return bas > 0 ? (double)(secici(Son) - bas) / bas * 100 : null;
        }
    }

    public class YilOzeti
    {
        public string Yil { get; set; } = "";
        public string YilGoster { get; set; } = "";

        public int KurumSayisi { get; set; }
        public int OgretimElemani { get; set; }
        public int OgretimElemaniErkek { get; set; }
        public int OgretimElemaniKadin { get; set; }

        public int Ogrenci { get; set; }
        public int Mezun { get; set; }

        // Öğretim türü (T007). Öğrenci sayısındaki değişimin hangi türden
        // geldiğini gösteriyor; toplam rakam tek başına yanıltıcı.
        public int Orgun { get; set; }
        public int Ikinci { get; set; }
        public int Uzaktan { get; set; }
        public int Acik { get; set; }

        public bool OgretimTuruVar => Orgun + Ikinci + Uzaktan + Acik > 0;

        public double KadinOrani =>
            OgretimElemani > 0 ? (double)OgretimElemaniKadin / OgretimElemani * 100 : 0;

        /// <summary>Öğretim elemanı başına düşen öğrenci. Yükseköğretimde temel gösterge.</summary>
        public double OgrenciBasinaElemanOrani =>
            OgretimElemani > 0 ? (double)Ogrenci / OgretimElemani : 0;

        public bool OgrenciVar => Ogrenci > 0;
        public bool MezunVar => Mezun > 0;
    }
}
