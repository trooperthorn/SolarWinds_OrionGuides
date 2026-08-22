using System.Windows;
using System.Windows.Controls;
using Porter.Core;
using Porter.Views;

namespace Porter;

public partial class MainWindow : Window
{
    // Shared app state — one session, one direction, one area at a time.
    public SwisSession? Session { get; set; }
    public string PlatformLabel { get; set; } = "";
    public bool ModeIsExport { get; set; } = true;

    public MainWindow()
    {
        InitializeComponent();
        Go(new ConnectView(this), "Connect");
    }

    public void Go(UserControl view, string crumb)
    {
        Host.Content = view;
        Crumb.Text = crumb;
        SessionBadge.Text = Session is null
            ? "not connected"
            : $"{Session.Server}:{Session.Port} · {(Session.WindowsAuth ? "Windows session" : Session.Username)} · {PlatformLabel}";
    }
}
