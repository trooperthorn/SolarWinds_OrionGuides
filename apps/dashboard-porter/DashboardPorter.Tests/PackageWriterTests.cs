using System.IO;
using System.IO.Compression;
using System.Text;
using System.Text.Json;
using DashboardPorter.Core;

namespace DashboardPorter.Tests;

public class PackageWriterTests
{
    [Theory]
    [InlineData("Core Router 1", "Core_Router_1")]
    [InlineData("a/b:c*d?", "a_b_c_d")]
    [InlineData("___", "unnamed")]
    [InlineData("", "unnamed")]
    public void Sanitize_ReplacesUnsafeCharacters(string input, string expected)
        => Assert.Equal(expected, PackageWriter.Sanitize(input));

    [Fact]
    public void ToolName_ComesFromTheAssemblyVersion()
        => Assert.Equal("DashboardPorter 0.2.0", PackageWriter.ToolName);

    [Fact]
    public void Manifest_CarriesVersionToolAndPerItemHashes()
    {
        var zip = PackageWriter.BuildZipInMemory("orion01", "Orion 2026.2", new[]
        {
            new PackageItem("dashboards/ops.json", "Ops", Encoding.UTF8.GetBytes(TestData.Dashboard), "note"),
        });
        using var archive = new ZipArchive(new MemoryStream(zip), ZipArchiveMode.Read);
        using var reader = new StreamReader(archive.GetEntry("manifest.json")!.Open());
        using var doc = JsonDocument.Parse(reader.ReadToEnd());
        var root = doc.RootElement;

        Assert.Equal(PackageReader.SupportedManifestVersion, root.GetProperty("manifestVersion").GetInt32());
        Assert.Equal("DashboardPorter 0.2.0", root.GetProperty("tool").GetString());
        Assert.Equal("orion01", root.GetProperty("source").GetProperty("server").GetString());
        var item = Assert.Single(root.GetProperty("items").EnumerateArray().ToList());
        Assert.Equal("dashboards", item.GetProperty("area").GetString());
        Assert.Equal("dashboards/ops.json", item.GetProperty("file").GetString());
        Assert.Equal(64, item.GetProperty("sha256").GetString()!.Length);
        Assert.Equal(DashboardsCore.ImportVia, item.GetProperty("importVia").GetString());
    }
}
