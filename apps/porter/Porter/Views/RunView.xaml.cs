using System.Diagnostics;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using Porter.Core;

namespace Porter.Views;

public sealed class RunSummary
{
    public int Ok;
    public int Warn;
    public int Failed;
    public int Skipped;
    public List<string> SkippedNames { get; } = new();
    public List<string> CopyNotes { get; } = new();
    public string? OutputPath;
}

public partial class RunView : UserControl
{
    private readonly MainWindow _shell;
    private readonly Func<IProgress<string>, CancellationToken, Task<RunSummary>> _job;
    private RunSummary? _summary;

    public RunView(MainWindow shell, string title,
        Func<IProgress<string>, CancellationToken, Task<RunSummary>> job)
    {
        _shell = shell;
        _job = job;
        InitializeComponent();
        TitleText.Text = title;
        Loaded += RunView_Loaded;
    }

    private bool _started;

    private async void RunView_Loaded(object sender, RoutedEventArgs e)
    {
        if (_started) return;
        _started = true;
        var progress = new Progress<string>(line =>
        {
            LogBox.AppendText($"[{DateTime.Now:HH:mm:ss}] {line}\r\n");
            LogBox.ScrollToEnd();
        });
        try
        {
            _summary = await _job(progress, CancellationToken.None);
            ChipsText.Text =
                $"OK {_summary.Ok}   ·   Warnings {_summary.Warn}   ·   Skipped {_summary.Skipped}   ·   Failed {_summary.Failed}";
            var detail = new List<string>();
            if (_summary.SkippedNames.Count > 0)
                detail.Add("Skipped: " + string.Join(" · ", _summary.SkippedNames));
            if (_summary.CopyNotes.Count > 0)
                detail.Add("Imported as copies: " + string.Join(" · ", _summary.CopyNotes));
            DetailText.Text = string.Join("\n", detail);
            OpenOutBtn.IsEnabled = _summary.OutputPath is not null;
        }
        catch (Exception ex)
        {
            ChipsText.Text = "Run failed";
            DetailText.Text = ex.Message;
            SessionLog.Log("run", TitleText.Text, "failed", ex.Message);
        }
        finally
        {
            DoneBtn.IsEnabled = true;
        }
    }

    // Absolute path: an elevated process must never resolve "explorer.exe" through the
    // working directory (CWE-427 binary planting — think a USB stick the exe runs from).
    private static string ExplorerPath => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.Windows), "explorer.exe");

    private void OpenLog_Click(object sender, RoutedEventArgs e)
    {
        SessionLog.Log("ui", "session-log", "opened");
        Process.Start(new ProcessStartInfo(ExplorerPath,
            $"/select,\"{SessionLog.CurrentPath}\"") { UseShellExecute = true });
    }

    private void OpenOut_Click(object sender, RoutedEventArgs e)
    {
        if (_summary?.OutputPath is not string path) return;
        var target = Directory.Exists(path) ? path : Path.GetDirectoryName(path)!;
        Process.Start(new ProcessStartInfo(ExplorerPath, $"\"{target}\"") { UseShellExecute = true });
    }

    private void Done_Click(object sender, RoutedEventArgs e)
        => _shell.Go(new ModeView(_shell), "Direction");
}
