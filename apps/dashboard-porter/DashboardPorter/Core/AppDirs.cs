using System.Diagnostics;
using System.IO;

namespace DashboardPorter.Core;

/// <summary>
/// %ProgramData%\DashboardPorter, hardened. ProgramData's default ACLs let a standard user
/// pre-create subdirectories (and plant files, or a junction), so on first use DashboardPorter
/// (running elevated) resets the directory's DACL to Administrators + SYSTEM only via
/// icacls (owner reset to Administrators, DACL replaced, recursively so anything already
/// planted inside is re-owned too), refuses to operate through a reparse point, and
/// records the hardening outcome. Ported from apps/porter/Porter/Core/AppDirs.cs.
/// SessionLog needs AppDirs.Base, so this class cannot log while it initialises; the
/// outcome is parked in <see cref="HardeningOutcome"/> and App startup logs it once.
/// </summary>
public static class AppDirs
{
    private static readonly Lazy<string> _base = new(Prepare);

    public static string Base => _base.Value;

    /// <summary>What the icacls hardening pass did: (outcome, detail). Outcome is
    /// "hardened" or "hardening-failed". Best-effort — a failure is logged, never thrown.</summary>
    public static (string Outcome, string Detail) HardeningOutcome { get; private set; }
        = ("hardening-failed", "not run yet");

    private static string Prepare()
    {
        var dir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "DashboardPorter");
        Directory.CreateDirectory(dir);

        // Fail closed on a junction/symlink — the classic ProgramData escalation primitive.
        if (File.GetAttributes(dir).HasFlag(FileAttributes.ReparsePoint))
            throw new IOException(
                $"{dir} is a reparse point (junction/symlink). Refusing to use it — delete it and restart DashboardPorter.");

        // Reset the owner (a pre-created directory may be owned by a standard user, who
        // could then rewrite the DACL at will), then the DACL: no inheritance,
        // BUILTIN\Administrators (S-1-5-32-544) and SYSTEM (S-1-5-18) full control,
        // nothing else. /T recurses so planted children are covered. SIDs, not names —
        // locale-safe.
        var icacls = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.Windows), "System32", "icacls.exe");
        try
        {
            var failures = new List<string>();
            foreach (var args in new[]
            {
                $"\"{dir}\" /setowner *S-1-5-32-544 /T /C /Q",
                $"\"{dir}\" /inheritance:r /grant:r *S-1-5-32-544:(OI)(CI)F *S-1-5-18:(OI)(CI)F /T /C /Q",
            })
            {
                var psi = new ProcessStartInfo(icacls, args) { UseShellExecute = false, CreateNoWindow = true };
                using var proc = Process.Start(psi);
                if (proc is null) { failures.Add("icacls did not start"); continue; }
                if (!proc.WaitForExit(15000))
                {
                    try { proc.Kill(); } catch (Exception) { /* already gone */ }
                    failures.Add("icacls timed out");
                }
                else if (proc.ExitCode != 0)
                    failures.Add($"icacls exit code {proc.ExitCode}");
            }
            HardeningOutcome = failures.Count == 0
                ? ("hardened", "owner reset to Administrators; DACL = Administrators + SYSTEM")
                : ("hardening-failed", string.Join("; ", failures));
        }
        catch (Exception ex)
        {
            // Hardening best-effort on exotic systems; the reparse check above still holds.
            HardeningOutcome = ("hardening-failed", ex.Message);
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
