using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

namespace YokIstatistikWeb.Models
{
    // YÖK verisi zamanla yeni alanlar kazanabiliyor (İngilizce adlar, ek kırılımlar).
    // Bu öznitelik olmadan MongoDB sürücüsü eşlenmemiş her alanda istisna fırlatır.
    [BsonIgnoreExtraElements]
    public class Universite
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

        public List<Birim> birimler { get; set; } = new();

        // Üniversite satırının YÖK'teki resmî toplamları. Birim satırlarının
        // toplamı kaynak verideki tekrar/eksik kayıtlar yüzünden bazı yıllarda
        // birkaç kişi sapabiliyor; yetkili rakam bunlar.
        public int? toplam_erkek { get; set; }
        public int? toplam_kadin { get; set; }
        public int? toplam_toplam { get; set; }

        public string yil { get; set; } = "";
    }
}
