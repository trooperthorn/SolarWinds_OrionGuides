using System.Xml.Linq;
using Porter.Areas;

namespace Porter.Tests;

public class AlertNameTests
{
    [Fact]
    public void DirectChildOfRoot_Wins_OverNestedActionNames()
    {
        var doc = XDocument.Parse(
            "<AlertDefinition><Actions><Action><Name>Send mail</Name></Action></Actions><Name>CPU high</Name></AlertDefinition>");
        Assert.Equal(("CPU high", false), AlertsProvider.ExtractName(doc));
    }

    [Fact]
    public void WrapperUnderRoot_IsUsedBeforeAnyDeepFallback()
    {
        var doc = XDocument.Parse(
            "<Export><Trigger><Name>Trigger name</Name></Trigger>" +
            "<AlertConfiguration><Name>Real alert</Name></AlertConfiguration></Export>");
        Assert.Equal(("Real alert", false), AlertsProvider.ExtractName(doc));
    }

    [Fact]
    public void DeepFallback_IsFlaggedAsNested()
    {
        var doc = XDocument.Parse("<AlertExport><Body><Deep><Name>Buried</Name></Deep></Body></AlertExport>");
        Assert.Equal(("Buried", true), AlertsProvider.ExtractName(doc));
    }

    [Fact]
    public void NoName_ReturnsNull()
        => Assert.Equal((null, false), AlertsProvider.ExtractName(XDocument.Parse("<Alert><X/></Alert>")));

    [Fact]
    public void Validate_WarnsWhenTheNameCameFromANestedElement()
    {
        var v = new AlertsProvider(TestData.Session()).Validate("a.xml",
            "<AlertExport><Body><Name>Buried</Name></Body></AlertExport>");
        Assert.True(v.Ok);
        Assert.Contains(v.Warnings, w => w.Contains("nested <Name>"));
        Assert.Equal("Buried", v.Items[0].Key);
    }

    [Fact]
    public void Validate_NoWarningForADirectName()
    {
        var v = new AlertsProvider(TestData.Session()).Validate("a.xml",
            "<AlertDefinition><Name>CPU high</Name></AlertDefinition>");
        Assert.Empty(v.Warnings);
    }
}

public class NodesCpBooleanTests
{
    [Theory]
    [InlineData("true", true)]
    [InlineData("TRUE", true)]
    [InlineData("1", true)]
    [InlineData("Yes", true)]
    [InlineData("false", false)]
    [InlineData("0", false)]
    [InlineData("No", false)]
    public void AcceptedSpellings(string raw, bool expected)
    {
        Assert.True(NodesCpProvider.TryConvert("boolean", raw, out var value));
        Assert.Equal(expected, value);
    }

    [Theory]
    [InlineData("maybe")]
    [InlineData("2")]
    [InlineData("y")]
    [InlineData("on")]
    public void Anything_Else_IsRejected_AndNothingIsWritten(string raw)
    {
        Assert.False(NodesCpProvider.TryConvert("boolean", raw, out var value));
        Assert.Null(value);
    }

    [Fact]
    public void OtherTypes_Convert_OrFallBackToText()
    {
        Assert.True(NodesCpProvider.TryConvert("integer", "42", out var i));
        Assert.Equal(42L, i);
        Assert.True(NodesCpProvider.TryConvert("double", "1.5", out var d));
        Assert.Equal(1.5, d);
        Assert.True(NodesCpProvider.TryConvert("integer", "abc", out var s));
        Assert.Equal("abc", s);
        Assert.True(NodesCpProvider.TryConvert("string", "x", out var str));
        Assert.Equal("x", str);
    }
}

public class PlanDefaultsTests
{
    [Fact]
    public async Task DefaultPlan_IsEmpty_AndWidgetKeysAreReadFromTheFile()
    {
        var provider = new ReportsProvider(TestData.Session());
        Assert.Empty(await provider.PlanAsync("<Report/>", CancellationToken.None));
        Assert.Equal(new[] { "w-1", "w-2" }, DashboardsProvider.WidgetKeys(TestData.Dashboard));
        Assert.Empty(DashboardsProvider.WidgetKeys("not json"));
    }
}
