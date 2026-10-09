using System.IO;
using System.Security.Cryptography;
using System.Text;

namespace DashboardPorter.Tests;

/// <summary>Shared fixtures. Nothing here connects to a server or touches %ProgramData%.</summary>
internal static class TestData
{
    public const string Dashboard = """
        {
          "version": 1,
          "dashboards": [
            { "unique_key": "dash-1", "name": "Ops",
              "widgets": [ { "unique_key": "w-1" }, { "unique_key": "w-2" } ] }
          ],
          "widgets": [
            { "unique_key": "w-1",
              "dataSource": { "properties": { "swql": "SELECT Name FROM Orion.Nodes WHERE Name = 'Ops'" } } },
            { "unique_key": "w-2" }
          ]
        }
        """;

    /// <summary>
    /// Writes an encrypted package from the documented layout (magic | 16-byte salt |
    /// 12-byte nonce | 16-byte tag | ciphertext; PBKDF2-SHA256 600k, AES-256-GCM) without
    /// going through PackageCrypto — so a decrypt test proves format compatibility with the
    /// other tool, not just agreement with this tool's own writer.
    /// </summary>
    public static void EncryptIndependently(byte[] plain, string path, string password, string magic)
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
}
