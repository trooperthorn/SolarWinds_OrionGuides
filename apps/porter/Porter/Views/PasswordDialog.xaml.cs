using System.Windows;

namespace Porter.Views;

public partial class PasswordDialog : Window
{
    public string Password => Box.Password;

    public PasswordDialog(string prompt)
    {
        InitializeComponent();
        PromptText.Text = prompt;
        Loaded += (_, _) => Box.Focus();
    }

    private void Ok_Click(object sender, RoutedEventArgs e) => DialogResult = true;
}
