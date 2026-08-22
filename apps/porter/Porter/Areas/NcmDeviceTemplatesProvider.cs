using System.Text;
using System.Text.Json;
using System.Xml.Linq;
using Porter.Core;

namespace Porter.Areas;

/// <summary>
/// NCM device templates — Cli.DeviceTemplates. No verbs at all: the TemplateXml column
/// (the whole .ConfigMgmtCommands document) is the export, and plain SWIS CRUD Create is
/// the import. IsDefault rows are built-ins and server-side read-only — they are listed
/// as system items and never written. Collision identity is TemplateName (the ID is the
/// only schema key and it is server-assigned; SystemOID is deliberately non-unique so
/// vendor-wide and model-specific templates can coexist).
/// </summary>
public sealed class NcmDeviceTemplatesProvider : AreaProvider
{
    public NcmDeviceTemplatesProvider(SwisSession swis) : base(swis) { }

    public override string Key => "ncmdevice";
    public override string DisplayName => "NCM Device Templates";
    public override string FileExtension => ".ConfigMgmtCommands";
    public override string FileDialogFilter => "NCM device templates|*.ConfigMgmtCommands";
    public override string ImportVia => "SWIS CRUD Create → Cli.DeviceTemplates";

    public override async Task<List<AreaItem>> ListAsync(CancellationToken ct)
    {
        var rows = await Swis.QueryAsync(
            "SELECT ID, TemplateName, SystemOID, IsDefault FROM Cli.DeviceTemplates " +
            "ORDER BY TemplateName", null, ct);
        var list = new List<AreaItem>();
        foreach (var row in rows.EnumerateArray())
        {
            var name = row.GetProperty("TemplateName").GetString() ?? "(unnamed)";
            var oid = row.GetProperty("SystemOID").GetString() ?? "";
            var isDefault = row.TryGetProperty("IsDefault", out var d) &&
                (d.ValueKind == JsonValueKind.True ||
                 (d.ValueKind == JsonValueKind.String && d.GetString() == "True"));
            list.Add(new AreaItem(row.GetProperty("ID").GetInt32().ToString(),
                name, name, isDefault, oid));
        }
        return list;
    }

    public override async Task<AreaExport> ExportAsync(AreaItem item, ExportOptions opt, CancellationToken ct)
    {
        var rows = await Swis.QueryAsync(
            "SELECT TemplateXml FROM Cli.DeviceTemplates WHERE ID = @id",
            new Dictionary<string, object?> { ["id"] = int.Parse(item.Id) }, ct);
        foreach (var row in rows.EnumerateArray())
        {
            var xml = row.GetProperty("TemplateXml").GetString();
            if (!string.IsNullOrWhiteSpace(xml))
            {
                // Console naming convention: underscored device name + SystemOID.
                var file = PackageWriter.Sanitize(item.Name).Replace(' ', '_')
                    + item.Detail + FileExtension;
                return new AreaExport(file, Encoding.UTF8.GetBytes(xml));
            }
        }
        throw new InvalidOperationException($"template {item.Id} has no TemplateXml on the server");
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

            if (doc.Root?.Name.LocalName != "Configuration-Management")
            {
                v.Errors.Add($"root element is <{doc.Root?.Name.LocalName}> — a device " +
                    "template starts with <Configuration-Management>");
                return v;
            }
            var device = doc.Root.Attribute("Device")?.Value?.Trim() ?? "";
            var oid = doc.Root.Attribute("SystemOID")?.Value?.Trim() ?? "";
            if (device.Length == 0)
            { v.Errors.Add("the root element has no Device attribute — no template name"); return v; }
            var commands = doc.Root.Elements("Commands").Elements("Command").ToList();
            if (commands.Count == 0)
                v.Warnings.Add("the template defines no <Command> entries");
            if (oid.Length == 0)
                v.Warnings.Add("no SystemOID attribute — auto-detection by OID cannot match this template");

            v.Items.Add((device, device));
            v.Detail = $"\"{device}\" · OID {(oid.Length > 0 ? oid : "(none)")} · {commands.Count} commands";
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
                "SELECT TemplateName, IsDefault FROM Cli.DeviceTemplates WHERE TemplateName = @n",
                new Dictionary<string, object?> { ["n"] = key }, ct);
            foreach (var row in rows.EnumerateArray())
            {
                var isDefault = row.TryGetProperty("IsDefault", out var d) &&
                    (d.ValueKind == JsonValueKind.True ||
                     (d.ValueKind == JsonValueKind.String && d.GetString() == "True"));
                map[key] = (row.GetProperty("TemplateName").GetString() ?? key)
                    + (isDefault ? " (built-in, read-only)" : "");
            }
        }
        return map;
    }

    public override async Task<ImportOutcome> ImportAsync(string text, IReadOnlyList<string> verifyKeys,
        ImportOptions opt, CancellationToken ct)
    {
        var doc = XDocument.Parse(text);
        var root = doc.Root!;
        var device = root.Attribute("Device")?.Value?.Trim()
            ?? throw new InvalidOperationException("the template has no Device attribute");
        var oid = root.Attribute("SystemOID")?.Value?.Trim() ?? "";
        var regex = root.Attribute("SystemDescriptionRegex")?.Value ?? "";
        // The XML attribute is a string; the entity column is an int (0 = by SystemOID,
        // 1 = by system description). Keep column and document in agreement.
        var autoDetect = root.Attribute("AutoDetectType")?.Value == "BySystemDescription" ? 1 : 0;

        var uri = await Swis.CreateAsync("Cli.DeviceTemplates", new
        {
            TemplateName = device,
            SystemOID = oid,
            SystemDescriptionRegex = regex,
            AutoDetectType = autoDetect,
            // Installation state that never travelled in the file: importing with
            // auto-detect ON could silently re-route existing nodes to this template.
            UseForAutoDetect = false,
            TemplateXml = text,
            Comments = "",
            Author = Swis.Username ?? "",
        }, ct);

        var rows = await Swis.QueryAsync(
            "SELECT ID, TemplateName, SystemOID FROM Cli.DeviceTemplates WHERE TemplateName = @n",
            new Dictionary<string, object?> { ["n"] = device }, ct);
        foreach (var row in rows.EnumerateArray())
            return new ImportOutcome(true,
                $"\"{row.GetProperty("TemplateName").GetString()}\" (id {row.GetProperty("ID").GetInt32()}) — " +
                "auto-detect left OFF; review the template, then enable Use for Auto Detect in the console");
        return new ImportOutcome(false,
            $"Create returned {uri} but the template was not found by name afterwards");
    }
}
