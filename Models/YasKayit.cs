using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

namespace YokIstatistikWeb.Models
{
    /// <summary>
    /// YÖK T007: yaş gruplarına göre öğrenci sayıları, öğrenim düzeyi ve
    /// öğretim türü kırılımında. Öğretim türü (örgün / ikinci / uzaktan /
    /// açık öğretim) başka hiçbir tabloda yok.
    /// </summary>
    [BsonIgnoreExtraElements]
    public class YasKayit
    {
        [BsonId]
        [BsonRepresentation(BsonType.ObjectId)]
        public string Id { get; set; } = "";

        public string yas { get; set; } = "";
        public string yil { get; set; } = "";

        public int? onlisans_orgun_toplam { get; set; }
        public int? onlisans_ikinci_toplam { get; set; }
        public int? onlisans_uzaktan_toplam { get; set; }
        public int? onlisans_acik_toplam { get; set; }

        public int? lisans_orgun_toplam { get; set; }
        public int? lisans_ikinci_toplam { get; set; }
        public int? lisans_uzaktan_toplam { get; set; }
        public int? lisans_acik_toplam { get; set; }

        public int? yuksek_lisans_orgun_toplam { get; set; }
        public int? yuksek_lisans_ikinci_toplam { get; set; }
        public int? yuksek_lisans_uzaktan_toplam { get; set; }

        public int? doktora_orgun_toplam { get; set; }

        public int? toplam_erkek { get; set; }
        public int? toplam_kadin { get; set; }
        public int? toplam_toplam { get; set; }

        public int Orgun => (onlisans_orgun_toplam ?? 0) + (lisans_orgun_toplam ?? 0)
                          + (yuksek_lisans_orgun_toplam ?? 0) + (doktora_orgun_toplam ?? 0);
        public int Ikinci => (onlisans_ikinci_toplam ?? 0) + (lisans_ikinci_toplam ?? 0)
                           + (yuksek_lisans_ikinci_toplam ?? 0);
        public int Uzaktan => (onlisans_uzaktan_toplam ?? 0) + (lisans_uzaktan_toplam ?? 0)
                            + (yuksek_lisans_uzaktan_toplam ?? 0);
        public int Acik => (onlisans_acik_toplam ?? 0) + (lisans_acik_toplam ?? 0);
    }
}
