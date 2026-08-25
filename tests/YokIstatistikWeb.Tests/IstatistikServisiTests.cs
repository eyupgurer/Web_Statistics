using System.Text.RegularExpressions;
using YokIstatistikWeb.Services;

namespace YokIstatistikWeb.Tests;

public class IstatistikServisiTests
{
    [Theory]
    [InlineData("bilgisayar", "BİLGİSAYAR MÜHENDİSLİĞİ")]
    [InlineData("muhendislik", "MÜHENDİSLİK FAKÜLTESİ")]
    [InlineData("bogazici", "BOĞAZİÇİ ÜNİVERSİTESİ")]
    public void TurkceAramaDeseni_TurkceHarfFarklariniEsler(string arama, string hedef)
    {
        var desen = IstatistikServisi.TurkceAramaDeseni(arama);

        Assert.Matches(new Regex(desen, RegexOptions.IgnoreCase), hedef);
    }

    [Fact]
    public void TurkceAramaDeseni_RegexOzelKarakterleriniMetinOlarakEleAlir()
    {
        var desen = IstatistikServisi.TurkceAramaDeseni("[(<script>");

        Assert.Matches(new Regex(desen, RegexOptions.IgnoreCase), "[(<SCRIPT>");
    }

    [Theory]
    [InlineData("VAKIF MYO", "Vakıf MYO")]
    [InlineData("DEVLET", "Devlet")]
    public void TurGoster_BaslikBiciminiUygular(string ham, string beklenen) =>
        Assert.Equal(beklenen, IstatistikServisi.TurGoster(ham));

    [Fact]
    public void YilDogrula_GecersizDegeriVarsayilanaCevirir() =>
        Assert.Equal(IstatistikServisi.VarsayilanYil, IstatistikServisi.YilDogrula("../../sistem"));

    [Fact]
    public void YilGoster_AltCizgiyiTireCevirir() =>
        Assert.Equal("2025-2026", IstatistikServisi.YilGoster("2025_2026"));
}
