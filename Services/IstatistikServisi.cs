using MongoDB.Driver;
using YokIstatistikWeb.Models;

namespace YokIstatistikWeb.Services
{
    /// <summary>
    /// Üniversite istatistiklerine tek erişim noktası.
    /// Önceden HomeController UniversiteService'i, Yuksekogretim ise MongoDbContext'i
    /// doğrudan kullanıyordu; iki ayrı yol iki ayrı davranış demekti.
    /// </summary>
    public class IstatistikServisi
    {
        private readonly MongoDbContext _context;
        private readonly ILogger<IstatistikServisi> _logger;

        public IstatistikServisi(MongoDbContext context, ILogger<IstatistikServisi> logger)
        {
            _context = context;
            _logger = logger;
        }

        /// <summary>Menüde ve rotalarda kullanılan öğretim yılları (en yeniden eskiye).</summary>
        public static readonly IReadOnlyList<string> Yillar = new[]
        {
            "2025_2026", "2024_2025", "2023_2024", "2022_2023", "2021_2022"
        };

        public static string VarsayilanYil => Yillar[0];

        /// <summary>Geçersiz yıl parametrelerinin koleksiyon adına sızmasını engeller.</summary>
        public static string YilDogrula(string? yil) =>
            !string.IsNullOrWhiteSpace(yil) && Yillar.Contains(yil) ? yil : VarsayilanYil;

        /// <summary>"2025_2026" -> "2025-2026" (ekranda gösterim için).</summary>
        public static string YilGoster(string yil) => yil.Replace("_", "-");

        private static readonly System.Globalization.CultureInfo TrKultur = new("tr-TR");

        /// <summary>
        /// "VAKIF MYO" -> "Vakıf MYO". Veri tümü büyük harf geliyor; ekranda
        /// bağırmasın diye başlık biçimine çevriliyor. Türkçe kültür şart:
        /// değişmez kültürde "VAKIF" -> "Vakif" olur (ı yerine i).
        /// </summary>
        public static string TurGoster(string? tur)
        {
            if (string.IsNullOrWhiteSpace(tur)) return "";
            return string.Join(' ', tur.Split(' ', StringSplitOptions.RemoveEmptyEntries)
                .Select(k => k.Length <= 3 && k == k.ToUpper(TrKultur)
                    ? k                                        // MYO gibi kısaltmalar korunur
                    : TrKultur.TextInfo.ToTitleCase(k.ToLower(TrKultur))));
        }

        /// <summary>
        /// Filtrelenmiş üniversite listesi. Filtreler Mongo tarafında uygulanıyor;
        /// önceden tüm koleksiyon belleğe çekilip LINQ ile süzülüyordu.
        /// </summary>
        public List<Universite> Listele(string yil, string? arama = null, string? sehir = null, string? tur = null)
        {
            var koleksiyon = _context.GetCollectionForYear(YilDogrula(yil));
            var f = Builders<Universite>.Filter;
            var filtre = f.Empty;

            if (!string.IsNullOrWhiteSpace(arama))
            {
                // Kullanıcı girdisi regex olarak yorumlanmasın diye kaçırılıyor.
                var desen = System.Text.RegularExpressions.Regex.Escape(arama.Trim());
                filtre &= f.Regex(u => u.universite,
                    new MongoDB.Bson.BsonRegularExpression(desen, "i"));
            }

            if (!string.IsNullOrWhiteSpace(sehir))
                filtre &= f.Eq(u => u.sehir, sehir);

            if (!string.IsNullOrWhiteSpace(tur))
                filtre &= f.Eq(u => u.tur, tur);

            return koleksiyon.Find(filtre)
                             .SortBy(u => u.universite)
                             .ToList();
        }

        public Universite? Getir(string yil, string id)
        {
            var koleksiyon = _context.GetCollectionForYear(YilDogrula(yil));
            return koleksiyon.Find(u => u.Id == id).FirstOrDefault();
        }

        /// <summary>Filtre açılır listeleri için o yılda geçen şehirler.</summary>
        public List<string> Sehirler(string yil) =>
            _context.GetCollectionForYear(YilDogrula(yil))
                    .Distinct<string>("sehir", Builders<Universite>.Filter.Empty)
                    .ToList()
                    .Where(s => !string.IsNullOrWhiteSpace(s))
                    .OrderBy(s => s, StringComparer.Create(new System.Globalization.CultureInfo("tr-TR"), false))
                    .ToList();

        public List<string> Turler(string yil) =>
            _context.GetCollectionForYear(YilDogrula(yil))
                    .Distinct<string>("tur", Builders<Universite>.Filter.Empty)
                    .ToList()
                    .Where(t => !string.IsNullOrWhiteSpace(t))
                    .OrderBy(t => t)
                    .ToList();

        /// <summary>
        /// Şehir bazlı öğretim elemanı toplamları. Yıl parametresi alıyor;
        /// önceden SehirController sabit 2024_2025 koleksiyonuna bağlıydı.
        /// </summary>
        public List<SehirVeriViewModel> SehirDagilimi(string yil)
        {
            return Listele(yil)
                .GroupBy(u => u.sehir)
                .Where(g => !string.IsNullOrWhiteSpace(g.Key))
                .Select(g => new SehirVeriViewModel
                {
                    Sehir = g.Key,
                    // YÖK'ün resmî üniversite toplamı kullanılıyor; birimleri
                    // toplamak bazı yıllarda kaynak hatası yüzünden sapıyor.
                    Toplam = g.Sum(u => u.toplam_toplam ?? 0)
                })
                .OrderByDescending(s => s.Toplam)
                .ToList();
        }

        /// <summary>Ana sayfa kartları için kurum sayıları.</summary>
        public (int Toplam, int Devlet, int Vakif, int VakifMyo) KurumSayilari(string yil)
        {
            var hepsi = Listele(yil);
            return (
                hepsi.Count,
                hepsi.Count(u => string.Equals(u.tur, "DEVLET", StringComparison.OrdinalIgnoreCase)),
                hepsi.Count(u => string.Equals(u.tur, "VAKIF", StringComparison.OrdinalIgnoreCase)),
                hepsi.Count(u => string.Equals(u.tur, "VAKIF MYO", StringComparison.OrdinalIgnoreCase))
            );
        }


        /// <summary>Akademik unvanlar ve Birim modelindeki alan önekleri.</summary>
        private static readonly (string Ad, Func<Birim, int?> Erkek, Func<Birim, int?> Kadin)[] Unvanlar =
        {
            ("Profesör",             b => b.profesor_erkek,             b => b.profesor_kadin),
            ("Doçent",               b => b.docent_erkek,               b => b.docent_kadin),
            ("Doktor öğretim üyesi", b => b.doktor_ogretim_uyesi_erkek, b => b.doktor_ogretim_uyesi_kadin),
            ("Öğretim görevlisi",    b => b.ogretim_gorevlisi_erkek,    b => b.ogretim_gorevlisi_kadin),
            ("Araştırma görevlisi",  b => b.arastirma_gorevlisi_erkek,  b => b.arastirma_gorevlisi_kadin),
        };

        private static readonly Dictionary<string, string> TurRenkleri = new()
        {
            ["DEVLET"]    = "var(--seri-1)",
            ["VAKIF"]     = "var(--seri-2)",
            ["VAKIF MYO"] = "var(--seri-3)",
        };

        /// <summary>Ana sayfa özeti: kurum sayıları, cinsiyet ve unvan dağılımları.</summary>
        public GenelBakisViewModel GenelBakis(string yil)
        {
            yil = YilDogrula(yil);
            var hepsi = Listele(yil);

            var model = new GenelBakisViewModel
            {
                Yil = yil,
                YilGoster = YilGoster(yil),
                ToplamKurum = hepsi.Count,
                // Üniversite satırındaki resmî toplamlar kullanılıyor.
                ToplamErkek = hepsi.Sum(u => u.toplam_erkek ?? 0),
                ToplamKadin = hepsi.Sum(u => u.toplam_kadin ?? 0),
                ToplamOgretimElemani = hepsi.Sum(u => u.toplam_toplam ?? 0),
            };

            model.Turler = hepsi
                .GroupBy(u => u.tur ?? "")
                .Select(g => new TurDagilimi
                {
                    Ad = TurGoster(g.Key),
                    KurumSayisi = g.Count(),
                    KisiSayisi = g.Sum(u => u.toplam_toplam ?? 0),
                    Renk = TurRenkleri.TryGetValue(g.Key, out var r) ? r : "var(--metin-soluk)",
                })
                .OrderByDescending(t => t.KisiSayisi)
                .ToList();

            foreach (var t in model.Turler)
                t.Oran = model.ToplamOgretimElemani > 0
                    ? (double)t.KisiSayisi / model.ToplamOgretimElemani * 100 : 0;

            // Unvan kırılımı birim satırlarından geliyor; unvan bazında resmî
            // toplam yok, yalnızca kurum geneli var.
            var birimler = hepsi.SelectMany(u => u.birimler ?? new List<Birim>()).ToList();
            model.Unvanlar = Unvanlar
                .Select(u => new UnvanDagilimi
                {
                    Ad = u.Ad,
                    Erkek = birimler.Sum(b => u.Erkek(b) ?? 0),
                    Kadin = birimler.Sum(b => u.Kadin(b) ?? 0),
                })
                .OrderByDescending(u => u.Toplam)
                .ToList();

            return model;
        }


        // ------------------------------------------------------------------
        // Diğer tablo grupları
        // ------------------------------------------------------------------

        /// <summary>
        /// Ortak filtreli listeleme. Tüm kurum tabloları aynı alan adlarını
        /// taşıyor (universite / sehir / tur), bu yüzden alan adları metin
        /// olarak veriliyor ve tek yöntem hepsine yetiyor.
        /// </summary>
        private List<T> FiltreliListe<T>(string onek, string yil,
            string? arama = null, string? sehir = null, string? tur = null)
        {
            var koleksiyon = _context.Koleksiyon<T>(onek, YilDogrula(yil));
            var f = Builders<T>.Filter;
            var filtre = f.Empty;

            if (!string.IsNullOrWhiteSpace(arama))
            {
                var desen = System.Text.RegularExpressions.Regex.Escape(arama.Trim());
                filtre &= f.Regex("universite", new MongoDB.Bson.BsonRegularExpression(desen, "i"));
            }
            if (!string.IsNullOrWhiteSpace(sehir)) filtre &= f.Eq("sehir", sehir);
            if (!string.IsNullOrWhiteSpace(tur)) filtre &= f.Eq("tur", tur);

            return koleksiyon.Find(filtre)
                             .Sort(Builders<T>.Sort.Ascending("universite"))
                             .ToList();
        }

        public List<Universite> YabanciUyruklular(string yil, string? arama = null,
            string? sehir = null, string? tur = null) =>
            FiltreliListe<Universite>(MongoDbContext.YabanciUyruklu, yil, arama, sehir, tur);

        public List<OgrenciKurum> Ogrenciler(string yil, string? arama = null,
            string? sehir = null, string? tur = null) =>
            FiltreliListe<OgrenciKurum>(MongoDbContext.Ogrenci, yil, arama, sehir, tur);

        public List<MezunKurum> Mezunlar(string yil, string? arama = null,
            string? sehir = null, string? tur = null) =>
            FiltreliListe<MezunKurum>(MongoDbContext.Mezun, yil, arama, sehir, tur);

        public List<AkademikBirimSayisi> AkademikBirimler(string yil) =>
            _context.Koleksiyon<AkademikBirimSayisi>(MongoDbContext.AkademikBirim, YilDogrula(yil))
                    .Find(Builders<AkademikBirimSayisi>.Filter.Empty)
                    .ToList();

        /// <summary>Menüde hangi kartların açık olacağını belirler.</summary>
        public bool GrupVar(string onek, string yil)
        {
            try { return _context.KoleksiyonVar(onek, YilDogrula(yil)); }
            catch (Exception hata)
            {
                _logger.LogError(hata, "{Onek}/{Yil} koleksiyon kontrolü başarısız", onek, yil);
                return false;
            }
        }

        /// <summary>O yıl için veri yüklü mü? Boş koleksiyonda anlamsız sayfa göstermemek için.</summary>
        public bool VeriVar(string yil)
        {
            try
            {
                return _context.GetCollectionForYear(YilDogrula(yil))
                               .CountDocuments(Builders<Universite>.Filter.Empty, new CountOptions { Limit = 1 }) > 0;
            }
            catch (Exception hata)
            {
                _logger.LogError(hata, "{Yil} yılı için veri kontrolü başarısız", yil);
                return false;
            }
        }
    }
}
