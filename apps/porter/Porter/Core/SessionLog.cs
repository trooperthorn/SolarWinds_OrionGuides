using System.IO;
using System.Text.Json;

namespace Porter.Core;

/// <summary>
/// JSONL audit log in %ProgramData%\Porter\logs — one file per app session, one line per
/// action, written before the UI reports success. Never logs passwords or payload bodies.
/// </summary>
public static class SessionLog
{
    private static readonly object Gate = new();
    private static string? _path;

    public static string LogDir => Path.Combine(AppDirs.Base, "logs");

    public static string CurrentPath
    {
        get
        {
            lock (Gate)
            {
                if (_path is null)
                {
                    Directory.CreateDirectory(LogDir);
                    if (File.GetAttributes(LogDir).HasFlag(FileAttributes.ReparsePoint))
                        throw new IOException($"{LogDir} is a reparse point. Refusing to log through it.");
                    _path = Path.Combine(LogDir, $"{DateTime.Now:yyyy-MM-dd_HHmmss}.jsonl");
                }
                return _path;
            }
        }
    }

    public static void Log(string action, string target, string outcome, string? detail = null)
    {
        var line = JsonSerializer.Serialize(new
        {
            ts = DateTime.UtcNow.ToString("o"),
            action,
            target,
            outcome,
            detail,
        });
        lock (Gate)
        {
            File.AppendAllText(CurrentPath, line + Environment.NewLine);
        }
    }
}
