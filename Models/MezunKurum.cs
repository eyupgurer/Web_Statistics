using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

namespace YokIstatistikWeb.Models
{
    /// <summary>
    /// YÖK M005: mezun sayıları. Birim kırılımı, birim ADI değil birim TÜRÜ
    /// bazında (fakülte, meslek yüksekokulu, yüksekokul).
    /// </summary>
    [BsonIgnoreExtraElements]
    public class MezunKurum
    {
        [BsonId]
        [BsonRepresentation(BsonType.ObjectId)]
        public string Id { get; set; } = "";

        public string universite { get; set; } = "";
        public string? universite_en { get; set; }
        public string tur { get; set; } = "";
        public string sehir { get; set; } = "";
        public string yil { get; set; } = "";

        public int? toplam_erkek { get; set; }
        public int? toplam_kadin { get; set; }
        public int? toplam_toplam { get; set; }

        public List<MezunBirim> birimler { get; set; } = new();
    }

    [BsonIgnoreExtraElements]
    public class MezunBirim
    {
        public string birim { get; set; } = "";
        public string? birim_en { get; set; }

        public int? toplam_erkek { get; set; }
        public int? toplam_kadin { get; set; }
        public int? toplam_toplam { get; set; }
    }
}
