using Porter.Areas;

namespace Porter.Tests;

public class NcmComplianceTests
{
    private static string Report(string auto) => $"""
        <PolicyReport><Name>Baseline</Name>
          <Policy><PolicyRule><RuleName>Fix ntp</RuleName>
            <RemediateScript>conf t</RemediateScript>
            <ExecuteScriptAutomatically>{auto}</ExecuteScriptAutomatically>
          </PolicyRule></Policy>
        </PolicyReport>
        """;

    [Fact]
    public void AutoExecuteRule_RaisesSecurityFlag()
    {
        var v = new NcmComplianceProvider(TestData.Session()).Validate("b.xml", Report("true"));
        Assert.True(v.Ok);
        Assert.NotEmpty(v.SecurityFlags);
        Assert.Contains("auto-executes", v.SecurityFlags[0]);
    }

    [Fact]
    public void ManualScript_OnlyWarns()
    {
        var v = new NcmComplianceProvider(TestData.Session()).Validate("b.xml", Report("false"));
        Assert.Empty(v.SecurityFlags);
        Assert.Contains(v.Warnings, w => w.Contains("manual execution"));
    }
}
