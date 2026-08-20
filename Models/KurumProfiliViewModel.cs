namespace YokIstatistikWeb.Models
{
    /// <summary>
    /// Bir üniversitenin tüm veri gruplarını tek yerde toplar.
    /// Gruplar ayrı koleksiyonlarda ve ortak bir kimlik taşımıyorlar; eşleştirme
    /// üniversite ADI üzerinden yapılıyor. Kaynakta adı yazılmamış kurumlar
    /// (M005'te 8 adet) eşleşemiyor, o yüzden her grup null olabilir.
    /// </summary>
    public class KurumProfiliViewModel
    {
        public Universite OgretimElemani { get; set; } = new();
        public OgrenciKurum? Ogrenci { get; set; }
        public MezunKurum? Mezun { get; set; }
        public Universite? YabanciUyruklu { get; set; }

        public string Yil { get; set; } = "";
        public string YilGoster { get; set; } = "";

        public bool OgrenciVar => (Ogrenci?.toplam_toplam ?? 0) > 0;
        public bool MezunVar => (Mezun?.toplam_toplam ?? 0) > 0;
        public bool YabanciVar => (YabanciUyruklu?.toplam_toplam ?? 0) > 0;

        /// <summary>
        /// Öğretim elemanı başına öğrenci. Yükseköğretimde temel kalite
        /// göstergesi; ikisi de yüklüyse hesaplanabiliyor.
        /// </summary>
        public double? OgrenciBasinaEleman
        {
            get
            {
                var eleman = OgretimElemani.toplam_toplam ?? 0;
                var ogrenci = Ogrenci?.toplam_toplam ?? 0;
                return eleman > 0 && ogrenci > 0 ? (double)ogrenci / eleman : null;
            }
        }
    }
}
