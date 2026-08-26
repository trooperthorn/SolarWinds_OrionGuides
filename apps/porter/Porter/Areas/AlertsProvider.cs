using System.Text;
using System.Text.Json;
using System.Xml.Linq;
using Porter.Core;

namespace Porter.Areas;

/// <summary>
/// Alerts — Orion.AlertConfigurations.
/// Export:  Export(alertId, stripSensitiveData, protectionPassword) → alert-definition XML.
/// Import:  Import(alertXml, stripSensitiveInformation, protectionPassword)
///          → AlertImportResult { AlertId, Name, MigrationMessage,
///            IncorrectPasswordForDecryptSensitiveData, AlertDefinitionIsNotSupported }.
/// Import always CREATES (fresh AlertID, no overwrite), so the only collision policy is
/// skip-by-name. Both verbs require the manageAlerts right.
/// </summary>
public sealed class AlertsProvider : AreaProvider
{
    public AlertsProvider(SwisSession swis) : base(swis) { }

    public override string Key => "alerts";
    public override string DisplayName => "Alerts";
    public override string FileExtension => ".xml";
    public override string FileDialogFilter => "Alert definitions|*.xml";
    public override string ImportVia => "Orion.AlertConfigurations.Import";
    public override bool OffersStripSensitive => true;
    public override string SecurityNotice =>
        "Alert definitions can embed account names, passwords, and token information inside " +
        "their action configurations. Leave \"Remove sensitive data\" ticked unless you " +
        "specifically need them to travel — and protect any export that carries them.";

    public override async Task<List<AreaItem>> ListAsync(CancellationToken ct)
    {
        var rows = await Swis.QueryAsync(
            "SELECT AlertID, Name, Enabled, Canned, Category, ObjectType " +
            "FROM Orion.AlertConfigurations ORDER BY Name", null, ct);
        var list = new List<AreaItem>();
        foreach (var row in rows.EnumerateArray())
        {
            var name = row.GetProperty("Name").GetString() ?? "(unnamed)";
            var canned = row.TryGetProperty("Canned", out var c) && c.ValueKind == JsonValueKind.True;
            var detail = (row.TryGetProperty("ObjectType", out var o) ? o.GetString() : null) ?? "";
            list.Add(new AreaItem(row.GetProperty("AlertID").GetInt32().ToString(),
                name, name, canned, detail));
        }
        return list;
    }

    public override async Task<AreaExport> ExportAsync(AreaItem item, ExportOptions opt, CancellationToken ct)
    {
        var result = await Swis.InvokeAsync("Orion.AlertConfigurations", "Export",
            new object?[] { int.Parse(item.Id), opt.StripSensitive, null }, ct);
        var xml = result?.ValueKind == JsonValueKind.String ? result.Value.GetString() : null;
        if (string.IsNullOrWhiteSpace(xml))
            throw new InvalidOperationException($"Export returned no definition for alert {item.Id}");
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

            var root = doc.Root?.Name.LocalName ?? "";
            if (!root.Contains("Alert", StringComparison.OrdinalIgnoreCase))
                v.Warnings.Add($"root element is <{root}> — expected an alert definition; " +
                    "the server makes the final call");

            // The definition's own name, wherever the schema put it — first <Name> wins.
            var name = doc.Descendants().FirstOrDefault(e => e.Name.LocalName == "Name")?.Value?.Trim();
            if (string.IsNullOrEmpty(name))
            {
                name = System.IO.Path.GetFileNameWithoutExtension(fileName);
                v.Warnings.Add("no <Name> element found — using the file name for collision checks");
            }
            v.Items.Add((name, name));
            v.Detail = $"alert \"{name}\"";
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
                "SELECT Name FROM Orion.AlertConfigurations WHERE Name = @n",
                new Dictionary<string, object?> { ["n"] = key }, ct);
            foreach (var row in rows.EnumerateArray())
                map[key] = row.GetProperty("Name").GetString() ?? key;
        }
        return map;
    }

    public override async Task<ImportOutcome> ImportAsync(string text, IReadOnlyList<string> verifyKeys,
        ImportOptions opt, CancellationToken ct)
    {
        var result = await Swis.InvokeAsync("Orion.AlertConfigurations", "Import",
            new object?[] { text, false, null }, ct);
        if (result is not { ValueKind: JsonValueKind.Object } r)
            return new ImportOutcome(false, "the Import verb returned no result object");

        var alertId = r.TryGetProperty("AlertId", out var idEl) && idEl.ValueKind == JsonValueKind.Number
            ? idEl.GetInt32() : 0;
        var name = r.TryGetProperty("Name", out var nEl) ? nEl.GetString() : null;
        var migration = r.TryGetProperty("MigrationMessage", out var mEl) ? mEl.GetString() : null;
        var badPassword = r.TryGetProperty("IncorrectPasswordForDecryptSensitiveData", out var p) &&
            p.ValueKind == JsonValueKind.True;
        var unsupported = r.TryGetProperty("AlertDefinitionIsNotSupported", out var u) &&
            u.ValueKind == JsonValueKind.True;

        if (unsupported)
            throw new InvalidOperationException("the target server does not support this alert definition");
        if (badPassword)
            throw new InvalidOperationException(
                "the definition carries protected sensitive data and the password did not match");
        if (alertId <= 0)
            return new ImportOutcome(false, "the server did not return a new AlertId");
        if (!string.IsNullOrWhiteSpace(migration))
            return new ImportOutcome(false,
                $"created as \"{name}\" (id {alertId}) but partial — {migration}");

        var rows = await Swis.QueryAsync(
            "SELECT AlertID, Name, Enabled FROM Orion.AlertConfigurations WHERE AlertID = @id",
            new Dictionary<string, object?> { ["id"] = alertId }, ct);
        foreach (var row in rows.EnumerateArray())
            return new ImportOutcome(true,
                $"\"{row.GetProperty("Name").GetString()}\" (id {alertId})");
        return new ImportOutcome(false,
            $"the server returned AlertId {alertId} but no data returned when reading it back (No Data Returned)");
    }
}
