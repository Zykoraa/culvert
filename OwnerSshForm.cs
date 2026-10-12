#if OWNER_BUILD
using static Culvert.DashboardTheme;

namespace Culvert;

internal sealed class OwnerSshForm : Form
{
    internal OwnerSshForm()
    {
        Text = "VM access · Culvert"; ClientSize = new(680, 410); MinimumSize = new(650, 410);
        StartPosition = FormStartPosition.CenterParent; BackColor = Background; ForeColor = DashboardTheme.Text;
        Font = new("Segoe UI", 10); StyleCaption(this);
        var options = OwnerSshPreferences.Read();
        var layout = Grid(100); layout.Padding = new(22); layout.RowCount = 7;
        foreach (int height in new[] { 75, 30, 40, 30, 50, 50, 60 }) layout.RowStyles.Add(new(SizeType.Absolute, height));
        layout.Controls.Add(Label("Owner tools manage the VM in your imported connection link.\nSSH access is saved separately for Culvert on this PC.", 11), 0, 0);
        layout.Controls.Add(Label("SSH username and port", 10, Muted), 0, 1);
        var login = new FlowLayoutPanel { Dock = DockStyle.Fill, WrapContents = false };
        var user = new TextBox { Text = options.User, Width = 270, MaxLength = 32, BackColor = Surface, ForeColor = DashboardTheme.Text, AccessibleName = "SSH username" };
        var port = new NumericUpDown { Value = options.Port, Minimum = 1, Maximum = 65535, Width = 100, BackColor = Surface, ForeColor = DashboardTheme.Text, AccessibleName = "SSH port" };
        login.Controls.Add(user); login.Controls.Add(port); layout.Controls.Add(login, 0, 2);
        layout.Controls.Add(Label("Private key file on this PC", 10, Muted), 0, 3);
        var files = Grid(78, 22);
        var key = new TextBox { Text = OwnerSshPreferences.ResolveKey(options), Dock = DockStyle.Fill, MaxLength = 1024, BackColor = Surface, ForeColor = DashboardTheme.Text, AccessibleName = "SSH private key path" };
        var browse = new DashboardButton { Text = "Browse…", Dock = DockStyle.Fill, BackColor = BlueTint, ForeColor = DashboardTheme.Text };
        browse.Click += (_, _) => { using var file = new OpenFileDialog { Title = "Choose the SSH private key for Culvert's VM", Filter = "SSH private key|*.key;*.pem;id_*|All files|*.*" }; if (file.ShowDialog(this) == DialogResult.OK) key.Text = file.FileName; };
        files.Controls.Add(key, 0, 0); files.Controls.Add(browse, 1, 0); layout.Controls.Add(files, 0, 4);
        var status = Label("The key stays on this PC. It is never included in a Client installer.", 10, Muted); layout.Controls.Add(status, 0, 5);
        var save = new DashboardButton { Text = "Save VM access", Dock = DockStyle.Fill, BackColor = AccentBlue, ForeColor = Background };
        save.Click += (_, _) =>
        {
            try
            {
                var updated = new OwnerSshOptions(user.Text.Trim(), (int)port.Value, key.Text.Trim());
                if (!File.Exists(OwnerSshPreferences.ResolveKey(updated))) throw new FileNotFoundException("Choose the downloaded private key file first.");
                OwnerSshPreferences.Save(updated); DialogResult = DialogResult.OK;
            }
            catch (Exception error) { status.Text = error.Message; }
        };
        layout.Controls.Add(save, 0, 6); Controls.Add(layout); AcceptButton = save; UiPreferences.Apply(this);
    }
}
#endif
