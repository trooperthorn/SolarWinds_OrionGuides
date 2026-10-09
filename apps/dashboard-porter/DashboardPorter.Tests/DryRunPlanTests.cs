using System.Text.Json.Nodes;
using DashboardPorter.Core;

namespace DashboardPorter.Tests;

/// <summary>
/// The dry-run widget-key check. PlanAsync's only server call is one read of
/// Orion.Dashboards.Widgets.UniqueKey; the pure half (PlanLines) is tested here with the
/// target's keys supplied directly, the same way Porter's tests avoid a live SWIS.
/// </summary>
public class DryRunPlanTests
{
    private static HashSet<string> Target(params string[] keys) => new(keys, StringComparer.OrdinalIgnoreCase);

    [Fact]
    public void WidgetKeys_AreDistinctAndCaseInsensitive()
    {
        var node = JsonNode.Parse(TestData.Dashboard)!.AsObject();
        node["widgets"]!.AsArray().Add(new JsonObject { ["unique_key"] = "W-1" });
        node["widgets"]!.AsArray().Add(new JsonObject { ["unique_key"] = "" });
        Assert.Equal(new[] { "w-1", "w-2" }, DashboardsCore.WidgetKeys(node.ToJsonString()));
    }

    [Fact]
    public void WidgetKeys_OfUnreadableText_IsEmpty()
        => Assert.Empty(DashboardsCore.WidgetKeys("{ not json"));

    [Fact]
    public void Plan_NamesTheDashboardItWouldCreate()
    {
        var lines = DashboardsCore.PlanLines(TestData.Dashboard, Target(), null);
        Assert.Contains("would create dashboard \"Ops\" (key dash-1)", lines);
    }

    [Fact]
    public void Plan_ReportsWidgetKeysAlreadyOnTheTarget()
    {
        var lines = DashboardsCore.PlanLines(TestData.Dashboard, Target("W-2", "unrelated"), null);
        Assert.Contains("WARNING: widget w-2 (already on target)", lines);
        Assert.DoesNotContain(lines, l => l.Contains("widget w-1"));
    }

    [Fact]
    public void Plan_SaysSoWhenNoWidgetKeyIsOnTheTarget()
    {
        var lines = DashboardsCore.PlanLines(TestData.Dashboard, Target("other"), null);
        Assert.Contains("2 widget definition(s), none already on target", lines);
        Assert.DoesNotContain(lines, l => l.StartsWith("WARNING"));
    }

    [Fact]
    public void Plan_WhenTheTargetCouldNotBeRead_SaysNotChecked()
    {
        var lines = DashboardsCore.PlanLines(TestData.Dashboard, null, "HTTP 400 Bad Request");
        Assert.Contains("widget keys not checked against the target: HTTP 400 Bad Request", lines);
    }

    [Fact]
    public void Plan_ListsTwentyHitsThenSummarisesTheRest()
    {
        var node = JsonNode.Parse(TestData.Dashboard)!.AsObject();
        var widgets = new JsonArray();
        var keys = Enumerable.Range(1, 25).Select(i => $"k-{i}").ToArray();
        foreach (var k in keys) widgets.Add(new JsonObject { ["unique_key"] = k });
        node["widgets"] = widgets;

        var lines = DashboardsCore.PlanLines(node.ToJsonString(), Target(keys), null);
        Assert.Equal(20, lines.Count(l => l.StartsWith("WARNING: widget ")));
        Assert.Contains("WARNING: … and 5 more widget key(s) already on target", lines);
    }

    [Fact]
    public void Plan_OfACopy_UsesTheRewrittenIdentities()
    {
        // In "Import as copy" the plan runs on the rewritten text: new names, new widget
        // keys — so the original widget keys on the target are no longer hits.
        var copy = DashboardsCore.AsCopy(TestData.Dashboard).Text;
        var lines = DashboardsCore.PlanLines(copy, Target("w-1", "w-2"), null);
        Assert.Contains(lines, l => l.StartsWith("would create dashboard \"Ops (Copy)\""));
        Assert.Contains("2 widget definition(s), none already on target", lines);
    }
}
