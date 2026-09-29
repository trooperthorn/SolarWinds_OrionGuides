using System.Text.Json.Nodes;
using Porter.Areas;

namespace Porter.Tests;

public class DashboardsAreaTests
{
    [Fact]
    public void AsCopy_RegeneratesKeysAndRemapsPlacements()
    {
        var (text, names, keys, _) = DashboardsArea.AsCopy(TestData.Dashboard);
        var root = JsonNode.Parse(text)!.AsObject();

        var dash = root["dashboards"]![0]!.AsObject();
        var newDashKey = dash["unique_key"]!.GetValue<string>();
        Assert.NotEqual("dash-1", newDashKey);
        Assert.Equal(new[] { newDashKey }, keys);

        var widgetKeys = root["widgets"]!.AsArray().Select(w => w!["unique_key"]!.GetValue<string>()).ToList();
        Assert.DoesNotContain("w-1", widgetKeys);
        Assert.DoesNotContain("w-2", widgetKeys);

        var placed = dash["widgets"]!.AsArray().Select(w => w!["unique_key"]!.GetValue<string>()).ToList();
        Assert.Equal(widgetKeys, placed);   // placements follow the definitions

        Assert.Equal("Ops (Copy)", dash["name"]!.GetValue<string>());
        Assert.Equal(new[] { "Ops (Copy)" }, names);
    }

    [Fact]
    public void AsCopy_RewritesQuotedSelfReferenceInSwql()
    {
        var (text, _, _, notes) = DashboardsArea.AsCopy(TestData.Dashboard);
        var swql = JsonNode.Parse(text)!["widgets"]![0]!["dataSource"]!["properties"]!["swql"]!.GetValue<string>();
        Assert.Contains("Name = 'Ops (Copy)'", swql);
        Assert.Contains(notes, n => n.Contains("rewrote 1"));
    }

    [Fact]
    public void AsCopy_LeavesUnquotedMentionAndFlagsIt()
    {
        var json = TestData.Dashboard.Replace("'Ops'", "Ops");
        var (_, _, _, notes) = DashboardsArea.AsCopy(json);
        Assert.Contains(notes, n => n.Contains("outside a quoted literal"));
    }
}
