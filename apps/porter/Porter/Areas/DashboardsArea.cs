using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using Porter.Core;

namespace Porter.Areas;

public sealed record DashboardListRow(int Id, string Name, string UniqueKey, bool IsSystem);

public sealed record DashboardImportOutcome(string File, string Outcome, string Detail);

/// <summary>
/// The Modern Dashboards provider — the Phase-1 verification area.
/// Export:  Orion.Dashboards.Instances.Export(dashboardId) → the JSON definition.
/// Import:  Orion.Dashboards.Instances.Import(definition) → void, so Porter verifies by
///          re-querying the file's dashboard unique_keys afterwards.
/// </summary>
public sealed class DashboardsArea
{
    private readonly SwisSession _swis;

    public DashboardsArea(SwisSession swis) => _swis = swis;

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

    /// <summary>Every dashboard and widget unique_key on the target — the identities a copy
    /// must not reuse. Read-only.</summary>
    public async Task<HashSet<string>> TargetKeysAsync(CancellationToken ct = default)
    {
        var keys = new HashSet<string>(DashboardKeyComparer.Instance);
        foreach (var swql in new[]
                 {
                     "SELECT UniqueKey FROM Orion.Dashboards.Instances",
                     "SELECT UniqueKey FROM Orion.Dashboards.Widgets",
                 })
        {
            var rows = await _swis.QueryAsync(swql, null, ct);
            foreach (var row in rows.EnumerateArray())
                if (row.TryGetProperty("UniqueKey", out var k) && k.GetString() is { Length: > 0 } s)
                    keys.Add(s);
        }
        return keys;
    }

    /// <summary>The target's widget unique_keys only. Read-only.</summary>
    public async Task<List<string>> TargetWidgetKeysAsync(CancellationToken ct = default)
    {
        var rows = await _swis.QueryAsync("SELECT UniqueKey FROM Orion.Dashboards.Widgets", null, ct);
        var keys = new List<string>();
        foreach (var row in rows.EnumerateArray())
            if (row.TryGetProperty("UniqueKey", out var k) && k.GetString() is { Length: > 0 } s)
                keys.Add(s);
        return keys;
    }

    /// <summary>Which dashboards on the target place each of these widget keys (the
    /// target's own spellings): key → dashboard names. Read-only.</summary>
    public async Task<Dictionary<string, List<string>>> WidgetConsumersAsync(
        IReadOnlyCollection<string> targetWidgetKeys, CancellationToken ct = default)
    {
        var map = new Dictionary<string, List<string>>(DashboardKeyComparer.Instance);
        if (targetWidgetKeys.Count == 0) return map;
        var rows = await _swis.QueryAsync(
            "SELECT TOP 1000 l.DashboardID, l.Dashboards.DisplayName AS [Dashboard], " +
            "l.Widgets.UniqueKey AS [WidgetKey] FROM Orion.Dashboards.Links l " +
            "WHERE l.Widgets.UniqueKey IN @widgetKeys ORDER BY l.DashboardID",
            new Dictionary<string, object?> { ["widgetKeys"] = targetWidgetKeys.ToArray() }, ct);
        foreach (var row in rows.EnumerateArray())
        {
            var key = row.TryGetProperty("WidgetKey", out var k) ? k.GetString() : null;
            if (string.IsNullOrEmpty(key)) continue;
            var name = (row.TryGetProperty("Dashboard", out var n) ? n.GetString() : null) ?? "(unnamed)";
            if (!map.TryGetValue(key, out var list)) map[key] = list = new List<string>();
            if (!list.Contains(name)) list.Add(name);
        }
        return map;
    }

    /// <summary>Pairs each of the file's widget keys with the target key it matches
    /// (normalized UUID, case-insensitive name).</summary>
    public static List<(string FileKey, string TargetKey)> MatchKeys(
        IEnumerable<string> fileKeys, IEnumerable<string> targetKeys)
    {
        var target = new Dictionary<string, string>(DashboardKeyComparer.Instance);
        foreach (var k in targetKeys) target.TryAdd(k, k);
        return fileKeys.Where(target.ContainsKey).Select(k => (k, target[k])).ToList();
    }

    /// <summary>
    /// The "import as copy" transform, done structurally rather than textually. Only the
    /// identity fields the format defines are regenerated — dashboards[].unique_key and
    /// widgets[].unique_key, with placements remapped — so GUIDs inside embedded SWQL and
    /// URLs (which reference server-side objects) are never touched. Each dashboard is
    /// renamed "… (Copy)", and where a query addresses a dashboard by its original name (the
    /// documented self-referencing link pattern), the quoted literal is rewritten to the new
    /// name so the copy points at itself.
    ///
    /// Identity rules (docs/webui/modern-dashboard-authoring.md, duplicating a dashboard;
    /// modern-dashboard-widget-identity-audit.md, rules 4-5):
    /// - New keys never reuse a key in <paramref name="avoid"/> (the target's dashboard and
    ///   widget keys) or one already issued, and dashboard and widget keys are mapped
    ///   separately, so two different source identities never share one new key.
    /// - The map is scoped to this one document; another file's copy gets its own keys.
    /// - A widget key carrying DIFFERENT definitions in this file is refused: placements
    ///   cannot say which one they mean, and one old→new mapping would carry the conflict
    ///   into the copy. Identical duplicates are one definition and share one new key.
    /// - A widget placed on several dashboards in this file stays shared under one new key,
    ///   detached from the original; the notes say so.
    /// Dashboard groups and routes (2026.4 export audit, section 2): a copy must not join the
    /// original's tab group or share its route, so groupId is remapped to a new group (shared
    /// by copies that were grouped together in this file) and routeId/dashboardRoutes are
    /// cleared to the empty forms seen in other exports. Notes describe each change.
    /// </summary>
    public static (string Text, List<string> NewNames, List<string> NewKeys, List<string> Notes)
        AsCopy(string definition, IEnumerable<string>? avoid = null, Func<string>? newKey = null)
    {
        var root = JsonNode.Parse(definition) as JsonObject
                   ?? throw new InvalidDataException("definition is not a JSON object");
        var taken = new HashSet<string>(avoid ?? Enumerable.Empty<string>(), DashboardKeyComparer.Instance);
        newKey ??= () => Guid.NewGuid().ToString("D");
        string Issue()
        {
            for (var attempt = 0; attempt < 1000; attempt++)
            {
                var candidate = newKey();
                if (!string.IsNullOrEmpty(candidate) && taken.Add(candidate)) return candidate;
            }
            throw new InvalidOperationException("could not generate an unused unique_key");
        }

        var newNames = new List<string>();
        var newKeys = new List<string>();
        var notes = new List<string>();
        var renames = new List<(string OldName, string NewName)>();

        // Widget definitions first, so the map is complete before placements remap.
        var widgets = (root["widgets"] as JsonArray ?? new JsonArray()).OfType<JsonObject>().ToList();
        foreach (var group in widgets
                     .Where(w => KeyOf(w) is { Length: > 0 })
                     .GroupBy(w => KeyOf(w)!, DashboardKeyComparer.Instance)
                     .Where(g => g.Count() > 1))
        {
            var distinct = group.Select(Canonical).Distinct(StringComparer.Ordinal).Count();
            if (distinct > 1)
                throw new InvalidDataException(
                    $"widget unique_key {group.Key} carries {distinct} different definitions in this file — " +
                    "placements cannot say which one they mean, so Porter will not copy it by guessing; " +
                    "give each definition its own key and remap its placements first");
            notes.Add($"widget unique_key {group.Key} appears {group.Count()} times with identical definitions — " +
                "the copy keeps them as one definition under one new key");
        }
        var widgetMap = new Dictionary<string, string>(DashboardKeyComparer.Instance);
        foreach (var w in widgets)
            if (KeyOf(w) is { Length: > 0 } wk)
            {
                if (!widgetMap.TryGetValue(wk, out var fresh)) widgetMap[wk] = fresh = Issue();
                w["unique_key"] = fresh;
            }

        var dashboards = (root["dashboards"] as JsonArray ?? new JsonArray()).OfType<JsonObject>().ToList();
        var dashboardMap = new Dictionary<string, string>(DashboardKeyComparer.Instance);
        var groupMap = new Dictionary<string, string>(StringComparer.Ordinal);
        var placedOn = new Dictionary<string, int>(DashboardKeyComparer.Instance);
        int regrouped = 0, rerouted = 0;
        foreach (var d in dashboards)
        {
            var oldName = d["name"]?.GetValue<string>() ?? "Dashboard";
            var newName = oldName + " (Copy)";
            d["name"] = newName;
            newNames.Add(newName);
            renames.Add((oldName, newName));

            if (KeyOf(d) is { Length: > 0 } dk)
            {
                if (!dashboardMap.TryGetValue(dk, out var fresh)) dashboardMap[dk] = fresh = Issue();
                d["unique_key"] = fresh;
                newKeys.Add(fresh);
            }
            var placedHere = new HashSet<string>(DashboardKeyComparer.Instance);
            foreach (var placement in (d["widgets"] as JsonArray ?? new JsonArray()).OfType<JsonObject>())
            {
                if (KeyOf(placement) is not { Length: > 0 } pk || !widgetMap.TryGetValue(pk, out var mapped)) continue;
                placement["unique_key"] = mapped;
                if (placedHere.Add(pk)) placedOn[pk] = placedOn.GetValueOrDefault(pk) + 1;
            }

            if (d["groupId"] is JsonValue gv && gv.TryGetValue<string>(out var gid) && gid.Length > 0)
            {
                if (!groupMap.TryGetValue(gid, out var newGroup)) groupMap[gid] = newGroup = Guid.NewGuid().ToString("D");
                d["groupId"] = newGroup;
                regrouped++;
            }
            var hadRoute = d["routeId"] is JsonValue rv && rv.TryGetValue<string>(out var rid) && rid.Length > 0;
            var hadRoutes = d["dashboardRoutes"] is JsonArray ra && ra.Count > 0;
            if (hadRoute || hadRoutes)
            {
                if (d.ContainsKey("routeId")) d["routeId"] = "";
                if (d.ContainsKey("dashboardRoutes")) d["dashboardRoutes"] = new JsonArray();
                rerouted++;
            }
        }

        var shared = placedOn.Where(kv => kv.Value > 1).ToList();
        if (shared.Count > 0)
            notes.Add($"{shared.Count} widget(s) are placed on more than one dashboard in this file — the copies " +
                "keep sharing each one under a single new key, detached from the original");
        if (regrouped > 0)
            notes.Add($"WARNING: groupId moved to a new group on {regrouped} dashboard(s) so the copy does not join " +
                "the original's tab group (copies grouped together in this file stay together); groupName, " +
                "groupRank and groupMemberName are unchanged — review the tab labels");
        if (rerouted > 0)
            notes.Add($"WARNING: routeId and dashboardRoutes cleared on {rerouted} dashboard(s) so the copy does " +
                "not share the original's route; links or tabs that target that route still reach the original — review them");

        // Self-referencing queries: rewrite exact quoted name literals so the copy's internal
        // links target the copy rather than the original that is still on the server.
        var rewrites = 0;
        foreach (var (key, value) in root.ToList())
            if (key != "dashboards") RewriteNames(value, renames, notes, ref rewrites, OuterQueryKeys);
        foreach (var d in dashboards)
        {
            foreach (var (key, value) in d.ToList())
                if (key != "configuration") RewriteNames(value, renames, notes, ref rewrites, OuterQueryKeys);
            RewriteConfiguration(d, renames, notes, ref rewrites);
        }
        if (rewrites > 0)
            notes.Add($"rewrote {rewrites} self-referencing dashboard-name literal(s) in embedded queries to the copy's name");

        return (root.ToJsonString(new JsonSerializerOptions { WriteIndented = false }),
                newNames, newKeys, notes);
    }

    private static string? KeyOf(JsonObject o)
        => o["unique_key"] is JsonValue v && v.TryGetValue<string>(out var k) ? k : null;

    /// <summary>A definition with its identity removed and object members sorted, so two
    /// definitions compare by content.</summary>
    private static string Canonical(JsonObject widget)
    {
        static JsonNode? Sort(JsonNode? n) => n switch
        {
            JsonObject o => new JsonObject(o.OrderBy(kv => kv.Key, StringComparer.Ordinal)
                .Select(kv => KeyValuePair.Create(kv.Key, Sort(kv.Value)))),
            JsonArray a => new JsonArray(a.Select(Sort).ToArray()),
            null => null,
            _ => JsonNode.Parse(n.ToJsonString()),
        };
        var copy = (JsonObject)Sort(widget)!;
        copy.Remove("unique_key");
        return copy.ToJsonString();
    }

    /// <summary>Query-bearing keys in the outer document.</summary>
    private static readonly HashSet<string> OuterQueryKeys = new(StringComparer.Ordinal) { "swql", "swqlQuery" };

    /// <summary>Inside the decoded dashboard configuration, conditional notices carry their
    /// query as "query" too (2026.4 export audit, sections 3 and 12).</summary>
    private static readonly HashSet<string> ConfigurationQueryKeys =
        new(StringComparer.Ordinal) { "swql", "swqlQuery", "query" };

    /// <summary>
    /// dashboards[].configuration may be a JSON-encoded string inside the JSON document (the
    /// 2026.4 exports show this; one decodes to null), or an already-decoded object. Decode
    /// it — through a second layer if the string itself holds an encoded string — rewrite its
    /// query fields, and re-encode only when something changed.
    /// </summary>
    private static void RewriteConfiguration(JsonObject dashboard,
        List<(string OldName, string NewName)> renames, List<string> notes, ref int rewrites)
    {
        var config = dashboard["configuration"];
        if (config is JsonObject or JsonArray)
        {
            RewriteNames(config, renames, notes, ref rewrites, ConfigurationQueryKeys);
            return;
        }
        if (config is not JsonValue cv || !cv.TryGetValue<string>(out var encoded)) return;

        var layers = 0;
        JsonNode? decoded = null;
        var current = encoded;
        while (layers < 3)
        {
            try { decoded = JsonNode.Parse(current); }
            catch (JsonException) { return; }   // not JSON: nothing Porter may rewrite
            layers++;
            if (decoded is JsonValue inner && inner.TryGetValue<string>(out var again)) { current = again; continue; }
            break;
        }
        if (decoded is not (JsonObject or JsonArray)) return;

        var before = rewrites;
        RewriteNames(decoded, renames, notes, ref rewrites, ConfigurationQueryKeys);
        if (rewrites == before) return;
        var text = decoded.ToJsonString();
        for (var i = 1; i < layers; i++) text = JsonSerializer.Serialize(text);
        dashboard["configuration"] = text;
    }

    private static void RewriteNames(JsonNode? node,
        List<(string OldName, string NewName)> renames, List<string> notes, ref int rewrites,
        HashSet<string> queryKeys)
    {
        switch (node)
        {
            case JsonObject obj:
                foreach (var key in obj.Select(kv => kv.Key).ToList())
                {
                    if (queryKeys.Contains(key) && obj[key] is JsonValue val &&
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
                        RewriteNames(obj[key], renames, notes, ref rewrites, queryKeys);
                    }
                }
                break;
            case JsonArray arr:
                foreach (var item in arr) RewriteNames(item, renames, notes, ref rewrites, queryKeys);
                break;
        }
    }
}
