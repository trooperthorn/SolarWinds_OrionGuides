using System.Collections.ObjectModel;
using System.ComponentModel;
using System.IO;
using System.Text;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Input;
using Microsoft.Win32;
using DashboardPorter.Core;

namespace DashboardPorter.Views;

public sealed class ExportRow : INotifyPropertyChanged
{
    private bool _isSelected;

    public required int Id { get; init; }
    public required string Name { get; init; }
    public required string UniqueKey { get; init; }
    public required bool IsSystem { get; init; }
    public string SystemLabel => IsSystem ? "built-in" : "";

    public bool IsSelected
    {
        get => _isSelected;
        set { if (_isSelected != value) { _isSelected = value; PropertyChanged?.Invoke(this, new(nameof(IsSelected))); } }
    }

    public event PropertyChangedEventHandler? PropertyChanged;
}

public sealed class StagedFile
{
    public required string FileName { get; init; }
    public required string Text { get; init; }
    public required DashboardValidation Validation { get; init; }
    public string StatusGlyph => !Validation.Ok ? "✕"
        : Validation.Warnings.Count > 0 ? "⚠" : "✓";
    public string Summary => Validation.Summary;
}

/// <summary>
/// A single tabbed Export/Import view for Modern Dashboards — a deliberate simplification
/// of Porter's separate ExportView/ImportView, because this tool only ever moves one area.
/// Export logic ported from Porter/Views/ExportView.xaml.cs, import staging and run logic
/// from Porter/Views/ImportView.xaml.cs, both narrowed from the generic AreaProvider
/// contract straight onto DashboardsCore/DashboardValidator.
/// </summary>
public partial class ExportImportView : UserControl
{
    private const string FileExtension = ".json";

    private readonly MainWindow _shell;
    private readonly DashboardsCore _core;
    private readonly ObservableCollection<ExportRow> _rows = new();
    private readonly Dictionary<int, DashboardListRow> _items = new();
    private readonly ObservableCollection<StagedFile> _staged = new();
    private CheckBox? _headCheck;

    public ExportImportView(MainWindow shell)
    {
        _shell = shell;
        _core = new DashboardsCore(shell.Session!);
        InitializeComponent();

        DestBox.Text = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
            "DashboardPorter", DateTime.Now.ToString("yyyy-MM-dd"));
        Grid.ItemsSource = _rows;
        var view = CollectionViewSource.GetDefaultView(_rows);
        view.Filter = RowVisible;

        StageList.ItemsSource = _staged;
        UpdateImportButtons();

        Loaded += async (_, _) => await RefreshAsync();
    }

    // ---------------------------------------------------------------- Export tab

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
            foreach (var item in await _core.ListAsync(CancellationToken.None))
            {
                _items[item.Id] = item;
                var row = new ExportRow
                {
                    Id = item.Id, Name = item.Name, UniqueKey = item.UniqueKey, IsSystem = item.IsSystem,
                };
                row.PropertyChanged += (_, _) => Recount();
                _rows.Add(row);
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show(ex.Message, "Could not list Modern Dashboards",
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
        ExportBtn.Content = $"Export ({selected})";
        ExportBtn.ToolTip = $"Export {selected} selected dashboard{(selected == 1 ? "" : "s")}";
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
                foreach (var row in _rows) row.IsSelected = false;
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
        var dialog = new OpenFolderDialog { Title = "Choose the export destination" };
        if (dialog.ShowDialog() == true) DestBox.Text = dialog.FolderName;
    }

    /// <summary>Ported from Porter's ExportView: the destination must be a full path that
    /// exists (or can be created) and accepts a write, checked before anything is fetched —
    /// so an unusable folder fails up front instead of after every dashboard was exported.</summary>
    private static bool TryPrepareDestination(string dest, out string problem)
    {
        problem = "";
        if (string.IsNullOrWhiteSpace(dest))
        { problem = "Choose a destination folder for the export first."; return false; }
        if (!Path.IsPathFullyQualified(dest))
        { problem = "The destination must be a full path, such as C:\\Exports\\DashboardPorter."; return false; }
        try
        {
            Directory.CreateDirectory(dest);
            var probe = Path.Combine(dest, $".dashboardporter-write-test-{Guid.NewGuid():N}.tmp");
            File.WriteAllBytes(probe, new byte[] { 0 });
            File.Delete(probe);
            return true;
        }
        catch (Exception ex)
        {
            problem = $"DashboardPorter cannot write to that folder: {ex.Message}";
            return false;
        }
    }

    private void Export_Click(object sender, RoutedEventArgs e)
    {
        if (_shell.Session is null) return;
        var picked = _rows.Where(r => r.IsSelected).Select(r => _items[r.Id]).ToList();
        if (picked.Count == 0) return;
        if (FmtAes.IsChecked == true && AesPass.Password.Length == 0)
        {
            MessageBox.Show("Enter a package password, or choose a different output format.",
                "Password required", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }
        var dest = DestBox.Text.Trim();
        if (!TryPrepareDestination(dest, out var destProblem))
        {
            MessageBox.Show(destProblem, "Destination not usable",
                MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }
        var asZip = FmtZip.IsChecked == true || FmtAes.IsChecked == true;
        var aesPassword = FmtAes.IsChecked == true ? AesPass.Password : null;
        var session = _shell.Session;
        var platform = _shell.PlatformLabel;
        var core = _core;

        // Ported from Porter's ExportView: package modes collect everything and write once
        // at the end, so "ok" (an audit claim that the output exists) is held in `pending`
        // until the package is on disk. Raw mode writes each file the moment its export
        // finishes, so an abort keeps what was already written.
        _shell.Go(new RunView(_shell, "Exporting Modern Dashboards",
            async (log, summary, ct) =>
        {
            var started = DateTime.UtcNow;
            var outcome = RunOutcome.Completed;
            var rawDir = Path.Combine(dest, PackageReader.AreaKey);
            var items = new List<PackageItem>();
            var pending = new List<(string Target, string Detail)>();

            void Recorded(string target, string outcomeText, string detail)
            {
                summary.Items.Add(new RunItem(target, outcomeText, detail));
                SessionLog.Log("export", target, outcomeText, detail);
            }

            void Accept(PackageItem package, string target, string detail)
            {
                if (asZip)
                {
                    items.Add(package);
                    pending.Add((target, detail));
                    return;
                }
                try
                {
                    PackageWriter.WriteRaw(rawDir, new[] { package });
                    summary.OutputPath = rawDir;
                    summary.Ok++;
                    Recorded(target, "ok", detail);
                }
                catch (Exception ex) when (ex is not OperationCanceledException)
                {
                    log.Report($"  FAILED: output not written: {ex.Message}");
                    summary.Failed++;
                    Recorded(target, "failed", $"output not written: {ex.Message}");
                }
            }

            try
            {
                foreach (var item in picked)
                {
                    ct.ThrowIfCancellationRequested();
                    try
                    {
                        log.Report($"Export \"{item.Name}\" (id {item.Id})");
                        var definition = await core.ExportAsync(item.Id, ct);
                        var fileName = PackageWriter.Sanitize(item.Name) + FileExtension;
                        Accept(new PackageItem($"{PackageReader.AreaKey}/{fileName}", item.Name,
                            Encoding.UTF8.GetBytes(definition), "skip-or-copy-selected-at-import"),
                            item.Name, $"dashboard {item.Id}");
                    }
                    catch (Exception ex) when (ex is not OperationCanceledException)
                    {
                        log.Report($"  FAILED: {ex.Message}");
                        summary.Failed++;
                        Recorded(item.Name, "failed", ex.Message);
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
                    // The dashboards were fetched but nothing reached the disk: none of them
                    // may be recorded as exported.
                    log.Report($"  FAILED: output not written: {ex.Message}");
                    foreach (var (target, _) in pending)
                    {
                        summary.Failed++;
                        Recorded(target, "failed", $"output not written: {ex.Message}");
                    }
                    outcome = RunOutcome.Failed;
                    return;
                }
                foreach (var (target, detail) in pending)
                {
                    summary.Ok++;
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
                    foreach (var (target, _) in pending)
                    {
                        summary.Skipped++;
                        Recorded(target, "cancelled", "aborted before the package was written");
                    }
                    log.Report($"Aborted — {pending.Count} dashboard(s) were fetched but " +
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
                RunReport.WriteAndLog(dest, new RunReportData("export", PackageReader.AreaKey,
                    session.Server, false, started, DateTime.UtcNow, outcome, summary));
                if (summary.ReportPath is not null) log.Report($"Run report → {summary.ReportPath}");
            }
        }), "Export · Modern Dashboards");
    }

    // ---------------------------------------------------------------- Import tab

    private void Drag_Over(object sender, DragEventArgs e)
    {
        e.Effects = e.Data.GetDataPresent(DataFormats.FileDrop)
            ? DragDropEffects.Copy : DragDropEffects.None;
        e.Handled = true;
    }

    private void Drop_Files(object sender, DragEventArgs e)
    {
        if (e.Data.GetData(DataFormats.FileDrop) is string[] paths) Stage(paths);
    }

    private void ImportBrowse_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog
        {
            Multiselect = true,
            Filter = "Dashboard files|*.json|Packages|*.zip;*.aes|All files|*.*",
        };
        if (dialog.ShowDialog() == true) Stage(dialog.FileNames);
    }

    private void Stage(IEnumerable<string> paths)
    {
        foreach (var path in paths)
        {
            try
            {
                var contents = PackageReader.Read(path, PromptPassword);
                foreach (var entry in contents.Entries)
                {
                    var validation = DashboardValidator.Validate(entry.Text);
                    // Origin findings lead the lists so they become the row summary: a
                    // modified or unlisted file must never read as "all checks pass".
                    validation.Errors.InsertRange(0, entry.Errors);
                    validation.Warnings.InsertRange(0, entry.Warnings);
                    validation.Source = SourceLine(contents.Info);
                    _staged.Add(new StagedFile
                    {
                        FileName = entry.DisplayName,
                        Text = entry.Text,
                        Validation = validation,
                    });
                }
            }
            catch (Exception ex)
            {
                var invalid = new DashboardValidation();
                invalid.Errors.Add(ex.Message);
                _staged.Add(new StagedFile
                {
                    FileName = Path.GetFileName(path), Text = "", Validation = invalid,
                });
            }
        }
        UpdateImportButtons();
    }

    /// <summary>The only UI the package reader needs: ask for a package password, null on cancel.</summary>
    private string? PromptPassword(string fileName)
    {
        var dialog = new PasswordDialog($"Package password for {fileName}")
            { Owner = Window.GetWindow(this) };
        return dialog.ShowDialog() == true ? dialog.Password : null;
    }

    /// <summary>"from core-orion · Orion 2026.2 · 2026-09-01T…" for a package with a
    /// manifest, else empty. Shown as recorded — no version arithmetic is done on it.</summary>
    private static string SourceLine(PackageInfo info)
    {
        if (!info.HasManifest) return "";
        var parts = new[] { info.SourceServer, info.SourcePlatform, info.Created }
            .Where(p => !string.IsNullOrWhiteSpace(p)).ToList();
        return parts.Count == 0 ? "" : $"from {string.Join(" · ", parts)}";
    }

    private void ClearStaged_Click(object sender, RoutedEventArgs e)
    {
        _staged.Clear();
        UpdateImportButtons();
    }

    private void UpdateImportButtons()
    {
        if (ImportBtn is null || DryRunBtn is null) return;
        var importable = Importable().Count;
        ImportBtn.Content = $"Import ({importable})";
        ImportBtn.ToolTip = $"Import {importable} staged file{(importable == 1 ? "" : "s")}";
        ImportBtn.IsEnabled = importable > 0 && _shell.Session is not null;
        DryRunBtn.IsEnabled = _staged.Count > 0 && _shell.Session is not null;
    }

    private List<StagedFile> Importable()
        => _staged.Where(f => f.Validation.Ok &&
               (AllowWarnBox.IsChecked == true || f.Validation.Warnings.Count == 0)).ToList();

    private void AllowWarn_Changed(object sender, RoutedEventArgs e) => UpdateImportButtons();

    private void DryRun_Click(object sender, RoutedEventArgs e) => Run(dryRun: true);
    private void Import_Click(object sender, RoutedEventArgs e) => Run(dryRun: false);

    private void Run(bool dryRun)
    {
        if (_shell.Session is null) return;
        var files = Importable();
        var skippedInvalid = _staged.Except(files).ToList();
        var asCopy = PolicyCopy.IsChecked == true;
        var core = _core;

        var server = _shell.Session.Server;

        // Captures the same staged-file snapshot (files/skippedInvalid/asCopy) regardless
        // of which mode runs, so "Import Now" after a dry run acts on exactly what the dry
        // run just checked, even if the user has since changed something on the tab.
        // Ported from Porter's ImportView: cancellation between files, a read-only dry-run
        // plan (dashboards it would create, widget keys already on the target), and a JSON
        // run report in the log folder whatever the outcome.
        Func<IProgress<string>, RunSummary, CancellationToken, Task> BuildJob(bool dry) => async (log, summary, ct) =>
        {
            var started = DateTime.UtcNow;
            var outcome = RunOutcome.Completed;
            try
            {
                foreach (var file in skippedInvalid)
                {
                    summary.Skipped++;
                    summary.SkippedNames.Add($"{file.FileName} — {file.Validation.Summary}");
                    summary.Items.Add(new RunItem(file.FileName, dry ? "no-go" : "skipped", file.Validation.Summary));
                    log.Report($"{(dry ? "NO-GO" : "SKIP")} {file.FileName}: {file.Validation.Summary}");
                }

                foreach (var file in files)
                {
                    // Between files only: a file already in flight finishes, so an abort
                    // never leaves a half-imported definition behind.
                    ct.ThrowIfCancellationRequested();
                    try
                    {
                        var keys = file.Validation.Dashboards.Select(d => d.Key).ToList();
                        var collisionHits = await core.FindCollisionsAsync(keys, ct);
                        var collisions = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
                        foreach (var (key, name) in collisionHits) collisions[key] = name;
                        var text = file.Text;
                        var verifyKeys = keys;
                        var note = "";

                        if (collisions.Count > 0 && !asCopy)
                        {
                            summary.Skipped++;
                            var parts = file.Validation.Dashboards.Select(d =>
                                collisions.TryGetValue(d.Key, out var existing)
                                ? $"\"{existing}\" (already on target)"
                                : $"\"{d.Name}\" (skipped with its file)").ToList();
                            var detail = string.Join(", ", parts);
                            summary.SkippedNames.Add($"{file.FileName} — {detail}");
                            summary.Items.Add(new RunItem(file.FileName, dry ? "no-go" : "skipped", detail));
                            log.Report($"{(dry ? "NO-GO" : "SKIP")} {file.FileName}: {detail}");
                            SessionLog.Log(dry ? "dry-run" : "import", file.FileName, "skipped", detail);
                            continue;
                        }
                        if (collisions.Count > 0)
                        {
                            var rewrite = DashboardsCore.AsCopy(file.Text);
                            text = rewrite.Text;
                            verifyKeys = rewrite.NewKeys;
                            note = $" as copy: {string.Join(", ", rewrite.NewNames.Select(n => $"\"{n}\""))}";
                            summary.CopyNotes.Add($"{file.FileName} → {string.Join(", ", rewrite.NewNames)}");
                            foreach (var extra in rewrite.Notes) log.Report($"  note: {extra}");
                        }

                        if (dry)
                        {
                            log.Report($"GO — would import {file.FileName}{note}");
                            summary.Items.Add(new RunItem(file.FileName, "go", note.Trim()));
                            summary.Ok++;
                            // Read-only narration of what the import would touch. A plan that
                            // cannot be gathered never turns a GO into a failure.
                            try
                            {
                                foreach (var line in await core.PlanAsync(text, ct))
                                    log.Report($"  plan: {line}");
                            }
                            catch (Exception ex) when (ex is not OperationCanceledException)
                            {
                                log.Report($"  plan unavailable: {ex.Message}");
                            }
                            continue;
                        }

                        log.Report($"Import {file.FileName}{note} → {DashboardsCore.ImportVia}");
                        await core.ImportAsync(text, ct);
                        var found = await core.VerifyAsync(verifyKeys, ct);
                        var expected = verifyKeys.Count(k => k.Length > 0);

                        if (found.Count >= expected && found.Count > 0)
                        {
                            var detail = string.Join(", ", found.Select(f => $"\"{f.Name}\" (id {f.Id})"));
                            log.Report($"  verified: {detail}");
                            SessionLog.Log("import", file.FileName, "ok", detail);
                            summary.Items.Add(new RunItem(file.FileName, "ok", detail));
                            summary.Ok++;
                        }
                        else
                        {
                            var detail = "import call succeeded but no data returned when reading it back (No Data Returned)";
                            log.Report($"  WARNING: {detail}");
                            SessionLog.Log("import", file.FileName, "unverified", detail);
                            summary.Items.Add(new RunItem(file.FileName, "unverified", detail));
                            summary.Warn++;
                        }
                    }
                    catch (Exception ex) when (ex is not OperationCanceledException)
                    {
                        log.Report($"{(dry ? "NO-GO" : "FAILED")} {file.FileName}: {ex.Message}");
                        SessionLog.Log(dry ? "dry-run" : "import", file.FileName, "failed", ex.Message);
                        summary.Items.Add(new RunItem(file.FileName, "failed", ex.Message));
                        summary.Failed++;
                    }
                }
            }
            catch (OperationCanceledException)
            {
                outcome = RunOutcome.Cancelled;
                log.Report("Aborted — files not yet started were left untouched.");
                throw;
            }
            catch (Exception)
            {
                outcome = RunOutcome.Failed;
                throw;
            }
            finally
            {
                RunReport.WriteAndLog(SessionLog.LogDir, new RunReportData("import", PackageReader.AreaKey,
                    server, dry, started, DateTime.UtcNow, outcome, summary));
                if (summary.ReportPath is not null) log.Report($"Run report → {summary.ReportPath}");
            }
        };

        if (dryRun)
        {
            _shell.Go(new RunView(_shell, "Dry run — Modern Dashboards (no writes)", BuildJob(true),
                onImportNow: () => _shell.Go(
                    new RunView(_shell, "Importing Modern Dashboards", BuildJob(false)),
                    "Import · Modern Dashboards"),
                onBack: () => _shell.Go(this, "Modern Dashboards")),
                "Import · Dry run");
        }
        else
        {
            _shell.Go(new RunView(_shell, "Importing Modern Dashboards", BuildJob(false)),
                "Import · Modern Dashboards");
        }
    }
}
