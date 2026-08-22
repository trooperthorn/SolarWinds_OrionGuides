using System.Text;
using System.Text.Json;
using System.Xml.Linq;
using Porter.Core;

namespace Porter.Areas;

/// <summary>
/// Reports — Orion.Report. No export verb exists: the Definition column IS the export
/// (the same XML the console's export button writes). Import is CreateReport with nine
/// positional parameters — limitationCategory sits THIRD, before category, and isFavorite
/// is a string. CreateReport is create-only; collisions are matched by Name and skipped
/// (in-place update via UpdateReport is a later, deliberate feature).
/// </summary>
public sealed class ReportsProvider : AreaProvider
{
    public ReportsProvider(SwisSession swis) : base(swis) { }

    public override string Key => "reports";
    public override string DisplayName => "Reports";
    public override string FileExtension => ".xml";
    public override string FileDialogFilter => "Report definitions|*.xml";
    public override string ImportVia => "Orion.Report.CreateReport";

    public override async Task<List<AreaItem>> ListAsync(CancellationToken ct)
    {
        var rows = await Swis.QueryAsync(
            "SELECT ReportID, Name, Title, Category, LimitationCategory, Owner " +
            "FROM Orion.Report ORDER BY Name", null, ct);
        var list = new List<AreaItem>();
        foreach (var row in rows.EnumerateArray())
        {
            var name = row.GetProperty("Name").GetString() ?? "(unnamed)";
            var detail = (row.TryGetProperty("Category", out var c) ? c.GetString() : null) ?? "";
            list.Add(new AreaItem(row.GetProperty("ReportID").GetInt32().ToString(),
                name, name, false, detail));
        }
        return list;
    }

    public override async Task<AreaExport> ExportAsync(AreaItem item, ExportOptions opt, CancellationToken ct)
    {
        var rows = await Swis.QueryAsync(
            "SELECT Definition FROM Orion.Report WHERE ReportID = @id",
            new Dictionary<string, object?> { ["id"] = int.Parse(item.Id) }, ct);
        foreach (var row in rows.EnumerateArray())
        {
            var definition = row.GetProperty("Definition").GetString();
            if (!string.IsNullOrWhiteSpace(definition))
                return new AreaExport(PackageWriter.Sanitize(item.Name) + FileExtension,
                    Encoding.UTF8.GetBytes(definition));
        }
        throw new InvalidOperationException($"report {item.Id} has no Definition on the server");
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

            var root = doc.Root?.Name.LocalName ?? "";
            if (!root.Equals("Report", StringComparison.OrdinalIgnoreCase))
                v.Warnings.Add($"root element is <{root}> — expected <Report>; the server makes the final call");

            var name = Element(doc, "Name") ?? System.IO.Path.GetFileNameWithoutExtension(fileName);
            v.Items.Add((name, name));
            v.Detail = $"report \"{name}\"" +
                (Element(doc, "Category") is string cat && cat.Length > 0 ? $" · {cat}" : "");
        }
        catch (Exception ex)
        {
            v.Errors.Add($"file could not be analysed: {ex.Message}");
        }
        return v;
    }

    /// <summary>First direct child of the root with the given local name.</summary>
    private static string? Element(XDocument doc, string localName)
        => doc.Root?.Elements().FirstOrDefault(e => e.Name.LocalName == localName)?.Value?.Trim();

    public override async Task<Dictionary<string, string>> FindCollisionsAsync(
        IReadOnlyCollection<string> keys, CancellationToken ct)
    {
        var map = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var key in keys.Where(k => k.Length > 0))
        {
            var rows = await Swis.QueryAsync(
                "SELECT Name FROM Orion.Report WHERE Name = @n",
                new Dictionary<string, object?> { ["n"] = key }, ct);
            foreach (var row in rows.EnumerateArray())
                map[key] = row.GetProperty("Name").GetString() ?? key;
        }
        return map;
    }

    public override async Task<ImportOutcome> ImportAsync(string text, IReadOnlyList<string> verifyKeys,
        ImportOptions opt, CancellationToken ct)
    {
        var doc = XDocument.Parse(text);
        var name = Element(doc, "Name") ?? (verifyKeys.Count > 0 ? verifyKeys[0] : "Imported report");
        var description = Element(doc, "Description") ?? "";
        var limitationCategory = Element(doc, "LimitationCategory") ?? "";
        var category = Element(doc, "Category") ?? "";
        // Title and SubTitle are not top-level: the definition keeps them inside <Header>
        // (DataContract output, foreign namespace prefixes — match by local name).
        var header = doc.Root?.Elements().FirstOrDefault(e => e.Name.LocalName == "Header");
        var title = header?.Descendants().FirstOrDefault(e => e.Name.LocalName == "Title")?.Value;
        if (string.IsNullOrWhiteSpace(title)) title = name;
        var subtitle = header?.Descendants().FirstOrDefault(e => e.Name.LocalName == "SubTitle")?.Value ?? "";

        // Exact CreateReport order from the 2026.2 contract: limitationCategory is THIRD,
        // before category, and isFavorite travels as the string "false".
        var result = await Swis.InvokeAsync("Orion.Report", "CreateReport",
            new object?[] { name, description, limitationCategory, category, title, subtitle,
                text, "false", Swis.Username ?? "" }, ct);
        if (result is not { ValueKind: JsonValueKind.Number } idEl)
            return new ImportOutcome(false, "CreateReport did not return the new ReportID");
        var newId = idEl.GetInt32();

        var rows = await Swis.QueryAsync(
            "SELECT ReportID, Name, Title FROM Orion.Report WHERE ReportID = @id",
            new Dictionary<string, object?> { ["id"] = newId }, ct);
        foreach (var row in rows.EnumerateArray())
            return new ImportOutcome(true,
                $"\"{row.GetProperty("Name").GetString()}\" (id {newId})");
        return new ImportOutcome(false,
            $"CreateReport returned id {newId} but the row was not found afterwards");
    }
}
