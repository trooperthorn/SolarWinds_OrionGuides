using System.Collections.ObjectModel;
using System.ComponentModel;
using System.IO;
using System.IO.Compression;
using System.Security.Cryptography;
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
        var dest = DestBox.Text;
        var asZip = FmtZip.IsChecked == true || FmtAes.IsChecked == true;
        var aesPassword = FmtAes.IsChecked == true ? AesPass.Password : null;
        var session = _shell.Session;
        var platform = _shell.PlatformLabel;
        var core = _core;

        _shell.Go(new RunView(_shell, "Exporting Modern Dashboards",
            async (log, ct) =>
        {
            var items = new List<PackageItem>();
            var summary = new RunSummary();
            foreach (var item in picked)
            {
                try
                {
                    log.Report($"Export \"{item.Name}\" (id {item.Id})");
                    var definition = await core.ExportAsync(item.Id, ct);
                    var fileName = PackageWriter.Sanitize(item.Name) + FileExtension;
                    items.Add(new PackageItem($"dashboards/{fileName}", item.Name,
                        Encoding.UTF8.GetBytes(definition), "skip-or-copy-selected-at-import"));
                    SessionLog.Log("export", item.Name, "ok", $"dashboard {item.Id}");
                    summary.Ok++;
                }
                catch (Exception ex)
                {
                    log.Report($"  FAILED: {ex.Message}");
                    SessionLog.Log("export", item.Name, "failed", ex.Message);
                    summary.Failed++;
                }
            }
            string where;
            if (items.Count == 0)
            {
                log.Report("Nothing exported — no output written.");
                where = dest;
            }
            else if (asZip)
            {
                where = PackageWriter.WritePackage(dest, session.Server, platform, items, aesPassword);
            }
            else
            {
                var rawDir = Path.Combine(dest, "dashboards");
                where = PackageWriter.WriteRaw(rawDir, items);
            }
            log.Report($"Output → {where}");
            summary.OutputPath = items.Count > 0 ? where : null;
            return summary;
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
                foreach (var (name, text) in ReadCandidates(path))
                    _staged.Add(new StagedFile
                    {
                        FileName = name,
                        Text = text,
                        Validation = DashboardValidator.Validate(text),
                    });
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

    private void ClearStaged_Click(object sender, RoutedEventArgs e)
    {
        _staged.Clear();
        UpdateImportButtons();
    }

    /// <summary>A path may be one raw export, a .zip of them, or an AES-encrypted package.</summary>
    private IEnumerable<(string Name, string Text)> ReadCandidates(string path)
    {
        if (path.EndsWith(".aes", StringComparison.OrdinalIgnoreCase))
        {
            var dialog = new PasswordDialog($"Package password for {Path.GetFileName(path)}")
                { Owner = Window.GetWindow(this) };
            if (dialog.ShowDialog() != true)
                throw new OperationCanceledException("password entry cancelled");
            byte[] zipBytes;
            try { zipBytes = PackageCrypto.DecryptFile(path, dialog.Password); }
            catch (CryptographicException)
            { throw new InvalidDataException("wrong password, or the package was modified"); }
            using var archive = new ZipArchive(new MemoryStream(zipBytes), ZipArchiveMode.Read);
            foreach (var pair in ReadZip(archive, Path.GetFileName(path))) yield return pair;
        }
        else if (path.EndsWith(".zip", StringComparison.OrdinalIgnoreCase))
        {
            using var archive = ZipFile.OpenRead(path);
            foreach (var pair in ReadZip(archive, Path.GetFileName(path))) yield return pair;
        }
        else
        {
            if (new FileInfo(path).Length > MaxItemBytes)
                throw new InvalidDataException($"{Path.GetFileName(path)} exceeds the {MaxItemBytes / (1024 * 1024)} MB limit");
            yield return (Path.GetFileName(path), ReadTextSniffed(File.ReadAllBytes(path)));
        }
    }

    /// <summary>Exports are small; anything past this is not a configuration export.</summary>
    private const long MaxItemBytes = 64L * 1024 * 1024;

    /// <summary>Platform exports lie about their encoding sometimes — trust the bytes (BOM),
    /// never a declaration inside the file.</summary>
    private static string ReadTextSniffed(byte[] bytes)
    {
        if (bytes.Length >= 2 && bytes[0] == 0xFF && bytes[1] == 0xFE)
            return Encoding.Unicode.GetString(bytes, 2, bytes.Length - 2);
        if (bytes.Length >= 2 && bytes[0] == 0xFE && bytes[1] == 0xFF)
            return Encoding.BigEndianUnicode.GetString(bytes, 2, bytes.Length - 2);
        if (bytes.Length >= 3 && bytes[0] == 0xEF && bytes[1] == 0xBB && bytes[2] == 0xBF)
            return Encoding.UTF8.GetString(bytes, 3, bytes.Length - 3);
        return Encoding.UTF8.GetString(bytes);
    }

    /// <summary>Reads to the cap and no further — a hostile zip's central directory can lie
    /// about entry sizes, so the guard counts what actually decompresses.</summary>
    private static string ReadLimited(Stream stream, long cap)
    {
        using var buffer = new MemoryStream();
        var chunk = new byte[81920];
        long total = 0;
        int n;
        while ((n = stream.Read(chunk, 0, chunk.Length)) > 0)
        {
            total += n;
            if (total > cap)
                throw new InvalidDataException($"entry decompresses past the {cap / (1024 * 1024)} MB limit");
            buffer.Write(chunk, 0, n);
        }
        return ReadTextSniffed(buffer.ToArray());
    }

    private IEnumerable<(string, string)> ReadZip(ZipArchive archive, string label)
    {
        var matching = archive.Entries.Where(en =>
            en.Name.EndsWith(FileExtension, StringComparison.OrdinalIgnoreCase) &&
            !en.Name.Equals("manifest.json", StringComparison.OrdinalIgnoreCase)).ToList();
        // A DashboardPorter package folders files under dashboards/ — prefer that folder so
        // a mixed package (e.g. from Porter) stages only the dashboards; flat zips still stage fully.
        var inFolder = matching.Where(en => en.FullName.StartsWith(
            "dashboards/", StringComparison.OrdinalIgnoreCase)).ToList();
        if (inFolder.Count > 0) matching = inFolder;
        var found = false;
        foreach (var entry in matching)
        {
            found = true;
            using var stream = entry.Open();
            yield return ($"{label} › {entry.Name}", ReadLimited(stream, MaxItemBytes));
        }
        if (!found)
            throw new InvalidDataException($"the package contains no {FileExtension} files for Modern Dashboards");
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

        _shell.Go(new RunView(_shell,
            dryRun ? "Dry run — Modern Dashboards (no writes)" : "Importing Modern Dashboards",
            async (log, ct) =>
        {
            var summary = new RunSummary();

            foreach (var file in skippedInvalid)
            {
                summary.Skipped++;
                summary.SkippedNames.Add($"{file.FileName} — {file.Validation.Summary}");
                log.Report($"{(dryRun ? "NO-GO" : "SKIP")} {file.FileName}: {file.Validation.Summary}");
            }

            foreach (var file in files)
            {
                try
                {
                    var keys = file.Validation.Dashboards.Select(d => d.Key).ToList();
                    var collisionHits = await core.FindCollisionsAsync(keys, ct);
                    var collisions = collisionHits.ToDictionary(h => h.Key, h => h.ExistingName,
                        StringComparer.OrdinalIgnoreCase);
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
                        log.Report($"{(dryRun ? "NO-GO" : "SKIP")} {file.FileName}: {detail}");
                        SessionLog.Log(dryRun ? "dry-run" : "import", file.FileName, "skipped", detail);
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

                    if (dryRun)
                    {
                        log.Report($"GO — would import {file.FileName}{note}");
                        summary.Ok++;
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
                        summary.Ok++;
                    }
                    else
                    {
                        var detail = "import call succeeded but no data returned when reading it back (No Data Returned)";
                        log.Report($"  WARNING: {detail}");
                        SessionLog.Log("import", file.FileName, "unverified", detail);
                        summary.Warn++;
                    }
                }
                catch (Exception ex)
                {
                    log.Report($"{(dryRun ? "NO-GO" : "FAILED")} {file.FileName}: {ex.Message}");
                    SessionLog.Log(dryRun ? "dry-run" : "import", file.FileName, "failed", ex.Message);
                    summary.Failed++;
                }
            }
            return summary;
        }), dryRun ? "Import · Dry run" : "Import · Modern Dashboards");
    }
}
