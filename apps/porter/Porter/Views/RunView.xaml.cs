using System.Diagnostics;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using Porter.Core;

namespace Porter.Views;

public partial class RunView : UserControl
{
    private readonly MainWindow _shell;
    private readonly Func<IProgress<string>, RunSummary, CancellationToken, Task> _job;
    // The view owns the summary and the token source: the job reports into the summary as
    // it goes, so an abort can still show exactly how far the run got.
    private readonly RunSummary _summary = new();
    private readonly CancellationTokenSource _cts = new();

    public RunView(MainWindow shell, string title,
        Func<IProgress<string>, RunSummary, CancellationToken, Task> job)
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
            await _job(progress, _summary, _cts.Token);
            ShowSummary("");
        }
        catch (OperationCanceledException)
        {
            ShowSummary("Aborted");
            SessionLog.Log("run", TitleText.Text, "cancelled");
        }
        catch (Exception ex)
        {
            ShowSummary("Run failed");
            DetailText.Text = string.Join("\n", new[] { ex.Message, DetailText.Text }
                .Where(t => !string.IsNullOrEmpty(t)));
            SessionLog.Log("run", TitleText.Text, "failed", ex.Message);
        }
        finally
        {
            AbortBtn.IsEnabled = false;
            DoneBtn.IsEnabled = true;
        }
    }

    /// <summary>Counts and detail from whatever the job reported so far — complete or partial.</summary>
    private void ShowSummary(string suffix)
    {
        var chips =
            $"OK {_summary.Ok}   ·   Warnings {_summary.Warn}   ·   Skipped {_summary.Skipped}   ·   Failed {_summary.Failed}";
        ChipsText.Text = suffix.Length > 0 ? $"{chips}   ·   {suffix}" : chips;
        var detail = new List<string>();
        if (_summary.SkippedNames.Count > 0)
            detail.Add("Skipped: " + string.Join(" · ", _summary.SkippedNames));
        if (_summary.CopyNotes.Count > 0)
            detail.Add("Imported as copies: " + string.Join(" · ", _summary.CopyNotes));
        if (_summary.ReportPath is not null)
            detail.Add("Run report: " + _summary.ReportPath);
        DetailText.Text = string.Join("\n", detail);
        OpenOutBtn.IsEnabled = _summary.OutputPath is not null;
    }

    private void Abort_Click(object sender, RoutedEventArgs e)
    {
        AbortBtn.IsEnabled = false;
        AbortBtn.Content = "Aborting…";
        SessionLog.Log("run", TitleText.Text, "abort-requested");
        _cts.Cancel();
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
        if (_summary.OutputPath is not string path) return;
        var target = Directory.Exists(path) ? path : Path.GetDirectoryName(path)!;
        Process.Start(new ProcessStartInfo(ExplorerPath, $"\"{target}\"") { UseShellExecute = true });
    }

    private void Done_Click(object sender, RoutedEventArgs e)
        => _shell.Go(new ModeView(_shell), "Direction");
}
