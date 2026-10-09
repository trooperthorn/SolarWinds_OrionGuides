using System.IO;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Porter.Areas;

namespace Porter.Core;

/// <summary>Where a staged entry came from — decides how much Porter can vouch for it.</summary>
public enum PackageOrigin
{
    /// <summary>A loose file picked or dropped directly; nothing vouches for it.</summary>
    RawFile,
    /// <summary>Inside a zip that carries no Porter manifest; routed by file extension.</summary>
    ForeignZip,
    /// <summary>Inside a Porter package; routed and hash-checked by its manifest.</summary>
    PorterPackage,
}

/// <summary>
/// One candidate file for the import provider. Errors and Warnings are findings about the
/// entry's origin (hash mismatch, unlisted, unverified) that the caller merges into the
/// provider's own validation — the reader has no opinion about file content.
/// </summary>
public sealed record PackageEntry(string DisplayName, string Text, PackageOrigin Origin)
{
    public IReadOnlyList<string> Errors { get; init; } = Array.Empty<string>();
    public IReadOnlyList<string> Warnings { get; init; } = Array.Empty<string>();
    /// <summary>Informational findings that do not block import (how the bytes were
    /// decoded). The caller shows them on the staged row and in the run log.</summary>
    public IReadOnlyList<string> Notes { get; init; } = Array.Empty<string>();
}

/// <summary>Package-level facts from manifest.json; all null/false for anything that is
/// not a Porter package.</summary>
public sealed record PackageInfo(string? SourceServer, string? SourcePlatform, string? Created,
    string? Tool, int? ManifestVersion, bool IsPorterPackage)
{
    public static readonly PackageInfo None = new(null, null, null, null, null, false);
}

public sealed record PackageContents(PackageInfo Info, IReadOnlyList<PackageEntry> Entries);

/// <summary>Hard ceilings that keep a hostile archive from exhausting memory. Tests pass
/// small ones; the defaults are what ships.</summary>
public sealed record PackageLimits(int MaxEntries, long MaxTotalBytes, long MaxItemBytes)
{
    public static readonly PackageLimits Default = new(
        MaxEntries: 5000,
        MaxTotalBytes: PackageCrypto.MaxPackageBytes,
        MaxItemBytes: 64L * 1024 * 1024);
}

/// <summary>
/// Reads an import source — a raw file, a .zip, or an AES-encrypted .zip.aes — into staged
/// candidates for one area. UI-free on purpose: the password prompt is a delegate, so the
/// view owns the dialog and this class stays testable.
/// With a Porter manifest, entries are chosen by the manifest's <c>area</c> (never by file
/// extension, which cannot tell alerts from reports) and each is checked against its
/// SHA-256. Without one, the extension heuristic applies and every entry is flagged as
/// unverified.
/// </summary>
public static class PackageReader
{
    /// <summary>Highest manifest schema this build understands.</summary>
    public const int SupportedManifestVersion = 1;

    public const string UnverifiedWarning = "unverified origin — no Porter manifest";

    /// <param name="passwordPrompt">Asked for the package password (given the file name);
    /// returns null when the operator cancels.</param>
    public static PackageContents Read(string path, AreaProvider provider,
        Func<string, string?> passwordPrompt, PackageLimits? limits = null)
    {
        limits ??= PackageLimits.Default;
        var fileName = Path.GetFileName(path);
        if (path.EndsWith(".aes", StringComparison.OrdinalIgnoreCase))
        {
            var password = passwordPrompt(fileName)
                ?? throw new OperationCanceledException("password entry cancelled");
            byte[] zipBytes;
            try { zipBytes = PackageCrypto.DecryptFile(path, password); }
            catch (CryptographicException)
            { throw new InvalidDataException("wrong password, or the package was modified"); }
            return ReadZipBytes(zipBytes, fileName, provider, limits);
        }
        if (path.EndsWith(".zip", StringComparison.OrdinalIgnoreCase))
        {
            using var archive = ZipFile.OpenRead(path);
            return ReadArchive(archive, fileName, provider, limits);
        }
        if (new FileInfo(path).Length > limits.MaxItemBytes)
            throw new InvalidDataException(
                $"{fileName} exceeds the {limits.MaxItemBytes / (1024 * 1024)} MB limit");
        var rawText = ReadTextSniffed(File.ReadAllBytes(path), out var rawNote);
        var raw = new PackageEntry(fileName, rawText, PackageOrigin.RawFile)
            { Warnings = new[] { UnverifiedWarning }, Notes = NotesOf(rawNote) };
        return new PackageContents(PackageInfo.None, new[] { raw });
    }

    public static PackageContents ReadZipBytes(byte[] zipBytes, string label, AreaProvider provider,
        PackageLimits? limits = null)
    {
        using var archive = new ZipArchive(new MemoryStream(zipBytes), ZipArchiveMode.Read);
        return ReadArchive(archive, label, provider, limits ?? PackageLimits.Default);
    }

    public static PackageContents ReadArchive(ZipArchive archive, string label, AreaProvider provider,
        PackageLimits limits)
    {
        // Count everything up front — entries the reader never opens still cost the central
        // directory parse, and a hostile archive can hold millions of them.
        if (archive.Entries.Count > limits.MaxEntries)
            throw new InvalidDataException(
                $"the package holds {archive.Entries.Count} entries — more than the {limits.MaxEntries} limit");

        var budget = new Budget(limits);
        var manifestEntry = archive.Entries.FirstOrDefault(e =>
            e.FullName.Equals("manifest.json", StringComparison.OrdinalIgnoreCase));
        return manifestEntry is null
            ? ReadForeign(archive, label, provider, budget)
            : ReadPorter(archive, manifestEntry, label, provider, budget);
    }

    // ---- foreign zip: extension heuristic, everything unverified ----

    private static PackageContents ReadForeign(ZipArchive archive, string label, AreaProvider provider,
        Budget budget)
    {
        var matching = archive.Entries.Where(en =>
            en.Name.EndsWith(provider.FileExtension, StringComparison.OrdinalIgnoreCase)).ToList();
        // A folder named for the area wins, so a mixed package stages only what belongs here.
        var inFolder = matching.Where(en => en.FullName.StartsWith(
            provider.Key + "/", StringComparison.OrdinalIgnoreCase)).ToList();
        if (inFolder.Count > 0) matching = inFolder;
        if (matching.Count == 0)
            throw new InvalidDataException(
                $"the package contains no {provider.FileExtension} files for {provider.DisplayName}");

        var entries = new List<PackageEntry>();
        foreach (var entry in matching)
        {
            var bytes = budget.Read(entry);
            var text = ReadTextSniffed(bytes, out var note);
            entries.Add(new PackageEntry($"{label} › {entry.Name}", text,
                PackageOrigin.ForeignZip) { Warnings = new[] { UnverifiedWarning }, Notes = NotesOf(note) });
        }
        return new PackageContents(PackageInfo.None, entries);
    }

    // ---- Porter package: manifest routes and verifies ----

    private sealed record ManifestItem(string Area, string File, string? Sha256);

    private static PackageContents ReadPorter(ZipArchive archive, ZipArchiveEntry manifestEntry,
        string label, AreaProvider provider, Budget budget)
    {
        JsonElement root;
        try
        {
            root = JsonDocument.Parse(budget.Read(manifestEntry)).RootElement;
        }
        catch (JsonException ex)
        {
            throw new InvalidDataException($"manifest.json is not valid JSON: {ex.Message}");
        }
        if (root.ValueKind != JsonValueKind.Object)
            throw new InvalidDataException("manifest.json is not a JSON object");

        var version = SupportedManifestVersion;
        if (root.TryGetProperty("manifestVersion", out var mv))
        {
            if (mv.ValueKind != JsonValueKind.Number || !mv.TryGetInt32(out version))
                throw new InvalidDataException("manifest.json has an unreadable manifestVersion");
        }
        if (version > SupportedManifestVersion)
            throw new InvalidDataException(
                $"the package manifest is version {version}; this Porter understands up to " +
                $"{SupportedManifestVersion} — update Porter to read it");

        string? Str(JsonElement el, string name) =>
            el.ValueKind == JsonValueKind.Object && el.TryGetProperty(name, out var p)
                ? (p.ValueKind == JsonValueKind.String ? p.GetString() : p.GetRawText())
                : null;
        var source = root.TryGetProperty("source", out var s) ? s : default;
        var info = new PackageInfo(Str(source, "server"), Str(source, "platform"), Str(root, "created"),
            Str(root, "tool"), version, IsPorterPackage: true);

        var items = new List<ManifestItem>();
        if (root.TryGetProperty("items", out var arr) && arr.ValueKind == JsonValueKind.Array)
            foreach (var it in arr.EnumerateArray())
                if (Str(it, "file") is { Length: > 0 } file)
                    items.Add(new ManifestItem(Str(it, "area") ?? "", Norm(file), Str(it, "sha256")));

        var mine = items.Where(i => i.Area.Equals(provider.Key, StringComparison.OrdinalIgnoreCase)).ToList();
        if (mine.Count == 0)
            throw new InvalidDataException($"the package contains no {provider.DisplayName} items");

        var entries = new List<PackageEntry>();
        var listed = new HashSet<string>(items.Select(i => i.File), StringComparer.OrdinalIgnoreCase);
        foreach (var item in mine)
        {
            var zipEntry = archive.Entries.FirstOrDefault(e =>
                Norm(e.FullName).Equals(item.File, StringComparison.OrdinalIgnoreCase));
            var display = $"{label} › {Path.GetFileName(item.File)}";
            if (zipEntry is null)
            {
                entries.Add(new PackageEntry(display, "", PackageOrigin.PorterPackage)
                    { Errors = new[] { "listed in the package manifest but missing from the package" } });
                continue;
            }
            var bytes = budget.Read(zipEntry);
            var errors = new List<string>();
            if (string.IsNullOrWhiteSpace(item.Sha256))
                errors.Add("the package manifest records no SHA-256 for this file");
            else if (!Convert.ToHexString(SHA256.HashData(bytes))
                         .Equals(item.Sha256, StringComparison.OrdinalIgnoreCase))
                errors.Add("SHA-256 does not match the package manifest — file was modified");
            var text = ReadTextSniffed(bytes, out var note);
            entries.Add(new PackageEntry(display, text, PackageOrigin.PorterPackage)
                { Errors = errors, Notes = NotesOf(note) });
        }

        // Files sitting in this area's folder that the manifest never mentions were added
        // after the package was sealed — stage them, but never as importable.
        foreach (var extra in archive.Entries.Where(e =>
                     e.Name.Length > 0 &&
                     Norm(e.FullName).StartsWith(provider.Key + "/", StringComparison.OrdinalIgnoreCase) &&
                     !listed.Contains(Norm(e.FullName))))
        {
            budget.Read(extra);   // counts against the caps, and reads what would import
            entries.Add(new PackageEntry($"{label} › {extra.Name}", "", PackageOrigin.PorterPackage)
                { Errors = new[] { "not listed in the package manifest" } });
        }
        return new PackageContents(info, entries);
    }

    private static string Norm(string path) => path.Replace('\\', '/').TrimStart('/');

    private static IReadOnlyList<string> NotesOf(string? note)
        => note is null ? Array.Empty<string>() : new[] { note };

    // ---- shared plumbing ----

    /// <summary>Tracks what has actually decompressed. A hostile zip's central directory can
    /// lie about entry sizes, so the guard counts real bytes, per item and per package.</summary>
    private sealed class Budget
    {
        private readonly PackageLimits _limits;
        private long _total;
        public Budget(PackageLimits limits) => _limits = limits;

        public byte[] Read(ZipArchiveEntry entry)
        {
            using var stream = entry.Open();
            using var buffer = new MemoryStream();
            var chunk = new byte[81920];
            long item = 0;
            int n;
            while ((n = stream.Read(chunk, 0, chunk.Length)) > 0)
            {
                item += n;
                _total += n;
                if (item > _limits.MaxItemBytes)
                    throw new InvalidDataException(
                        $"entry decompresses past the {_limits.MaxItemBytes / (1024 * 1024)} MB limit");
                if (_total > _limits.MaxTotalBytes)
                    throw new InvalidDataException(
                        $"the package decompresses past the {_limits.MaxTotalBytes / (1024 * 1024)} MB limit");
                buffer.Write(chunk, 0, n);
            }
            return buffer.ToArray();
        }
    }

    /// <summary>Platform exports lie about their encoding — NCM policy reports declare
    /// utf-16 in the XML prolog while the file on disk is utf-8. Trust the bytes, never the
    /// declaration: a BOM first, then the shape of BOM-less UTF-16 (NUL high bytes), then
    /// UTF-8.</summary>
    internal static string ReadTextSniffed(byte[] bytes) => ReadTextSniffed(bytes, out _);

    /// <param name="diagnostic">Set when the bytes were not read the way they declare or
    /// carry no BOM to vouch for them: a BOM-less UTF-16 detection, or the UTF-8 fallback
    /// under a declaration that says otherwise (docs/modules/ncm-compliance-reports.md
    /// asks for that fallback to be reported, not hidden). Null when nothing needs saying.</param>
    internal static string ReadTextSniffed(byte[] bytes, out string? diagnostic)
    {
        diagnostic = null;
        if (bytes.Length >= 2 && bytes[0] == 0xFF && bytes[1] == 0xFE)
            return Encoding.Unicode.GetString(bytes, 2, bytes.Length - 2);
        if (bytes.Length >= 2 && bytes[0] == 0xFE && bytes[1] == 0xFF)
            return Encoding.BigEndianUnicode.GetString(bytes, 2, bytes.Length - 2);
        if (bytes.Length >= 3 && bytes[0] == 0xEF && bytes[1] == 0xBB && bytes[2] == 0xBF)
            return Encoding.UTF8.GetString(bytes, 3, bytes.Length - 3);

        switch (SniffBomlessUtf16(bytes))
        {
            case true:
                diagnostic = "encoding: no byte-order mark; the bytes are UTF-16 little-endian and were read as such";
                return Encoding.Unicode.GetString(bytes);
            case false:
                diagnostic = "encoding: no byte-order mark; the bytes are UTF-16 big-endian and were read as such";
                return Encoding.BigEndianUnicode.GetString(bytes);
        }

        var text = Encoding.UTF8.GetString(bytes);
        var declared = DeclaredEncoding(text);
        if (declared is not null && !declared.Equals("utf-8", StringComparison.OrdinalIgnoreCase) &&
            !declared.Equals("utf8", StringComparison.OrdinalIgnoreCase))
            diagnostic = $"encoding: the XML declaration says \"{declared}\" but the bytes carry no " +
                         "byte-order mark and are not UTF-16 — read as UTF-8 (fallback)";
        if (text.Contains('\uFFFD'))
            diagnostic = (diagnostic is null ? "encoding: " : diagnostic + "; ") +
                         "the bytes are not valid UTF-8 — undecodable sequences were replaced";
        return text;
    }

    /// <summary>
    /// BOM-less UTF-16 detection: true = little-endian, false = big-endian, null = not
    /// UTF-16. An XML declaration or JSON/XML opener written in UTF-16 starts with a NUL
    /// beside an ASCII byte ("&lt;\0?\0" or "\0&lt;\0?"), and text in UTF-16 that is mostly
    /// ASCII has NUL in nearly every high byte while UTF-8 text has no NUL at all. The
    /// sample is the first 4 KB.
    /// </summary>
    internal static bool? SniffBomlessUtf16(byte[] bytes)
    {
        if (bytes.Length < 4) return null;
        if (bytes[0] == (byte)'<' && bytes[1] == 0 && bytes[2] == (byte)'?' && bytes[3] == 0) return true;
        if (bytes[0] == 0 && bytes[1] == (byte)'<' && bytes[2] == 0 && bytes[3] == (byte)'?') return false;

        var pairs = Math.Min(bytes.Length, 4096) / 2;
        int evenNul = 0, oddNul = 0;
        for (var i = 0; i < pairs; i++)
        {
            if (bytes[2 * i] == 0) evenNul++;
            if (bytes[2 * i + 1] == 0) oddNul++;
        }
        // Thresholds leave room for non-ASCII characters while rejecting the stray NUL a
        // damaged UTF-8 file might hold.
        if (oddNul >= pairs * 0.4 && evenNul <= pairs * 0.05) return true;
        if (evenNul >= pairs * 0.4 && oddNul <= pairs * 0.05) return false;
        return null;
    }

    /// <summary>The encoding="…" value of a leading XML declaration, if any.</summary>
    private static string? DeclaredEncoding(string text)
    {
        var start = text.TrimStart();
        if (!start.StartsWith("<?xml", StringComparison.Ordinal)) return null;
        var end = start.IndexOf("?>", StringComparison.Ordinal);
        if (end < 0) return null;
        var match = System.Text.RegularExpressions.Regex.Match(start[..end],
            "encoding\\s*=\\s*[\"']([^\"']+)[\"']");
        return match.Success ? match.Groups[1].Value : null;
    }
}
