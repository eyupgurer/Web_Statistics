using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

namespace YokIstatistikWeb.Models
{
    /// <summary>
    /// YÖK T022: enstitülere göre lisansüstü öğrenci sayıları.
    /// Kullandığımız T012 yalnızca önlisans ve lisansı kapsıyor; yüksek lisans
    /// ve doktora bu tablodan geliyor.
    /// </summary>
    [BsonIgnoreExtraElements]
    public class LisansustuKurum
    {
        [BsonId]
        [BsonRepresentation(BsonType.ObjectId)]
        public string Id { get; set; } = "";

        /// <summary>Kalıcı ve okunabilir kurum kimliği (URL'lerde kullanılıyor).</summary>
        public string? slug { get; set; }

        public string universite { get; set; } = "";
        public string tur { get; set; } = "";
        public string sehir { get; set; } = "";
        public string yil { get; set; } = "";

        public int? yuksek_lisans_erkek { get; set; }
        public int? yuksek_lisans_kadin { get; set; }
        public int? yuksek_lisans_toplam { get; set; }

        public int? doktora_erkek { get; set; }
        public int? doktora_kadin { get; set; }
        public int? doktora_toplam { get; set; }

        public int? toplam_erkek { get; set; }
        public int? toplam_kadin { get; set; }
        public int? toplam_toplam { get; set; }

        public int? yeni_kayit_toplam { get; set; }
        public int? yeni_kayit_yuksek_lisans_toplam { get; set; }
        public int? yeni_kayit_doktora_toplam { get; set; }

        public List<LisansustuBirim> birimler { get; set; } = new();
    }

    [BsonIgnoreExtraElements]
    public class LisansustuBirim
    {
        public string birim { get; set; } = "";
        public int? yuksek_lisans_toplam { get; set; }
        public int? doktora_toplam { get; set; }
        public int? toplam_toplam { get; set; }
    }
}
