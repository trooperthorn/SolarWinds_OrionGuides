using System.Text.Json.Nodes;
using Porter.Areas;

namespace Porter.Tests;

public class DashboardValidatorTests
{
    [Fact]
    public void ValidEnvelope_Passes()
    {
        var v = DashboardValidator.Validate(TestData.Dashboard);
        Assert.True(v.Ok, string.Join("; ", v.Errors));
        Assert.Equal(2, v.WidgetCount);
        Assert.Single(v.Dashboards);
        Assert.Equal(("dash-1", "Ops"), v.Dashboards[0]);
    }

    [Theory]
    [InlineData("version")]
    [InlineData("dashboards")]
    [InlineData("widgets")]
    public void MissingEnvelopeKey_IsAnError(string key)
    {
        var node = JsonNode.Parse(TestData.Dashboard)!.AsObject();
        node.Remove(key);
        var v = DashboardValidator.Validate(node.ToJsonString());
        Assert.False(v.Ok);
        Assert.Contains(v.Errors, e => e.Contains($"\"{key}\""));
    }

    [Fact]
    public void DanglingPlacement_IsAnError()
    {
        var node = JsonNode.Parse(TestData.Dashboard)!.AsObject();
        node["dashboards"]![0]!["widgets"]![1]!["unique_key"] = "ghost";
        var v = DashboardValidator.Validate(node.ToJsonString());
        Assert.False(v.Ok);
        Assert.Contains(v.Errors, e => e.Contains("ghost"));
    }

    [Fact]
    public void DuplicateWidgetKeys_Warn()
    {
        var node = JsonNode.Parse(TestData.Dashboard)!.AsObject();
        node["widgets"]![1]!["unique_key"] = "w-1";
        var v = DashboardValidator.Validate(node.ToJsonString());
        Assert.Contains(v.Warnings, w => w.Contains("unique_key reused"));
    }

    [Fact]
    public void EmptyAndMalformedInput_NeverThrow()
    {
        Assert.False(DashboardValidator.Validate("").Ok);
        Assert.False(DashboardValidator.Validate("{ not json").Ok);
        Assert.False(DashboardValidator.Validate("[]").Ok);
    }

    [Theory]
    [InlineData("6AE07BDB-AABF-4B31-A26A-F74AC1172C6E", "{6ae07bdb-aabf-4b31-a26a-f74ac1172c6e}")]
    [InlineData("W-1", "w-1")]
    public void DuplicateWidgetKeys_AreFoundAcrossSpellings(string first, string second)
    {
        var node = JsonNode.Parse(TestData.Dashboard)!.AsObject();
        node["widgets"]![0]!["unique_key"] = first;
        node["widgets"]![1]!["unique_key"] = second;
        node["dashboards"]![0]!["widgets"]![0]!["unique_key"] = first;
        node["dashboards"]![0]!["widgets"]![1]!["unique_key"] = second;
        var v = DashboardValidator.Validate(node.ToJsonString());
        Assert.True(v.Ok, string.Join("; ", v.Errors));
        Assert.Contains(v.Warnings, w => w.Contains("unique_key reused"));
    }

    [Fact]
    public void QueryCopyMismatch_DoesNotClaimWhichCopyRuns()
    {
        var node = JsonNode.Parse(TestData.Dashboard)!.AsObject();
        node["widgets"]![0]!["adapter"] = JsonNode.Parse(
            "{ \"properties\": { \"dataSource\": { \"properties\": { \"swql\": \"SELECT 1 FROM Orion.Nodes\" } } } }");
        var v = DashboardValidator.Validate(node.ToJsonString());
        var warning = Assert.Single(v.Warnings, w => w.Contains("dataSource and adapter copies"));
        Assert.Contains("not established", warning);
        Assert.DoesNotContain("still runs", warning);
    }
}
