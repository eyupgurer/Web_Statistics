using Microsoft.Extensions.Options;
using MongoDB.Driver;

namespace YokIstatistikWeb.Models
{
    /// <summary>
    /// Koleksiyon adları veri pipeline'ının ürettiği kalıba göre kuruluyor:
    /// {onek}_{yil_slug}, ör. YOI_ogrenci_sayilari_2025_2026.
    /// </summary>
    public class MongoDbContext
    {
        private readonly IMongoDatabase _database;

        public MongoDbContext(IOptions<MongoDBSettings> settings)
        {
            var client = new MongoClient(settings.Value.ConnectionString);
            _database = client.GetDatabase(settings.Value.DatabaseName);
        }

        public const string OgretimElemani     = "YOI_ogretim_elemani_akademik_gorev_sayilari";
        public const string YabanciUyruklu     = "YOI_yabanci_uyruklu_ogretim_elemani";
        public const string Ogrenci            = "YOI_ogrenci_sayilari";
        public const string Mezun              = "YOI_mezun_sayilari";
        public const string AkademikBirim      = "YOI_akademik_birim_sayilari";
        public const string Lisansustu         = "YOI_lisansustu_ogrenci";
        public const string UyrukUlke          = "YOI_yabanci_uyruklu_ulke";
        public const string AlanLisans         = "YOI_egitim_alani_lisans";
        public const string AlanOnlisans       = "YOI_egitim_alani_onlisans";
        public const string YasOgretimTuru     = "YOI_yas_ogretim_turu";
        public const string OgrenciIlIlce      = "YOI_ogrenci_il_ilce";
        public const string BirimTuruOzet      = "YOI_birim_turu_ozet";
        public const string ProgramOgrenci     = "YOI_program_ogrenci";

        public IMongoCollection<T> Koleksiyon<T>(string onek, string yil) =>
            _database.GetCollection<T>($"{onek}_{yil}");

        /// <summary>Öğretim elemanı sayıları (T028) — uygulamanın ana tablosu.</summary>
        public IMongoCollection<Universite> GetCollectionForYear(string year) =>
            Koleksiyon<Universite>(OgretimElemani, year);

        /// <summary>
        /// Veritabanında verisi bulunan öğretim yılları (en yeniden eskiye).
        /// Elle tutulan bir liste yerine koleksiyon adlarından okunuyor; veri
        /// pipeline'ı yeni bir yıl yüklediğinde menüde kendiliğinden beliriyor.
        /// </summary>
        public List<string> MevcutYillar(string onek = OgretimElemani)
        {
            var desen = new MongoDB.Bson.BsonRegularExpression($"^{onek}_\\d{{4}}_\\d{{4}}$");
            return _database.ListCollectionNames(new ListCollectionNamesOptions
                {
                    Filter = Builders<MongoDB.Bson.BsonDocument>.Filter.Regex("name", desen)
                })
                .ToList()
                .Select(ad => ad[(onek.Length + 1)..])
                .OrderByDescending(y => y)
                .ToList();
        }

        /// <summary>Veritabanında hangi koleksiyonlar var? Boş sayfa göstermemek için.</summary>
        public bool KoleksiyonVar(string onek, string yil) =>
            _database.ListCollectionNames(new ListCollectionNamesOptions
            {
                Filter = Builders<MongoDB.Bson.BsonDocument>.Filter.Eq("name", $"{onek}_{yil}")
            }).Any();
    }
}
