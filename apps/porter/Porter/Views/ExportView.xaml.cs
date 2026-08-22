using System.Collections.ObjectModel;
using System.ComponentModel;
using System.IO;
using System.Text;
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

public partial class ExportView : UserControl
{
    private readonly MainWindow _shell;
    private readonly ObservableCollection<ExportRow> _rows = new();
    private CheckBox? _headCheck;

    public ExportView(MainWindow shell)
    {
        _shell = shell;
        InitializeComponent();
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

    private async Task RefreshAsync()
    {
        if (_shell.Session is null) return;
        _rows.Clear();
        try
        {
            var area = new DashboardsArea(_shell.Session);
            foreach (var d in await area.ListAsync())
            {
                var row = new ExportRow { Id = d.Id, Name = d.Name, UniqueKey = d.UniqueKey, IsSystem = d.IsSystem };
                row.PropertyChanged += (_, _) => Recount();
                _rows.Add(row);
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show(ex.Message, "Could not list dashboards", MessageBoxButton.OK, MessageBoxImage.Error);
        }
        Recount();
    }

    private List<ExportRow> VisibleRows()
        => CollectionViewSource.GetDefaultView(_rows).Cast<ExportRow>().ToList();

    private void Recount()
    {
        var selected = _rows.Count(r => r.IsSelected);
        CountText.Text = $"{selected} of {_rows.Count} selected";
        ExportBtn.Content = $"Export {selected} selected";
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
        => AesPass.IsEnabled = FmtAes.IsChecked == true;

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
        var dialog = new OpenFolderDialog { Title = "Choose the export destination" };
        if (dialog.ShowDialog() == true) DestBox.Text = dialog.FolderName;
    }

    private void Back_Click(object sender, RoutedEventArgs e)
        => _shell.Go(new AreaView(_shell), "Export · choose area");

    private void Export_Click(object sender, RoutedEventArgs e)
    {
        if (_shell.Session is null) return;
        var picked = _rows.Where(r => r.IsSelected).ToList();
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

        _shell.Go(new RunView(_shell, "Exporting Modern Dashboards", async (log, ct) =>
        {
            var area = new DashboardsArea(session);
            var items = new List<PackageItem>();
            var summary = new RunSummary();
            foreach (var row in picked)
            {
                try
                {
                    log.Report($"Export \"{row.Name}\" (id {row.Id}) → Orion.Dashboards.Instances.Export");
                    var definition = await area.ExportAsync(row.Id, ct);
                    var file = PackageWriter.Sanitize(row.Name) + ".json";
                    items.Add(new PackageItem("dashboards", $"dashboards/{file}", row.Name,
                        Encoding.UTF8.GetBytes(definition),
                        "Orion.Dashboards.Instances.Import", "skip-or-copy-selected-at-import"));
                    SessionLog.Log("export", row.Name, "ok", $"dashboard {row.Id}");
                    summary.Ok++;
                }
                catch (Exception ex)
                {
                    log.Report($"  FAILED: {ex.Message}");
                    SessionLog.Log("export", row.Name, "failed", ex.Message);
                    summary.Failed++;
                }
            }
            string where;
            if (asZip)
            {
                where = PackageWriter.WritePackage(dest, session.Server, platform, items, aesPassword);
            }
            else
            {
                var rawDir = Path.Combine(dest, "dashboards");
                where = PackageWriter.WriteRaw(rawDir, items);
            }
            log.Report($"Output → {where}");
            summary.OutputPath = where;
            return summary;
        }), "Export · running");
    }
}
