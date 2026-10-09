using System.IO;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using DashboardPorter.Core;

namespace DashboardPorter.Tests;

public sealed class PackageReaderTests : IDisposable
{
    private readonly string _dir = Directory.CreateTempSubdirectory("dbporter-reader-").FullName;
    public void Dispose() { try { Directory.Delete(_dir, true); } catch (IOException) { } }

    private static PackageItem Item(string file, string name, string text)
        => new($"dashboards/{file}", name, Encoding.UTF8.GetBytes(text), "note");

    private static byte[] Package(params PackageItem[] items)
        => PackageWriter.BuildZipInMemory("core-orion", "Orion 2026.2", items);

    private static byte[] OnePackage() => Package(Item("ops.json", "Ops", TestData.Dashboard));

    private static byte[] Mutate(byte[] zip, Action<ZipArchive> change)
    {
        var ms = new MemoryStream();
        ms.Write(zip);
        using (var archive = new ZipArchive(ms, ZipArchiveMode.Update, leaveOpen: true)) change(archive);
        return ms.ToArray();
    }

    private static void Write(ZipArchive z, string name, string text)
    {
        using var w = new StreamWriter(z.CreateEntry(name).Open(), new UTF8Encoding(false));
        w.Write(text);
    }

    private static void Replace(ZipArchive z, string name, string text)
    {
        z.GetEntry(name)!.Delete();
        Write(z, name, text);
    }

    private static JsonObject ReadManifest(ZipArchive z)
    {
        using var reader = new StreamReader(z.GetEntry("manifest.json")!.Open());
        return JsonNode.Parse(reader.ReadToEnd())!.AsObject();
    }

    private static string Sha(string text)
        => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(text))).ToLowerInvariant();

    [Fact]
    public void OwnPackage_IsVerifiedAndCarriesItsSource()
    {
        var contents = PackageReader.ReadZipBytes(OnePackage(), "p.zip");
        var entry = Assert.Single(contents.Entries);
        Assert.Empty(entry.Errors);
        Assert.Empty(entry.Warnings);
        Assert.Equal(PackageOrigin.ManifestPackage, entry.Origin);
        Assert.Equal(TestData.Dashboard, entry.Text);
        Assert.Contains("ops.json", entry.DisplayName);
        Assert.True(contents.Info.HasManifest);
        Assert.Equal("core-orion", contents.Info.SourceServer);
        Assert.Equal("Orion 2026.2", contents.Info.SourcePlatform);
        Assert.Equal(1, contents.Info.ManifestVersion);
        Assert.Matches(@"^DashboardPorter \d+\.\d+\.\d+$", contents.Info.Tool);
    }

    [Fact]
    public void ModifiedFile_FailsShaCheck_ButIsStagedWithAnError()
    {
        var evil = TestData.Dashboard.Replace("\"Ops\"", "\"Evil\"");
        var tampered = Mutate(OnePackage(), z => Replace(z, "dashboards/ops.json", evil));
        var entry = Assert.Single(PackageReader.ReadZipBytes(tampered, "p.zip").Entries);
        Assert.Contains("SHA-256 does not match the package manifest — file was modified", entry.Errors);
        Assert.Contains("Evil", entry.Text);
    }

    [Fact]
    public void FileAddedAfterExport_IsAnError_AndNotImportable()
    {
        var extra = Mutate(OnePackage(), z => Write(z, "dashboards/planted.json", TestData.Dashboard));
        var entries = PackageReader.ReadZipBytes(extra, "p.zip").Entries;
        Assert.Equal(2, entries.Count);
        var planted = Assert.Single(entries, e => e.DisplayName.Contains("planted.json"));
        Assert.Contains("not listed in the package manifest", planted.Errors);
        Assert.Equal("", planted.Text);   // never handed to the importer
    }

    [Fact]
    public void ListedFileMissingFromPackage_IsAnError()
    {
        var missing = Mutate(OnePackage(), z => z.GetEntry("dashboards/ops.json")!.Delete());
        var entry = Assert.Single(PackageReader.ReadZipBytes(missing, "p.zip").Entries);
        Assert.Contains("listed in the package manifest but missing from the package", entry.Errors);
    }

    [Fact]
    public void ManifestWithoutSha_IsAnError()
    {
        var unsigned = Mutate(OnePackage(), z =>
        {
            var manifest = ReadManifest(z);
            manifest["items"]![0]!.AsObject().Remove("sha256");
            Replace(z, "manifest.json", manifest.ToJsonString());
        });
        var entry = Assert.Single(PackageReader.ReadZipBytes(unsigned, "p.zip").Entries);
        Assert.Contains("the package manifest records no SHA-256 for this file", entry.Errors);
    }

    [Fact]
    public void PorterMixedPackage_StagesOnlyItsDashboards()
    {
        // The shape Porter writes: several areas in one package, routed by manifest area.
        var ms = new MemoryStream();
        using (var z = new ZipArchive(ms, ZipArchiveMode.Create, leaveOpen: true))
        {
            Write(z, "dashboards/ops.json", TestData.Dashboard);
            Write(z, "alerts/cpu.xml", "<AlertDefinition/>");
            Write(z, "manifest.json", JsonSerializer.Serialize(new
            {
                manifestVersion = 1,
                tool = "Porter 0.2.0",
                source = new { server = "orion01", platform = "Orion 2026.2", swis = "v3" },
                created = "2026-09-29T10:00:00Z",
                items = new object[]
                {
                    new { area = "dashboards", file = "dashboards/ops.json", sha256 = Sha(TestData.Dashboard) },
                    new { area = "alerts", file = "alerts/cpu.xml", sha256 = Sha("<AlertDefinition/>") },
                },
            }));
        }
        var contents = PackageReader.ReadZipBytes(ms.ToArray(), "porter.zip");
        var entry = Assert.Single(contents.Entries);
        Assert.Empty(entry.Errors);
        Assert.Equal("Porter 0.2.0", contents.Info.Tool);
        Assert.Equal("orion01", contents.Info.SourceServer);
    }

    [Fact]
    public void PackageWithNoDashboardItems_Throws()
    {
        var other = Mutate(OnePackage(), z =>
        {
            var manifest = ReadManifest(z);
            manifest["items"]![0]!["area"] = "alerts";
            Replace(z, "manifest.json", manifest.ToJsonString());
        });
        var ex = Assert.Throws<InvalidDataException>(() => PackageReader.ReadZipBytes(other, "p.zip"));
        Assert.Contains("no Modern Dashboards items", ex.Message);
    }

    [Fact]
    public void ManifestVersionTwo_IsRejected()
    {
        var future = Mutate(OnePackage(), z =>
        {
            var manifest = ReadManifest(z);
            manifest["manifestVersion"] = 2;
            Replace(z, "manifest.json", manifest.ToJsonString());
        });
        var ex = Assert.Throws<InvalidDataException>(() => PackageReader.ReadZipBytes(future, "p.zip"));
        Assert.Contains("version 2", ex.Message);
    }

    [Fact]
    public void LegacyManifestWithoutVersion_IsTreatedAsOne()
    {
        // DashboardPorter 0.1 wrote no manifestVersion.
        var legacy = Mutate(OnePackage(), z =>
        {
            var manifest = ReadManifest(z);
            manifest.Remove("manifestVersion");
            manifest["tool"] = "DashboardPorter 0.1";
            Replace(z, "manifest.json", manifest.ToJsonString());
        });
        var contents = PackageReader.ReadZipBytes(legacy, "p.zip");
        Assert.Equal(1, contents.Info.ManifestVersion);
        Assert.Empty(Assert.Single(contents.Entries).Errors);
    }

    [Fact]
    public void EntryCountCap_IsEnforcedUpFront()
    {
        var limits = new PackageLimits(MaxEntries: 2, MaxTotalBytes: 1 << 20, MaxItemBytes: 1 << 20);
        var pkg = Package(Item("a.json", "A", TestData.Dashboard), Item("b.json", "B", TestData.Dashboard));
        // two dashboards + manifest = 3 entries
        var ex = Assert.Throws<InvalidDataException>(() => PackageReader.ReadZipBytes(pkg, "p.zip", limits));
        Assert.Contains("entries", ex.Message);
    }

    [Fact]
    public void DefaultLimits_AreTheDocumentedOnes()
    {
        Assert.Equal(5000, PackageLimits.Default.MaxEntries);
        Assert.Equal(256L * 1024 * 1024, PackageLimits.Default.MaxTotalBytes);
        Assert.Equal(64L * 1024 * 1024, PackageLimits.Default.MaxItemBytes);
    }

    [Fact]
    public void PerItemCap_CountsDecompressedBytes()
    {
        var body = TestData.Dashboard + new string(' ', 2000);
        var pkg = Package(Item("big.json", "Big", body));
        var limits = new PackageLimits(MaxEntries: 100, MaxTotalBytes: 1 << 20, MaxItemBytes: 1000);
        var ex = Assert.Throws<InvalidDataException>(() => PackageReader.ReadZipBytes(pkg, "p.zip", limits));
        Assert.Contains("entry decompresses past", ex.Message);
    }

    [Fact]
    public void TotalSizeCap_IsCumulative()
    {
        var body = TestData.Dashboard + new string(' ', 200);
        var pkg = Package(Item("a.json", "A", body), Item("b.json", "B", body));
        // Each file fits the per-item cap; together (plus the manifest) they pass the total cap.
        var limits = new PackageLimits(MaxEntries: 100, MaxTotalBytes: 1500, MaxItemBytes: 1000);
        var ex = Assert.Throws<InvalidDataException>(() => PackageReader.ReadZipBytes(pkg, "p.zip", limits));
        Assert.Contains("package decompresses past", ex.Message);
    }

    [Fact]
    public void ForeignZip_StagesByExtension_WithUnverifiedWarning()
    {
        var ms = new MemoryStream();
        using (var z = new ZipArchive(ms, ZipArchiveMode.Create, leaveOpen: true))
            Write(z, "stuff/ops.json", TestData.Dashboard);
        var contents = PackageReader.ReadZipBytes(ms.ToArray(), "foreign.zip");
        Assert.False(contents.Info.HasManifest);
        var entry = Assert.Single(contents.Entries);
        Assert.Equal(PackageOrigin.ForeignZip, entry.Origin);
        Assert.Contains(PackageReader.UnverifiedWarning, entry.Warnings);
    }

    [Fact]
    public void RawFile_CarriesUnverifiedWarning()
    {
        var path = Path.Combine(_dir, "ops.json");
        File.WriteAllText(path, TestData.Dashboard);
        var entry = Assert.Single(PackageReader.Read(path, _ => null).Entries);
        Assert.Equal(PackageOrigin.RawFile, entry.Origin);
        Assert.Contains(PackageReader.UnverifiedWarning, entry.Warnings);
    }

    [Fact]
    public void RawFile_OverTheItemCap_IsRefused()
    {
        var path = Path.Combine(_dir, "big.json");
        File.WriteAllText(path, TestData.Dashboard + new string(' ', 2000));
        var limits = new PackageLimits(MaxEntries: 100, MaxTotalBytes: 1 << 20, MaxItemBytes: 1000);
        Assert.Throws<InvalidDataException>(() => PackageReader.Read(path, _ => null, limits));
    }

    [Fact]
    public void EncryptedPackage_RoundTripsThroughThePasswordPrompt()
    {
        var path = Path.Combine(_dir, "p.zip.aes");
        PackageCrypto.EncryptToFile(OnePackage(), path, "pw");
        string? asked = null;
        var contents = PackageReader.Read(path, name => { asked = name; return "pw"; });
        Assert.Equal("p.zip.aes", asked);
        Assert.Empty(Assert.Single(contents.Entries).Errors);
        Assert.Throws<InvalidDataException>(() => PackageReader.Read(path, _ => "nope"));
        Assert.Throws<OperationCanceledException>(() => PackageReader.Read(path, _ => null));
    }

    [Fact]
    public void EncryptedPorterPackage_IsReadAndVerified()
    {
        var path = Path.Combine(_dir, "porter.zip.aes");
        TestData.EncryptIndependently(OnePackage(), path, "pw", "PORTERA1");
        var entry = Assert.Single(PackageReader.Read(path, _ => "pw").Entries);
        Assert.Empty(entry.Errors);
        Assert.Equal(PackageOrigin.ManifestPackage, entry.Origin);
    }
}
