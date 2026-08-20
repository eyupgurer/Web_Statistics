using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

namespace YokIstatistikWeb.Models
{
    /// <summary>
    /// YÖK T012: önlisans ve lisans düzeyinde öğrenci sayıları.
    /// Üst seviyedeki toplamlar üniversite satırının resmî rakamları.
    /// </summary>
    [BsonIgnoreExtraElements]
    public class OgrenciKurum
    {
        [BsonId]
        [BsonRepresentation(BsonType.ObjectId)]
        public string Id { get; set; } = "";

        /// <summary>Kalıcı ve okunabilir kurum kimliği (URL'lerde kullanılıyor).</summary>
        public string? slug { get; set; }

        public string universite { get; set; } = "";
        public string? universite_en { get; set; }
        public string tur { get; set; } = "";
        public string sehir { get; set; } = "";
        public string yil { get; set; } = "";

        public int? yeni_kayit_erkek { get; set; }
        public int? yeni_kayit_kadin { get; set; }
        public int? yeni_kayit_toplam { get; set; }

        public int? toplam_erkek { get; set; }
        public int? toplam_kadin { get; set; }
        public int? toplam_toplam { get; set; }

        public List<OgrenciBirim> birimler { get; set; } = new();
    }

    [BsonIgnoreExtraElements]
    public class OgrenciBirim
    {
        public string birim { get; set; } = "";
        public string? birim_en { get; set; }

        /// <summary>Birimin bulunduğu ilçe. Yalnızca öğrenci tablosunda var.</summary>
        public string? ilce { get; set; }

        public int? yeni_kayit_erkek { get; set; }
        public int? yeni_kayit_kadin { get; set; }
        public int? yeni_kayit_toplam { get; set; }

        public int? toplam_erkek { get; set; }
        public int? toplam_kadin { get; set; }
        public int? toplam_toplam { get; set; }
    }
}
