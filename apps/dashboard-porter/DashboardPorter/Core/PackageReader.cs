using System.IO;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace DashboardPorter.Core;

/// <summary>Where a staged entry came from — decides how much DashboardPorter can vouch for it.</summary>
public enum PackageOrigin
{
    /// <summary>A loose file picked or dropped directly; nothing vouches for it.</summary>
    RawFile,
    /// <summary>Inside a zip that carries no package manifest; routed by file extension.</summary>
    ForeignZip,
    /// <summary>Inside a DashboardPorter or Porter package; routed and hash-checked by its manifest.</summary>
    ManifestPackage,
}

/// <summary>
/// One candidate file for import. Errors and Warnings are findings about the entry's
/// origin (hash mismatch, unlisted, unverified) that the caller merges into the
/// dashboard validator's own findings — the reader has no opinion about file content.
/// </summary>
public sealed record PackageEntry(string DisplayName, string Text, PackageOrigin Origin)
{
    public IReadOnlyList<string> Errors { get; init; } = Array.Empty<string>();
    public IReadOnlyList<string> Warnings { get; init; } = Array.Empty<string>();
}

/// <summary>Package-level facts from manifest.json; all null/false for anything that has
/// no manifest.</summary>
public sealed record PackageInfo(string? SourceServer, string? SourcePlatform, string? Created,
    string? Tool, int? ManifestVersion, bool HasManifest)
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
/// Modern Dashboard candidates. Ported from apps/porter/Porter/Core/PackageReader.cs and
/// narrowed to the one area this tool moves (manifest area "dashboards", extension .json).
/// UI-free on purpose: the password prompt is a delegate, so the view owns the dialog and
/// this class stays testable.
/// With a manifest (written by DashboardPorter or Porter — the format is shared), entries
/// are chosen by the manifest's <c>area</c> and each is checked against its SHA-256; files
/// in the dashboards/ folder the manifest does not list are staged as errors. Without a
/// manifest, the extension heuristic applies and every entry is flagged as unverified.
/// </summary>
public static class PackageReader
{
    /// <summary>Highest manifest schema this build understands (same numbering as Porter).</summary>
    public const int SupportedManifestVersion = 1;

    /// <summary>The manifest area and package folder this tool imports.</summary>
    public const string AreaKey = "dashboards";
    private const string FileExtension = ".json";
    private const string DisplayName = "Modern Dashboards";

    public const string UnverifiedWarning = "unverified origin — no package manifest";

    /// <param name="passwordPrompt">Asked for the package password (given the file name);
    /// returns null when the operator cancels.</param>
    public static PackageContents Read(string path, Func<string, string?> passwordPrompt,
        PackageLimits? limits = null)
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
            return ReadZipBytes(zipBytes, fileName, limits);
        }
        if (path.EndsWith(".zip", StringComparison.OrdinalIgnoreCase))
        {
            using var archive = ZipFile.OpenRead(path);
            return ReadArchive(archive, fileName, limits);
        }
        if (new FileInfo(path).Length > limits.MaxItemBytes)
            throw new InvalidDataException(
                $"{fileName} exceeds the {limits.MaxItemBytes / (1024 * 1024)} MB limit");
        var raw = new PackageEntry(fileName, ReadTextSniffed(File.ReadAllBytes(path)), PackageOrigin.RawFile)
            { Warnings = new[] { UnverifiedWarning } };
        return new PackageContents(PackageInfo.None, new[] { raw });
    }

    public static PackageContents ReadZipBytes(byte[] zipBytes, string label, PackageLimits? limits = null)
    {
        using var archive = new ZipArchive(new MemoryStream(zipBytes), ZipArchiveMode.Read);
        return ReadArchive(archive, label, limits ?? PackageLimits.Default);
    }

    public static PackageContents ReadArchive(ZipArchive archive, string label, PackageLimits limits)
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
            ? ReadForeign(archive, label, budget)
            : ReadManifest(archive, manifestEntry, label, budget);
    }

    // ---- foreign zip: extension heuristic, everything unverified ----

    private static PackageContents ReadForeign(ZipArchive archive, string label, Budget budget)
    {
        var matching = archive.Entries.Where(en =>
            en.Name.EndsWith(FileExtension, StringComparison.OrdinalIgnoreCase)).ToList();
        // A dashboards/ folder wins, so a mixed zip stages only the dashboards.
        var inFolder = matching.Where(en => en.FullName.StartsWith(
            AreaKey + "/", StringComparison.OrdinalIgnoreCase)).ToList();
        if (inFolder.Count > 0) matching = inFolder;
        if (matching.Count == 0)
            throw new InvalidDataException(
                $"the package contains no {FileExtension} files for {DisplayName}");

        var entries = new List<PackageEntry>();
        foreach (var entry in matching)
        {
            var bytes = budget.Read(entry);
            entries.Add(new PackageEntry($"{label} › {entry.Name}", ReadTextSniffed(bytes),
                PackageOrigin.ForeignZip) { Warnings = new[] { UnverifiedWarning } });
        }
        return new PackageContents(PackageInfo.None, entries);
    }

    // ---- manifest package: the manifest routes and verifies ----

    private sealed record ManifestItem(string Area, string File, string? Sha256);

    private static PackageContents ReadManifest(ZipArchive archive, ZipArchiveEntry manifestEntry,
        string label, Budget budget)
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
                $"the package manifest is version {version}; this DashboardPorter understands up to " +
                $"{SupportedManifestVersion} — import it with Porter, or update DashboardPorter");

        string? Str(JsonElement el, string name) =>
            el.ValueKind == JsonValueKind.Object && el.TryGetProperty(name, out var p)
                ? (p.ValueKind == JsonValueKind.String ? p.GetString() : p.GetRawText())
                : null;
        var source = root.TryGetProperty("source", out var s) ? s : default;
        var info = new PackageInfo(Str(source, "server"), Str(source, "platform"), Str(root, "created"),
            Str(root, "tool"), version, HasManifest: true);

        var items = new List<ManifestItem>();
        if (root.TryGetProperty("items", out var arr) && arr.ValueKind == JsonValueKind.Array)
            foreach (var it in arr.EnumerateArray())
                if (Str(it, "file") is { Length: > 0 } file)
                    items.Add(new ManifestItem(Str(it, "area") ?? "", Norm(file), Str(it, "sha256")));

        var mine = items.Where(i => i.Area.Equals(AreaKey, StringComparison.OrdinalIgnoreCase)).ToList();
        if (mine.Count == 0)
            throw new InvalidDataException($"the package contains no {DisplayName} items");

        var entries = new List<PackageEntry>();
        var listed = new HashSet<string>(items.Select(i => i.File), StringComparer.OrdinalIgnoreCase);
        foreach (var item in mine)
        {
            var zipEntry = archive.Entries.FirstOrDefault(e =>
                Norm(e.FullName).Equals(item.File, StringComparison.OrdinalIgnoreCase));
            var display = $"{label} › {Path.GetFileName(item.File)}";
            if (zipEntry is null)
            {
                entries.Add(new PackageEntry(display, "", PackageOrigin.ManifestPackage)
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
            entries.Add(new PackageEntry(display, ReadTextSniffed(bytes), PackageOrigin.ManifestPackage)
                { Errors = errors });
        }

        // Files sitting in the dashboards/ folder that the manifest never mentions were added
        // after the package was sealed — stage them, but never as importable.
        foreach (var extra in archive.Entries.Where(e =>
                     e.Name.Length > 0 &&
                     Norm(e.FullName).StartsWith(AreaKey + "/", StringComparison.OrdinalIgnoreCase) &&
                     !listed.Contains(Norm(e.FullName))))
        {
            budget.Read(extra);   // counts against the caps, and reads what would import
            entries.Add(new PackageEntry($"{label} › {extra.Name}", "", PackageOrigin.ManifestPackage)
                { Errors = new[] { "not listed in the package manifest" } });
        }
        return new PackageContents(info, entries);
    }

    private static string Norm(string path) => path.Replace('\\', '/').TrimStart('/');

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

    /// <summary>Platform exports lie about their encoding sometimes — trust the bytes (BOM),
    /// never a declaration inside the file.</summary>
    internal static string ReadTextSniffed(byte[] bytes)
    {
        if (bytes.Length >= 2 && bytes[0] == 0xFF && bytes[1] == 0xFE)
            return Encoding.Unicode.GetString(bytes, 2, bytes.Length - 2);
        if (bytes.Length >= 2 && bytes[0] == 0xFE && bytes[1] == 0xFF)
            return Encoding.BigEndianUnicode.GetString(bytes, 2, bytes.Length - 2);
        if (bytes.Length >= 3 && bytes[0] == 0xEF && bytes[1] == 0xBB && bytes[2] == 0xBF)
            return Encoding.UTF8.GetString(bytes, 3, bytes.Length - 3);
        return Encoding.UTF8.GetString(bytes);
    }
}
