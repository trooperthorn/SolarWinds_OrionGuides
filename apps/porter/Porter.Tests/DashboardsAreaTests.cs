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

    private static Func<string> Sequence(params string[] keys)
    {
        var queue = new Queue<string>(keys);
        return () => queue.Dequeue();
    }

    [Fact]
    public void AsCopy_NeverIssuesAKeyAlreadyOnTheTarget()
    {
        // The generator offers target keys first (in another spelling); each must be passed over.
        var (text, _, keys, _) = DashboardsArea.AsCopy(TestData.Dashboard,
            avoid: new[] { "taken-a", "11111111-1111-1111-1111-111111111111" },
            newKey: Sequence("TAKEN-A", "{11111111-1111-1111-1111-111111111111}", "n1", "n2", "n3"));
        var root = JsonNode.Parse(text)!;
        var widgetKeys = root["widgets"]!.AsArray().Select(w => w!["unique_key"]!.GetValue<string>()).ToList();
        Assert.Equal(new[] { "n1", "n2" }, widgetKeys);
        Assert.Equal(new[] { "n3" }, keys);
    }

    [Fact]
    public void AsCopy_DashboardAndWidgetSharingAnOldKey_GetDifferentNewKeys()
    {
        var json = TestData.Dashboard.Replace("\"dash-1\"", "\"w-1\"");
        var (text, _, keys, _) = DashboardsArea.AsCopy(json);
        var root = JsonNode.Parse(text)!;
        var widgetKeys = root["widgets"]!.AsArray().Select(w => w!["unique_key"]!.GetValue<string>());
        Assert.DoesNotContain(keys[0], widgetKeys);
    }

    [Fact]
    public void AsCopy_RefusesConflictingDefinitionsUnderOneKey()
    {
        var node = JsonNode.Parse(TestData.Dashboard)!.AsObject();
        node["widgets"]![1]!["unique_key"] = "W-1";   // same identity, different definition
        var ex = Assert.Throws<System.IO.InvalidDataException>(() => DashboardsArea.AsCopy(node.ToJsonString()));
        Assert.Contains("different definitions", ex.Message);
    }

    [Fact]
    public void AsCopy_IdenticalDuplicateDefinitions_ShareOneNewKey()
    {
        var node = JsonNode.Parse(TestData.Dashboard)!.AsObject();
        node["widgets"]!.AsArray().Add(JsonNode.Parse(node["widgets"]![0]!.ToJsonString()));
        var (text, _, _, notes) = DashboardsArea.AsCopy(node.ToJsonString());
        var widgets = JsonNode.Parse(text)!["widgets"]!.AsArray();
        Assert.Equal(widgets[0]!["unique_key"]!.GetValue<string>(), widgets[2]!["unique_key"]!.GetValue<string>());
        Assert.NotEqual(widgets[0]!["unique_key"]!.GetValue<string>(), widgets[1]!["unique_key"]!.GetValue<string>());
        Assert.Contains(notes, n => n.Contains("identical definitions"));
    }

    [Fact]
    public void AsCopy_LeavesTheOriginalsGroupAndRoute()
    {
        var node = JsonNode.Parse(TestData.Dashboard)!.AsObject();
        var dash = node["dashboards"]![0]!.AsObject();
        dash["groupId"] = "AwsCostsDashboard";
        dash["groupRank"] = 1;
        dash["groupMemberName"] = "Month";
        dash["routeId"] = "aws-monthly-costs";
        dash["dashboardRoutes"] = JsonNode.Parse("[ \"aws-monthly-costs\" ]");
        var second = JsonNode.Parse(dash.ToJsonString())!.AsObject();
        second["unique_key"] = "dash-2";
        second["groupRank"] = 2;
        node["dashboards"]!.AsArray().Add(second);

        var (text, _, _, notes) = DashboardsArea.AsCopy(node.ToJsonString());
        var copies = JsonNode.Parse(text)!["dashboards"]!.AsArray();
        var group = copies[0]!["groupId"]!.GetValue<string>();
        Assert.NotEqual("AwsCostsDashboard", group);
        Assert.Equal(group, copies[1]!["groupId"]!.GetValue<string>());   // copies stay grouped together
        Assert.Equal(1, copies[0]!["groupRank"]!.GetValue<int>());
        Assert.Equal("", copies[0]!["routeId"]!.GetValue<string>());
        Assert.Empty(copies[0]!["dashboardRoutes"]!.AsArray());
        Assert.Contains(notes, n => n.Contains("groupId") && n.Contains("2 dashboard"));
        Assert.Contains(notes, n => n.Contains("routeId") && n.Contains("2 dashboard"));
    }

    [Fact]
    public void AsCopy_RewritesSelfReferenceInsideTheEncodedConfiguration()
    {
        var node = JsonNode.Parse(TestData.Dashboard)!.AsObject();
        var config = new JsonObject
        {
            ["messages"] = JsonNode.Parse(
                "[ { \"query\": \"SELECT COUNT(1) AS C FROM Orion.Dashboards.Instances WHERE DisplayName = 'Ops'\" } ]"),
            ["globalFilter"] = JsonNode.Parse(
                "{ \"swqlQuery\": \"SELECT DashboardID FROM Orion.Dashboards.Instances WHERE DisplayName = 'Ops'\" }"),
            ["nocView"] = JsonNode.Parse("{ \"enabled\": true }"),
        };
        // The 2026.4 exports carry configuration as a JSON string inside the JSON document.
        node["dashboards"]![0]!["configuration"] = config.ToJsonString();
        node["widgets"]![1]!["dataSource"] = JsonNode.Parse(
            "{ \"properties\": { \"swqlQuery\": \"SELECT 1 AS X FROM Orion.Dashboards.Instances WHERE DisplayName = 'Ops'\" } }");

        var (text, _, _, notes) = DashboardsArea.AsCopy(node.ToJsonString());
        var root = JsonNode.Parse(text)!;
        var encoded = root["dashboards"]![0]!["configuration"]!.GetValue<string>();
        var decoded = JsonNode.Parse(encoded)!;
        Assert.Contains("'Ops (Copy)'", decoded["messages"]![0]!["query"]!.GetValue<string>());
        Assert.Contains("'Ops (Copy)'", decoded["globalFilter"]!["swqlQuery"]!.GetValue<string>());
        Assert.True(decoded["nocView"]!["enabled"]!.GetValue<bool>());
        Assert.Contains("'Ops (Copy)'",
            root["widgets"]![1]!["dataSource"]!["properties"]!["swqlQuery"]!.GetValue<string>());
        Assert.Contains(notes, n => n.Contains("rewrote 4"));
        Assert.DoesNotContain(notes, n => n.Contains("outside a quoted literal"));
    }

    [Fact]
    public void AsCopy_DoubleEncodedConfiguration_StaysDoubleEncoded()
    {
        var node = JsonNode.Parse(TestData.Dashboard)!.AsObject();
        var inner = "{\"messages\":[{\"query\":\"SELECT 1 AS X FROM Orion.Nodes WHERE Caption = 'Ops'\"}]}";
        node["dashboards"]![0]!["configuration"] = System.Text.Json.JsonSerializer.Serialize(inner);

        var (text, _, _, _) = DashboardsArea.AsCopy(node.ToJsonString());
        var layer1 = JsonNode.Parse(text)!["dashboards"]![0]!["configuration"]!.GetValue<string>();
        var layer2 = JsonNode.Parse(layer1)!.GetValue<string>();
        Assert.Contains("'Ops (Copy)'", JsonNode.Parse(layer2)!["messages"]![0]!["query"]!.GetValue<string>());
    }

    [Fact]
    public void MatchKeys_NormalizesUuidSpellingAndNameCase()
    {
        var hits = DashboardsArea.MatchKeys(
            new[] { "6ae07bdb-aabf-4b31-a26a-f74ac1172c6e", "CLM-Aws-Monthly", "fresh" },
            new[] { "{6AE07BDB-AABF-4B31-A26A-F74AC1172C6E}", "clm-aws-monthly" });
        Assert.Equal(2, hits.Count);
        Assert.Contains(("CLM-Aws-Monthly", "clm-aws-monthly"), hits);
    }
}
