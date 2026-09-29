using System.IO;
using System.Security.Cryptography;
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
}
