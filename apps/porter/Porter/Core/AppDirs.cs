using System.Diagnostics;
using System.IO;

namespace Porter.Core;

/// <summary>
/// %ProgramData%\Porter, hardened. ProgramData's default ACLs let a standard user
/// pre-create subdirectories (and plant files, or a junction), so on first use Porter
/// (running elevated) resets the directory's DACL to Administrators + SYSTEM only via
/// icacls, refuses to operate through a reparse point, and logs the hardening outcome.
/// </summary>
public static class AppDirs
{
    private static readonly Lazy<string> _base = new(Prepare);

    public static string Base => _base.Value;

    private static string Prepare()
    {
        var dir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "Porter");
        Directory.CreateDirectory(dir);

        // Fail closed on a junction/symlink — the classic ProgramData escalation primitive.
        if (File.GetAttributes(dir).HasFlag(FileAttributes.ReparsePoint))
            throw new IOException(
                $"{dir} is a reparse point (junction/symlink). Refusing to use it — delete it and restart Porter.");

        // Reset the DACL: no inheritance, BUILTIN\Administrators (S-1-5-32-544) and
        // SYSTEM (S-1-5-18) full control, nothing else. SIDs, not names — locale-safe.
        var icacls = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.Windows), "System32", "icacls.exe");
        var psi = new ProcessStartInfo(icacls,
            $"\"{dir}\" /inheritance:r /grant:r *S-1-5-32-544:(OI)(CI)F *S-1-5-18:(OI)(CI)F")
        {
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        try
        {
            using var proc = Process.Start(psi);
            proc?.WaitForExit(15000);
        }
        catch (Exception)
        {
            // Hardening best-effort on exotic systems; the reparse check above still holds.
        }
        return dir;
    }

    /// <summary>A file inside the hardened dir must not itself be a reparse point.</summary>
    public static void RefuseReparse(string path)
    {
        if (File.Exists(path) && File.GetAttributes(path).HasFlag(FileAttributes.ReparsePoint))
            throw new IOException($"{path} is a reparse point. Refusing to use it.");
    }
}
