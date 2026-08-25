using YokIstatistikWeb.Models;
using YokIstatistikWeb.Services;

namespace YokIstatistikWeb.Tests;

public class BicimVeModelTests
{
    [Fact]
    public void Yuzde_TurkceOndalikAyiriciKullanir() =>
        Assert.Equal("47,2", Bicim.Yuzde(47.24));

    [Fact]
    public void Css_NoktaOndalikAyiriciKullanir() =>
        Assert.Equal("47.2", Bicim.Css(47.24));

    [Fact]
    public void YilOzeti_OranlariDogruHesaplar()
    {
        var ozet = new YilOzeti
        {
            OgretimElemani = 200,
            OgretimElemaniKadin = 90,
            Ogrenci = 4_000,
            Orgun = 3_000,
        };

        Assert.Equal(45, ozet.KadinOrani);
        Assert.Equal(20, ozet.OgrenciBasinaElemanOrani);
        Assert.True(ozet.OgrenciVar);
        Assert.True(ozet.OgretimTuruVar);
    }

    [Fact]
    public void ZamanSerisi_DegisimiIkiUcYilArasindaHesaplar()
    {
        var model = new ZamanSerisiViewModel
        {
            Yillar =
            [
                new YilOzeti { OgretimElemani = 100 },
                new YilOzeti { OgretimElemani = 125 },
            ],
        };

        Assert.Equal(25, model.Degisim(y => y.OgretimElemani));
    }
}
