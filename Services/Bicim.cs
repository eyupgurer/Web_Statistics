using System.Globalization;

namespace YokIstatistikWeb.Services
{
    /// <summary>
    /// Sayı biçimlendirme. İki ayrı iş var ve karıştırılmamaları gerekiyor:
    /// kullanıcıya gösterilen sayılar Türkçe ondalık ayırıcı (virgül) kullanır,
    /// CSS'e yazılan sayılar ise her zaman nokta ister — <c>width:47,2%</c>
    /// tarayıcı tarafından geçersiz sayılır ve çubuk çizilmez.
    /// </summary>
    public static class Bicim
    {
        private static readonly CultureInfo Turkce = CultureInfo.GetCultureInfo("tr-TR");

        /// <summary>Ekranda gösterilecek yüzde: <c>47,2</c></summary>
        public static string Yuzde(double d) => d.ToString("N1", Turkce);

        /// <summary>Stil özniteliğine yazılacak sayı: <c>47.2</c></summary>
        public static string Css(double d) => d.ToString("F1", CultureInfo.InvariantCulture);
    }
}
