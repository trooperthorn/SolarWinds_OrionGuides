using System.IO;
using System.Text.Json;
using Porter.Core;

namespace Porter.Tests;

public sealed class RunReportTests : IDisposable
{
    private readonly string _dir = Directory.CreateTempSubdirectory("porter-report-").FullName;
    public void Dispose() { try { Directory.Delete(_dir, true); } catch (IOException) { } }

    private static RunReportData Sample(string outcome = RunOutcome.Completed, string direction = "export")
    {
        var summary = new RunSummary { Ok = 2, Warn = 1, Failed = 1, Skipped = 3, OutputPath = @"C:\out" };
        summary.Items.Add(new RunItem("Core dashboard", "ok", "dashboards 12"));
        summary.Items.Add(new RunItem("Bad one", "failed", "output not written: disk full"));
        return new RunReportData(direction, "dashboards", "orion01", false,
            new DateTime(2026, 9, 29, 10, 15, 0, DateTimeKind.Utc),
            new DateTime(2026, 9, 29, 10, 16, 5, DateTimeKind.Utc), outcome, summary);
    }

    [Fact]
    public void Serialize_CarriesIdentityCountsAndItems()
    {
        using var doc = JsonDocument.Parse(RunReport.Serialize(Sample(RunOutcome.Cancelled, "import")));
        var root = doc.RootElement;

        Assert.Matches(@"^Porter \d+\.\d+\.\d+$", root.GetProperty("tool").GetString());
        Assert.Equal("import", root.GetProperty("direction").GetString());
        Assert.Equal("dashboards", root.GetProperty("area").GetString());
        Assert.Equal("orion01", root.GetProperty("server").GetString());
        Assert.Equal("cancelled", root.GetProperty("outcome").GetString());
        Assert.False(root.GetProperty("dryRun").GetBoolean());
        Assert.Equal(DateTimeKind.Utc, root.GetProperty("startedUtc").GetDateTime().Kind);

        var counts = root.GetProperty("counts");
        Assert.Equal(2, counts.GetProperty("ok").GetInt32());
        Assert.Equal(1, counts.GetProperty("warnings").GetInt32());
        Assert.Equal(3, counts.GetProperty("skipped").GetInt32());
        Assert.Equal(1, counts.GetProperty("failed").GetInt32());

        var items = root.GetProperty("items").EnumerateArray().ToList();
        Assert.Equal(2, items.Count);
        Assert.Equal("Core dashboard", items[0].GetProperty("name").GetString());
        Assert.Equal("failed", items[1].GetProperty("outcome").GetString());
        Assert.Equal("output not written: disk full", items[1].GetProperty("detail").GetString());
    }

    [Fact]
    public void Serialize_HasOnlyTheDocumentedFields()
    {
        using var doc = JsonDocument.Parse(RunReport.Serialize(Sample()));
        var names = doc.RootElement.EnumerateObject().Select(p => p.Name).ToHashSet();
        Assert.Equal(new[] { "tool", "direction", "dryRun", "area", "server", "startedUtc",
            "finishedUtc", "outcome", "counts", "output", "items" }.ToHashSet(), names);
    }

    [Fact]
    public void FileName_FollowsTheDocumentedPattern()
        => Assert.Equal("porter-run_export_2026-09-29_101500.json",
            RunReport.FileName("export", new DateTime(2026, 9, 29, 10, 15, 0)));

    [Fact]
    public void Write_NeverOverwritesAnEarlierReportFromTheSameSecond()
    {
        var first = RunReport.Write(_dir, Sample());
        var second = RunReport.Write(_dir, Sample());
        Assert.NotEqual(first, second);
        Assert.True(File.Exists(first));
        Assert.True(File.Exists(second));
        Assert.Matches(@"^porter-run_export_.*\.json$", Path.GetFileName(first));
    }

    [Fact]
    public void Write_CreatesTheDirectory()
    {
        var nested = Path.Combine(_dir, "a", "b");
        Assert.True(File.Exists(RunReport.Write(nested, Sample())));
    }
}
