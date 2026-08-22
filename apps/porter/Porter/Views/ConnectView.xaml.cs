using System.Net.Http;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Porter.Core;

namespace Porter.Views;

public partial class ConnectView : UserControl
{
    private readonly MainWindow _shell;

    public ConnectView(MainWindow shell)
    {
        _shell = shell;
        InitializeComponent();

        // Coming Back while connected shows the live session; otherwise the last
        // successful connect is remembered (server, port, auth mode, username — never
        // the password, which must always be re-entered). The memory read runs off the
        // UI thread after Loaded: its first touch of %ProgramData%\Porter triggers the
        // icacls hardening, which must not stall the window from appearing.
        if (_shell.Session is SwisSession live)
        {
            ServerBox.Text = live.Server;
            PortBox.Text = live.Port.ToString();
            WinAuthBox.IsChecked = live.WindowsAuth;
            UserBox.Text = live.Username ?? "";
            VerifyTlsBox.IsChecked = live.VerifyTls;
        }
        else
        {
            Loaded += async (_, _) =>
            {
                var last = await Task.Run(ConnectionMemory.Load);
                if (last is null || ServerBox.Text.Trim().Length > 0) return;
                ServerBox.Text = last.Server;
                PortBox.Text = last.Port.ToString();
                WinAuthBox.IsChecked = last.WindowsAuth;
                UserBox.Text = last.Username;
                VerifyTlsBox.IsChecked = last.VerifyTls;
            };
        }
    }

    private void WinAuth_Changed(object sender, RoutedEventArgs e)
    {
        var winAuth = WinAuthBox.IsChecked == true;
        UserBox.IsEnabled = !winAuth;
        PassBox.IsEnabled = !winAuth;
    }

    private async void Test_Click(object sender, RoutedEventArgs e)
        => await AttemptAsync(connectAfter: false);

    private async void Connect_Click(object sender, RoutedEventArgs e)
        => await AttemptAsync(connectAfter: true);

    private async Task AttemptAsync(bool connectAfter)
    {
        var server = ServerBox.Text.Trim();
        if (server.Length == 0) { Fail("Enter a server name or address."); return; }
        if (Uri.CheckHostName(server) == UriHostNameType.Unknown)
        { Fail("That does not look like a hostname, FQDN, or IP address. Enter the server only — no https:// and no path."); return; }
        if (!int.TryParse(PortBox.Text.Trim(), out var port) || port < 1 || port > 65535)
        { Fail("Port must be a number between 1 and 65535 (SWIS REST default: 17774)."); return; }
        var winAuth = WinAuthBox.IsChecked == true;
        if (!winAuth && UserBox.Text.Trim().Length == 0) { Fail("Enter a username, or tick the Windows account option."); return; }

        TestBtn.IsEnabled = ConnectBtn.IsEnabled = false;
        Info("Connecting…");
        SwisSession? session = null;
        try
        {
            var verifyTls = VerifyTlsBox.IsChecked == true;
            session = new SwisSession(server, port, winAuth, UserBox.Text.Trim(), PassBox.Password, verifyTls);
            await session.TestAsync();
            var label = await PlatformLabelAsync(session);
            var tlsNote = session.VerifyTls ? "TLS verified"
                : $"TLS unverified — fingerprint logged{(session.PresentedThumbprint is null ? "" : $" ({session.PresentedThumbprint[..12]}…)")}";
            Ok($"Docking complete — {server}:{port} · {label} · {tlsNote}");
            SessionLog.Log("connect", $"{server}:{port}", "ok", winAuth ? "windows-auth" : UserBox.Text.Trim());
            if (connectAfter)
            {
                ConnectionMemory.Save(new LastConnection(
                    server, port, winAuth, UserBox.Text.Trim(), verifyTls));
                _shell.Session?.Dispose();
                _shell.Session = session;
                _shell.PlatformLabel = label;
                _shell.Go(new ModeView(_shell), "Direction");
                return;
            }
            session.Dispose();
        }
        catch (HttpRequestException) when (session?.LastUntrustedThumbprint is not null)
        {
            var thumb = session.LastUntrustedThumbprint!;
            var subject = session.LastUntrustedSubject ?? "(unknown subject)";
            session.Dispose();
            var pin = MessageBox.Show(
                "The server presented a certificate Porter does not trust.\n\n" +
                $"Subject: {subject}\n" +
                $"SHA-256: {thumb}\n\n" +
                "Pin this certificate for this server? The pin is recorded in the audit log.",
                "First contact — unknown certificate", MessageBoxButton.YesNo, MessageBoxImage.Warning);
            if (pin == MessageBoxResult.Yes)
            {
                CertPinStore.Pin(server, port, thumb);
                await AttemptAsync(connectAfter);
                return;
            }
            Fail("Not connected — certificate was not pinned.");
        }
        catch (SwisException ex) when (winAuth && ex.StatusCode == 401)
        {
            session?.Dispose();
            Fail("This server's SWIS REST endpoint did not accept your Windows session — the " +
                 "documented REST contract offers basic authentication only. Untick the Windows " +
                 "account option and enter a username and password. (Windows-session auth over " +
                 "the SOAP endpoint on 17777 is a pinned item.)");
            SessionLog.Log("connect", $"{server}:{port}", "failed", "windows-auth 401");
        }
        catch (Exception ex)
        {
            session?.Dispose();
            Fail(ex.Message);
            SessionLog.Log("connect", $"{server}:{port}", "failed", ex.Message);
        }
        finally
        {
            TestBtn.IsEnabled = ConnectBtn.IsEnabled = true;
        }
    }

    private static async Task<string> PlatformLabelAsync(SwisSession session)
    {
        try
        {
            var rows = await session.QueryAsync(
                "SELECT TOP 1 EngineVersion FROM Orion.Engines WHERE ServerType = 'Primary'");
            foreach (var row in rows.EnumerateArray())
                return "Platform " + (row.GetProperty("EngineVersion").GetString() ?? "?");
        }
        catch (SwisException) { }
        return "SWIS v3";
    }

    private void Info(string text) { StatusText.Foreground = Brushes.Gray; StatusText.Text = text; }
    private void Ok(string text) { StatusText.Foreground = Brushes.DarkGreen; StatusText.Text = text; }
    private void Fail(string text) { StatusText.Foreground = Brushes.DarkRed; StatusText.Text = text; }
}
