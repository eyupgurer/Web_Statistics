using System.Globalization;
using YokIstatistikWeb.Models;
using YokIstatistikWeb.Services;

// Biçimlendirme makinenin yerel ayarına bağlı kalmasın: sayılar her ortamda
// "189.868" görünsün, "189,868" değil.
var kultur = new CultureInfo("tr-TR");
CultureInfo.DefaultThreadCurrentCulture = kultur;
CultureInfo.DefaultThreadCurrentUICulture = kultur;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllersWithViews();

// MongoDB yapılandırması
builder.Services.Configure<MongoDBSettings>(
    builder.Configuration.GetSection("MongoDBSettings"));
builder.Services.AddSingleton<MongoDbContext>();

// Tüm veri erişimi bu servis üzerinden yapılıyor.
builder.Services.AddScoped<IstatistikServisi>();

var app = builder.Build();

// Yıl listesi önbelleğini açılışta doldur: ilk isteğin yedek listeyi görmesini
// engelliyor. Mongo kapalıysa uygulama yine de açılıyor, yedek liste devreye
// giriyor.
using (var kapsam = app.Services.CreateScope())
{
    var servis = kapsam.ServiceProvider.GetRequiredService<IstatistikServisi>();
    var yillar = servis.MevcutYillar();
    app.Logger.LogInformation("Veritabanında {Sayi} öğretim yılı bulundu: {Yillar}",
        yillar.Count, string.Join(", ", yillar));
}

if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Home/Error");
    app.UseHsts();
}

app.UseHttpsRedirection();
app.UseStaticFiles();
app.UseRouting();
app.UseAuthorization();

app.MapControllerRoute(
    name: "default",
    pattern: "{controller=Home}/{action=Index}/{id?}");

app.Run();
