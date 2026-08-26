using System.IO;
using System.Text;
using System.Text.Json;
using System.Xml;
using System.Xml.Linq;
using Porter.Core;

namespace Porter.Areas;

/// <summary>
/// NCM compliance policy reports — Cirrus.PolicyReports verbs (the Cirrus.Policy* SWQL
/// entities are read-only; every write is a verb).
/// Export:  GetPolicyReport(reportId, exportFlag=true) returns the full nested
///          PolicyReport object; Porter writes it as the SAME XML document the web
///          console exports (verified against real console files), UTF-16 with BOM,
///          so files interchange with the WebUI in both directions.
/// Import:  AddPolicyReport(report, importFlag=true) persists report, policies, and
///          rules in one call and returns the new server-assigned GUID; Porter then
///          starts compliance caching for just that report so it is not inert.
/// SECURITY GATE: a rule with ExecuteScriptAutomatically=true pushes configuration to
/// failing devices on the next compliance cycle. Validation raises a blocking security
/// flag for every such rule — the file cannot import until the operator acknowledges.
/// </summary>
public sealed class NcmComplianceProvider : AreaProvider
{
    public NcmComplianceProvider(SwisSession swis) : base(swis) { }

    public override string Key => "ncmcompliance";
    public override string DisplayName => "NCM Compliance Reports";
    public override string FileExtension => ".xml";
    public override string FileDialogFilter => "NCM policy reports|*.xml";
    public override string ImportVia => "Cirrus.PolicyReports.AddPolicyReport(report, importFlag=true)";
    public override string SecurityNotice =>
        "Policy rules can carry remediation scripts, and a rule flagged to auto-execute " +
        "will push configuration to failing devices once imported and cached. Porter " +
        "blocks such files at import until the flags are explicitly acknowledged.";

    public override async Task<List<AreaItem>> ListAsync(CancellationToken ct)
    {
        var rows = await Swis.QueryAsync(
            "SELECT PolicyReportID, Name, Grouping, ReportStatus FROM Cirrus.PolicyReports " +
            "ORDER BY Name", null, ct);
        var list = new List<AreaItem>();
        foreach (var row in rows.EnumerateArray())
        {
            var name = row.GetProperty("Name").GetString() ?? "(unnamed)";
            var grouping = (row.TryGetProperty("Grouping", out var g) ? g.GetString() : null) ?? "";
            list.Add(new AreaItem(row.GetProperty("PolicyReportID").GetString() ?? "",
                name, name, false, grouping));
        }
        return list;
    }

    // ---- export: verb object → console-format XML ----

    public override async Task<AreaExport> ExportAsync(AreaItem item, ExportOptions opt, CancellationToken ct)
    {
        var result = await Swis.InvokeAsync("Cirrus.PolicyReports", "GetPolicyReport",
            new object?[] { item.Id, true }, ct);
        if (result is not { ValueKind: JsonValueKind.Object } report)
            throw new InvalidOperationException($"GetPolicyReport returned nothing for \"{item.Name}\"");
        var doc = BuildConsoleXml(report);

        // The console writes UTF-16; matching it keeps the file importable through the
        // WebUI as well as through Porter.
        using var buffer = new MemoryStream();
        using (var writer = XmlWriter.Create(buffer, new XmlWriterSettings
        {
            Encoding = Encoding.Unicode, Indent = true, IndentChars = "  ",
        }))
        {
            doc.Save(writer);
        }
        return new AreaExport(PackageWriter.Sanitize(item.Name) + FileExtension, buffer.ToArray());
    }

    private static string S(JsonElement obj, string name)
        => obj.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.String
            ? v.GetString() ?? "" : "";

    private static string Raw(JsonElement obj, string name)
        => obj.TryGetProperty(name, out var v) ? v.ValueKind switch
        {
            JsonValueKind.String => v.GetString() ?? "",
            JsonValueKind.Number => v.GetRawText(),
            JsonValueKind.True => "true",
            JsonValueKind.False => "false",
            _ => "",
        } : "";

    private static string B(JsonElement obj, string name)
        => obj.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.True ? "true" : "false";

    private static XDocument BuildConsoleXml(JsonElement report)
    {
        XNamespace xsd = "http://www.w3.org/2001/XMLSchema";
        XNamespace xsi = "http://www.w3.org/2001/XMLSchema-instance";
        var policies = new XElement("AssignedPolicies");
        if (report.TryGetProperty("AssignedPolicies", out var pols) &&
            pols.ValueKind == JsonValueKind.Array)
        {
            foreach (var p in pols.EnumerateArray())
            {
                var rules = new XElement("AssignedPolicyRules");
                if (p.TryGetProperty("AssignedPolicyRules", out var rs) &&
                    rs.ValueKind == JsonValueKind.Array)
                    foreach (var r in rs.EnumerateArray())
                        rules.Add(RuleXml(r));
                policies.Add(new XElement("Policy",
                    new XElement("NodeSelectionString", S(p, "NodeSelectionString")),
                    new XElement("ConfigTypes", S(p, "ConfigTypes")),
                    rules,
                    new XElement("Grouping", S(p, "Grouping")),
                    new XElement("Comments", S(p, "Comments")),
                    new XElement("PolicyName", S(p, "PolicyName"))));
            }
        }
        // Element order copied from real console exports — .NET XML deserializers on the
        // receiving side are order-sensitive.
        var root = new XElement("PolicyReport",
            new XAttribute(XNamespace.Xmlns + "xsd", xsd),
            new XAttribute(XNamespace.Xmlns + "xsi", xsi),
            new XElement("ID", S(report, "ID")),
            new XElement("Name", S(report, "Name")),
            new XElement("Comments", S(report, "Comments")),
            new XElement("Group", S(report, "Group")),
            new XElement("ShowSummaryFlag", B(report, "ShowSummaryFlag")),
            new XElement("ShowRulesWithoutViolationFlag", B(report, "ShowRulesWithoutViolationFlag")),
            policies,
            new XElement("ReportStatus", Raw(report, "ReportStatus")));
        return new XDocument(new XDeclaration("1.0", "utf-16", null), root);
    }

    private static XElement RuleXml(JsonElement r)
    {
        var patterns = new XElement("MultiLineRulePatterns");
        if (r.TryGetProperty("MultiLineRulePatterns", out var ps) &&
            ps.ValueKind == JsonValueKind.Array)
            foreach (var p in ps.EnumerateArray())
                patterns.Add(new XElement("MultiLineRulePattern",
                    new XElement("EndBracket", S(p, "EndBracket")),
                    new XElement("PatternType", Raw(p, "PatternType")),
                    new XElement("Condition", S(p, "Condition")),
                    new XElement("Pattern", S(p, "Pattern")),
                    new XElement("Criteria", B(p, "Criteria")),
                    new XElement("BeginBracket", S(p, "BeginBracket"))));
        return new XElement("PolicyRule",
            patterns,
            new XElement("RuleId", S(r, "RuleId")),
            new XElement("RuleName", S(r, "RuleName")),
            new XElement("Comments", S(r, "Comments")),
            new XElement("Grouping", S(r, "Grouping")),
            new XElement("RemediateScript", S(r, "RemediateScript")),
            new XElement("ConfigBlockStart", S(r, "ConfigBlockStart")),
            new XElement("ConfigBlockEnd", S(r, "ConfigBlockEnd")),
            new XElement("ConfigBlockPatternType", Raw(r, "ConfigBlockPatternType")),
            new XElement("ConfigBlockMustExist", B(r, "ConfigBlockMustExist")),
            new XElement("PatternType", Raw(r, "PatternType")),
            new XElement("PatternMustExist", B(r, "PatternMustExist")),
            new XElement("AdvancedMode", B(r, "AdvancedMode")),
            new XElement("ErrorLevel", Raw(r, "ErrorLevel")),
            new XElement("SimplePatternText", S(r, "SimplePatternText")),
            new XElement("ExecuteScriptAutomatically", B(r, "ExecuteScriptAutomatically")),
            new XElement("Owner", S(r, "Owner")),
            new XElement("RemediateScriptType", Raw(r, "RemediateScriptType")),
            new XElement("ExecuteRemediationScriptPerBlock", B(r, "ExecuteRemediationScriptPerBlock")),
            new XElement("ExecuteScriptInConfigMode", B(r, "ExecuteScriptInConfigMode")));
    }

    // ---- validation: the remediation gate lives here ----

    public override AreaValidation Validate(string fileName, string text)
    {
        var v = new AreaValidation();
        try
        {
            if (string.IsNullOrWhiteSpace(text))
            { v.Errors.Add("file is empty (0 bytes) — not importable"); return v; }
            XDocument doc;
            try { doc = XDocument.Parse(text); }
            catch (Exception ex) { v.Errors.Add($"not valid XML: {ex.Message}"); return v; }

            if (doc.Root?.Name.LocalName != "PolicyReport")
            {
                v.Errors.Add($"root element is <{doc.Root?.Name.LocalName}> — an NCM policy " +
                    "report starts with <PolicyReport>");
                return v;
            }
            var name = doc.Root.Element("Name")?.Value?.Trim() ?? "";
            if (name.Length == 0)
            { v.Errors.Add("the report has no <Name> — nothing to identify it by"); return v; }
            v.Items.Add((name, name));

            var policies = doc.Root.Descendants("Policy").ToList();
            var rules = doc.Root.Descendants("PolicyRule").ToList();
            if (policies.Count == 0) v.Warnings.Add("the report contains no policies");
            v.Detail = $"\"{name}\" · {policies.Count} policies · {rules.Count} rules";

            var withScript = rules.Where(r =>
                !string.IsNullOrWhiteSpace(r.Element("RemediateScript")?.Value)).ToList();
            var auto = rules.Where(r =>
                string.Equals(r.Element("ExecuteScriptAutomatically")?.Value?.Trim(), "true",
                    StringComparison.OrdinalIgnoreCase)).ToList();
            foreach (var rule in auto.Take(5))
                v.SecurityFlags.Add($"rule \"{rule.Element("RuleName")?.Value}\" auto-executes " +
                    "its remediation script on failing devices once this report is cached");
            if (auto.Count > 5)
                v.SecurityFlags.Add($"… and {auto.Count - 5} more auto-executing rules");
            var manualScripts = withScript.Count(r => !auto.Contains(r));
            if (manualScripts > 0)
                v.Warnings.Add($"{manualScripts} rule(s) carry remediation scripts " +
                    "(manual execution only)");
        }
        catch (Exception ex)
        {
            v.Errors.Add($"file could not be analysed: {ex.Message}");
        }
        return v;
    }

    public override async Task<Dictionary<string, string>> FindCollisionsAsync(
        IReadOnlyCollection<string> keys, CancellationToken ct)
    {
        var map = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var key in keys.Where(k => k.Length > 0))
        {
            var rows = await Swis.QueryAsync(
                "SELECT Name FROM Cirrus.PolicyReports WHERE Name = @n",
                new Dictionary<string, object?> { ["n"] = key }, ct);
            foreach (var row in rows.EnumerateArray())
                map[key] = row.GetProperty("Name").GetString() ?? key;
        }
        return map;
    }

    // ---- import: XML → contract object → AddPolicyReport ----

    public override async Task<ImportOutcome> ImportAsync(string text, IReadOnlyList<string> verifyKeys,
        ImportOptions opt, CancellationToken ct)
    {
        var doc = XDocument.Parse(text);
        var root = doc.Root ?? throw new InvalidDataException("empty document");
        var report = new Dictionary<string, object?>
        {
            ["ID"] = El(root, "ID"),
            ["Name"] = El(root, "Name"),
            ["Comments"] = El(root, "Comments"),
            ["Group"] = El(root, "Group"),
            ["ShowSummaryFlag"] = Bool(root, "ShowSummaryFlag"),
            ["ShowRulesWithoutViolationFlag"] = Bool(root, "ShowRulesWithoutViolationFlag"),
            ["AssignedPolicies"] = root.Element("AssignedPolicies")?.Elements("Policy")
                .Select(PolicyObject).ToList() ?? new List<Dictionary<string, object?>>(),
            ["ReportStatus"] = El(root, "ReportStatus") is { Length: > 0 } s ? s : "Enabled",
        };

        var result = await Swis.InvokeAsync("Cirrus.PolicyReports", "AddPolicyReport",
            new object?[] { report, true }, ct);
        var newId = result?.ValueKind == JsonValueKind.String ? result.Value.GetString() : null;
        if (string.IsNullOrWhiteSpace(newId))
            return new ImportOutcome(false, "AddPolicyReport did not return the new report id");

        var rows = await Swis.QueryAsync(
            "SELECT PolicyReportID, Name FROM Cirrus.PolicyReports WHERE PolicyReportID = @id",
            new Dictionary<string, object?> { ["id"] = newId }, ct);
        string? confirmed = null;
        foreach (var row in rows.EnumerateArray())
            confirmed = row.GetProperty("Name").GetString();
        if (confirmed is null)
            return new ImportOutcome(false,
                $"AddPolicyReport returned {newId} but no data returned when reading it back (No Data Returned)");

        // A report is inert until compliance caching runs; start it for just this one.
        var caching = "";
        try
        {
            await Swis.InvokeAsync("Cirrus.PolicyReports", "StartCaching",
                new object?[] { new[] { newId } }, ct);
            caching = " · compliance caching started";
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            caching = $" · start compliance caching manually ({ex.Message})";
        }
        return new ImportOutcome(true, $"\"{confirmed}\" ({newId}){caching}");
    }

    private static string El(XElement parent, string name) => parent.Element(name)?.Value ?? "";
    private static bool Bool(XElement parent, string name)
        => string.Equals(parent.Element(name)?.Value?.Trim(), "true", StringComparison.OrdinalIgnoreCase);

    private static Dictionary<string, object?> PolicyObject(XElement p) => new()
    {
        ["PolicyName"] = El(p, "PolicyName"),
        ["Comments"] = El(p, "Comments"),
        ["Grouping"] = El(p, "Grouping"),
        ["NodeSelectionString"] = El(p, "NodeSelectionString"),
        ["ConfigTypes"] = El(p, "ConfigTypes"),
        ["AssignedPolicyRules"] = p.Element("AssignedPolicyRules")?.Elements("PolicyRule")
            .Select(RuleObject).ToList() ?? new List<Dictionary<string, object?>>(),
    };

    private static Dictionary<string, object?> RuleObject(XElement r) => new()
    {
        ["RuleId"] = El(r, "RuleId"),
        ["RuleName"] = El(r, "RuleName"),
        ["Comments"] = El(r, "Comments"),
        ["Grouping"] = El(r, "Grouping"),
        ["SimplePatternText"] = El(r, "SimplePatternText"),
        ["PatternType"] = El(r, "PatternType"),
        ["PatternMustExist"] = Bool(r, "PatternMustExist"),
        ["AdvancedMode"] = Bool(r, "AdvancedMode"),
        ["MultiLineRulePatterns"] = r.Element("MultiLineRulePatterns")?
            .Elements("MultiLineRulePattern").Select(p => (object)new Dictionary<string, object?>
            {
                ["Pattern"] = El(p, "Pattern"),
                ["PatternType"] = El(p, "PatternType"),
                ["IsRegEx"] = string.Equals(El(p, "PatternType"), "Regex", StringComparison.OrdinalIgnoreCase),
                ["Condition"] = El(p, "Condition"),
                ["Criteria"] = Bool(p, "Criteria"),
                ["BeginBracket"] = El(p, "BeginBracket"),
                ["EndBracket"] = El(p, "EndBracket"),
            }).ToList() ?? new List<object>(),
        ["ConfigBlockStart"] = El(r, "ConfigBlockStart"),
        ["ConfigBlockEnd"] = El(r, "ConfigBlockEnd"),
        ["ConfigBlockPatternType"] = El(r, "ConfigBlockPatternType"),
        ["ConfigBlockMustExist"] = Bool(r, "ConfigBlockMustExist"),
        ["IsConfigBlockPatternRegEx"] = string.Equals(El(r, "ConfigBlockPatternType"), "Regex",
            StringComparison.OrdinalIgnoreCase),
        ["ErrorLevel"] = int.TryParse(El(r, "ErrorLevel"), out var lvl) ? lvl : 0,
        ["RemediateScript"] = El(r, "RemediateScript"),
        ["RemediateScriptType"] = El(r, "RemediateScriptType") is { Length: > 0 } t ? t : "CLI",
        ["ExecuteScriptAutomatically"] = Bool(r, "ExecuteScriptAutomatically"),
        ["ExecuteRemediationScriptPerBlock"] = Bool(r, "ExecuteRemediationScriptPerBlock"),
        ["ExecuteScriptInConfigMode"] = Bool(r, "ExecuteScriptInConfigMode"),
        ["Owner"] = El(r, "Owner"),
    };
}
