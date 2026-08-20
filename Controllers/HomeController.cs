using System.Diagnostics;
using Microsoft.AspNetCore.Mvc;
using YokIstatistikWeb.Models;
using YokIstatistikWeb.Services;

namespace YokIstatistikWeb.Controllers
{
    public class HomeController : Controller
    {
        private readonly ILogger<HomeController> _logger;
        private readonly IstatistikServisi _servis;

        public HomeController(ILogger<HomeController> logger, IstatistikServisi servis)
        {
            _logger = logger;
            _servis = servis;
        }

        [Route("")]
        public IActionResult Index(string? year)
        {
            var yil = IstatistikServisi.YilDogrula(year);

            var (toplam, devlet, vakif, vakifMyo) = _servis.KurumSayilari(yil);

            ViewBag.Yil = yil;
            ViewBag.YilGoster = IstatistikServisi.YilGoster(yil);
            ViewBag.Toplam = toplam;
            ViewBag.Devlet = devlet;
            ViewBag.Vakif = vakif;
            ViewBag.VakifMyo = vakifMyo;
            ViewBag.VeriVar = toplam > 0;

            return View();
        }

        public IActionResult Privacy() => View();

        [ResponseCache(Duration = 0, Location = ResponseCacheLocation.None, NoStore = true)]
        public IActionResult Error()
        {
            var hataOzelligi = HttpContext.Features.Get<Microsoft.AspNetCore.Diagnostics.IExceptionHandlerFeature>();
            if (hataOzelligi is not null)
                _logger.LogError(hataOzelligi.Error, "İşlenmemiş hata: {Yol}", HttpContext.Request.Path);

            return View(new ErrorViewModel { RequestId = Activity.Current?.Id ?? HttpContext.TraceIdentifier });
        }
    }
}
