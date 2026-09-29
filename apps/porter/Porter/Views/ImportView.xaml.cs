using System.Collections.ObjectModel;
using System.IO;
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
                var contents = PackageReader.Read(path, _provider, PromptPassword);
                foreach (var entry in contents.Entries)
                {
                    var validation = _provider.Validate(entry.DisplayName, entry.Text);
                    // Origin findings lead the lists so they become the row summary: a
                    // modified file must never read as "all checks pass".
                    validation.Errors.InsertRange(0, entry.Errors);
                    validation.Warnings.InsertRange(0, entry.Warnings);
                    if (SourceLine(contents.Info) is { Length: > 0 } source)
                        validation.Detail = validation.Detail.Length > 0
                            ? $"{source} — {validation.Detail}" : source;
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

    /// <summary>The only UI the reader needs: ask for a package password, null on cancel.</summary>
    private string? PromptPassword(string fileName)
    {
        var dialog = new PasswordDialog($"Package password for {fileName}")
            { Owner = Window.GetWindow(this) };
        return dialog.ShowDialog() == true ? dialog.Password : null;
    }

    /// <summary>"from core-orion · Orion 2026.2 · 2026-09-01T…" for a Porter package, else
    /// empty. The source platform is shown as recorded, beside the connected server's own
    /// label in the header — Porter does no version arithmetic on it.</summary>
    private static string SourceLine(PackageInfo info)
    {
        if (!info.IsPorterPackage) return "";
        var parts = new[] { info.SourceServer, info.SourcePlatform, info.Created }
            .Where(p => !string.IsNullOrWhiteSpace(p)).ToList();
        return parts.Count == 0 ? "" : $"from {string.Join(" · ", parts)}";
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

        var session = _shell.Session;

        _shell.Go(new RunView(_shell,
            dryRun ? $"Simulation — {provider.DisplayName} (Go / No-Go, no writes)"
                   : $"Mission Control — importing {provider.DisplayName}",
            async (log, summary, ct) =>
        {
            var started = DateTime.UtcNow;
            var outcome = RunOutcome.Completed;
            try
            {
                foreach (var file in skippedInvalid)
                {
                    summary.Skipped++;
                    summary.SkippedNames.Add($"{file.FileName} — {file.Validation.Summary}");
                    summary.Items.Add(new RunItem(file.FileName, dryRun ? "no-go" : "skipped", file.Validation.Summary));
                    log.Report($"{(dryRun ? "NO-GO" : "SKIP")} {file.FileName}: {file.Validation.Summary}");
                }

                foreach (var file in files)
                {
                    // Between items only: a file already in flight finishes, so an abort never
                    // leaves a half-imported definition behind.
                    ct.ThrowIfCancellationRequested();
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
                            summary.Items.Add(new RunItem(file.FileName, dryRun ? "no-go" : "skipped", detail));
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

                        if (dryRun)
                        {
                            log.Report($"GO — would import {file.FileName}{note}");
                            summary.Items.Add(new RunItem(file.FileName, "go", note.Trim()));
                            summary.Ok++;
                            // Read-only narration of what the import would touch. A plan that
                            // cannot be gathered never turns a GO into a failure.
                            try
                            {
                                foreach (var line in await provider.PlanAsync(text, ct))
                                    log.Report($"  plan: {line}");
                            }
                            catch (Exception ex) when (ex is not OperationCanceledException)
                            {
                                log.Report($"  plan unavailable: {ex.Message}");
                            }
                            continue;
                        }

                        log.Report($"Import {file.FileName}{note} → {provider.ImportVia}");
                        var result = await provider.ImportAsync(text, verifyKeys, options, ct);

                        if (result.Verified)
                        {
                            log.Report($"  tricorder — verified: {result.Detail}");
                            SessionLog.Log("import", file.FileName, "ok", result.Detail);
                            summary.Items.Add(new RunItem(file.FileName, "ok", result.Detail));
                            summary.Ok++;
                        }
                        else
                        {
                            log.Report($"  WARNING: {result.Detail}");
                            SessionLog.Log("import", file.FileName, "unverified", result.Detail);
                            summary.Items.Add(new RunItem(file.FileName, "unverified", result.Detail));
                            summary.Warn++;
                        }
                    }
                    catch (Exception ex) when (ex is not OperationCanceledException)
                    {
                        log.Report($"{(dryRun ? "NO-GO" : "FAILED")} {file.FileName}: {ex.Message}");
                        SessionLog.Log(dryRun ? "dry-run" : "import", file.FileName, "failed", ex.Message);
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
                RunReport.WriteAndLog(SessionLog.LogDir, new RunReportData("import", provider.Key,
                    session.Server, dryRun, started, DateTime.UtcNow, outcome, summary));
                if (summary.ReportPath is not null) log.Report($"Run report → {summary.ReportPath}");
            }
        }), dryRun ? "Import · Simulation" : "Import · Mission Control");
    }
}
