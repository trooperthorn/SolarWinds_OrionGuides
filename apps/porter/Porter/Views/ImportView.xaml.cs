using System.Collections.ObjectModel;
using System.IO;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;
using System.Windows;
using System.Windows.Controls;
using Microsoft.Win32;
using Porter.Areas;
using Porter.Core;

namespace Porter.Views;

public sealed class StagedFile
{
    public required string FileName { get; init; }
    public required string Text { get; init; }
    public required DashboardValidation Validation { get; init; }
    public string StatusGlyph => Validation.Ok
        ? (Validation.Warnings.Count > 0 ? "⚠" : "✓") : "✕";
    public string Summary => Validation.Summary;
}

public partial class ImportView : UserControl
{
    private readonly MainWindow _shell;
    private readonly ObservableCollection<StagedFile> _staged = new();

    public ImportView(MainWindow shell)
    {
        _shell = shell;
        InitializeComponent();
        StageList.ItemsSource = _staged;
        UpdateButtons();
    }

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

    private void Browse_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog
        {
            Multiselect = true,
            Filter = "Dashboards and packages|*.json;*.zip;*.aes|All files|*.*",
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
        UpdateButtons();
    }

    /// <summary>A path may be one .json, a .zip of them, or an AES-encrypted package.</summary>
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
            yield return (Path.GetFileName(path), File.ReadAllText(path));
        }
    }

    /// <summary>Dashboard JSON is small; anything past this is not a dashboard.</summary>
    private const long MaxItemBytes = 64L * 1024 * 1024;

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
        return Encoding.UTF8.GetString(buffer.ToArray());
    }

    private static IEnumerable<(string, string)> ReadZip(ZipArchive archive, string label)
    {
        var found = false;
        foreach (var entry in archive.Entries.Where(en =>
                     en.Name.EndsWith(".json", StringComparison.OrdinalIgnoreCase) &&
                     !en.Name.Equals("manifest.json", StringComparison.OrdinalIgnoreCase)))
        {
            found = true;
            using var stream = entry.Open();
            yield return ($"{label} › {entry.Name}", ReadLimited(stream, MaxItemBytes));
        }
        if (!found)
            throw new InvalidDataException("the package contains no dashboard .json files");
    }

    private void UpdateButtons()
    {
        var importable = Importable().Count;
        ImportBtn.Content = $"Energize ({importable})";
        ImportBtn.ToolTip = $"Import {importable} staged file{(importable == 1 ? "" : "s")}";
        ImportBtn.IsEnabled = importable > 0 && _shell.Session is not null;
        DryRunBtn.IsEnabled = _staged.Count > 0 && _shell.Session is not null;
    }

    private List<StagedFile> Importable()
        => _staged.Where(f => f.Validation.Ok &&
               (AllowWarnBox.IsChecked == true || f.Validation.Warnings.Count == 0)).ToList();

    private void AllowWarn_Changed(object sender, RoutedEventArgs e) => UpdateButtons();

    private void DryRun_Click(object sender, RoutedEventArgs e) => Run(dryRun: true);
    private void Import_Click(object sender, RoutedEventArgs e) => Run(dryRun: false);

    private void Back_Click(object sender, RoutedEventArgs e)
        => _shell.Go(new AreaView(_shell), "Import · Constellations");

    private void Run(bool dryRun)
    {
        if (_shell.Session is null) return;
        var files = Importable();
        var skippedInvalid = _staged.Except(files).ToList();
        var asCopy = PolicyCopy.IsChecked == true;
        var session = _shell.Session;

        _shell.Go(new RunView(_shell,
            dryRun ? "Simulation — Modern Dashboards (Go / No-Go, no writes)"
                   : "Mission Control — importing Modern Dashboards",
            async (log, ct) =>
        {
            var area = new DashboardsArea(session);
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
                    var collisions = await area.FindCollisionsAsync(keys, ct);
                    var text = file.Text;
                    var verifyKeys = keys;
                    var note = "";

                    if (collisions.Count > 0 && !asCopy)
                    {
                        summary.Skipped++;
                        var collidingKeys = collisions.Select(c => c.Key).ToHashSet(StringComparer.OrdinalIgnoreCase);
                        var parts = file.Validation.Dashboards.Select(d => collidingKeys.Contains(d.Key)
                            ? $"\"{d.Name}\" (already on target)"
                            : $"\"{d.Name}\" (skipped with its file)").ToList();
                        var detail = string.Join(", ", parts);
                        summary.SkippedNames.Add($"{file.FileName} — {detail}");
                        log.Report($"{(dryRun ? "NO-GO" : "SKIP")} {file.FileName}: {detail}");
                        SessionLog.Log(dryRun ? "dry-run" : "import", file.FileName, "skipped", detail);
                        continue;
                    }
                    if (collisions.Count > 0)
                    {
                        var (copyText, newNames, newKeys, copyNotes) = DashboardsArea.AsCopy(file.Text);
                        text = copyText;
                        verifyKeys = newKeys;
                        note = $" as copy: {string.Join(", ", newNames.Select(n => $"\"{n}\""))}";
                        summary.CopyNotes.Add($"{file.FileName} → {string.Join(", ", newNames)}");
                        foreach (var extra in copyNotes) log.Report($"  note: {extra}");
                    }

                    if (dryRun)
                    {
                        log.Report($"GO — would import {file.FileName}{note}");
                        summary.Ok++;
                        continue;
                    }

                    log.Report($"Import {file.FileName}{note} → Orion.Dashboards.Instances.Import");
                    await area.ImportAsync(text, ct);

                    var found = await area.VerifyAsync(verifyKeys, ct);
                    if (found.Count >= verifyKeys.Count(k => k.Length > 0) && found.Count > 0)
                    {
                        log.Report($"  tricorder — verified: {string.Join(", ", found.Select(f => $"\"{f.Name}\" (id {f.Id})"))}");
                        SessionLog.Log("import", file.FileName, "ok", string.Join(",", found.Select(f => f.Id)));
                        summary.Ok++;
                    }
                    else
                    {
                        log.Report("  WARNING: import call succeeded but the dashboard was not found afterwards");
                        SessionLog.Log("import", file.FileName, "unverified", null);
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
        }), dryRun ? "Import · Simulation" : "Import · Mission Control");
    }
}
