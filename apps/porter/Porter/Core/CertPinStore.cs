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
            // Refuse a planted link, then write a temp file beside the target and move it
            // into place: a crash mid-write can never leave a truncated pins.json (which
            // Load would read as "no pins" and silently drop every pinned certificate).
            AppDirs.RefuseReparse(PinPath);
            var temp = Path.Combine(BaseDir, $"pins.{Guid.NewGuid():N}.tmp");
            try
            {
                File.WriteAllText(temp, JsonSerializer.Serialize(pins,
                    new JsonSerializerOptions { WriteIndented = true }));
                File.Move(temp, PinPath, overwrite: true);
            }
            finally
            {
                if (File.Exists(temp)) File.Delete(temp);
            }
        }
        SessionLog.Log("cert-pin", $"{server}:{port}", "pinned", thumbprint);
    }
}
