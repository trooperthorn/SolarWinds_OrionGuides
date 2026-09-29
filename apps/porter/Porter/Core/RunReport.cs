using System.IO;
using System.Text.Json;

namespace Porter.Core;

/// <summary>One file or object a run acted on. Detail is a short human sentence — never a payload.</summary>
public sealed record RunItem(string Name, string Outcome, string Detail);

/// <summary>Live counts and per-item results for one run. The view creates it and hands it
/// to the job, so an aborted run can still show what happened before the abort.</summary>
public sealed class RunSummary
{
    public int Ok;
    public int Warn;
    public int Failed;
    public int Skipped;
    public List<string> SkippedNames { get; } = new();
    public List<string> CopyNotes { get; } = new();
    public List<RunItem> Items { get; } = new();
    public string? OutputPath;
    /// <summary>Where the JSON run report landed, once written.</summary>
    public string? ReportPath;
}

/// <summary>How a run ended, as recorded in the run report.</summary>
public static class RunOutcome
{
    public const string Completed = "completed";
    public const string Cancelled = "cancelled";
    public const string Failed = "failed";
}

/// <summary>Everything the run report records about one run — identity and results only.</summary>
public sealed record RunReportData(string Direction, string AreaKey, string Server, bool DryRun,
    DateTime StartedUtc, DateTime FinishedUtc, string Outcome, RunSummary Summary);

/// <summary>
/// The per-run JSON record an operator can keep beside an export or in the log folder:
/// who/what/when, how it ended (completed, cancelled, failed), the counts, and one line per
/// item. It exists because the session log is per app session and line-oriented — this is
/// the one file that answers "what did that run do?". Never contains passwords, tokens, or
/// exported payloads.
/// </summary>
public static class RunReport
{
    private static readonly JsonSerializerOptions Pretty = new() { WriteIndented = true };

    public static string Serialize(RunReportData d) => JsonSerializer.Serialize(new
    {
        tool = PackageWriter.ToolName,
        direction = d.Direction,
        dryRun = d.DryRun,
        area = d.AreaKey,
        server = d.Server,
        startedUtc = d.StartedUtc.ToString("o"),
        finishedUtc = d.FinishedUtc.ToString("o"),
        outcome = d.Outcome,
        counts = new { ok = d.Summary.Ok, warnings = d.Summary.Warn,
            skipped = d.Summary.Skipped, failed = d.Summary.Failed },
        output = d.Summary.OutputPath,
        items = d.Summary.Items.Select(i => new { name = i.Name, outcome = i.Outcome, detail = i.Detail }),
    }, Pretty);

    /// <summary>"porter-run_export_2026-09-29_101500.json".</summary>
    public static string FileName(string direction, DateTime local)
        => $"porter-run_{direction}_{local:yyyy-MM-dd_HHmmss}.json";

    /// <summary>Writes the report into dir (never overwriting an earlier one from the same
    /// second) and returns its path.</summary>
    public static string Write(string dir, RunReportData d)
    {
        Directory.CreateDirectory(dir);
        var json = Serialize(d);
        var name = FileName(d.Direction, d.StartedUtc.ToLocalTime());
        var path = Path.Combine(dir, name);
        for (var n = 2; File.Exists(path); n++)
            path = Path.Combine(dir, Path.GetFileNameWithoutExtension(name) + $" ({n}).json");
        File.WriteAllText(path, json);
        return path;
    }

    /// <summary>Writes the report, then records the path in the session log. A failure to
    /// write the report is logged and swallowed — it must never mask the run's own result.</summary>
    public static void WriteAndLog(string dir, RunReportData d)
    {
        try
        {
            d.Summary.ReportPath = Write(dir, d);
            SessionLog.Log("run-report", d.AreaKey, d.Outcome, d.Summary.ReportPath);
        }
        catch (Exception ex)
        {
            try { SessionLog.Log("run-report", d.AreaKey, "failed", ex.Message); }
            catch { /* nothing left to report to */ }
        }
    }
}
