using System.Windows;
using Porter.Core;

namespace Porter;

public partial class App : Application
{
    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
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
