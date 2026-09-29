using System.Windows;
using Porter.Core;

namespace Porter;

public partial class App : Application
{
    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        try
        {
            // Touch Base first so the hardening pass has run, then record how it went —
            // AppDirs cannot log itself (SessionLog depends on AppDirs.Base).
            var dir = AppDirs.Base;
            var (outcome, detail) = AppDirs.HardeningOutcome;
            SessionLog.Log("appdirs", dir, outcome, detail);
        }
        catch (Exception ex)
        {
            MessageBox.Show(ex.Message, "Porter — cannot start",
                MessageBoxButton.OK, MessageBoxImage.Error);
            Shutdown(1);
            return;
        }
        DispatcherUnhandledException += (_, args) =>
        {
            try { SessionLog.Log("error", "unhandled", "dispatcher", args.Exception.ToString()); }
            catch { /* the dialog must appear even if logging is what broke */ }
            MessageBox.Show(args.Exception.Message, "Porter — unexpected error",
                MessageBoxButton.OK, MessageBoxImage.Error);
            args.Handled = true;
        };
    }
}
