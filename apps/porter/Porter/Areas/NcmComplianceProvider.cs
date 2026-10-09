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
/// Import:  AddPolicyReport(report, importFlag=true) with ReportStatus Disabled returns the
///          new server-assigned GUID; UpdateReportStatus(Disabled) confirms the status, and
///          GetPolicyReport(id, exportFlag=true) reads the stored tree back so policy and
///          rule counts and names are compared with the file (a server has been seen
///          storing only the report row). A mismatch is reported as a partial import and
///          the report stays Disabled. Reports stay Disabled and uncached unless the
///          operator opts in to keeping the exported status; then an Enabled report is
///          enabled and compliance caching starts for just that report.
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

    public override string? KeepEnabledOptionLabel =>
        "Keep each NCM report's exported status — an Enabled report starts evaluating " +
        "(Porter starts caching it, and the scheduled policy cache refreshes it). " +
        "Off: reports import Disabled for review.";

    /// <summary>
    /// The status a report ends with. Imported reports start evaluating on their own — the
    /// policy cache refreshes daily and report jobs can be scheduled — so the default is
    /// Disabled for review (docs/modules/ncm-compliance-reports.md). Only the explicit
    /// opt-in keeps the file's status; a file with no status keeps the console's Enabled.
    /// </summary>
    internal static string TargetStatus(bool keepExported, string fileStatus)
    {
        if (!keepExported) return "Disabled";
        return fileStatus.Trim().Equals("Disabled", StringComparison.OrdinalIgnoreCase) ? "Disabled" : "Enabled";
    }

    public override async Task<ImportOutcome> ImportAsync(string text, IReadOnlyList<string> verifyKeys,
        ImportOptions opt, CancellationToken ct)
    {
        var doc = XDocument.Parse(text);
        var root = doc.Root ?? throw new InvalidDataException("empty document");
        var target = TargetStatus(opt.KeepEnabled, El(root, "ReportStatus"));
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
            // Always created Disabled: nothing evaluates before the stored tree is verified.
            // The opt-in enables it afterwards.
            ["ReportStatus"] = "Disabled",
        };

        var result = await Swis.InvokeAsync("Cirrus.PolicyReports", "AddPolicyReport",
            new object?[] { report, true }, ct);
        var newId = result?.ValueKind == JsonValueKind.String ? result.Value.GetString() : null;
        if (string.IsNullOrWhiteSpace(newId))
            return new ImportOutcome(false, "AddPolicyReport did not return the new report id");

        // The status travels in the payload, but UpdateReportStatus is the verb that owns it.
        var statusNote = "";
        try
        {
            await Swis.InvokeAsync("Cirrus.PolicyReports", "UpdateReportStatus",
                new object?[] { "Disabled", new[] { newId } }, ct);
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            statusNote = $" · UpdateReportStatus(Disabled) failed ({ex.Message}) — check the status in the console";
        }

        // A server has been observed accepting the nested call and storing only the report
        // row, so the row alone proves nothing: read the whole tree back and compare it with
        // what the file carried.
        var expected = ExpectedTree(root);
        JsonElement? tree;
        try
        {
            tree = await Swis.InvokeAsync("Cirrus.PolicyReports", "GetPolicyReport",
                new object?[] { newId, true }, ct);
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            return new ImportOutcome(false,
                $"report {newId} was created but GetPolicyReport(id, true) failed ({ex.Message}), so its " +
                $"policies and rules are unverified · left Disabled and not cached{statusNote}");
        }
        var actual = tree is { ValueKind: JsonValueKind.Object } t ? ReadBackTree(t) : null;
        var differences = actual is null
            ? new List<string> { "GetPolicyReport(id, true) returned no report object" }
            : CompareTrees(expected, actual);
        if (differences.Count > 0)
        {
            var held = actual is null ? "nothing readable"
                : $"{actual.Policies.Count} policies / {actual.RuleCount} rules";
            return new ImportOutcome(false,
                $"PARTIAL import: report {newId} was created but the server holds {held}, the file " +
                $"carried {expected.Policies.Count} policies / {expected.RuleCount} rules — " +
                string.Join("; ", differences.Take(5)) +
                (differences.Count > 5 ? $"; … and {differences.Count - 5} more" : "") +
                $" · left Disabled and not cached; delete or repair it before use{statusNote}",
                Partial: true);
        }

        var enabledNote = "";
        if (target == "Enabled")
        {
            try
            {
                await Swis.InvokeAsync("Cirrus.PolicyReports", "UpdateReportStatus",
                    new object?[] { "Enabled", new[] { newId } }, ct);
                // An enabled report shows nothing until cached; start it for just this one
                // (an empty array would re-cache every report on the server).
                try
                {
                    await Swis.InvokeAsync("Cirrus.PolicyReports", "StartCaching",
                        new object?[] { new[] { newId } }, ct);
                    enabledNote = " · compliance caching started";
                }
                catch (Exception ex) when (ex is not OperationCanceledException)
                {
                    enabledNote = $" · start compliance caching manually ({ex.Message})";
                }
            }
            catch (Exception ex) when (ex is not OperationCanceledException)
            {
                enabledNote = $" · UpdateReportStatus(Enabled) failed ({ex.Message}); left Disabled";
            }
        }
        else
        {
            // Disabled for review: caching is skipped, as the import guidance says.
            enabledNote = opt.KeepEnabled
                ? " · not cached (the file's status is Disabled)"
                : " · not cached; enable it in the console (or with UpdateReportStatus) after review";
        }

        var rows = await Swis.QueryAsync(
            "SELECT PolicyReportID, Name, ReportStatus FROM Cirrus.PolicyReports WHERE PolicyReportID = @id",
            new Dictionary<string, object?> { ["id"] = newId }, ct);
        string? confirmed = null;
        var stored = "unknown";
        foreach (var row in rows.EnumerateArray())
        {
            confirmed = row.GetProperty("Name").GetString();
            if (row.TryGetProperty("ReportStatus", out var rs))
                stored = rs.ValueKind switch
                {
                    JsonValueKind.True => "Enabled",
                    JsonValueKind.False => "Disabled",
                    _ => rs.ToString(),
                };
        }
        if (confirmed is null)
            return new ImportOutcome(false,
                $"AddPolicyReport returned {newId} and GetPolicyReport matched the tree, but the " +
                "report row was not returned when reading it back (No Data Returned)");

        var chosen = opt.KeepEnabled ? $"{target} (kept from file)" : "Disabled (Porter default)";
        return new ImportOutcome(true,
            $"\"{confirmed}\" ({newId}) · {expected.Policies.Count} policies / {expected.RuleCount} rules " +
            $"verified with GetPolicyReport · status chosen {chosen}, stored {stored}{enabledNote}{statusNote}");
    }

    /// <summary>Policy and rule names in one report tree, in document order.</summary>
    internal sealed record ReportTree(List<(string Policy, List<string> Rules)> Policies)
    {
        public int RuleCount => Policies.Sum(p => p.Rules.Count);
    }

    /// <summary>What the file asks the server to store.</summary>
    internal static ReportTree ExpectedTree(XElement root)
        => new((root.Element("AssignedPolicies")?.Elements("Policy") ?? Enumerable.Empty<XElement>())
            .Select(p => (El(p, "PolicyName"),
                (p.Element("AssignedPolicyRules")?.Elements("PolicyRule") ?? Enumerable.Empty<XElement>())
                    .Select(r => El(r, "RuleName")).ToList()))
            .ToList());

    /// <summary>What GetPolicyReport(id, exportFlag=true) says the server stored. Null when
    /// the nested AssignedPolicies array is absent but the report lists policy ids — the
    /// tree was not returned, so it cannot be compared.</summary>
    internal static ReportTree? ReadBackTree(JsonElement report)
    {
        if (!report.TryGetProperty("AssignedPolicies", out var pols) || pols.ValueKind != JsonValueKind.Array)
        {
            var listed = report.TryGetProperty("AssignedPoliciesList", out var ids) &&
                         ids.ValueKind == JsonValueKind.Array && ids.GetArrayLength() > 0;
            return listed ? null : new ReportTree(new());
        }
        var list = new List<(string, List<string>)>();
        foreach (var p in pols.EnumerateArray())
        {
            var rules = new List<string>();
            if (p.TryGetProperty("AssignedPolicyRules", out var rs) && rs.ValueKind == JsonValueKind.Array)
                foreach (var r in rs.EnumerateArray()) rules.Add(S(r, "RuleName"));
            list.Add((S(p, "PolicyName"), rules));
        }
        return new ReportTree(list);
    }

    /// <summary>Differences between the file's tree and the stored one: policy count, rule
    /// count, and per-policy rule names. Empty means they match.</summary>
    internal static List<string> CompareTrees(ReportTree expected, ReportTree actual)
    {
        var diffs = new List<string>();
        if (expected.Policies.Count != actual.Policies.Count)
            diffs.Add($"policies: expected {expected.Policies.Count}, stored {actual.Policies.Count}");
        if (expected.RuleCount != actual.RuleCount)
            diffs.Add($"rules: expected {expected.RuleCount}, stored {actual.RuleCount}");

        var stored = actual.Policies.GroupBy(p => p.Policy, StringComparer.Ordinal)
            .ToDictionary(g => g.Key, g => g.ToList(), StringComparer.Ordinal);
        foreach (var (policy, rules) in expected.Policies)
        {
            if (!stored.TryGetValue(policy, out var candidates) || candidates.Count == 0)
            {
                diffs.Add($"policy \"{policy}\" missing");
                continue;
            }
            var match = candidates[0];
            candidates.RemoveAt(0);
            var missing = rules.Except(match.Rules, StringComparer.Ordinal).ToList();
            if (match.Rules.Count != rules.Count || missing.Count > 0)
                diffs.Add($"policy \"{policy}\": expected {rules.Count} rules, stored {match.Rules.Count}" +
                    (missing.Count > 0 ? $" (missing \"{string.Join("\", \"", missing.Take(3))}\"" +
                        (missing.Count > 3 ? ", …" : "") + ")" : ""));
        }
        return diffs;
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
