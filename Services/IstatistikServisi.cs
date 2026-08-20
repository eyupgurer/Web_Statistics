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
