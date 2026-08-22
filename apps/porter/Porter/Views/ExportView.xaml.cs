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
        var dest = DestBox.Text;
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
            async (log, ct) =>
        {
            var items = new List<PackageItem>();
            var summary = new RunSummary();
            if (provider.BulkExport)
            {
                try
                {
                    log.Report($"Export {picked.Count} item(s) → one {provider.FileExtension} file");
                    var export = await provider.ExportBulkAsync(picked, options, ct);
                    items.Add(new PackageItem(provider.Key, $"{provider.Key}/{export.FileName}",
                        provider.DisplayName, export.Bytes, provider.ImportVia, "bulk"));
                    SessionLog.Log("export", provider.Key, "ok", $"{picked.Count} items, bulk");
                    summary.Ok = picked.Count;
                }
                catch (Exception ex)
                {
                    log.Report($"  FAILED: {ex.Message}");
                    SessionLog.Log("export", provider.Key, "failed", ex.Message);
                    summary.Failed = picked.Count;
                }
            }
            else
            {
                foreach (var item in picked)
                {
                    try
                    {
                        log.Report($"Export \"{item.Name}\" (id {item.Id})");
                        var export = await provider.ExportAsync(item, options, ct);
                        items.Add(new PackageItem(provider.Key, $"{provider.Key}/{export.FileName}",
                            item.Name, export.Bytes, provider.ImportVia, "skip-or-copy-selected-at-import"));
                        SessionLog.Log("export", item.Name, "ok", $"{provider.Key} {item.Id}");
                        summary.Ok++;
                    }
                    catch (Exception ex)
                    {
                        log.Report($"  FAILED: {ex.Message}");
                        SessionLog.Log("export", item.Name, "failed", ex.Message);
                        summary.Failed++;
                    }
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
                var rawDir = Path.Combine(dest, provider.Key);
                where = PackageWriter.WriteRaw(rawDir, items);
            }
            log.Report($"Output → {where}");
            summary.OutputPath = items.Count > 0 ? where : null;
            return summary;
        }), "Export · Mission Control");
    }
}
