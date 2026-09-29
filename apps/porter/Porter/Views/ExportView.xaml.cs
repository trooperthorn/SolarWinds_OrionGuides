using System.Collections.ObjectModel;
using System.ComponentModel;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Input;
using Microsoft.Win32;
using Porter.Areas;
using Porter.Core;

namespace Porter.Views;

public sealed class ExportRow : INotifyPropertyChanged
{
    private bool _isSelected;

    public required string Id { get; init; }
    public required string Name { get; init; }
    public required string UniqueKey { get; init; }
    public required bool IsSystem { get; init; }
    public string Detail { get; init; } = "";
    public string SystemLabel => IsSystem ? "built-in" : "";

    public bool IsSelected
    {
        get => _isSelected;
        set { if (_isSelected != value) { _isSelected = value; PropertyChanged?.Invoke(this, new(nameof(IsSelected))); } }
    }

    public event PropertyChangedEventHandler? PropertyChanged;
}

public partial class ExportView : UserControl
{
    private readonly MainWindow _shell;
    private readonly AreaProvider _provider;
    private readonly ObservableCollection<ExportRow> _rows = new();
    private readonly Dictionary<string, AreaItem> _items = new();
    private CheckBox? _headCheck;

    public ExportView(MainWindow shell, AreaProvider provider)
    {
        _shell = shell;
        _provider = provider;
        InitializeComponent();
        TitleText.Text = $"Export — {provider.DisplayName} · Cargo Manifest";
        if (provider.SecurityNotice is string notice)
        {
            SecurityNoticeText.Text = notice;
            SecurityNoticeText.Visibility = Visibility.Visible;
        }
        if (provider.OffersStripSensitive) StripSensitiveBox.Visibility = Visibility.Visible;
        if (provider.RequiresCipherPassword) CipherPanel.Visibility = Visibility.Visible;
        DestBox.Text = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
            "Porter", DateTime.Now.ToString("yyyy-MM-dd"));
        Grid.ItemsSource = _rows;
        var view = CollectionViewSource.GetDefaultView(_rows);
        view.Filter = RowVisible;
        Loaded += async (_, _) => await RefreshAsync();
    }

    private bool RowVisible(object o)
    {
        if (o is not ExportRow row) return false;
        if (row.IsSystem && ShowSystemBox.IsChecked != true) return false;
        var q = FilterBox.Text.Trim();
        return q.Length == 0
            || row.Name.Contains(q, StringComparison.OrdinalIgnoreCase)
            || row.UniqueKey.Contains(q, StringComparison.OrdinalIgnoreCase);
    }

    private bool _refreshing;

    private async Task RefreshAsync()
    {
        if (_shell.Session is null || _refreshing) return;
        _refreshing = true;
        _rows.Clear();
        _items.Clear();
        try
        {
            foreach (var item in await _provider.ListAsync(CancellationToken.None))
            {
                _items[item.Id] = item;
                var row = new ExportRow
                {
                    Id = item.Id, Name = item.Name, UniqueKey = item.Key,
                    IsSystem = item.IsSystem, Detail = item.Detail,
                };
                row.PropertyChanged += (_, _) => Recount();
                _rows.Add(row);
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show(ex.Message, $"Could not list {_provider.DisplayName}",
                MessageBoxButton.OK, MessageBoxImage.Error);
        }
        finally
        {
            _refreshing = false;
        }
        Recount();
    }

    private List<ExportRow> VisibleRows()
        => CollectionViewSource.GetDefaultView(_rows).Cast<ExportRow>().ToList();

    private void Recount()
    {
        var selected = _rows.Count(r => r.IsSelected);
        CountText.Text = $"{selected} of {_rows.Count} selected";
        ExportBtn.Content = $"Begin Transit ({selected})";
        ExportBtn.ToolTip = $"Export {selected} selected item{(selected == 1 ? "" : "s")}";
        ExportBtn.IsEnabled = selected > 0;
        if (_headCheck is not null)
        {
            var vis = VisibleRows();
            var visSel = vis.Count(r => r.IsSelected);
            _headCheck.IsChecked = vis.Count > 0 && visSel == vis.Count ? true
                : visSel == 0 ? false : null;
        }
    }

    private void HeadCheck_Loaded(object sender, RoutedEventArgs e)
    {
        _headCheck = (CheckBox)sender;
        Recount();
    }

    private void HeadCheck_Click(object sender, RoutedEventArgs e)
    {
        // Independent of the checkbox's own toggled state: all visible selected → clear,
        // anything else → select all visible. Recount() then repaints the box.
        var visible = VisibleRows();
        var target = !visible.All(r => r.IsSelected) || visible.Count == 0;
        foreach (var row in visible) row.IsSelected = target;
        Recount();
    }

    private void RowCheck_Click(object sender, RoutedEventArgs e) => Recount();
    private void All_Click(object sender, RoutedEventArgs e)
        { foreach (var row in VisibleRows()) row.IsSelected = true; Recount(); }
    private void None_Click(object sender, RoutedEventArgs e)
        { foreach (var row in _rows) row.IsSelected = false; Recount(); }   // ALL rows, hidden included

    private void Filter_Changed(object sender, TextChangedEventArgs e)
        { CollectionViewSource.GetDefaultView(_rows).Refresh(); Recount(); }

    private void ShowSystem_Changed(object sender, RoutedEventArgs e)
        { CollectionViewSource.GetDefaultView(_rows).Refresh(); Recount(); }

    private void Fmt_Changed(object sender, RoutedEventArgs e)
    {
        if (AesPass is null) return;    // Checked can fire during InitializeComponent
        AesPass.IsEnabled = FmtAes.IsChecked == true;
    }

    private async void Grid_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Space)
        {
            foreach (var row in Grid.SelectedItems.OfType<ExportRow>())
                row.IsSelected = !row.IsSelected;
            Recount();
            e.Handled = true;
        }
        else if (e.Key == Key.A && Keyboard.Modifiers.HasFlag(ModifierKeys.Control))
        {
            if (Keyboard.Modifiers.HasFlag(ModifierKeys.Shift))
                foreach (var row in _rows) row.IsSelected = false;          // uncheck ALL, hidden included
            else
                foreach (var row in VisibleRows()) row.IsSelected = true;
            Recount();
            e.Handled = true;
        }
        else if (e.Key == Key.F5)
        {
            await RefreshAsync();
            e.Handled = true;
        }
    }

    private void Browse_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFolderDialog { Title = "Landing site — choose the export destination" };
        if (dialog.ShowDialog() == true) DestBox.Text = dialog.FolderName;
    }

    private void Back_Click(object sender, RoutedEventArgs e)
        => _shell.Go(new AreaView(_shell), "Export · Constellations");

    /// <summary>
    /// Checks the landing site before the run starts, so a bad path fails at the console
    /// instead of after every item has been pulled from the server: it must be a full
    /// path, creatable, and writable (a temp file is written and removed as the probe).
    /// </summary>
    private static bool TryPrepareDestination(string dest, out string problem)
    {
        problem = "";
        if (string.IsNullOrWhiteSpace(dest))
        { problem = "Choose a landing site for the export first."; return false; }
        if (!Path.IsPathFullyQualified(dest))
        { problem = "The landing site must be a full path, such as C:\\Exports\\Porter."; return false; }
        try
        {
            Directory.CreateDirectory(dest);
            var probe = Path.Combine(dest, $".porter-write-test-{Guid.NewGuid():N}.tmp");
            File.WriteAllBytes(probe, new byte[] { 0 });
            File.Delete(probe);
            return true;
        }
        catch (Exception ex)
        {
            problem = $"Porter cannot write to that landing site: {ex.Message}";
            return false;
        }
    }

    private void Export_Click(object sender, RoutedEventArgs e)
    {
        if (_shell.Session is null) return;
        var picked = _rows.Where(r => r.IsSelected)
            .Select(r => _items[r.Id]).ToList();
        if (picked.Count == 0) return;
        if (FmtAes.IsChecked == true && AesPass.Password.Length == 0)
        {
            MessageBox.Show("Enter a package password, or choose a different output format.",
                "Password required", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }
        if (_provider.RequiresCipherPassword && CipherPass.Password.Length == 0)
        {
            MessageBox.Show("The platform requires a cipher password on every recording export. " +
                "Enter one — the same password will be needed at import.",
                "Cipher password required", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }
        var dest = DestBox.Text.Trim();
        if (!TryPrepareDestination(dest, out var destProblem))
        {
            MessageBox.Show(destProblem, "Landing site not usable",
                MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }
        var asZip = FmtZip.IsChecked == true || FmtAes.IsChecked == true;
        var aesPassword = FmtAes.IsChecked == true ? AesPass.Password : null;
        var options = new ExportOptions
        {
            StripSensitive = !_provider.OffersStripSensitive || StripSensitiveBox.IsChecked == true,
            CipherPassword = _provider.RequiresCipherPassword ? CipherPass.Password : null,
        };
        var session = _shell.Session;
        var platform = _shell.PlatformLabel;
        var provider = _provider;

        _shell.Go(new RunView(_shell, $"Mission Control — exporting {provider.DisplayName}",
            async (log, summary, ct) =>
        {
            var started = DateTime.UtcNow;
            var outcome = RunOutcome.Completed;
            var rawDir = Path.Combine(dest, provider.Key);
            // Package modes (zip / encrypted) collect everything and write once at the end:
            // "ok" is an audit claim that the output exists, so those audit lines are held
            // in `pending` until the package is on disk. Raw mode writes each file the
            // moment its export finishes, so an abort keeps what was already written.
            var items = new List<PackageItem>();
            var pending = new List<(string Target, string Detail, int Count)>();

            void Recorded(string target, string outcomeText, string detail)
            {
                summary.Items.Add(new RunItem(target, outcomeText, detail));
                SessionLog.Log("export", target, outcomeText, detail);
            }

            void Accept(PackageItem package, string target, string detail, int count)
            {
                if (asZip)
                {
                    items.Add(package);
                    pending.Add((target, detail, count));
                    return;
                }
                try
                {
                    PackageWriter.WriteRaw(rawDir, new[] { package });
                    summary.OutputPath = rawDir;
                    summary.Ok += count;
                    Recorded(target, "ok", detail);
                }
                catch (Exception ex) when (ex is not OperationCanceledException)
                {
                    log.Report($"  FAILED: output not written: {ex.Message}");
                    summary.Failed += count;
                    Recorded(target, "failed", $"output not written: {ex.Message}");
                }
            }

            try
            {
                if (provider.BulkExport)
                {
                    ct.ThrowIfCancellationRequested();
                    try
                    {
                        log.Report($"Export {picked.Count} item(s) → one {provider.FileExtension} file");
                        var export = await provider.ExportBulkAsync(picked, options, ct);
                        Accept(new PackageItem(provider.Key, $"{provider.Key}/{export.FileName}",
                            provider.DisplayName, export.Bytes, provider.ImportVia, "bulk"),
                            provider.Key, $"{picked.Count} items, bulk", picked.Count);
                    }
                    catch (Exception ex) when (ex is not OperationCanceledException)
                    {
                        log.Report($"  FAILED: {ex.Message}");
                        summary.Failed = picked.Count;
                        Recorded(provider.Key, "failed", ex.Message);
                    }
                }
                else
                {
                    foreach (var item in picked)
                    {
                        ct.ThrowIfCancellationRequested();
                        try
                        {
                            log.Report($"Export \"{item.Name}\" (id {item.Id})");
                            var export = await provider.ExportAsync(item, options, ct);
                            Accept(new PackageItem(provider.Key, $"{provider.Key}/{export.FileName}",
                                item.Name, export.Bytes, provider.ImportVia, "skip-or-copy-selected-at-import"),
                                item.Name, $"{provider.Key} {item.Id}", 1);
                        }
                        catch (Exception ex) when (ex is not OperationCanceledException)
                        {
                            log.Report($"  FAILED: {ex.Message}");
                            summary.Failed++;
                            Recorded(item.Name, "failed", ex.Message);
                        }
                    }
                }

                if (items.Count == 0)
                {
                    if (summary.OutputPath is null) log.Report("Nothing exported — no output written.");
                    else log.Report($"Output → {summary.OutputPath}");
                    return;
                }

                // Package modes: the single write happens here.
                ct.ThrowIfCancellationRequested();
                string where;
                try
                {
                    where = PackageWriter.WritePackage(dest, session.Server, platform, items, aesPassword);
                }
                catch (Exception ex) when (ex is not OperationCanceledException)
                {
                    // The items were fetched but nothing reached the disk: none of them may
                    // be recorded as exported.
                    log.Report($"  FAILED: output not written: {ex.Message}");
                    foreach (var (target, _, count) in pending)
                    {
                        summary.Failed += count;
                        Recorded(target, "failed", $"output not written: {ex.Message}");
                    }
                    outcome = RunOutcome.Failed;
                    return;
                }
                foreach (var (target, detail, count) in pending)
                {
                    summary.Ok += count;
                    Recorded(target, "ok", detail);
                }
                log.Report($"Output → {where}");
                summary.OutputPath = where;
            }
            catch (OperationCanceledException)
            {
                outcome = RunOutcome.Cancelled;
                if (pending.Count > 0)
                {
                    // Package modes write once at the end, so an abort means no output.
                    foreach (var (target, _, count) in pending)
                    {
                        summary.Skipped += count;
                        Recorded(target, "cancelled", "aborted before the package was written");
                    }
                    log.Report($"Aborted — {pending.Sum(p => p.Count)} item(s) were fetched but " +
                        "no package was written. Nothing was saved.");
                }
                else
                    log.Report("Aborted.");
                throw;
            }
            catch (Exception)
            {
                outcome = RunOutcome.Failed;
                throw;
            }
            finally
            {
                if (outcome == RunOutcome.Completed && summary.Failed > 0 && summary.Ok == 0)
                    outcome = RunOutcome.Failed;
                RunReport.WriteAndLog(dest, new RunReportData("export", provider.Key, session.Server,
                    false, started, DateTime.UtcNow, outcome, summary));
                if (summary.ReportPath is not null) log.Report($"Run report → {summary.ReportPath}");
            }
        }), "Export · Mission Control");
    }
}
