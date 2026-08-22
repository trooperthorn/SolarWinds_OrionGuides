using System.IO;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Porter.Core;

public sealed record PackageItem(string Area, string RelPath, string Name, byte[] Data,
    string ImportVia, string CollisionNote);

/// <summary>
/// Writes an export either as raw files or as a self-describing package: the raw files
/// plus manifest.json carrying SHA-256 per item, the source server's identity, and the
/// verb each file re-imports through. The package is assembled entirely in memory, so
/// when the encrypted format is chosen no plaintext ever reaches the destination disk.
/// </summary>
public static class PackageWriter
{
    public static string WriteRaw(string destDir, IEnumerable<PackageItem> items)
    {
        Directory.CreateDirectory(destDir);
        foreach (var item in items)
        {
            var path = Path.Combine(destDir, Path.GetFileName(item.RelPath));
            File.WriteAllBytes(Unique(path), item.Data);
        }
        return destDir;
    }

    public static string WritePackage(string destDir, string server, string platformVersion,
        IReadOnlyList<PackageItem> items, string? aesPassword)
    {
        Directory.CreateDirectory(destDir);
        var stamp = DateTime.Now.ToString("yyyy-MM-dd_HHmmss");
        var baseName = Path.Combine(destDir, $"porter-pkg_{Sanitize(server)}_{stamp}");

        var zipBytes = BuildZipInMemory(server, platformVersion, items);

        if (aesPassword is null)
        {
            var zipPath = baseName + ".zip";
            File.WriteAllBytes(zipPath, zipBytes);
            return zipPath;
        }
        var aesPath = baseName + ".zip.aes";
        PackageCrypto.EncryptToFile(zipBytes, aesPath, aesPassword);
        return aesPath;
    }

    private static byte[] BuildZipInMemory(string server, string platformVersion,
        IReadOnlyList<PackageItem> items)
    {
        var manifestItems = new List<object>();
        using var buffer = new MemoryStream();
        using (var zip = new ZipArchive(buffer, ZipArchiveMode.Create, leaveOpen: true))
        {
            var used = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (var item in items)
            {
                var rel = UniqueRel(item.RelPath.Replace('\\', '/'), used);
                var entry = zip.CreateEntry(rel, CompressionLevel.Optimal);
                using (var stream = entry.Open()) stream.Write(item.Data);
                manifestItems.Add(new
                {
                    area = item.Area,
                    file = rel,
                    name = item.Name,
                    sha256 = Convert.ToHexString(SHA256.HashData(item.Data)).ToLowerInvariant(),
                    importVia = item.ImportVia,
                    collision = item.CollisionNote,
                });
            }
            var manifest = JsonSerializer.Serialize(new
            {
                tool = "Porter 0.1",
                source = new { server, platform = platformVersion, swis = "v3" },
                created = DateTime.UtcNow.ToString("o"),
                items = manifestItems,
            }, new JsonSerializerOptions { WriteIndented = true });
            var manifestEntry = zip.CreateEntry("manifest.json", CompressionLevel.Optimal);
            using var ms = manifestEntry.Open();
            ms.Write(Encoding.UTF8.GetBytes(manifest));
        }
        return buffer.ToArray();
    }

    public static string Sanitize(string name)
    {
        var bad = Path.GetInvalidFileNameChars();
        var chars = name.Select(c => bad.Contains(c) || c == ' ' ? '_' : c).ToArray();
        var s = new string(chars).Trim('_');
        return s.Length == 0 ? "unnamed" : s;
    }

    private static string UniqueRel(string rel, HashSet<string> used)
    {
        if (used.Add(rel)) return rel;
        var dir = Path.GetDirectoryName(rel)?.Replace('\\', '/');
        var stem = Path.GetFileNameWithoutExtension(rel);
        var ext = Path.GetExtension(rel);
        for (var n = 2; ; n++)
        {
            var candidate = string.IsNullOrEmpty(dir) ? $"{stem} ({n}){ext}" : $"{dir}/{stem} ({n}){ext}";
            if (used.Add(candidate)) return candidate;
        }
    }

    private static string Unique(string path)
    {
        if (!File.Exists(path)) return path;
        var dir = Path.GetDirectoryName(path)!;
        var stem = Path.GetFileNameWithoutExtension(path);
        var ext = Path.GetExtension(path);
        for (var n = 2; ; n++)
        {
            var candidate = Path.Combine(dir, $"{stem} ({n}){ext}");
            if (!File.Exists(candidate)) return candidate;
        }
    }
}
