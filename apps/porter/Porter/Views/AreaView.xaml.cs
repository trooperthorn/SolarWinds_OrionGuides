using System.Windows;
using System.Windows.Automation;
using System.Windows.Controls;
using System.Windows.Media;
using Porter.Areas;

namespace Porter.Views;

public partial class AreaView : UserControl
{
    private readonly MainWindow _shell;

    public AreaView(MainWindow shell)
    {
        _shell = shell;
        InitializeComponent();
        foreach (var area in AreaCatalog.All)
            Cards.Items.Add(BuildCard(area));
    }

    private UIElement BuildCard(AreaInfo area)
    {
        // Full-width row: name left, phase tag right, mechanism and note wrapping below.
        var head = new DockPanel();
        var phase = new TextBlock
        {
            Text = area.Phase, Foreground = Brushes.Gray, FontSize = 12,
            VerticalAlignment = VerticalAlignment.Center,
            Margin = new Thickness(12, 0, 0, 0),
        };
        DockPanel.SetDock(phase, Dock.Right);
        head.Children.Add(phase);
        head.Children.Add(new TextBlock
        {
            Text = area.Name, FontWeight = FontWeights.SemiBold, FontSize = 15,
        });

        var panel = new StackPanel();
        panel.Children.Add(head);
        panel.Children.Add(new TextBlock
        {
            Text = "SWIS mechanism: " + area.Mechanism, Foreground = Brushes.Gray,
            FontSize = 11.5, TextWrapping = TextWrapping.Wrap,
            Margin = new Thickness(0, 4, 0, 2),
        });
        panel.Children.Add(new TextBlock
        {
            Text = area.Note, TextWrapping = TextWrapping.Wrap, FontSize = 12.5,
            Foreground = Brushes.DimGray,
        });
        var card = new Button
        {
            Content = panel,
            Margin = new Thickness(0, 0, 0, 10),
            Padding = new Thickness(16, 12, 16, 12),
            IsEnabled = area.Enabled,
            HorizontalContentAlignment = HorizontalAlignment.Stretch,
            Tag = area.Key,
        };
        AutomationProperties.SetName(card, area.Name);
        card.Click += Card_Click;
        return card;
    }

    private void Card_Click(object sender, RoutedEventArgs e)
    {
        var key = (string)((Button)sender).Tag;
        if (_shell.Session is null) return;
        var provider = AreaRegistry.Create(key, _shell.Session);
        if (provider is null) return;
        if (_shell.ModeIsExport)
            _shell.Go(new ExportView(_shell, provider), $"Export · {provider.DisplayName}");
        else if (provider.CanImport)
            _shell.Go(new ImportView(_shell, provider), $"Import · {provider.DisplayName}");
        else
            MessageBox.Show($"{provider.DisplayName} is export-only — the platform has no " +
                "import route for it.", provider.DisplayName,
                MessageBoxButton.OK, MessageBoxImage.Information);
    }

    private void Back_Click(object sender, RoutedEventArgs e)
        => _shell.Go(new ModeView(_shell), "Direction");
}
