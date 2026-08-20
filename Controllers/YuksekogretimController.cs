using Microsoft.AspNetCore.Mvc;
using YokIstatistikWeb.Models;
using YokIstatistikWeb.Services;

namespace YokIstatistikWeb.Controllers
{
    [Route("Yuksekogretim")]
    public class YuksekogretimController : Controller
    {
        private readonly IstatistikServisi _servis;
        private readonly ILogger<YuksekogretimController> _logger;

        public YuksekogretimController(IstatistikServisi servis, ILogger<YuksekogretimController> logger)
        {
            _servis = servis;
            _logger = logger;
        }

        /// <summary>
        /// Görünümlerin ihtiyaç duyduğu ortak yıl/filtre verisini doldurur.
        /// Yıl biçimi tek yerde çevriliyor; önceden controller "_"->"-",
        /// görünüm ise "-"->"_" yapıp duruyordu.
        /// </summary>
        private void OrtakVeriyiDoldur(string yil)
        {
            ViewBag.Yil = yil;
            ViewBag.YilGoster = IstatistikServisi.YilGoster(yil);
            ViewBag.Yillar = IstatistikServisi.Yillar;
        }

        [Route("")]
        public IActionResult Index(string? search, string? sehir, string? tur, string? year)
            => ListeyiGoster(search, sehir, tur, year);

        /// <summary>
        /// Liste görünümünü üretir. Görünüm adı AÇIKÇA veriliyor: aksi hâlde MVC
        /// görünümü çalışan action'ın adından çözer ve AkademikPersonel üzerinden
        /// gelindiğinde var olmayan AkademikPersonel.cshtml aranır.
        /// </summary>
        private IActionResult ListeyiGoster(string? search, string? sehir, string? tur, string? year)
        {
            var yil = IstatistikServisi.YilDogrula(year);
            OrtakVeriyiDoldur(yil);

            try
            {
                var veriler = _servis.Listele(yil, search, sehir, tur);

                ViewBag.Sehirler = _servis.Sehirler(yil);
                ViewBag.Turler = _servis.Turler(yil);
                ViewBag.Arama = search;
                ViewBag.SeciliSehir = sehir;
                ViewBag.SeciliTur = tur;

                return View("Index", veriler);
            }
            catch (Exception hata)
            {
                _logger.LogError(hata, "{Yil} listesi çekilemedi", yil);
                TempData["Error"] = "Veri çekilirken bir hata oluştu.";
                ViewBag.Sehirler = new List<string>();
                ViewBag.Turler = new List<string>();
                return View("Index", new List<Universite>());
            }
        }

        [Route("Detay")]
        public IActionResult Detay(string id, string? year)
        {
            var yil = IstatistikServisi.YilDogrula(year);
            OrtakVeriyiDoldur(yil);

            try
            {
                var universite = _servis.Getir(yil, id);
                if (universite is null)
                {
                    _logger.LogWarning("{Yil} yılında {Id} bulunamadı", yil, id);
                    return NotFound();
                }
                return View(universite);
            }
            catch (Exception hata)
            {
                _logger.LogError(hata, "{Id} detayı çekilemedi", id);
                TempData["Error"] = "Detay bilgileri çekilirken bir hata oluştu.";
                return RedirectToAction(nameof(Index), new { year = yil });
            }
        }

        [Route("Karsilastir")]
        public IActionResult Karsilastir(string? id1, string? id2, string? year)
        {
            var yil = IstatistikServisi.YilDogrula(year);
            OrtakVeriyiDoldur(yil);

            try
            {
                // Seçim listesi her durumda gerekiyor: kullanıcı sayfaya doğrudan
                // gelmiş olabilir ya da seçimini değiştirmek isteyebilir.
                ViewBag.Secenekler = _servis.Listele(yil);
                ViewBag.Id1 = id1;
                ViewBag.Id2 = id2;

                if (string.IsNullOrWhiteSpace(id1) || string.IsNullOrWhiteSpace(id2))
                    return View((Tuple<Universite, Universite>?)null);

                var u1 = _servis.Getir(yil, id1);
                var u2 = _servis.Getir(yil, id2);

                if (u1 is null || u2 is null)
                {
                    TempData["Error"] = "Seçilen üniversitelerden biri bulunamadı.";
                    return View((Tuple<Universite, Universite>?)null);
                }

                return View(Tuple.Create(u1, u2));
            }
            catch (Exception hata)
            {
                _logger.LogError(hata, "Karşılaştırma başarısız: {Id1} / {Id2}", id1, id2);
                TempData["Error"] = "Karşılaştırma yapılırken bir hata oluştu.";
                return RedirectToAction(nameof(Index), new { year = yil });
            }
        }

        [HttpGet]
        [Route("YilMenu")]
        public IActionResult YilMenu(string? year)
        {
            var yil = IstatistikServisi.YilDogrula(year);
            OrtakVeriyiDoldur(yil);

            // Kartların açık mı kilitli mi olacağı veritabanındaki koleksiyonlara
            // bakarak belirleniyor; elle bakım gerektiren bir liste tutmuyoruz.
            ViewBag.Hazir = new Dictionary<string, bool>
            {
                ["ogretim_elemani"] = _servis.GrupVar(MongoDbContext.OgretimElemani, yil),
                ["yabanci_uyruklu"] = _servis.GrupVar(MongoDbContext.YabanciUyruklu, yil),
                ["ogrenci"]         = _servis.GrupVar(MongoDbContext.Ogrenci, yil),
                ["mezun"]           = _servis.GrupVar(MongoDbContext.Mezun, yil),
                ["ozet"]            = _servis.GrupVar(MongoDbContext.AkademikBirim, yil),
            };

            return View();
        }

        [Route("AkademikPersonel")]
        public IActionResult AkademikPersonel(string? year, string? search, string? sehir, string? tur)
        {
            ViewBag.AkademikPersonel = true;
            return ListeyiGoster(search, sehir, tur, year);
        }

        // ------------------------------------------------------------------
        // Öğrenci, mezun ve yabancı uyruklu sayfaları ortak görünümü kullanıyor
        // ------------------------------------------------------------------

        private void FiltreSeceneklerini_Doldur(KurumListesiViewModel model, string yil,
            string? arama, string? sehir, string? tur)
        {
            model.Yil = yil;
            model.YilGoster = IstatistikServisi.YilGoster(yil);
            model.Sehirler = _servis.Sehirler(yil);
            model.Turler = _servis.Turler(yil);
            model.Arama = arama;
            model.SeciliSehir = sehir;
            model.SeciliTur = tur;
        }

        [Route("YabanciUyruklu")]
        public IActionResult YabanciUyruklu(string? year, string? search, string? sehir, string? tur)
        {
            var yil = IstatistikServisi.YilDogrula(year);
            OrtakVeriyiDoldur(yil);

            var kayitlar = _servis.YabanciUyruklular(yil, search, sehir, tur);
            var model = new KurumListesiViewModel
            {
                Baslik = "Yabancı uyruklu öğretim elemanları",
                Aciklama = "Akademik unvana göre yabancı uyruklu öğretim elemanı sayıları",
                OlcumBasliklari = new() { "Erkek", "Kadın", "Toplam" },
                Satirlar = kayitlar.Select(u => new KurumSatiri
                {
                    Universite = u.universite,
                    Tur = u.tur,
                    Sehir = u.sehir,
                    Olcumler = new() { u.toplam_erkek ?? 0, u.toplam_kadin ?? 0, u.toplam_toplam ?? 0 },
                    AnaOlcum = u.toplam_toplam ?? 0,
                }).ToList(),
            };
            FiltreSeceneklerini_Doldur(model, yil, search, sehir, tur);

            var toplam = model.Satirlar.Sum(x => x.AnaOlcum);
            var kadin = model.Satirlar.Sum(x => x.Olcumler[1]);
            model.Kartlar = new()
            {
                new() { Etiket = "Kurum", Deger = model.Satirlar.Count.ToString("N0"),
                        Alt = "Yabancı uyruklu personeli olan" },
                new() { Etiket = "Yabancı uyruklu öğretim elemanı", Deger = toplam.ToString("N0") },
                new() { Etiket = "Kadın oranı",
                        Deger = toplam > 0 ? "%" + ((double)kadin / toplam * 100).ToString("N1") : "—",
                        Alt = kadin.ToString("N0") + " kişi" },
            };

            return View("KurumListesi", model);
        }

        [Route("OgrenciSayilari")]
        public IActionResult OgrenciSayilari(string? year, string? search, string? sehir, string? tur)
        {
            var yil = IstatistikServisi.YilDogrula(year);
            OrtakVeriyiDoldur(yil);

            var kayitlar = _servis.Ogrenciler(yil, search, sehir, tur);
            var model = new KurumListesiViewModel
            {
                Baslik = "Öğrenci sayıları",
                Aciklama = "Önlisans ve lisans düzeyinde öğrenci ve yeni kayıt sayıları",
                OlcumBasliklari = new() { "Yeni kayıt", "Erkek", "Kadın", "Toplam" },
                Satirlar = kayitlar.Select(u => new KurumSatiri
                {
                    Universite = u.universite,
                    Tur = u.tur,
                    Sehir = u.sehir,
                    Olcumler = new()
                    {
                        u.yeni_kayit_toplam ?? 0, u.toplam_erkek ?? 0,
                        u.toplam_kadin ?? 0, u.toplam_toplam ?? 0
                    },
                    AnaOlcum = u.toplam_toplam ?? 0,
                }).ToList(),
            };
            FiltreSeceneklerini_Doldur(model, yil, search, sehir, tur);

            var toplam = model.Satirlar.Sum(x => x.AnaOlcum);
            var yeni = model.Satirlar.Sum(x => x.Olcumler[0]);
            var kadin = model.Satirlar.Sum(x => x.Olcumler[2]);
            model.Kartlar = new()
            {
                new() { Etiket = "Kurum", Deger = model.Satirlar.Count.ToString("N0") },
                new() { Etiket = "Öğrenci", Deger = toplam.ToString("N0"),
                        Alt = "Önlisans ve lisans" },
                new() { Etiket = "Yeni kayıt", Deger = yeni.ToString("N0") },
                new() { Etiket = "Kadın oranı",
                        Deger = toplam > 0 ? "%" + ((double)kadin / toplam * 100).ToString("N1") : "—",
                        Alt = kadin.ToString("N0") + " öğrenci" },
            };

            return View("KurumListesi", model);
        }

        [Route("MezunSayilari")]
        public IActionResult MezunSayilari(string? year, string? search, string? sehir, string? tur)
        {
            var yil = IstatistikServisi.YilDogrula(year);
            OrtakVeriyiDoldur(yil);

            var kayitlar = _servis.Mezunlar(yil, search, sehir, tur);
            var model = new KurumListesiViewModel
            {
                Baslik = "Mezun sayıları",
                Aciklama = "Önlisans ve lisans düzeyinde mezun sayıları",
                OlcumBasliklari = new() { "Erkek", "Kadın", "Toplam" },
                Satirlar = kayitlar.Select(u => new KurumSatiri
                {
                    Universite = u.universite,
                    Tur = u.tur,
                    Sehir = u.sehir,
                    Olcumler = new() { u.toplam_erkek ?? 0, u.toplam_kadin ?? 0, u.toplam_toplam ?? 0 },
                    AnaOlcum = u.toplam_toplam ?? 0,
                }).ToList(),
            };
            FiltreSeceneklerini_Doldur(model, yil, search, sehir, tur);

            var toplam = model.Satirlar.Sum(x => x.AnaOlcum);
            var kadin = model.Satirlar.Sum(x => x.Olcumler[1]);
            model.Kartlar = new()
            {
                new() { Etiket = "Kurum", Deger = model.Satirlar.Count.ToString("N0") },
                new() { Etiket = "Mezun", Deger = toplam.ToString("N0"),
                        Alt = "Önlisans ve lisans" },
                new() { Etiket = "Kadın oranı",
                        Deger = toplam > 0 ? "%" + ((double)kadin / toplam * 100).ToString("N1") : "—",
                        Alt = kadin.ToString("N0") + " mezun" },
            };

            return View("KurumListesi", model);
        }

        [Route("OzetTablolar")]
        public IActionResult OzetTablolar(string? year)
        {
            var yil = IstatistikServisi.YilDogrula(year);
            OrtakVeriyiDoldur(yil);
            return View(_servis.AkademikBirimler(yil));
        }
    }
}
