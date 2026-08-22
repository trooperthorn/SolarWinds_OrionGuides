using System.Text.Json;
using System.Text.Json.Nodes;

namespace Porter.Areas;

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
                "placements cannot say which duplicate they mean, so Porter will not guess; the server's pick is undefined");

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
