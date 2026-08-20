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
        public IActionResult Karsilastir(string id1, string id2, string? year)
        {
            var yil = IstatistikServisi.YilDogrula(year);
            OrtakVeriyiDoldur(yil);

            try
            {
                var u1 = _servis.Getir(yil, id1);
                var u2 = _servis.Getir(yil, id2);

                if (u1 is null || u2 is null)
                {
                    _logger.LogWarning("Karşılaştırma için kayıt eksik: {Id1} / {Id2}", id1, id2);
                    return NotFound();
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
            ViewBag.VeriVar = _servis.VeriVar(yil);
            return View();
        }

        [Route("AkademikPersonel")]
        public IActionResult AkademikPersonel(string? year, string? search, string? sehir, string? tur)
        {
            ViewBag.AkademikPersonel = true;
            return ListeyiGoster(search, sehir, tur, year);
        }
    }
}
