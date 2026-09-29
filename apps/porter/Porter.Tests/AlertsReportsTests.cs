using Porter.Areas;

namespace Porter.Tests;

public class AlertsReportsTests
{
    private const string AlertXml = "<AlertDefinition><Name>CPU high</Name></AlertDefinition>";
    private const string ReportXml = "<Report><Name>Inventory</Name></Report>";

    [Fact]
    public void Alerts_AcceptsAlertRoot()
    {
        var v = new AlertsProvider(TestData.Session()).Validate("a.xml", AlertXml);
        Assert.True(v.Ok, string.Join("; ", v.Errors));
    }

    [Fact]
    public void Alerts_WrongRoot_IsAnError()
    {
        var v = new AlertsProvider(TestData.Session()).Validate("r.xml", ReportXml);
        Assert.False(v.Ok);
    }

    [Fact]
    public void Reports_AcceptsReportRoot()
    {
        var v = new ReportsProvider(TestData.Session()).Validate("r.xml", ReportXml);
        Assert.True(v.Ok, string.Join("; ", v.Errors));
    }

    [Fact]
    public void Reports_WrongRoot_IsAnError()
    {
        var v = new ReportsProvider(TestData.Session()).Validate("a.xml", AlertXml);
        Assert.False(v.Ok);
    }
}
