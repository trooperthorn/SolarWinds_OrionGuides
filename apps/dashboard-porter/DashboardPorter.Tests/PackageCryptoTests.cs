using System.IO;
using System.Security.Cryptography;
using System.Text;
using DashboardPorter.Core;

namespace DashboardPorter.Tests;

public sealed class PackageCryptoTests : IDisposable
{
    private readonly string _dir = Directory.CreateTempSubdirectory("dbporter-crypto-").FullName;
    private string PathFor(string n) => Path.Combine(_dir, n);
    public void Dispose() { try { Directory.Delete(_dir, true); } catch (IOException) { } }

    private static readonly byte[] Plain = Encoding.UTF8.GetBytes("PK-not-really-a-zip but bytes");

    [Fact]
    public void RoundTrip_ReturnsOriginalBytes()
    {
        var path = PathFor("a.zip.aes");
        PackageCrypto.EncryptToFile(Plain, path, "correct horse");
        Assert.Equal(Plain, PackageCrypto.DecryptFile(path, "correct horse"));
    }

    [Fact]
    public void Encrypt_StillWritesTheDashboardPorterMagic()
    {
        var path = PathFor("own.zip.aes");
        PackageCrypto.EncryptToFile(Plain, path, "pw");
        Assert.Equal("DBPORTA1", Encoding.ASCII.GetString(File.ReadAllBytes(path), 0, 8));
        Assert.Equal("DBPORTA1", PackageCrypto.WriteMagic);
    }

    [Fact]
    public void Decrypt_AcceptsAPorterPackage()
    {
        var path = PathFor("porter.zip.aes");
        TestData.EncryptIndependently(Plain, path, "pw", "PORTERA1");
        Assert.Equal(Plain, PackageCrypto.DecryptFile(path, "pw"));
    }

    [Fact]
    public void Decrypt_AcceptsAnIndependentlyWrittenDashboardPorterPackage()
    {
        var path = PathFor("own-independent.zip.aes");
        TestData.EncryptIndependently(Plain, path, "pw", "DBPORTA1");
        Assert.Equal(Plain, PackageCrypto.DecryptFile(path, "pw"));
    }

    [Fact]
    public void PorterPackage_WithWrongPassword_StillFailsAuthentication()
    {
        var path = PathFor("porter-wrong.zip.aes");
        TestData.EncryptIndependently(Plain, path, "right", "PORTERA1");
        Assert.ThrowsAny<CryptographicException>(() => PackageCrypto.DecryptFile(path, "wrong"));
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

    [Theory]
    [InlineData("XBPORTA1")]
    [InlineData("PORTERA2")]
    public void UnknownMagic_ThrowsInvalidData(string magic)
    {
        var path = PathFor("d.zip.aes");
        TestData.EncryptIndependently(Plain, path, "pw", magic);
        Assert.Throws<InvalidDataException>(() => PackageCrypto.DecryptFile(path, "pw"));
    }
}
