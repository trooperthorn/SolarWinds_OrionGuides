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
    public required AreaValidation Validation { get; init; }
    public string StatusGlyph => !Validation.Ok ? "✕"
        : Validation.SecurityFlags.Count > 0 ? "✋"
        : Validation.Warnings.Count > 0 ? "⚠" : "✓";
    public string Summary => Validation.Summary;
}

public partial class ImportView : UserControl
{
    private readonly MainWindow _shell;
    private readonly AreaProvider _provider;
    private readonly ObservableCollection<StagedFile> _staged = new();

    public ImportView(MainWindow shell, AreaProvider provider)
    {
        _shell = shell;
        _provider = provider;
        InitializeComponent();
        TitleText.Text = $"Import — {provider.DisplayName} · The Airlock";
        StageList.ItemsSource = _staged;
        if (provider.RequiresCipherPassword) CipherPanel.Visibility = Visibility.Visible;
        switch (provider.CopyMode)
        {
            case CopyMode.NotSupported:
                PolicyCopy.Visibility = Visibility.Collapsed;
                PolicyHint.Text = "This area has no copy mechanism — an item that already " +
                    "exists on the target can only be skipped.";
                break;
            case CopyMode.ClientRewrite:
                PolicyHint.Text = "Existence is matched by each item's key. Copies get every " +
                    "identity regenerated so the server sees a new object, and the run report " +
                    "shows the new name.";
                break;
            case CopyMode.ServerRename:
                PolicyCopyText.Text = "Replicate — import anyway; the server itself creates " +
                    "the duplicate and renames it \"Copy of …\"";
                PolicyHint.Text = "This area's import verb never overwrites: on a name " +
                    "collision the server always creates the copy. The run report shows " +
                    "what the server named it.";
                break;
        }
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
            Filter = $"{_provider.FileDialogFilter}|Packages|*.zip;*.aes|All files|*.*",
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
                        Validation = _provider.Validate(name, text),
                    });
            }
            catch (Exception ex)
            {
                var invalid = new AreaValidation();
                invalid.Errors.Add(ex.Message);
                _staged.Add(new StagedFile
                {
                    FileName = Path.GetFileName(path), Text = "", Validation = invalid,
                });
            }
        }
        if (_staged.Any(f => f.Validation.SecurityFlags.Count > 0))
        {
            AckSecurityBox.Visibility = Visibility.Visible;
            // Every newly staged flagged file resets the tick — one acknowledgement never
            // silently covers files that arrived after it was given.
            AckSecurityBox.IsChecked = false;
        }
        UpdateButtons();
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

    /// <summary>Platform exports lie about their encoding — NCM policy reports declare
    /// utf-16 in the XML prolog while the file on disk is utf-8. Trust the bytes (BOM),
    /// never the declaration.</summary>
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
            en.Name.EndsWith(_provider.FileExtension, StringComparison.OrdinalIgnoreCase) &&
            !en.Name.Equals("manifest.json", StringComparison.OrdinalIgnoreCase)).ToList();
        // A Porter cargo pod folders files by area — prefer this area's folder so a
        // mixed-area package stages only what belongs here; flat zips still stage fully.
        var inFolder = matching.Where(en => en.FullName.StartsWith(
            _provider.Key + "/", StringComparison.OrdinalIgnoreCase)).ToList();
        if (inFolder.Count > 0) matching = inFolder;
        var found = false;
        foreach (var entry in matching)
        {
            found = true;
            using var stream = entry.Open();
            yield return ($"{label} › {entry.Name}", ReadLimited(stream, MaxItemBytes));
        }
        if (!found)
            throw new InvalidDataException(
                $"the package contains no {_provider.FileExtension} files for {_provider.DisplayName}");
    }

    private void UpdateButtons()
    {
        // AllowWarnBox ships IsChecked="True", and compiled XAML wires Checked before the
        // later-declared buttons exist — so this runs mid-InitializeComponent. Bail until
        // every control is alive; the constructor calls UpdateButtons() again at the end.
        if (ImportBtn is null || DryRunBtn is null || AckSecurityBox is null) return;
        var importable = Importable().Count;
        ImportBtn.Content = $"Energize ({importable})";
        ImportBtn.ToolTip = $"Import {importable} staged file{(importable == 1 ? "" : "s")}";
        ImportBtn.IsEnabled = importable > 0 && _shell.Session is not null;
        DryRunBtn.IsEnabled = _staged.Count > 0 && _shell.Session is not null;
    }

    private List<StagedFile> Importable()
        => _staged.Where(f => f.Validation.Ok &&
               (AllowWarnBox.IsChecked == true || f.Validation.Warnings.Count == 0) &&
               (f.Validation.SecurityFlags.Count == 0 || AckSecurityBox.IsChecked == true)).ToList();

    private void AllowWarn_Changed(object sender, RoutedEventArgs e) => UpdateButtons();

    private void DryRun_Click(object sender, RoutedEventArgs e) => Run(dryRun: true);
    private void Import_Click(object sender, RoutedEventArgs e) => Run(dryRun: false);

    private void Back_Click(object sender, RoutedEventArgs e)
        => _shell.Go(new AreaView(_shell), "Import · Constellations");

    private void Run(bool dryRun)
    {
        if (_shell.Session is null) return;
        if (!dryRun && _provider.RequiresCipherPassword && CipherPass.Password.Length == 0)
        {
            MessageBox.Show("Enter the cipher password the recordings were exported with.",
                "Cipher password required", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }
        var files = Importable();
        var skippedInvalid = _staged.Except(files).ToList();
        var asCopy = PolicyCopy.IsChecked == true && _provider.CopyMode != CopyMode.NotSupported;
        var options = new ImportOptions
        {
            CipherPassword = _provider.RequiresCipherPassword ? CipherPass.Password : null,
        };
        var provider = _provider;

        _shell.Go(new RunView(_shell,
            dryRun ? $"Simulation — {provider.DisplayName} (Go / No-Go, no writes)"
                   : $"Mission Control — importing {provider.DisplayName}",
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
                    var keys = file.Validation.Items.Select(i => i.Key).ToList();
                    var collisions = await provider.FindCollisionsAsync(keys, ct);
                    var text = file.Text;
                    var verifyKeys = keys;
                    var note = "";

                    if (collisions.Count > 0 && !asCopy)
                    {
                        summary.Skipped++;
                        var parts = file.Validation.Items.Select(i =>
                            collisions.TryGetValue(i.Key, out var existing)
                            ? $"\"{existing}\" (already on target)"
                            : $"\"{i.Name}\" (skipped with its file)").ToList();
                        var detail = string.Join(", ", parts);
                        summary.SkippedNames.Add($"{file.FileName} — {detail}");
                        log.Report($"{(dryRun ? "NO-GO" : "SKIP")} {file.FileName}: {detail}");
                        SessionLog.Log(dryRun ? "dry-run" : "import", file.FileName, "skipped", detail);
                        continue;
                    }
                    if (collisions.Count > 0 && provider.CopyMode == CopyMode.ClientRewrite)
                    {
                        var rewrite = provider.AsCopy(file.Text);
                        text = rewrite.Text;
                        verifyKeys = rewrite.NewKeys;
                        note = $" as copy: {string.Join(", ", rewrite.NewNames.Select(n => $"\"{n}\""))}";
                        summary.CopyNotes.Add($"{file.FileName} → {string.Join(", ", rewrite.NewNames)}");
                        foreach (var extra in rewrite.Notes) log.Report($"  note: {extra}");
                    }
                    else if (collisions.Count > 0)
                    {
                        note = " — the server will import it as its own \"Copy of …\"";
                    }

                    if (dryRun)
                    {
                        log.Report($"GO — would import {file.FileName}{note}");
                        summary.Ok++;
                        continue;
                    }

                    log.Report($"Import {file.FileName}{note} → {provider.ImportVia}");
                    var outcome = await provider.ImportAsync(text, verifyKeys, options, ct);

                    if (outcome.Verified)
                    {
                        log.Report($"  tricorder — verified: {outcome.Detail}");
                        SessionLog.Log("import", file.FileName, "ok", outcome.Detail);
                        summary.Ok++;
                    }
                    else
                    {
                        log.Report($"  WARNING: {outcome.Detail}");
                        SessionLog.Log("import", file.FileName, "unverified", outcome.Detail);
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
