using System.IO;
using System.Text.Json;

namespace Porter.Core;

public sealed record LastConnection(
    string Server, int Port, bool WindowsAuth, string Username, bool VerifyTls);

/// <summary>
/// Remembers the last successful connection — server, port, auth mode, username, and the
/// TLS choice — in the hardened %ProgramData%\Porter directory. Never the password.
/// A missing or unreadable file simply means nothing to prefill.
/// </summary>
public static class ConnectionMemory
{
    private static string FilePath => Path.Combine(AppDirs.Base, "connection.json");

    public static LastConnection? Load()
    {
        try
        {
            AppDirs.RefuseReparse(FilePath);
            if (!File.Exists(FilePath)) return null;
            return JsonSerializer.Deserialize<LastConnection>(File.ReadAllText(FilePath));
        }
        catch (Exception)
        {
            return null;
        }
    }

    public static void Save(LastConnection last)
    {
        try
        {
            AppDirs.RefuseReparse(FilePath);
            File.WriteAllText(FilePath,
                JsonSerializer.Serialize(last, new JsonSerializerOptions { WriteIndented = true }));
        }
        catch (Exception ex)
        {
            SessionLog.Log("memory", "connection.json", "unwritable", ex.Message);
        }
    }
}
