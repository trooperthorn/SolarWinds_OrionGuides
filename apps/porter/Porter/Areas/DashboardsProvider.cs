using System.IO;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Porter.Core;

namespace Porter.Areas;

/// <summary>
/// Modern Dashboards — the Phase-1 verification area, now behind the provider contract.
/// Export:  Orion.Dashboards.Instances.Export(dashboardId) → the JSON definition.
/// Import:  Orion.Dashboards.Instances.Import(definition) → void, so verification
///          re-queries the file's dashboard unique_keys and reports the new ids.
/// Copy:    client-side structural rewrite (DashboardsArea.AsCopy) that avoids every key
///          already on the target.
/// Collisions: a dashboard key on the target, or any of the file's widget keys on the
///          target. SolarWinds documents that an import with an existing key overwrites
///          the original, so a widget key shared with another dashboard would silently
///          change that dashboard: the file is skipped unless imported as a copy.
/// </summary>
public sealed class DashboardsProvider : AreaProvider
{
    private readonly DashboardsArea _area;

    public DashboardsProvider(SwisSession swis) : base(swis) => _area = new DashboardsArea(swis);

    public override string Key => "dashboards";
    public override string DisplayName => "Modern Dashboards";
    public override string FileExtension => ".json";
    public override string FileDialogFilter => "Dashboard files|*.json";
    public override string ImportVia => "Orion.Dashboards.Instances.Import";
    public override CopyMode CopyMode => CopyMode.ClientRewrite;

    public override async Task<List<AreaItem>> ListAsync(CancellationToken ct)
        => (await _area.ListAsync(ct))
            .Select(d => new AreaItem(d.Id.ToString(), d.Name, d.UniqueKey, d.IsSystem))
            .ToList();

    public override async Task<AreaExport> ExportAsync(AreaItem item, ExportOptions opt, CancellationToken ct)
    {
        var definition = await _area.ExportAsync(int.Parse(item.Id), ct);
        return new AreaExport(PackageWriter.Sanitize(item.Name) + FileExtension,
            Encoding.UTF8.GetBytes(definition));
    }

    public override AreaValidation Validate(string fileName, string text)
    {
        var d = DashboardValidator.Validate(text);
        var v = new AreaValidation { Detail = $"{d.WidgetCount} widgets · {d.QueryCount} queries" };
        v.Errors.AddRange(d.Errors);
        v.Warnings.AddRange(d.Warnings);
        v.Items.AddRange(d.Dashboards);
        return v;
    }

    public override async Task<Dictionary<string, string>> FindCollisionsAsync(
        IReadOnlyCollection<string> keys, CancellationToken ct)
    {
        var hits = await _area.FindCollisionsAsync(keys, ct);
        var map = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var (key, name) in hits) map[key] = name;
        return map;
    }

    /// <summary>
    /// Dashboard-key collisions plus widget-key collisions. A same-key import is an update
    /// that overwrites the existing object (docs/webui/modern-dashboard-authoring.md,
    /// "Duplicating a dashboard onto the same server"; identity audit, "Import behavior"),
    /// so a widget key already on the target — normally placed by a different dashboard —
    /// is a collision, not a dry-run footnote. A target that cannot be checked fails the
    /// file rather than importing it unchecked.
    /// </summary>
    public override async Task<Dictionary<string, string>> FindCollisionsAsync(string text,
        IReadOnlyCollection<string> keys, CancellationToken ct)
    {
        var map = await FindCollisionsAsync(keys, ct);
        var fileWidgetKeys = WidgetKeys(text);
        if (fileWidgetKeys.Count == 0) return map;

        List<string> targetKeys;
        try { targetKeys = await _area.TargetWidgetKeysAsync(ct); }
        catch (SwisException ex)
        {
            throw new InvalidOperationException(
                $"widget keys could not be checked against the target, so the file was not imported: {ex.Message}");
        }
        var matches = DashboardsArea.MatchKeys(fileWidgetKeys, targetKeys);
        if (matches.Count == 0) return map;

        Dictionary<string, List<string>> consumers;
        try { consumers = await _area.WidgetConsumersAsync(matches.Select(m => m.TargetKey).ToList(), ct); }
        catch (SwisException) { consumers = new(DashboardKeyComparer.Instance); }
        foreach (var (fileKey, targetKey) in matches)
        {
            var where = consumers.TryGetValue(targetKey, out var names) && names.Count > 0
                ? $"placed on {string.Join(", ", names.Take(3).Select(n => $"\"{n}\""))}" +
                  (names.Count > 3 ? $" and {names.Count - 3} more" : "")
                : "on no dashboard this account can see";
            map[fileKey] = $"widget unique_key already on the target ({where}) — importing would " +
                "overwrite that widget; import as a copy for an independent one";
        }
        return map;
    }

    /// <summary>The copy transform, avoiding every dashboard and widget key on the target.</summary>
    public override async Task<CopyRewrite> AsCopyAsync(string text, CancellationToken ct)
    {
        var avoid = await _area.TargetKeysAsync(ct);
        var (copyText, newNames, newKeys, notes) = DashboardsArea.AsCopy(text, avoid);
        return new CopyRewrite(copyText, newNames, newKeys, notes);
    }

    /// <summary>
    /// Dry-run plan: which dashboards the file would create, and any widget unique_keys
    /// that already exist on the target. Those widget keys are collisions too (see
    /// <see cref="FindCollisionsAsync(string, IReadOnlyCollection{string}, CancellationToken)"/>),
    /// so the simulation has already marked the file NO-GO unless it imports as a copy;
    /// this list names them. The widget query targets Orion.Dashboards.Widgets.UniqueKey
    /// (inherited from Orion.Dashboards.Entity in the 2026.2 schema, checked with
    /// tools/schema_query.py); here it is wrapped in a SwisException catch so a schema
    /// difference degrades the narration to "not checked".
    /// </summary>
    public override async Task<List<string>> PlanAsync(string text, CancellationToken ct)
    {
        var lines = new List<string>();
        var validation = DashboardValidator.Validate(text);
        foreach (var (key, name) in validation.Dashboards)
            lines.Add($"would create dashboard \"{name}\" (key {key})");

        var widgetKeys = WidgetKeys(text);
        if (widgetKeys.Count == 0) return lines;
        try
        {
            var hits = DashboardsArea.MatchKeys(widgetKeys, await _area.TargetWidgetKeysAsync(ct))
                .Select(m => m.FileKey).ToList();
            foreach (var key in hits.Take(20))
                lines.Add($"WARNING: widget {key} (already on target)");
            if (hits.Count > 20)
                lines.Add($"WARNING: … and {hits.Count - 20} more widget key(s) already on target");
            if (hits.Count == 0)
                lines.Add($"{widgetKeys.Count} widget definition(s), none already on target");
        }
        catch (SwisException ex)
        {
            lines.Add($"widget keys not checked against the target: {ex.Message}");
        }
        return lines;
    }

    internal static List<string> WidgetKeys(string text)
    {
        var keys = new List<string>();
        try
        {
            if (JsonNode.Parse(text) is JsonObject root && root["widgets"] is JsonArray widgets)
                foreach (var w in widgets.OfType<JsonObject>())
                    if (w["unique_key"] is JsonValue v && v.TryGetValue<string>(out var k) &&
                        !string.IsNullOrEmpty(k))
                        keys.Add(k);
        }
        catch (JsonException) { /* Validate already reported the file as unreadable */ }
        return keys.Distinct(DashboardKeyComparer.Instance).ToList();
    }

    public override CopyRewrite AsCopy(string text)
    {
        var (copyText, newNames, newKeys, notes) = DashboardsArea.AsCopy(text);
        return new CopyRewrite(copyText, newNames, newKeys, notes);
    }

    public override async Task<ImportOutcome> ImportAsync(string text, IReadOnlyList<string> verifyKeys,
        ImportOptions opt, CancellationToken ct)
    {
        await _area.ImportAsync(text, ct);
        var found = await _area.VerifyAsync(verifyKeys, ct);
        var expected = verifyKeys.Count(k => k.Length > 0);
        if (found.Count >= expected && found.Count > 0)
            return new ImportOutcome(true,
                string.Join(", ", found.Select(f => $"\"{f.Name}\" (id {f.Id})")));
        return new ImportOutcome(false,
            "import call succeeded but no data returned when reading it back (No Data Returned)");
    }
}
