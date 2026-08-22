using System.Globalization;
using System.Text;
using System.Text.Json;
using Porter.Core;

namespace Porter.Areas;

/// <summary>
/// Nodes + custom properties — a bulk CSV, not per-item files.
/// Export:  one .csv — Caption, IPAddress, then every node custom property, with
///          annotation rows (#datatype, #allowedvalues, #mandatory, #default) so
///          definitions can be recreated faithfully. Node identity columns only —
///          SNMP community strings and other node secrets are deliberately NOT exported.
/// Import:  pre-flights each missing definition with ValidateCustomProperty, creates it
///          (CreateCustomPropertyWithValues when an allowed-value list travelled — needs
///          admin), then writes values per node matched by IPAddress with Caption
///          fallback. Every row and every definition fails individually: one bad value
///          never aborts the rest, and the outcome accounts for all of it.
/// </summary>
public sealed class NodesCpProvider : AreaProvider
{
    public NodesCpProvider(SwisSession swis) : base(swis) { }

    public override string Key => "nodescp";
    public override string DisplayName => "Nodes + Custom Properties";
    public override string FileExtension => ".csv";
    public override string FileDialogFilter => "Node custom-property tables|*.csv";
    public override string ImportVia => "ValidateCustomProperty → CreateCustomProperty(+WithValues) + per-node CustomProperties update";
    public override bool BulkExport => true;
    public override string SecurityNotice =>
        "The table carries node names, addresses, and custom-property values only. SNMP " +
        "community strings and other node secrets are never exported.";

    public override async Task<List<AreaItem>> ListAsync(CancellationToken ct)
    {
        var rows = await Swis.QueryAsync(
            "SELECT NodeID, Caption, IPAddress, MachineType FROM Orion.Nodes ORDER BY Caption",
            null, ct);
        var list = new List<AreaItem>();
        foreach (var row in rows.EnumerateArray())
        {
            list.Add(new AreaItem(row.GetProperty("NodeID").GetInt32().ToString(),
                row.GetProperty("Caption").GetString() ?? "(unnamed)",
                row.GetProperty("IPAddress").GetString() ?? "",
                false,
                (row.TryGetProperty("MachineType", out var m) ? m.GetString() : null) ?? ""));
        }
        return list;
    }

    private sealed record CpDef(string Field, string ValueType, int Size,
        bool Mandatory, string Default, List<string> AllowedValues);

    private async Task<List<CpDef>> DefinitionsAsync(CancellationToken ct)
    {
        var rows = await Swis.QueryAsync(
            "SELECT Field, DataType, MaxLength, Mandatory, Default FROM Orion.CustomProperty " +
            "WHERE Table = 'NodesCustomProperties' ORDER BY Field", null, ct);
        var values = new Dictionary<string, List<string>>(StringComparer.OrdinalIgnoreCase);
        var valueRows = await Swis.QueryAsync(
            "SELECT Field, Value FROM Orion.CustomPropertyValues " +
            "WHERE Table = 'NodesCustomProperties' ORDER BY Field, Value", null, ct);
        foreach (var row in valueRows.EnumerateArray())
        {
            var f = row.GetProperty("Field").GetString() ?? "";
            if (f.Length == 0) continue;
            if (!values.TryGetValue(f, out var list)) values[f] = list = new List<string>();
            if (row.GetProperty("Value").GetString() is string val) list.Add(val);
        }

        var defs = new List<CpDef>();
        foreach (var row in rows.EnumerateArray())
        {
            var field = row.GetProperty("Field").GetString() ?? "";
            if (field.Length == 0) continue;
            var sqlType = (row.TryGetProperty("DataType", out var d) ? d.GetString() : null) ?? "";
            var size = row.TryGetProperty("MaxLength", out var s) && s.ValueKind == JsonValueKind.Number
                ? s.GetInt32() : 0;
            var mandatory = row.TryGetProperty("Mandatory", out var mn) && mn.ValueKind == JsonValueKind.True;
            var deflt = (row.TryGetProperty("Default", out var df) &&
                df.ValueKind == JsonValueKind.String ? df.GetString() : null) ?? "";
            defs.Add(new CpDef(field, SqlToValueType(sqlType), size, mandatory, deflt,
                values.TryGetValue(field, out var av) ? av : new List<string>()));
        }
        return defs;
    }

    /// <summary>SQL storage type → the ValueType vocabulary CreateCustomProperty accepts.</summary>
    private static string SqlToValueType(string sqlType) => sqlType.ToLowerInvariant() switch
    {
        "int" or "bigint" or "smallint" => "integer",
        "datetime" or "datetime2" => "datetime",
        "real" => "single",
        "float" => "double",
        "bit" => "boolean",
        _ => "string",
    };

    public override async Task<AreaExport> ExportBulkAsync(IReadOnlyList<AreaItem> items,
        ExportOptions opt, CancellationToken ct)
    {
        var all = await DefinitionsAsync(ct);
        // SWQL brackets any identifier that needs quoting; a field with ']' in its name
        // cannot be quoted at all and is skipped, visibly.
        var defs = all.Where(d => !d.Field.Contains(']')).ToList();
        var skipped = all.Except(defs).Select(d => d.Field).ToList();

        var ids = string.Join(",", items.Select(i => int.Parse(i.Id)));
        var fieldList = string.Join(", ", defs.Select(d => $"ncp.[{d.Field}]"));
        var swql = defs.Count > 0
            ? $"SELECT ncp.NodeID, ncp.Node.Caption AS Caption, ncp.Node.IPAddress AS IPAddress, {fieldList} " +
              $"FROM Orion.NodesCustomProperties ncp WHERE ncp.NodeID IN ({ids})"
            : $"SELECT NodeID, Caption, IPAddress FROM Orion.Nodes WHERE NodeID IN ({ids})";
        var rows = await Swis.QueryAsync(swql, null, ct);

        var sb = new StringBuilder();
        if (skipped.Count > 0)
            sb.AppendLine("#note," + Csv("skipped unquotable columns: " + string.Join("; ", skipped)));
        sb.AppendLine(string.Join(",", new[] { "Caption", "IPAddress" }
            .Concat(defs.Select(d => Csv(d.Field)))));
        if (defs.Count > 0)
        {
            sb.AppendLine("#datatype,," + string.Join(",",
                defs.Select(d => d.ValueType == "string" ? $"string:{Math.Max(d.Size, 1)}" : d.ValueType)));
            if (defs.Any(d => d.AllowedValues.Count > 0))
                sb.AppendLine("#allowedvalues,," + string.Join(",", defs.Select(d =>
                    d.AllowedValues.Count > 0 ? Csv(JsonSerializer.Serialize(d.AllowedValues)) : "")));
            if (defs.Any(d => d.Mandatory))
                sb.AppendLine("#mandatory,," + string.Join(",",
                    defs.Select(d => d.Mandatory ? "true" : "")));
            if (defs.Any(d => d.Default.Length > 0))
                sb.AppendLine("#default,," + string.Join(",", defs.Select(d => Csv(d.Default))));
        }
        foreach (var row in rows.EnumerateArray())
        {
            var cells = new List<string>
            {
                Csv(row.GetProperty("Caption").GetString() ?? ""),
                Csv(row.GetProperty("IPAddress").GetString() ?? ""),
            };
            foreach (var d in defs)
            {
                var val = row.TryGetProperty(d.Field, out var v) ? v : default;
                cells.Add(Csv(val.ValueKind switch
                {
                    JsonValueKind.String => val.GetString() ?? "",
                    JsonValueKind.Number => val.GetRawText(),
                    JsonValueKind.True => "true",
                    JsonValueKind.False => "false",
                    _ => "",
                }));
            }
            sb.AppendLine(string.Join(",", cells));
        }
        return new AreaExport("nodes-custom-properties.csv", Encoding.UTF8.GetBytes(sb.ToString()));
    }

    private static string Csv(string s)
        => s.IndexOfAny(new[] { ',', '"', '\n', '\r' }) >= 0
            ? "\"" + s.Replace("\"", "\"\"") + "\"" : s;

    /// <summary>Full-record CSV scanner: a quoted cell may span physical lines, so records
    /// are split by the scanner, never by a naive line split.</summary>
    private static List<List<string>> ParseCsv(string text)
    {
        var records = new List<List<string>>();
        var cells = new List<string>();
        var sb = new StringBuilder();
        var quoted = false;
        var any = false;
        void EndCell() { cells.Add(sb.ToString()); sb.Clear(); }
        void EndRecord()
        {
            EndCell();
            if (cells.Count > 1 || cells[0].Trim().Length > 0)
                records.Add(new List<string>(cells));
            cells.Clear();
            any = false;
        }
        for (var i = 0; i < text.Length; i++)
        {
            var ch = text[i];
            if (quoted)
            {
                if (ch == '"' && i + 1 < text.Length && text[i + 1] == '"') { sb.Append('"'); i++; }
                else if (ch == '"') quoted = false;
                else sb.Append(ch);
                continue;
            }
            switch (ch)
            {
                case '"': quoted = true; any = true; break;
                case ',': EndCell(); any = true; break;
                case '\r': break;
                case '\n': if (any || sb.Length > 0 || cells.Count > 0) EndRecord(); break;
                default: sb.Append(ch); any = true; break;
            }
        }
        if (any || sb.Length > 0 || cells.Count > 0) EndRecord();
        return records;
    }

    private sealed record Table(List<string> Fields, Dictionary<string, string> Types,
        Dictionary<string, List<string>> AllowedValues, Dictionary<string, bool> Mandatory,
        Dictionary<string, string> Defaults,
        List<(string Caption, string Ip, List<string> Values)> Rows);

    private static Table? ParseTable(string text, AreaValidation v)
    {
        var records = ParseCsv(text);
        // Annotation records ride under '#'-prefixed first cells; the header is the first
        // record that is not an annotation.
        var annotations = new Dictionary<string, List<string>>(StringComparer.OrdinalIgnoreCase);
        List<string>? header = null;
        var dataStart = -1;
        for (var i = 0; i < records.Count; i++)
        {
            var first = records[i][0].Trim();
            if (first.StartsWith('#')) { annotations[first] = records[i]; continue; }
            if (header is null) { header = records[i]; continue; }
            dataStart = i; break;
        }
        if (header is null) { v.Errors.Add("file has no header row"); return null; }
        var capIdx = header.FindIndex(h => h.Trim().Equals("Caption", StringComparison.OrdinalIgnoreCase));
        var ipIdx = header.FindIndex(h => h.Trim().Equals("IPAddress", StringComparison.OrdinalIgnoreCase));
        if (capIdx < 0 || ipIdx < 0)
        { v.Errors.Add("the header row needs Caption and IPAddress columns"); return null; }
        var fieldIdx = Enumerable.Range(0, header.Count).Where(i => i != capIdx && i != ipIdx).ToList();
        var fields = fieldIdx.Select(i => header[i].Trim()).ToList();

        List<string> Ann(string key) => annotations.TryGetValue(key, out var r) ? r : new List<string>();
        string AnnCell(List<string> rec, int headerIdx)
            => headerIdx < rec.Count ? rec[headerIdx].Trim() : "";

        var types = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var allowed = new Dictionary<string, List<string>>(StringComparer.OrdinalIgnoreCase);
        var mandatory = new Dictionary<string, bool>(StringComparer.OrdinalIgnoreCase);
        var defaults = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var typeRec = Ann("#datatype");
        var allowedRec = Ann("#allowedvalues");
        var mandatoryRec = Ann("#mandatory");
        var defaultRec = Ann("#default");
        for (var i = 0; i < fields.Count; i++)
        {
            var col = fieldIdx[i];
            if (AnnCell(typeRec, col) is { Length: > 0 } t) types[fields[i]] = t;
            var av = AnnCell(allowedRec, col);
            if (av.Length > 0)
            {
                try
                {
                    allowed[fields[i]] = JsonSerializer.Deserialize<List<string>>(av) ?? new List<string>();
                }
                catch (JsonException)
                {
                    v.Warnings.Add($"#allowedvalues for \"{fields[i]}\" is not a JSON array — ignored");
                }
            }
            if (AnnCell(mandatoryRec, col).Equals("true", StringComparison.OrdinalIgnoreCase))
                mandatory[fields[i]] = true;
            if (AnnCell(defaultRec, col) is { Length: > 0 } df) defaults[fields[i]] = df;
        }

        var rows = new List<(string, string, List<string>)>();
        if (dataStart >= 0)
        {
            for (var ri = dataStart; ri < records.Count; ri++)
            {
                var rec = records[ri];
                if (rec[0].Trim().StartsWith('#')) continue;
                string Cell(int i) => i < rec.Count ? rec[i] : "";
                rows.Add((Cell(capIdx).Trim(), Cell(ipIdx).Trim(), fieldIdx.Select(Cell).ToList()));
            }
        }
        return new Table(fields, types, allowed, mandatory, defaults, rows);
    }

    public override AreaValidation Validate(string fileName, string text)
    {
        var v = new AreaValidation();
        try
        {
            var table = ParseTable(text, v);
            if (table is null) return v;
            if (table.Rows.Count == 0) v.Errors.Add("no data rows after the header");
            var blank = table.Rows.Count(r => r.Caption.Length == 0 && r.Ip.Length == 0);
            if (blank > 0)
                v.Warnings.Add($"{blank} row(s) have neither Caption nor IPAddress and will be skipped");
            if (table.Fields.Count == 0)
                v.Warnings.Add("no custom-property columns — only node identity, nothing to write");
            v.Detail = $"{table.Rows.Count} nodes · {table.Fields.Count} custom-property columns";
            // No Items on purpose: existing definitions are not a reason to skip the file —
            // the import reconciles per property and per node, and reports each decision.
        }
        catch (Exception ex)
        {
            v.Errors.Add($"file could not be analysed: {ex.Message}");
        }
        return v;
    }

    public override async Task<ImportOutcome> ImportAsync(string text, IReadOnlyList<string> verifyKeys,
        ImportOptions opt, CancellationToken ct)
    {
        var scratch = new AreaValidation();
        var table = ParseTable(text, scratch)
            ?? throw new InvalidOperationException(scratch.Errors.FirstOrDefault() ?? "unreadable table");

        var existing = (await DefinitionsAsync(ct)).Select(d => d.Field)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
        var created = 0;
        var problems = new List<string>();
        foreach (var field in table.Fields.Where(f => !existing.Contains(f)))
        {
            var spec = table.Types.TryGetValue(field, out var t) ? t : "string:250";
            var parts = spec.Split(':');
            var valueType = parts[0].Trim().ToLowerInvariant();
            var size = parts.Length > 1 && int.TryParse(parts[1], out var s) ? s : 250;
            if (valueType is not ("string" or "integer" or "datetime" or "single" or "double" or "boolean"))
                valueType = "string";
            var values = table.AllowedValues.TryGetValue(field, out var av) ? av : new List<string>();
            var isMandatory = table.Mandatory.TryGetValue(field, out var mn) && mn;
            var deflt = table.Defaults.TryGetValue(field, out var df) ? df : null;
            try
            {
                // Server-side pre-flight; its result shape is undocumented, so a thrown
                // fault is the signal Porter acts on.
                await Swis.InvokeAsync("Orion.NodesCustomProperties", "ValidateCustomProperty",
                    new object?[] { field, "", valueType, size, values.ToArray(), null, null }, ct);
                if (values.Count > 0)
                    // WithValues: the required Value array sits after the six unused
                    // ValidRange..Units slots, then Usages, Mandatory, Default.
                    await Swis.InvokeAsync("Orion.NodesCustomProperties", "CreateCustomPropertyWithValues",
                        new object?[] { field, "", valueType, size, null, null, null, null, null, null,
                            values.ToArray(), null, isMandatory, deflt }, ct);
                else
                    await Swis.InvokeAsync("Orion.NodesCustomProperties", "CreateCustomProperty",
                        new object?[] { field, "", valueType, size, null, null, null, null, null, null,
                            null, isMandatory, deflt }, ct);
                created++;
                existing.Add(field);
            }
            catch (Exception ex) when (ex is not OperationCanceledException)
            {
                problems.Add($"definition \"{field}\" not created: {ex.Message}");
            }
        }

        int updated = 0;
        foreach (var (caption, ip, values) in table.Rows)
        {
            if (caption.Length == 0 && ip.Length == 0) continue;
            var label = caption.Length > 0 ? caption : ip;
            try
            {
                JsonElement matches;
                if (ip.Length > 0)
                    matches = await Swis.QueryAsync(
                        "SELECT NodeID, Uri, Caption FROM Orion.Nodes WHERE IPAddress = @ip",
                        new Dictionary<string, object?> { ["ip"] = ip }, ct);
                else
                    matches = await Swis.QueryAsync(
                        "SELECT NodeID, Uri, Caption FROM Orion.Nodes WHERE Caption = @c",
                        new Dictionary<string, object?> { ["c"] = caption }, ct);
                var rows = matches.EnumerateArray().ToList();
                if (rows.Count == 0 && ip.Length > 0 && caption.Length > 0)
                {
                    matches = await Swis.QueryAsync(
                        "SELECT NodeID, Uri, Caption FROM Orion.Nodes WHERE Caption = @c",
                        new Dictionary<string, object?> { ["c"] = caption }, ct);
                    rows = matches.EnumerateArray().ToList();
                }
                if (rows.Count == 0) { problems.Add($"\"{label}\" not found"); continue; }
                if (rows.Count > 1) { problems.Add($"\"{label}\" matches {rows.Count} nodes — ambiguous"); continue; }

                var props = new Dictionary<string, object?>();
                for (var i = 0; i < table.Fields.Count && i < values.Count; i++)
                {
                    if (!existing.Contains(table.Fields[i])) continue;   // definition failed above
                    var raw = values[i].Trim();
                    if (raw.Length == 0) continue;   // empty cells never clear target values
                    var spec = table.Types.TryGetValue(table.Fields[i], out var t) ? t : "string";
                    props[table.Fields[i]] = spec.Split(':')[0].ToLowerInvariant() switch
                    {
                        "integer" when long.TryParse(raw, out var l) => l,
                        "boolean" => raw.Equals("true", StringComparison.OrdinalIgnoreCase) || raw == "1",
                        "single" or "double" when double.TryParse(raw, NumberStyles.Float,
                            CultureInfo.InvariantCulture, out var dd) => dd,
                        _ => raw,
                    };
                }
                if (props.Count == 0) continue;
                var uri = rows[0].GetProperty("Uri").GetString()
                    ?? throw new InvalidOperationException("no Uri returned for the node");
                await Swis.UpdateAsync(uri + "/CustomProperties", props, ct);
                updated++;
            }
            catch (Exception ex) when (ex is not OperationCanceledException)
            {
                problems.Add($"\"{label}\": {ex.Message}");
            }
        }

        var detail = $"{created} definition(s) created · values written on {updated} node(s)";
        if (problems.Count > 0)
        {
            var shown = string.Join(", ", problems.Take(10));
            if (problems.Count > 10) shown += $" … and {problems.Count - 10} more";
            return new ImportOutcome(false, $"{detail} · {problems.Count} item(s) not applied: {shown}");
        }
        return new ImportOutcome(true, detail);
    }
}
