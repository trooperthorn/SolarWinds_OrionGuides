using System.Text;
using System.Text.Json;
using System.Xml.Linq;
using Porter.Core;

namespace Porter.Areas;

/// <summary>
/// SAM application templates — Orion.APM.ApplicationTemplate.
/// Export:  ExportTemplate(ApplicationTemplateID:int) → the .apmtemplate XML
///          (root ArrayOfApplicationTemplate in the 2007/08/APM namespace).
/// Import:  ImportTemplate(xml:string) → the new integer ApplicationTemplateID.
/// Collision identity is the template's UniqueId GUID (travels in the XML) with Name as
/// the human-facing secondary; ImportTemplate's own collision behavior is undocumented,
/// so Porter detects client-side and only ever skips. Verbs need node-management rights.
/// </summary>
public sealed class SamTemplatesProvider : AreaProvider
{
    public SamTemplatesProvider(SwisSession swis) : base(swis) { }

    public override string Key => "sam";
    public override string DisplayName => "SAM Templates";
    public override string FileExtension => ".apmtemplate";
    public override string FileDialogFilter => "SAM templates|*.apmtemplate";
    public override string ImportVia => "Orion.APM.ApplicationTemplate.ImportTemplate";
    public override string SecurityNotice =>
        "Script monitors export their ScriptBody verbatim — scripts can carry hard-coded " +
        "secrets, hostnames, and connection strings. Review templates before sharing them. " +
        "(Assigned credentials never travel; imported templates need credentials re-chosen.)";

    public override async Task<List<AreaItem>> ListAsync(CancellationToken ct)
    {
        var rows = await Swis.QueryAsync(
            "SELECT ApplicationTemplateID, Name, UniqueId, CustomApplicationType " +
            "FROM Orion.APM.ApplicationTemplate WHERE IsMockTemplate = FALSE ORDER BY Name",
            null, ct);
        var list = new List<AreaItem>();
        foreach (var row in rows.EnumerateArray())
        {
            var name = row.GetProperty("Name").GetString() ?? "(unnamed)";
            var uniqueId = row.GetProperty("UniqueId").GetString() ?? "";
            var detail = (row.TryGetProperty("CustomApplicationType", out var c)
                ? c.GetString() : null) ?? "";
            list.Add(new AreaItem(row.GetProperty("ApplicationTemplateID").GetInt32().ToString(),
                name, uniqueId, false, detail));
        }
        return list;
    }

    public override async Task<AreaExport> ExportAsync(AreaItem item, ExportOptions opt, CancellationToken ct)
    {
        var result = await Swis.InvokeAsync("Orion.APM.ApplicationTemplate", "ExportTemplate",
            new object?[] { int.Parse(item.Id) }, ct);
        var xml = result?.ValueKind == JsonValueKind.String ? result.Value.GetString() : null;
        if (string.IsNullOrWhiteSpace(xml))
            throw new InvalidOperationException($"ExportTemplate returned nothing for template {item.Id}");
        return new AreaExport(PackageWriter.Sanitize(item.Name) + FileExtension,
            Encoding.UTF8.GetBytes(xml));
    }

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

            if (doc.Root?.Name.LocalName != "ArrayOfApplicationTemplate")
            {
                v.Errors.Add($"root element is <{doc.Root?.Name.LocalName}> — a .apmtemplate " +
                    "file starts with <ArrayOfApplicationTemplate>");
                return v;
            }
            var templates = doc.Root.Elements()
                .Where(e => e.Name.LocalName == "ApplicationTemplate").ToList();
            if (templates.Count == 0)
            { v.Errors.Add("the file contains no <ApplicationTemplate> elements"); return v; }
            if (templates.Count > 1)
                v.Warnings.Add($"{templates.Count} templates in one file — the import verb " +
                    "returns a single id, so per-template results cannot be confirmed " +
                    "individually; exporting one template per file is the reliable shape");

            var scripts = 0;
            foreach (var t in templates)
            {
                var name = t.Elements().FirstOrDefault(e => e.Name.LocalName == "Name")?.Value?.Trim()
                    ?? System.IO.Path.GetFileNameWithoutExtension(fileName);
                var uniqueId = t.Descendants().FirstOrDefault(e => e.Name.LocalName == "UniqueId")?.Value?.Trim()
                    ?? "";
                v.Items.Add((uniqueId.Length > 0 ? uniqueId : name, name));
                scripts += t.Descendants().Count(e => e.Name.LocalName == "ScriptBody" &&
                    !string.IsNullOrWhiteSpace(e.Value));
            }
            if (scripts > 0)
                v.Warnings.Add($"{scripts} script bod{(scripts == 1 ? "y" : "ies")} travel " +
                    "verbatim — review for embedded secrets before importing");
            v.Detail = templates.Count == 1
                ? $"template \"{v.Items[0].Name}\"" : $"{templates.Count} templates";
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
            // Key is the UniqueId GUID when the file carried one, else the name — and a
            // plain name must never reach the Guid-typed column, or the query faults.
            var rows = await Swis.QueryAsync(
                Guid.TryParse(key, out _)
                    ? "SELECT Name, UniqueId FROM Orion.APM.ApplicationTemplate WHERE UniqueId = @k"
                    : "SELECT Name, UniqueId FROM Orion.APM.ApplicationTemplate WHERE Name = @k",
                new Dictionary<string, object?> { ["k"] = key }, ct);
            foreach (var row in rows.EnumerateArray())
                map[key] = row.GetProperty("Name").GetString() ?? key;
        }
        return map;
    }

    public override async Task<ImportOutcome> ImportAsync(string text, IReadOnlyList<string> verifyKeys,
        ImportOptions opt, CancellationToken ct)
    {
        var result = await Swis.InvokeAsync("Orion.APM.ApplicationTemplate", "ImportTemplate",
            new object?[] { text }, ct);
        if (result is not { ValueKind: JsonValueKind.Number } idEl)
            return new ImportOutcome(false, "ImportTemplate did not return the new template id");
        var newId = idEl.GetInt32();

        var rows = await Swis.QueryAsync(
            "SELECT ApplicationTemplateID, Name, UniqueId FROM Orion.APM.ApplicationTemplate " +
            "WHERE ApplicationTemplateID = @id",
            new Dictionary<string, object?> { ["id"] = newId }, ct);
        foreach (var row in rows.EnumerateArray())
            return new ImportOutcome(true,
                $"\"{row.GetProperty("Name").GetString()}\" (id {newId})");
        return new ImportOutcome(false,
            $"ImportTemplate returned id {newId} but no data returned when reading it back (No Data Returned)");
    }
}
