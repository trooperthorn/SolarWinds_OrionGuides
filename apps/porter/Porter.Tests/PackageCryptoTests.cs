using System.IO;
using System.Security.Cryptography;
using System.Text;
using Porter.Core;

namespace Porter.Tests;

public sealed class PackageCryptoTests : IDisposable
{
    private readonly string _dir = Directory.CreateTempSubdirectory("porter-tests-").FullName;
    private string PathFor(string n) => Path.Combine(_dir, n);
    public void Dispose() { try { Directory.Delete(_dir, true); } catch (IOException) { } }

    private static readonly byte[] Plain = System.Text.Encoding.UTF8.GetBytes("PK-not-really-a-zip but bytes");

    [Fact]
    public void RoundTrip_ReturnsOriginalBytes()
    {
        var path = PathFor("a.zip.aes");
        PackageCrypto.EncryptToFile(Plain, path, "correct horse");
        Assert.Equal(Plain, PackageCrypto.DecryptFile(path, "correct horse"));
    }

    [Fact]
    public void WrongPassword_ThrowsCryptographicException()
    {
        var path = PathFor("b.zip.aes");
        PackageCrypto.EncryptToFile(Plain, path, "right");
        Assert.ThrowsAny<CryptographicException>(() => PackageCrypto.DecryptFile(path, "wrong"));
    }

    [Fact]
    public void TamperedByte_ThrowsCryptographicException()
    {
        var path = PathFor("c.zip.aes");
        PackageCrypto.EncryptToFile(Plain, path, "pw");
        var bytes = File.ReadAllBytes(path);
        bytes[^1] ^= 0xFF;
        File.WriteAllBytes(path, bytes);
        Assert.ThrowsAny<CryptographicException>(() => PackageCrypto.DecryptFile(path, "pw"));
    }

    [Fact]
    public void BadMagic_ThrowsInvalidData()
    {
        var path = PathFor("d.zip.aes");
        PackageCrypto.EncryptToFile(Plain, path, "pw");
        var bytes = File.ReadAllBytes(path);
        bytes[0] = (byte)'X';
        File.WriteAllBytes(path, bytes);
        Assert.Throws<InvalidDataException>(() => PackageCrypto.DecryptFile(path, "pw"));
    }

    /// <summary>Writes the documented layout (magic | salt | nonce | tag | ciphertext;
    /// PBKDF2-SHA256 600k, AES-256-GCM) without PackageCrypto, so a decrypt test proves
    /// compatibility with the other tool's format rather than with Porter's own writer.</summary>
    private static void EncryptIndependently(byte[] plain, string path, string password, string magic)
    {
        var salt = RandomNumberGenerator.GetBytes(16);
        var nonce = RandomNumberGenerator.GetBytes(12);
        var key = Rfc2898DeriveBytes.Pbkdf2(password, salt, 600_000, HashAlgorithmName.SHA256, 32);
        var cipher = new byte[plain.Length];
        var tag = new byte[16];
        using (var aes = new AesGcm(key, 16))
            aes.Encrypt(nonce, plain, cipher, tag);
        using var fs = File.Create(path);
        fs.Write(Encoding.ASCII.GetBytes(magic));
        fs.Write(salt);
        fs.Write(nonce);
        fs.Write(tag);
        fs.Write(cipher);
    }

    [Fact]
    public void Encrypt_StillWritesThePorterMagic()
    {
        var path = PathFor("own.zip.aes");
        PackageCrypto.EncryptToFile(Plain, path, "pw");
        Assert.Equal("PORTERA1", Encoding.ASCII.GetString(File.ReadAllBytes(path), 0, 8));
    }

    [Fact]
    public void Decrypt_AcceptsALegacyDashboardPorterPackage()
    {
        var path = PathFor("dbporter.zip.aes");
        EncryptIndependently(Plain, path, "pw", "DBPORTA1");
        Assert.Equal(Plain, PackageCrypto.DecryptFile(path, "pw"));
    }

    [Fact]
    public void LegacyDashboardPorterPackage_WithWrongPassword_StillFailsAuthentication()
    {
        var path = PathFor("dbporter-wrong.zip.aes");
        EncryptIndependently(Plain, path, "right", "DBPORTA1");
        Assert.ThrowsAny<CryptographicException>(() => PackageCrypto.DecryptFile(path, "wrong"));
    }

    [Fact]
    public void EncryptedDashboardPorterPackage_ImportsThroughThePackageReader()
    {
        // The manifest DashboardPorter writes: area "dashboards", per-item SHA-256.
        var zip = PackageWriter.BuildZipInMemory("orion01", "Orion 2026.2", new[]
        {
            new PackageItem("dashboards", "dashboards/ops.json", "Ops",
                Encoding.UTF8.GetBytes(TestData.Dashboard), "Orion.Dashboards.Instances.Import", "note"),
        });
        var path = PathFor("dbporter-pkg.zip.aes");
        EncryptIndependently(zip, path, "pw", "DBPORTA1");
        var contents = PackageReader.Read(path, new Porter.Areas.DashboardsProvider(TestData.Session()), _ => "pw");
        Assert.Empty(Assert.Single(contents.Entries).Errors);
    }
}
