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
            var model = _servis.GenelBakis(IstatistikServisi.YilDogrula(year));
            ViewBag.Yil = model.Yil;
            ViewBag.YilGoster = model.YilGoster;
            return View(model);
        }

        /// <summary>Yıllar arası eğilim: tek yıla değil, seyre bakmak için.</summary>
        [Route("Trend")]
        public IActionResult Trend()
        {
            var model = _servis.ZamanSerisi();
            ViewBag.Yil = model.Son?.Yil ?? IstatistikServisi.VarsayilanYil;
            ViewBag.YilGoster = IstatistikServisi.YilGoster((string)ViewBag.Yil);
            return View(model);
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
