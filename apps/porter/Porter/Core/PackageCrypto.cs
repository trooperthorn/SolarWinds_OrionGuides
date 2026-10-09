using System.IO;
using System.Security.Cryptography;
using System.Text;

namespace Porter.Core;

/// <summary>
/// Optional package encryption: AES-256-GCM with a PBKDF2-derived key (SHA-256, 600k
/// iterations). File layout: magic "PORTERA1" | 16-byte salt | 12-byte nonce |
/// 16-byte tag | ciphertext. Uses Windows CNG primitives, so it runs under FIPS policy.
/// Plaintext package bytes are only ever held in memory — never written to disk.
/// DashboardPorter (apps/dashboard-porter) writes the identical layout under the magic
/// "DBPORTA1"; decrypt accepts it read-only so those packages import here. Porter itself
/// always writes "PORTERA1". The magic is a format label, not authenticated data — the
/// GCM tag covers the ciphertext, so accepting two labels does not weaken the check.
/// </summary>
public static class PackageCrypto
{
    /// <summary>The magic Porter writes.</summary>
    internal const string WriteMagic = "PORTERA1";
    /// <summary>Every magic decrypt accepts: Porter's own, then DashboardPorter's (legacy, read-only).</summary>
    internal static readonly string[] ReadMagics = { WriteMagic, "DBPORTA1" };

    private static readonly byte[] Magic = Encoding.ASCII.GetBytes(WriteMagic);
    private static readonly byte[][] AcceptedMagics =
        ReadMagics.Select(m => Encoding.ASCII.GetBytes(m)).ToArray();
    private const int Iterations = 600_000;

    /// <summary>Cap on the encrypted file size accepted for decryption (zip-bomb hygiene).</summary>
    public const long MaxPackageBytes = 256L * 1024 * 1024;

    public static void EncryptToFile(byte[] plain, string outPath, string password)
    {
        var salt = RandomNumberGenerator.GetBytes(16);
        var nonce = RandomNumberGenerator.GetBytes(12);
        var key = Rfc2898DeriveBytes.Pbkdf2(password, salt, Iterations, HashAlgorithmName.SHA256, 32);
        try
        {
            var cipher = new byte[plain.Length];
            var tag = new byte[16];
            using (var aes = new AesGcm(key, 16))
                aes.Encrypt(nonce, plain, cipher, tag);
            using var fs = File.Create(outPath);
            fs.Write(Magic); fs.Write(salt); fs.Write(nonce); fs.Write(tag); fs.Write(cipher);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(key);
        }
    }

    /// <summary>Throws CryptographicException on a wrong password or a tampered file.</summary>
    public static byte[] DecryptFile(string path, string password)
    {
        var info = new FileInfo(path);
        if (info.Length > MaxPackageBytes)
            throw new InvalidDataException(
                $"package is {info.Length / (1024 * 1024)} MB — larger than the {MaxPackageBytes / (1024 * 1024)} MB limit");
        var all = File.ReadAllBytes(path);
        if (all.Length < 8 + 16 + 12 + 16 || !AcceptedMagics.Any(m => all.AsSpan(0, 8).SequenceEqual(m)))
            throw new InvalidDataException("Not a Porter or DashboardPorter encrypted package (.zip.aes).");
        var salt = all.AsSpan(8, 16).ToArray();
        var nonce = all.AsSpan(24, 12).ToArray();
        var tag = all.AsSpan(36, 16).ToArray();
        var cipher = all.AsSpan(52).ToArray();
        var key = Rfc2898DeriveBytes.Pbkdf2(password, salt, Iterations, HashAlgorithmName.SHA256, 32);
        var plain = new byte[cipher.Length];
        try
        {
            using var aes = new AesGcm(key, 16);
            aes.Decrypt(nonce, cipher, tag, plain);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(key);
        }
        return plain;
    }
}
