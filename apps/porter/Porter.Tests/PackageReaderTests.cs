using System.IO;
using System.IO.Compression;
using System.Text;
using System.Text.Json.Nodes;
using Porter.Areas;
using Porter.Core;

namespace Porter.Tests;

public sealed class PackageReaderTests : IDisposable
{
    private const string AlertXml = "<AlertDefinition><Name>CPU high</Name></AlertDefinition>";
    private const string ReportXml = "<Report><Name>Inventory</Name></Report>";

    private readonly string _dir = Directory.CreateTempSubdirectory("porter-reader-").FullName;
    public void Dispose() { try { Directory.Delete(_dir, true); } catch (IOException) { } }

    private static PackageItem Item(string area, string file, string name, string text)
        => new(area, $"{area}/{file}", name, Encoding.UTF8.GetBytes(text), "verb", "note");

    private static byte[] MixedPackage() => PackageWriter.BuildZipInMemory("core-orion", "Orion 2026.2",
        new[]
        {
            Item("alerts", "cpu.xml", "CPU high", AlertXml),
            Item("reports", "inv.xml", "Inventory", ReportXml),
        });

    private static byte[] Mutate(byte[] zip, Action<ZipArchive> change)
    {
        var ms = new MemoryStream();
        ms.Write(zip);
        using (var archive = new ZipArchive(ms, ZipArchiveMode.Update, leaveOpen: true)) change(archive);
        return ms.ToArray();
    }

    private static void Replace(ZipArchive z, string name, string text)
    {
        z.GetEntry(name)!.Delete();
        using var w = new StreamWriter(z.CreateEntry(name).Open(), new UTF8Encoding(false));
        w.Write(text);
    }

    private static JsonObject ReadManifest(ZipArchive z)
    {
        using var reader = new StreamReader(z.GetEntry("manifest.json")!.Open());
        return JsonNode.Parse(reader.ReadToEnd())!.AsObject();
    }

    private static ReportsProvider Reports() => new(TestData.Session());
    private static AlertsProvider Alerts() => new(TestData.Session());

    [Fact]
    public void ManifestRoutesByArea_NotByExtension()
    {
        var pkg = MixedPackage();

        var reports = PackageReader.ReadZipBytes(pkg, "p.zip", Reports());
        var r = Assert.Single(reports.Entries);
        Assert.Contains("inv.xml", r.DisplayName);
        Assert.Empty(r.Errors);
        Assert.Empty(r.Warnings);
        Assert.Equal(PackageOrigin.PorterPackage, r.Origin);
        Assert.Equal(ReportXml, r.Text);
        Assert.True(reports.Info.IsPorterPackage);
        Assert.Equal("core-orion", reports.Info.SourceServer);
        Assert.Equal("Orion 2026.2", reports.Info.SourcePlatform);
        Assert.Equal(1, reports.Info.ManifestVersion);

        var alerts = PackageReader.ReadZipBytes(pkg, "p.zip", Alerts());
        Assert.Contains("cpu.xml", Assert.Single(alerts.Entries).DisplayName);
    }

    [Fact]
    public void ModifiedFile_FailsShaCheck_ButIsStagedWithAnError()
    {
        var tampered = Mutate(MixedPackage(), z => Replace(z, "reports/inv.xml", "<Report><Name>Evil</Name></Report>"));
        var entry = Assert.Single(PackageReader.ReadZipBytes(tampered, "p.zip", Reports()).Entries);
        Assert.Contains("SHA-256 does not match the package manifest — file was modified", entry.Errors);
        Assert.Contains("Evil", entry.Text);
    }

    [Fact]
    public void FileMissingFromManifest_IsAnError()
    {
        var extra = Mutate(MixedPackage(), z =>
        {
            using var w = new StreamWriter(z.CreateEntry("reports/planted.xml").Open());
            w.Write(ReportXml);
        });
        var entries = PackageReader.ReadZipBytes(extra, "p.zip", Reports()).Entries;
        Assert.Equal(2, entries.Count);
        var planted = Assert.Single(entries, e => e.DisplayName.Contains("planted.xml"));
        Assert.Contains("not listed in the package manifest", planted.Errors);
    }

    [Fact]
    public void AreaWithNoItemsInManifest_Throws()
    {
        var pkg = PackageWriter.BuildZipInMemory("s", "p",
            new[] { Item("alerts", "cpu.xml", "CPU high", AlertXml) });
        var ex = Assert.Throws<InvalidDataException>(() => PackageReader.ReadZipBytes(pkg, "p.zip", Reports()));
        Assert.Contains("no Reports items", ex.Message);
    }

    [Fact]
    public void ManifestVersionTwo_IsRejected()
    {
        var future = Mutate(MixedPackage(), z =>
        {
            var manifest = ReadManifest(z);
            manifest["manifestVersion"] = 2;
            Replace(z, "manifest.json", manifest.ToJsonString());
        });
        var ex = Assert.Throws<InvalidDataException>(() => PackageReader.ReadZipBytes(future, "p.zip", Reports()));
        Assert.Contains("version 2", ex.Message);
    }

    [Fact]
    public void MissingManifestVersion_IsTreatedAsOne()
    {
        var legacy = Mutate(MixedPackage(), z =>
        {
            var manifest = ReadManifest(z);
            manifest.Remove("manifestVersion");
            Replace(z, "manifest.json", manifest.ToJsonString());
        });
        var contents = PackageReader.ReadZipBytes(legacy, "p.zip", Reports());
        Assert.Equal(1, contents.Info.ManifestVersion);
        Assert.Empty(Assert.Single(contents.Entries).Errors);
    }

    [Fact]
    public void EntryCountCap_IsEnforcedUpFront()
    {
        var limits = new PackageLimits(MaxEntries: 2, MaxTotalBytes: 1 << 20, MaxItemBytes: 1 << 20);
        // alerts + reports + manifest = 3 entries
        var ex = Assert.Throws<InvalidDataException>(() =>
            PackageReader.ReadZipBytes(MixedPackage(), "p.zip", Reports(), limits));
        Assert.Contains("entries", ex.Message);
    }

    [Fact]
    public void TotalSizeCap_IsCumulative()
    {
        var body = "<Report><Name>" + new string('x', 400) + "</Name></Report>";
        var pkg = PackageWriter.BuildZipInMemory("s", "p", new[]
        {
            Item("reports", "a.xml", "A", body),
            Item("reports", "b.xml", "B", body),
        });
        // Each file fits the per-item cap; together (plus the manifest) they pass the total cap.
        var limits = new PackageLimits(MaxEntries: 100, MaxTotalBytes: 1000, MaxItemBytes: 700);
        var ex = Assert.Throws<InvalidDataException>(() =>
            PackageReader.ReadZipBytes(pkg, "p.zip", Reports(), limits));
        Assert.Contains("package decompresses past", ex.Message);
    }

    [Fact]
    public void ForeignZip_StagesByExtension_WithUnverifiedWarning()
    {
        var ms = new MemoryStream();
        using (var z = new ZipArchive(ms, ZipArchiveMode.Create, leaveOpen: true))
        {
            using var w = new StreamWriter(z.CreateEntry("stuff/r.xml").Open());
            w.Write(ReportXml);
        }
        var contents = PackageReader.ReadZipBytes(ms.ToArray(), "foreign.zip", Reports());
        Assert.False(contents.Info.IsPorterPackage);
        var entry = Assert.Single(contents.Entries);
        Assert.Equal(PackageOrigin.ForeignZip, entry.Origin);
        Assert.Contains(PackageReader.UnverifiedWarning, entry.Warnings);
    }

    [Fact]
    public void RawFile_CarriesUnverifiedWarning()
    {
        var path = Path.Combine(_dir, "r.xml");
        File.WriteAllText(path, ReportXml);
        var entry = Assert.Single(PackageReader.Read(path, Reports(), _ => null).Entries);
        Assert.Equal(PackageOrigin.RawFile, entry.Origin);
        Assert.Contains(PackageReader.UnverifiedWarning, entry.Warnings);
    }

    [Fact]
    public void EncryptedPackage_RoundTripsThroughThePasswordPrompt()
    {
        var path = Path.Combine(_dir, "p.zip.aes");
        PackageCrypto.EncryptToFile(MixedPackage(), path, "pw");
        string? asked = null;
        var contents = PackageReader.Read(path, Reports(), name => { asked = name; return "pw"; });
        Assert.Equal("p.zip.aes", asked);
        Assert.Single(contents.Entries);
        Assert.Throws<InvalidDataException>(() => PackageReader.Read(path, Reports(), _ => "nope"));
        Assert.Throws<OperationCanceledException>(() => PackageReader.Read(path, Reports(), _ => null));
    }
}
