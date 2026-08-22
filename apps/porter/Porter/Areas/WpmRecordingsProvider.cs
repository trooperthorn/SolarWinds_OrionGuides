using System.Text;
using System.Text.Json;
using Porter.Core;

namespace Porter.Areas;

/// <summary>
/// WPM transaction recordings — Orion.SEUM.Recordings.
/// Export:  Export(recordingId:int, password:string) → RecordingFileContent
///          { Content, Name } — the platform REQUIRES the cipher password; only the
///          Content string is written to disk.
/// Import:  Import(content:string, recordingName:string, password:string) → new id.
///          The same password must be supplied; a mismatch fails the import outright.
/// The file body is an opaque ciphered blob, so pre-flight checks are limited to
/// non-emptiness and a name-collision query; the server is the real validator.
/// Transactions (the monitors) have no export route — recordings only.
/// </summary>
public sealed class WpmRecordingsProvider : AreaProvider
{
    public WpmRecordingsProvider(SwisSession swis) : base(swis) { }

    public override string Key => "wpm";
    public override string DisplayName => "WPM Recordings";
    public override string FileExtension => ".recording";
    public override string FileDialogFilter => "WPM recordings|*.recording";
    public override string ImportVia => "Orion.SEUM.Recordings.Import";
    public override bool RequiresCipherPassword => true;
    public override string SecurityNotice =>
        "Recordings carry the site credentials and certificates they were recorded with. " +
        "The platform ciphers every export with the password you set here — the export " +
        "file cannot be opened without it, and the import side must use the same password.";

    public override async Task<List<AreaItem>> ListAsync(CancellationToken ct)
    {
        var rows = await Swis.QueryAsync(
            "SELECT RecordingId, Name, Guid, Version FROM Orion.SEUM.Recordings ORDER BY Name",
            null, ct);
        var list = new List<AreaItem>();
        foreach (var row in rows.EnumerateArray())
        {
            var name = row.GetProperty("Name").GetString() ?? "(unnamed)";
            var guid = row.GetProperty("Guid").GetString() ?? "";
            list.Add(new AreaItem(row.GetProperty("RecordingId").GetInt32().ToString(),
                name, guid, false, $"v{row.GetProperty("Version").GetRawText().Trim('"')}"));
        }
        return list;
    }

    public override async Task<AreaExport> ExportAsync(AreaItem item, ExportOptions opt, CancellationToken ct)
    {
        if (string.IsNullOrEmpty(opt.CipherPassword))
            throw new InvalidOperationException("the platform requires a cipher password on every recording export");
        var result = await Swis.InvokeAsync("Orion.SEUM.Recordings", "Export",
            new object?[] { int.Parse(item.Id), opt.CipherPassword }, ct);
        if (result is not { ValueKind: JsonValueKind.Object } r ||
            !r.TryGetProperty("Content", out var contentEl) ||
            contentEl.GetString() is not string content || content.Length == 0)
            throw new InvalidOperationException($"Export returned no content for recording {item.Id}");
        // The blob is opaque, so the recording's real name and Guid travel in a small
        // envelope — a sanitized FILENAME must never become the identity (spaces would
        // come back as underscores, missing collisions and renaming the import).
        var envelope = JsonSerializer.Serialize(new
        {
            porter = "wpm-recording",
            name = item.Name,
            guid = item.Key,
            content,
        });
        return new AreaExport(PackageWriter.Sanitize(item.Name) + FileExtension,
            Encoding.UTF8.GetBytes(envelope));
    }

    /// <summary>Splits an export into (name, guid, content). Porter's own envelope carries
    /// all three; a foreign bare blob falls back to the file stem with no guid.</summary>
    private static (string Name, string? Guid, string Content) Unwrap(string text, string fileStem)
    {
        try
        {
            using var doc = JsonDocument.Parse(text);
            if (doc.RootElement.ValueKind == JsonValueKind.Object &&
                doc.RootElement.TryGetProperty("porter", out var tag) &&
                tag.GetString() == "wpm-recording" &&
                doc.RootElement.TryGetProperty("content", out var c) &&
                c.GetString() is string content && content.Length > 0)
            {
                var name = doc.RootElement.TryGetProperty("name", out var n)
                    ? n.GetString() : null;
                var guid = doc.RootElement.TryGetProperty("guid", out var g)
                    ? g.GetString() : null;
                return (string.IsNullOrWhiteSpace(name) ? fileStem : name!, guid, content);
            }
        }
        catch (JsonException) { }
        return (fileStem, null, text);
    }

    public override AreaValidation Validate(string fileName, string text)
    {
        var v = new AreaValidation();
        var stem = System.IO.Path.GetFileNameWithoutExtension(fileName);
        // A path like "pkg.zip › name.recording" keeps only the real file's stem.
        var sep = stem.LastIndexOf('›');
        if (sep >= 0) stem = stem[(sep + 1)..].Trim();
        if (string.IsNullOrWhiteSpace(text))
        { v.Errors.Add("file is empty (0 bytes) — not importable"); return v; }
        var (name, guid, content) = Unwrap(text, stem);
        v.Items.Add((name, name));
        if (guid is null)
            v.Warnings.Add("no Porter envelope — the file stem names the recording, and a " +
                "collision against a differently spelled original cannot be detected");
        v.Detail = $"ciphered recording \"{name}\" ({content.Length:N0} chars) — content can " +
            "only be checked by the server at import";
        return v;
    }

    public override async Task<Dictionary<string, string>> FindCollisionsAsync(
        IReadOnlyCollection<string> keys, CancellationToken ct)
    {
        var map = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var key in keys.Where(k => k.Length > 0))
        {
            var rows = await Swis.QueryAsync(
                "SELECT Name FROM Orion.SEUM.Recordings WHERE Name = @n",
                new Dictionary<string, object?> { ["n"] = key }, ct);
            foreach (var row in rows.EnumerateArray())
                map[key] = row.GetProperty("Name").GetString() ?? key;
        }
        return map;
    }

    public override async Task<ImportOutcome> ImportAsync(string text, IReadOnlyList<string> verifyKeys,
        ImportOptions opt, CancellationToken ct)
    {
        if (string.IsNullOrEmpty(opt.CipherPassword))
            throw new InvalidOperationException("enter the cipher password the recording was exported with");
        var fallback = verifyKeys.Count > 0 ? verifyKeys[0] : "Imported recording";
        var (recordingName, _, content) = Unwrap(text, fallback);
        var result = await Swis.InvokeAsync("Orion.SEUM.Recordings", "Import",
            new object?[] { content, recordingName, opt.CipherPassword }, ct);
        if (result is not { ValueKind: JsonValueKind.Number } idEl)
            return new ImportOutcome(false, "Import did not return the new recording id");
        var newId = idEl.GetInt32();

        var rows = await Swis.QueryAsync(
            "SELECT RecordingId, Name, Guid FROM Orion.SEUM.Recordings WHERE RecordingId = @id",
            new Dictionary<string, object?> { ["id"] = newId }, ct);
        foreach (var row in rows.EnumerateArray())
            return new ImportOutcome(true,
                $"\"{row.GetProperty("Name").GetString()}\" (id {newId}) — transactions do not " +
                "travel: re-create monitors against this recording on the target");
        return new ImportOutcome(false,
            $"Import returned id {newId} but the row was not found afterwards");
    }
}
