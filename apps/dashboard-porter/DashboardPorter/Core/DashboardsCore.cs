using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace DashboardPorter.Core;

public sealed record DashboardListRow(int Id, string Name, string UniqueKey, bool IsSystem);

/// <summary>
/// Modern Dashboards, the only area this tool moves.
/// Export:  Orion.Dashboards.Instances.Export(dashboardId) → the JSON definition.
/// Import:  Orion.Dashboards.Instances.Import(definition) → void, so Porter verifies by
///          re-querying the file's dashboard unique_keys afterwards.
/// Ported from apps/porter/Porter/Areas/DashboardsArea.cs.
/// </summary>
public sealed class DashboardsCore
{
    public const string ImportVia = "Orion.Dashboards.Instances.Import";

    private readonly SwisSession _swis;

    public DashboardsCore(SwisSession swis) => _swis = swis;

    public async Task<List<DashboardListRow>> ListAsync(CancellationToken ct = default)
    {
        const string withSystem =
            "SELECT DashboardID, DisplayName, UniqueKey, IsSystem " +
            "FROM Orion.Dashboards.Instances ORDER BY DisplayName";
        const string withoutSystem =
            "SELECT DashboardID, DisplayName, UniqueKey " +
            "FROM Orion.Dashboards.Instances ORDER BY DisplayName";

        JsonElement rows;
        var haveSystem = true;
        try { rows = await _swis.QueryAsync(withSystem, null, ct); }
        catch (SwisException)
        {
            // Older schema without the IsSystem member — degrade rather than fail.
            rows = await _swis.QueryAsync(withoutSystem, null, ct);
            haveSystem = false;
        }

        var list = new List<DashboardListRow>();
        foreach (var row in rows.EnumerateArray())
        {
            list.Add(new DashboardListRow(
                row.GetProperty("DashboardID").GetInt32(),
                row.GetProperty("DisplayName").GetString() ?? "(unnamed)",
                row.GetProperty("UniqueKey").GetString() ?? "",
                haveSystem && row.TryGetProperty("IsSystem", out var s) &&
                    s.ValueKind == JsonValueKind.True));
        }
        return list;
    }

    public async Task<string> ExportAsync(int dashboardId, CancellationToken ct = default)
    {
        var result = await _swis.InvokeAsync("Orion.Dashboards.Instances", "Export",
            new object?[] { dashboardId }, ct);
        var definition = result?.ValueKind == JsonValueKind.String ? result.Value.GetString() : null;
        if (string.IsNullOrWhiteSpace(definition))
            throw new InvalidOperationException($"Export returned no definition for dashboard {dashboardId}");
        return definition;
    }

    /// <summary>Which of the file's dashboard unique_keys already exist on the target.</summary>
    public async Task<List<(string Key, string ExistingName)>> FindCollisionsAsync(
        IEnumerable<string> keys, CancellationToken ct = default)
    {
        var hits = new List<(string, string)>();
        foreach (var key in keys.Where(k => !string.IsNullOrEmpty(k)))
        {
            var rows = await _swis.QueryAsync(
                "SELECT DisplayName FROM Orion.Dashboards.Instances WHERE UniqueKey = @k",
                new Dictionary<string, object?> { ["k"] = key }, ct);
            foreach (var row in rows.EnumerateArray())
                hits.Add((key, row.GetProperty("DisplayName").GetString() ?? "(unnamed)"));
        }
        return hits;
    }

    public async Task ImportAsync(string definition, CancellationToken ct = default)
        => await _swis.InvokeAsync("Orion.Dashboards.Instances", "Import",
            new object?[] { definition }, ct);

    /// <summary>Import returns void, so confirm arrival by unique_key and return the new ids.</summary>
    public async Task<List<(string Key, int Id, string Name)>> VerifyAsync(
        IEnumerable<string> keys, CancellationToken ct = default)
    {
        var found = new List<(string, int, string)>();
        foreach (var key in keys.Where(k => !string.IsNullOrEmpty(k)))
        {
            var rows = await _swis.QueryAsync(
                "SELECT DashboardID, DisplayName FROM Orion.Dashboards.Instances WHERE UniqueKey = @k",
                new Dictionary<string, object?> { ["k"] = key }, ct);
            foreach (var row in rows.EnumerateArray())
                found.Add((key,
                    row.GetProperty("DashboardID").GetInt32(),
                    row.GetProperty("DisplayName").GetString() ?? ""));
        }
        return found;
    }

    /// <summary>
    /// The "import as copy" transform, done structurally rather than textually. Only the
    /// identity fields the format defines are regenerated — dashboards[].unique_key and
    /// widgets[].unique_key, with placements remapped through the same old→new map — so
    /// GUIDs inside embedded SWQL and URLs (which reference server-side objects) are never
    /// touched. Each dashboard is renamed "… (Copy)", and where a widget's SWQL addresses a
    /// dashboard by its original name (the documented self-referencing link pattern), the
    /// quoted literal is rewritten to the new name so the copy points at itself. Returns
    /// the new names and keys plus notes for the run report.
    /// </summary>
    public static (string Text, List<string> NewNames, List<string> NewKeys, List<string> Notes)
        AsCopy(string definition)
    {
        var root = JsonNode.Parse(definition) as JsonObject
                   ?? throw new InvalidDataException("definition is not a JSON object");
        var map = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        string Fresh(string old)
        {
            if (!map.TryGetValue(old, out var fresh))
            {
                fresh = Guid.NewGuid().ToString("D");
                map[old] = fresh;
            }
            return fresh;
        }

        var newNames = new List<string>();
        var newKeys = new List<string>();
        var notes = new List<string>();
        var renames = new List<(string OldName, string NewName)>();

        // Widget definition keys first, so the map is complete before placements remap.
        foreach (var w in (root["widgets"] as JsonArray ?? new JsonArray()).OfType<JsonObject>())
            if (w["unique_key"]?.GetValue<string>() is string wk && wk.Length > 0)
                w["unique_key"] = Fresh(wk);

        foreach (var d in (root["dashboards"] as JsonArray ?? new JsonArray()).OfType<JsonObject>())
        {
            var oldName = d["name"]?.GetValue<string>() ?? "Dashboard";
            var newName = oldName + " (Copy)";
            d["name"] = newName;
            newNames.Add(newName);
            renames.Add((oldName, newName));

            if (d["unique_key"]?.GetValue<string>() is string dk && dk.Length > 0)
            {
                var fresh = Fresh(dk);
                d["unique_key"] = fresh;
                newKeys.Add(fresh);
            }
            foreach (var placement in (d["widgets"] as JsonArray ?? new JsonArray()).OfType<JsonObject>())
                if (placement["unique_key"]?.GetValue<string>() is string pk &&
                    map.TryGetValue(pk, out var mapped))
                    placement["unique_key"] = mapped;
        }

        // Self-referencing SWQL: rewrite exact quoted name literals so the copy's internal
        // links target the copy rather than the original that is still on the server.
        var rewrites = 0;
        RewriteSwqlNames(root, renames, notes, ref rewrites);
        if (rewrites > 0)
            notes.Add($"rewrote {rewrites} self-referencing dashboard-name literal(s) in embedded SWQL to the copy's name");

        return (root.ToJsonString(new JsonSerializerOptions { WriteIndented = false }),
                newNames, newKeys, notes);
    }

    private static void RewriteSwqlNames(JsonNode? node,
        List<(string OldName, string NewName)> renames, List<string> notes, ref int rewrites)
    {
        switch (node)
        {
            case JsonObject obj:
                foreach (var key in obj.Select(kv => kv.Key).ToList())
                {
                    if (key == "swql" && obj[key] is JsonValue val &&
                        val.TryGetValue<string>(out var swql) && swql is not null)
                    {
                        var updated = swql;
                        foreach (var (oldName, newName) in renames)
                        {
                            if (oldName.Contains('\'')) continue;   // apostrophes: leave, warn below
                            var literal = "'" + oldName + "'";
                            if (updated.Contains(literal, StringComparison.Ordinal))
                            {
                                updated = updated.Replace(literal, "'" + newName + "'", StringComparison.Ordinal);
                                rewrites++;
                            }
                            else if (updated.Contains(oldName, StringComparison.Ordinal))
                            {
                                notes.Add($"a query mentions \"{oldName}\" outside a quoted literal — left unchanged, review the copy's widget");
                            }
                        }
                        if (!ReferenceEquals(updated, swql) && updated != swql)
                            obj[key] = updated;
                    }
                    else
                    {
                        RewriteSwqlNames(obj[key], renames, notes, ref rewrites);
                    }
                }
                break;
            case JsonArray arr:
                foreach (var item in arr) RewriteSwqlNames(item, renames, notes, ref rewrites);
                break;
        }
    }
}

public sealed class DashboardValidation
{
    public List<string> Errors { get; } = new();
    public List<string> Warnings { get; } = new();
    public List<(string Key, string Name)> Dashboards { get; } = new();
    public int WidgetCount { get; set; }
    public int QueryCount { get; set; }
    public bool Ok => Errors.Count == 0;

    public string Summary =>
        Errors.Count > 0 ? Errors[0]
        : Warnings.Count > 0 ? $"{WidgetCount} widgets · {QueryCount} queries · {Warnings[0]}"
        : $"{WidgetCount} widgets · {QueryCount} queries · all checks pass";
}

/// <summary>
/// The Modern Dashboard file invariants, ported from the SolarWinds_OrionGuides
/// documentation repository (docs/webui/modern-dashboards.md): the envelope, placements
/// resolving to definitions, duplicate widget unique_keys, and the SWQL that is stored
/// twice and must agree. Validation is local and free — no API call, nothing written.
/// </summary>
public static class DashboardValidator
{
    public static DashboardValidation Validate(string text)
    {
        var v = new DashboardValidation();
        try
        {
            ValidateCore(text, v);
        }
        catch (Exception ex)
        {
            // The validator's contract is a structured result, never an exception — a
            // hostile or malformed file must degrade to a plain-English error line.
            v.Errors.Add($"file could not be analysed: {ex.Message}");
        }
        return v;
    }

    private static void ValidateCore(string text, DashboardValidation v)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            v.Errors.Add("file is empty (0 bytes) — not importable");
            return;
        }

        JsonNode? root;
        try { root = JsonNode.Parse(text); }
        catch (JsonException ex)
        {
            v.Errors.Add($"not valid JSON: {ex.Message}");
            return;
        }
        if (root is not JsonObject obj)
        {
            v.Errors.Add("root is not a JSON object");
            return;
        }

        foreach (var key in new[] { "version", "dashboards", "widgets" })
            if (!obj.ContainsKey(key))
                v.Errors.Add($"envelope is missing \"{key}\"");
        if (v.Errors.Count > 0) return;

        if (!(obj["version"] is JsonValue verVal && verVal.TryGetValue<int>(out var version) && version == 1))
            v.Warnings.Add($"version is {obj["version"]?.ToJsonString() ?? "absent"}, expected 1");

        var widgets = obj["widgets"] as JsonArray ?? new JsonArray();
        var dashboards = obj["dashboards"] as JsonArray ?? new JsonArray();
        v.WidgetCount = widgets.Count;

        // Widget definitions: collect keys, find duplicates.
        var keyCounts = new Dictionary<string, int>();
        foreach (var w in widgets.OfType<JsonObject>())
        {
            var key = (w["unique_key"] as JsonValue)?.TryGetValue<string>(out var wk) == true ? wk : null;
            if (key is null) { v.Errors.Add("a widget definition has no unique_key"); continue; }
            keyCounts[key] = keyCounts.GetValueOrDefault(key) + 1;
        }
        var dupes = keyCounts.Where(kv => kv.Value > 1).ToList();
        if (dupes.Count > 0)
            v.Warnings.Add(
                $"unique_key reused ×{dupes.Max(kv => kv.Value)} across {dupes.Sum(kv => kv.Value)} widget definitions — " +
                "placements cannot say which duplicate they mean, so DashboardPorter will not guess; the server's pick is undefined");

        // Placements must resolve to definitions.
        foreach (var d in dashboards.OfType<JsonObject>())
        {
            var dKey = (d["unique_key"] as JsonValue)?.TryGetValue<string>(out var dk) == true ? dk : "";
            var dName = (d["name"] as JsonValue)?.TryGetValue<string>(out var dn) == true ? dn : "(unnamed dashboard)";
            v.Dashboards.Add((dKey, dName));
            foreach (var p in (d["widgets"] as JsonArray ?? new JsonArray()).OfType<JsonObject>())
            {
                var pKey = (p["unique_key"] as JsonValue)?.TryGetValue<string>(out var pk) == true ? pk : null;
                if (pKey is not null && !keyCounts.ContainsKey(pKey))
                    v.Errors.Add($"dashboard \"{dName}\" places widget {pKey}, which no definition provides");
            }
        }
        if (v.Dashboards.Count == 0)
            v.Errors.Add("the file contains no dashboards");

        // The SWQL stored twice must agree (dataSource vs adapter.dataSource).
        var mismatches = 0;
        v.QueryCount = CountQueriesAndCheckPairs(root, ref mismatches);
        if (mismatches > 0)
            v.Warnings.Add($"{mismatches} widget(s) where the dataSource and adapter copies of the SWQL differ — both are real, the stale one still runs");
    }

    private static int CountQueriesAndCheckPairs(JsonNode? node, ref int mismatches)
    {
        var queries = 0;
        switch (node)
        {
            case JsonObject o:
                if (o.ContainsKey("swql")) queries++;
                if (o["dataSource"] is JsonObject ds && o["adapter"] is JsonObject ad)
                {
                    string? a = null, b = null;
                    if (ds["properties"]?["swql"] is JsonValue av) av.TryGetValue(out a);
                    if (ad["properties"]?["dataSource"]?["properties"]?["swql"] is JsonValue bv) bv.TryGetValue(out b);
                    if (a is not null && b is not null && a != b) mismatches++;
                }
                foreach (var kv in o) queries += CountQueriesAndCheckPairs(kv.Value, ref mismatches);
                break;
            case JsonArray arr:
                foreach (var item in arr) queries += CountQueriesAndCheckPairs(item, ref mismatches);
                break;
        }
        return queries;
    }
}
