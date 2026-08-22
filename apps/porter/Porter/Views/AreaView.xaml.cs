using System.Windows;
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
        var panel = new StackPanel { Width = 236 };
        panel.Children.Add(new TextBlock
        {
            Text = area.Name, FontWeight = FontWeights.SemiBold, FontSize = 14,
        });
        panel.Children.Add(new TextBlock
        {
            Text = $"{area.Mechanism} · {area.Phase}", Foreground = Brushes.Gray, FontSize = 11,
            Margin = new Thickness(0, 2, 0, 4),
        });
        panel.Children.Add(new TextBlock
        {
            Text = area.Note, TextWrapping = TextWrapping.Wrap, FontSize = 11.5,
            Foreground = Brushes.DimGray,
        });
        var card = new Button
        {
            Content = panel,
            Margin = new Thickness(0, 0, 12, 12),
            Padding = new Thickness(12),
            IsEnabled = area.Enabled,
            HorizontalContentAlignment = HorizontalAlignment.Left,
            Tag = area.Key,
        };
        card.Click += Card_Click;
        return card;
    }

    private void Card_Click(object sender, RoutedEventArgs e)
    {
        var key = (string)((Button)sender).Tag;
        if (key != "dashboards") return;
        if (_shell.ModeIsExport)
            _shell.Go(new ExportView(_shell), "Export · Modern Dashboards");
        else
            _shell.Go(new ImportView(_shell), "Import · Modern Dashboards");
    }

    private void Back_Click(object sender, RoutedEventArgs e)
        => _shell.Go(new ModeView(_shell), "Direction");
}
