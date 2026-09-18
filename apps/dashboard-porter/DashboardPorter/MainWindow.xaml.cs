using System.Windows;
using System.Windows.Controls;
using DashboardPorter.Core;
using DashboardPorter.Views;

namespace DashboardPorter;

public partial class MainWindow : Window
{
    // Shared app state — one session at a time. There is no mode/area choice to carry,
    // because this app only ever moves Modern Dashboards.
    public SwisSession? Session { get; set; }
    public string PlatformLabel { get; set; } = "";

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
