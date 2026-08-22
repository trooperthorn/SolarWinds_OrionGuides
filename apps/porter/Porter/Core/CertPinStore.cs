using System.IO;
using System.Text.Json;

namespace Porter.Core;

/// <summary>
/// Pinned self-signed certificate thumbprints, stored per server:port in
/// %ProgramData%\Porter\pins.json. Pins are SHA-256 over the certificate's raw bytes.
/// No secrets live here — a thumbprint identifies a certificate, it does not unlock anything.
/// </summary>
public static class CertPinStore
{
    private static readonly object Gate = new();

    public static string BaseDir => AppDirs.Base;

    private static string PinPath => Path.Combine(BaseDir, "pins.json");

    private static Dictionary<string, List<string>> Load()
    {
        try
        {
            AppDirs.RefuseReparse(PinPath);
            if (File.Exists(PinPath))
                return JsonSerializer.Deserialize<Dictionary<string, List<string>>>(
                    File.ReadAllText(PinPath)) ?? new();
        }
        catch (Exception ex) when (ex is IOException or JsonException) { }
        return new();
    }

    public static bool IsPinned(string server, int port, string thumbprint)
    {
        lock (Gate)
        {
            var pins = Load();
            return pins.TryGetValue($"{server}:{port}".ToLowerInvariant(), out var list) &&
                   list.Any(t => string.Equals(t, thumbprint, StringComparison.OrdinalIgnoreCase));
        }
    }

    public static void Pin(string server, int port, string thumbprint)
    {
        lock (Gate)
        {
            var pins = Load();
            var key = $"{server}:{port}".ToLowerInvariant();
            if (!pins.TryGetValue(key, out var list)) pins[key] = list = new List<string>();
            if (!list.Contains(thumbprint, StringComparer.OrdinalIgnoreCase)) list.Add(thumbprint);
            File.WriteAllText(PinPath, JsonSerializer.Serialize(pins,
                new JsonSerializerOptions { WriteIndented = true }));
        }
        SessionLog.Log("cert-pin", $"{server}:{port}", "pinned", thumbprint);
    }
}
