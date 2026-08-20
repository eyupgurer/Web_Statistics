using MongoDB.Bson.Serialization.Attributes;

namespace YokIstatistikWeb.Models
{
    [BsonIgnoreExtraElements]
    public class Birim
    {
        public string birim { get; set; }
        public string? birim_en { get; set; }
        public int? profesor_erkek { get; set; }
        public int? profesor_kadin { get; set; }
        public int? profesor_toplam { get; set; }

        public int? docent_erkek { get; set; }
        public int? docent_kadin { get; set; }
        public int? docent_toplam { get; set; }

        public int? doktor_ogretim_uyesi_erkek { get; set; }
        public int? doktor_ogretim_uyesi_kadin { get; set; }
        public int? doktor_ogretim_uyesi_toplam { get; set; }

        public int? ogretim_gorevlisi_erkek { get; set; }
        public int? ogretim_gorevlisi_kadin { get; set; }
        public int? ogretim_gorevlisi_toplam { get; set; }

        public int? arastirma_gorevlisi_erkek { get; set; }
        public int? arastirma_gorevlisi_kadin { get; set; }
        public int? arastirma_gorevlisi_toplam { get; set; }

        public int? toplam_erkek { get; set; }
        public int? toplam_kadin { get; set; }
        public int? toplam_toplam { get; set; }
    }
}
