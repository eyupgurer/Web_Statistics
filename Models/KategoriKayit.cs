using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

namespace YokIstatistikWeb.Models
{
    /// <summary>
    /// YÖK T201: yabancı uyruklu öğretim elemanları, uyruğuna göre.
    /// Satırlar üniversite değil ülke.
    /// </summary>
    [BsonIgnoreExtraElements]
    public class UlkeKayit
    {
        [BsonId]
        [BsonRepresentation(BsonType.ObjectId)]
        public string Id { get; set; } = "";

        public string ulke { get; set; } = "";
        public string? ulke_en { get; set; }
        public string yil { get; set; } = "";

        public int? profesor_toplam { get; set; }
        public int? docent_toplam { get; set; }
        public int? doktor_ogretim_uyesi_toplam { get; set; }
        public int? ogretim_gorevlisi_toplam { get; set; }
        public int? arastirma_gorevlisi_toplam { get; set; }

        public int? toplam_erkek { get; set; }
        public int? toplam_kadin { get; set; }
        public int? toplam_toplam { get; set; }
    }

    /// <summary>
    /// YÖK T017 / T019: eğitim ve öğretim alanına göre öğrenci sayıları.
    /// Satırlar hiyerarşik: 0 = geniş alan, 1 = dar alan, 2 = ayrıntılı alan.
    /// Her seviye kendi içinde ülke toplamına eşit; seviyeler toplanmamalı.
    /// </summary>
    [BsonIgnoreExtraElements]
    public class EgitimAlaniKayit
    {
        [BsonId]
        [BsonRepresentation(BsonType.ObjectId)]
        public string Id { get; set; } = "";

        public string alan { get; set; } = "";
        public string? alan_en { get; set; }
        public string yil { get; set; } = "";
        public int seviye { get; set; }

        public int? yeni_kayit_erkek { get; set; }
        public int? yeni_kayit_kadin { get; set; }
        public int? yeni_kayit_toplam { get; set; }

        public int? toplam_erkek { get; set; }
        public int? toplam_kadin { get; set; }
        public int? toplam_toplam { get; set; }

        public double KadinOrani =>
            (toplam_toplam ?? 0) > 0 ? (double)(toplam_kadin ?? 0) / toplam_toplam!.Value * 100 : 0;
    }
}
