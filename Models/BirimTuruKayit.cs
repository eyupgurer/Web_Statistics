using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

namespace YokIstatistikWeb.Models
{
    /// <summary>
    /// YÖK T003: eğitim birimlerine göre öğrenci ve öğretim elemanı sayıları.
    /// İki veri grubunu yan yana veren tek tablo. Satırlar hiyerarşik:
    /// seviye 1 = birim türü (FAKÜLTE), seviye 2 = tek tek birim adları.
    /// Her seviye ayrı ayrı ülke toplamına eşit; toplanmamalı.
    /// </summary>
    [BsonIgnoreExtraElements]
    public class BirimTuruKayit
    {
        [BsonId]
        [BsonRepresentation(BsonType.ObjectId)]
        public string Id { get; set; } = "";

        public string birim_turu { get; set; } = "";
        public string yil { get; set; } = "";
        public int seviye { get; set; }

        public int? onlisans_lisans_toplam { get; set; }
        public int? onlisans_lisans_yeni_kayit_toplam { get; set; }
        public int? yuksek_lisans_toplam { get; set; }
        public int? doktora_toplam { get; set; }
        public int? ogretim_elemani_toplam { get; set; }

        public int Ogrenci => (onlisans_lisans_toplam ?? 0)
                            + (yuksek_lisans_toplam ?? 0) + (doktora_toplam ?? 0);

        /// <summary>Öğretim elemanı başına öğrenci. Birim türleri arasında büyük fark var.</summary>
        public double? OgrenciBasina =>
            (ogretim_elemani_toplam ?? 0) > 0 && Ogrenci > 0
                ? (double)Ogrenci / ogretim_elemani_toplam!.Value : null;
    }

    /// <summary>YÖK T102: öğrenci sayıları, il/ilçe ve öğretim türü kırılımında.</summary>
    [BsonIgnoreExtraElements]
    public class IlIlceOgrenci
    {
        [BsonId]
        [BsonRepresentation(BsonType.ObjectId)]
        public string Id { get; set; } = "";

        public string? slug { get; set; }
        public string universite { get; set; } = "";
        public string tur { get; set; } = "";
        public string sehir { get; set; } = "";
        public string yil { get; set; } = "";

        public int? onlisans_orgun_toplam { get; set; }
        public int? onlisans_acik_toplam { get; set; }
        public int? lisans_orgun_toplam { get; set; }
        public int? lisans_acik_toplam { get; set; }
        public int? toplam_toplam { get; set; }
    }
}
