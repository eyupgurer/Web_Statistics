using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

namespace YokIstatistikWeb.Models
{
    /// <summary>
    /// YÖK T105: program düzeyinde öğrenci sayıları. Her satır bir program;
    /// üniversite ve birim adı satırda tekrarlıyor (denormalize düz tablo).
    /// Yalnızca en güncel öğretim yılı için tutuluyor.
    /// </summary>
    [BsonIgnoreExtraElements]
    public class ProgramKayit
    {
        [BsonId]
        [BsonRepresentation(BsonType.ObjectId)]
        public string Id { get; set; } = "";

        public string universite { get; set; } = "";
        public string birim { get; set; } = "";
        public string program { get; set; } = "";
        public string yil { get; set; } = "";

        public int? onlisans_orgun_toplam { get; set; }
        public int? onlisans_acik_toplam { get; set; }
        public int? lisans_orgun_toplam { get; set; }
        public int? lisans_acik_toplam { get; set; }
        public int? yuksek_lisans_orgun_toplam { get; set; }
        public int? doktora_orgun_toplam { get; set; }

        public int? toplam_erkek { get; set; }
        public int? toplam_kadin { get; set; }
        public int? toplam_toplam { get; set; }

        public double KadinOrani =>
            (toplam_toplam ?? 0) > 0 ? (double)(toplam_kadin ?? 0) / toplam_toplam!.Value * 100 : 0;
    }

    /// <summary>Bir programın ülke genelindeki toplamı.</summary>
    public class ProgramOzeti
    {
        public string Program { get; set; } = "";
        public int KurumSayisi { get; set; }
        public int Toplam { get; set; }
        public int Erkek { get; set; }
        public int Kadin { get; set; }

        public double KadinOrani => Toplam > 0 ? (double)Kadin / Toplam * 100 : 0;
    }

    public class ProgramAramaViewModel
    {
        public string Yil { get; set; } = "";
        public string YilGoster { get; set; } = "";
        public string? Arama { get; set; }

        public List<ProgramOzeti> Programlar { get; set; } = new();
        public string? SeciliProgram { get; set; }
        public List<ProgramKayit> Kurumlar { get; set; } = new();

        public int ToplamProgram { get; set; }
        public bool VeriVar => Programlar.Count > 0 || Kurumlar.Count > 0;
    }
}
