using Microsoft.AspNetCore.Mvc;
using YokIstatistikWeb.Services;

namespace YokIstatistikWeb.Controllers
{
    public class SehirController : Controller
    {
        private readonly IstatistikServisi _servis;
        private readonly ILogger<SehirController> _logger;

        public SehirController(IstatistikServisi servis, ILogger<SehirController> logger)
        {
            _servis = servis;
            _logger = logger;
        }

        /// <summary>
        /// Şehir bazlı öğretim elemanı haritası.
        /// Artık yıl parametresi alıyor; önceden sabit 2024_2025 koleksiyonuna bağlıydı.
        /// </summary>
        public IActionResult Grafik(string? year)
        {
            var yil = IstatistikServisi.YilDogrula(year);
            var veriler = _servis.SehirDagilimi(yil);
            ViewBag.SehirOgrenci = _servis.SehirOgrenci(yil);

            _logger.LogInformation("{Yil}: {Sayi} şehir için veri hazırlandı", yil, veriler.Count);

            ViewBag.Yil = yil;
            ViewBag.YilGoster = IstatistikServisi.YilGoster(yil);
            return View(veriler);
        }
    }
}
