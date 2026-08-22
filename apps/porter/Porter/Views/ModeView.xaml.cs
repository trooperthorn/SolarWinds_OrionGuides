using System.Windows;
using System.Windows.Controls;

namespace Porter.Views;

public partial class ModeView : UserControl
{
    private readonly MainWindow _shell;

    public ModeView(MainWindow shell)
    {
        _shell = shell;
        InitializeComponent();
    }

    private void Export_Click(object sender, RoutedEventArgs e)
    {
        _shell.ModeIsExport = true;
        _shell.Go(new AreaView(_shell), "Export · choose area");
    }

    private void Import_Click(object sender, RoutedEventArgs e)
    {
        _shell.ModeIsExport = false;
        _shell.Go(new AreaView(_shell), "Import · choose area");
    }

    private void Back_Click(object sender, RoutedEventArgs e)
        => _shell.Go(new ConnectView(_shell), "Connect");
}
