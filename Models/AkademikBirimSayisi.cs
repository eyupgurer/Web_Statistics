using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

namespace YokIstatistikWeb.Models
{
    /// <summary>
    /// YÖK T107: türlerine göre akademik birim sayıları.
    /// Üniversite kırılımı yok; birim türü satırlarda, üniversite türü kolonlarda.
    /// </summary>
    [BsonIgnoreExtraElements]
    public class AkademikBirimSayisi
    {
        [BsonId]
        [BsonRepresentation(BsonType.ObjectId)]
        public string Id { get; set; } = "";

        public string birim_turu { get; set; } = "";
        public string? birim_turu_en { get; set; }
        public string yil { get; set; } = "";

        public int? devlet_aktif { get; set; }
        public int? devlet_pasif { get; set; }
        public int? vakif_aktif { get; set; }
        public int? vakif_pasif { get; set; }
        public int? vakif_myo_aktif { get; set; }
        public int? vakif_myo_pasif { get; set; }
        public int? toplam_aktif { get; set; }
        public int? toplam_pasif { get; set; }
    }
}
