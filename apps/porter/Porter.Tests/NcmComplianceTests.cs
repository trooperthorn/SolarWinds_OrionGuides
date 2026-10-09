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

    [Theory]
    [InlineData(false, "Enabled", "Disabled")]
    [InlineData(false, "", "Disabled")]
    [InlineData(true, "Enabled", "Enabled")]
    [InlineData(true, "", "Enabled")]
    [InlineData(true, "Disabled", "Disabled")]
    public void ImportStatus_IsDisabledUnlessOptedIn(bool keep, string fileStatus, string expected)
        => Assert.Equal(expected, NcmComplianceProvider.TargetStatus(keep, fileStatus));

    private const string TwoPolicies = """
        <PolicyReport><Name>Baseline</Name><AssignedPolicies>
          <Policy><AssignedPolicyRules>
            <PolicyRule><RuleName>ntp</RuleName></PolicyRule>
            <PolicyRule><RuleName>snmp</RuleName></PolicyRule>
          </AssignedPolicyRules><PolicyName>Core</PolicyName></Policy>
          <Policy><AssignedPolicyRules>
            <PolicyRule><RuleName>banner</RuleName></PolicyRule>
          </AssignedPolicyRules><PolicyName>Edge</PolicyName></Policy>
        </AssignedPolicies></PolicyReport>
        """;

    private static NcmComplianceProvider.ReportTree Expected()
        => NcmComplianceProvider.ExpectedTree(System.Xml.Linq.XDocument.Parse(TwoPolicies).Root!);

    private static NcmComplianceProvider.ReportTree? ReadBack(string json)
        => NcmComplianceProvider.ReadBackTree(System.Text.Json.JsonDocument.Parse(json).RootElement);

    [Fact]
    public void ReadBack_MatchingTree_HasNoDifferences()
    {
        var actual = ReadBack("""
            { "ID": "x", "AssignedPolicies": [
              { "PolicyName": "Core", "AssignedPolicyRules": [ { "RuleName": "ntp" }, { "RuleName": "snmp" } ] },
              { "PolicyName": "Edge", "AssignedPolicyRules": [ { "RuleName": "banner" } ] } ] }
            """);
        Assert.Equal(2, Expected().Policies.Count);
        Assert.Equal(3, Expected().RuleCount);
        Assert.Empty(NcmComplianceProvider.CompareTrees(Expected(), actual!));
    }

    [Fact]
    public void ReadBack_ReportRowOnly_IsAPartialImportWithCounts()
    {
        // The field observation: the server accepted the nested call and stored only the row.
        var actual = ReadBack("""{ "ID": "x", "Name": "Baseline", "AssignedPolicies": [] }""");
        var diffs = NcmComplianceProvider.CompareTrees(Expected(), actual!);
        Assert.Contains("policies: expected 2, stored 0", diffs);
        Assert.Contains("rules: expected 3, stored 0", diffs);
    }

    [Fact]
    public void ReadBack_MissingRule_IsNamed()
    {
        var actual = ReadBack("""
            { "AssignedPolicies": [
              { "PolicyName": "Core", "AssignedPolicyRules": [ { "RuleName": "ntp" } ] },
              { "PolicyName": "Edge", "AssignedPolicyRules": [ { "RuleName": "banner" } ] } ] }
            """);
        var diffs = NcmComplianceProvider.CompareTrees(Expected(), actual!);
        Assert.Contains(diffs, d => d.Contains("policy \"Core\": expected 2 rules, stored 1") && d.Contains("snmp"));
    }

    [Fact]
    public void ReadBack_IdListWithoutNestedTree_CannotBeCompared()
        => Assert.Null(ReadBack("""{ "AssignedPoliciesList": [ "p1" ] }"""));
}
