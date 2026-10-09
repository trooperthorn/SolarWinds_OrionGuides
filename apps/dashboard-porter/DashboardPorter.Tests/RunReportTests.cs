using System.IO;
using System.Text.Json;
using DashboardPorter.Core;

namespace DashboardPorter.Tests;

public sealed class RunReportTests : IDisposable
{
    private readonly string _dir = Directory.CreateTempSubdirectory("dbporter-report-").FullName;
    public void Dispose() { try { Directory.Delete(_dir, true); } catch (IOException) { } }

    private static RunReportData Sample(string outcome = RunOutcome.Completed, string direction = "export",
        bool dryRun = false)
    {
        var summary = new RunSummary { Ok = 2, Warn = 1, Failed = 1, Skipped = 3, OutputPath = @"C:\out" };
        summary.Items.Add(new RunItem("Core dashboard", "ok", "dashboard 12"));
        summary.Items.Add(new RunItem("Bad one", "failed", "output not written: disk full"));
        return new RunReportData(direction, "dashboards", "orion01", dryRun,
            new DateTime(2026, 9, 29, 10, 15, 0, DateTimeKind.Utc),
            new DateTime(2026, 9, 29, 10, 16, 5, DateTimeKind.Utc), outcome, summary);
    }

    [Fact]
    public void Serialize_CarriesIdentityCountsAndItems()
    {
        using var doc = JsonDocument.Parse(RunReport.Serialize(Sample(RunOutcome.Cancelled, "import", dryRun: true)));
        var root = doc.RootElement;

        Assert.Equal("DashboardPorter 0.2.0", root.GetProperty("tool").GetString());
        Assert.Equal("import", root.GetProperty("direction").GetString());
        Assert.Equal("dashboards", root.GetProperty("area").GetString());
        Assert.Equal("orion01", root.GetProperty("server").GetString());
        Assert.Equal("cancelled", root.GetProperty("outcome").GetString());
        Assert.True(root.GetProperty("dryRun").GetBoolean());

        var counts = root.GetProperty("counts");
        Assert.Equal(2, counts.GetProperty("ok").GetInt32());
        Assert.Equal(1, counts.GetProperty("warnings").GetInt32());
        Assert.Equal(3, counts.GetProperty("skipped").GetInt32());
        Assert.Equal(1, counts.GetProperty("failed").GetInt32());

        var items = root.GetProperty("items").EnumerateArray().ToList();
        Assert.Equal(2, items.Count);
        Assert.Equal("output not written: disk full", items[1].GetProperty("detail").GetString());
    }

    [Fact]
    public void Serialize_HasTheSameFieldsAsPortersReport()
    {
        using var doc = JsonDocument.Parse(RunReport.Serialize(Sample()));
        var names = doc.RootElement.EnumerateObject().Select(p => p.Name).ToHashSet();
        Assert.Equal(new[] { "tool", "direction", "dryRun", "area", "server", "startedUtc",
            "finishedUtc", "outcome", "counts", "output", "items" }.ToHashSet(), names);
    }

    [Fact]
    public void FileName_FollowsTheDocumentedPattern()
        => Assert.Equal("dashboardporter-run_export_2026-09-29_101500.json",
            RunReport.FileName("export", new DateTime(2026, 9, 29, 10, 15, 0)));

    [Fact]
    public void Write_NeverOverwritesAnEarlierReportFromTheSameSecond()
    {
        var first = RunReport.Write(_dir, Sample());
        var second = RunReport.Write(_dir, Sample());
        Assert.NotEqual(first, second);
        Assert.True(File.Exists(first));
        Assert.True(File.Exists(second));
    }
}
