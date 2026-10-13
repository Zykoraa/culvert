using System.Drawing.Drawing2D;

namespace Culvert;

/// <summary>Decorative branding only; it never represents tunnel health or traffic.</summary>
internal sealed class CulvertWordmark : Control, IAnimatedControl
{
    private readonly System.Windows.Forms.Timer _orbit = new() { Interval = 50 };
    private float _angle = -44;
    public CulvertWordmark()
    {
        SetStyle(ControlStyles.UserPaint | ControlStyles.AllPaintingInWmPaint |
            ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw | ControlStyles.SupportsTransparentBackColor, true);
        Dock = DockStyle.Fill; Margin = Padding.Empty; BackColor = Color.Transparent;
        Font = new Font("Consolas", 23, FontStyle.Bold);
        Text = "Culvert"; AccessibleName = "Culvert";
        AccessibleDescription = "Taking your data underground. Decorative tunnel mascot.";
        AccessibleRole = AccessibleRole.StaticText; TabStop = false;
        _orbit.Tick += (_, _) => { if (AnimationSettings.Allowed(this)) { _angle = (_angle + 1.5f) % 360; Invalidate(); } };
    }

    protected override void OnHandleCreated(EventArgs e)
    {
        base.OnHandleCreated(e);
        Microsoft.Win32.SystemEvents.UserPreferenceChanged += PreferencesChanged;
        _orbit.Start();
    }

    private void PreferencesChanged(object sender, Microsoft.Win32.UserPreferenceChangedEventArgs e)
    {
        if (!IsHandleCreated || IsDisposed) return;
        try { BeginInvoke((Action)Invalidate); } catch (InvalidOperationException) { }
    }

    public void RefreshMotion() => Invalidate();

    protected override void OnPaint(PaintEventArgs e)
    {
        base.OnPaint(e);
        if (Width < 2 || Height < 2) return;
        var g = e.Graphics; g.SmoothingMode = SmoothingMode.AntiAlias;
        float size = Math.Min(Height - 2, Font.GetHeight(g) * 1.3f);
        if (size < 4) return;
        float top = (Height - size) / 2, left = 2;
        Color blue = SystemInformation.HighContrast ? SystemColors.WindowText : DashboardTheme.Blue;
        Color pink = SystemInformation.HighContrast ? SystemColors.WindowText : DashboardTheme.Pink;
        BrandMark.Draw(g, new RectangleF(left, top, size, size), _angle);

        using var letters = new GraphicsPath();
        letters.AddString("CULVERT", Font.FontFamily, (int)Font.Style, Font.SizeInPoints * g.DpiY / 72,
            new PointF(0, 0), StringFormat.GenericTypographic);
        var textBounds = letters.GetBounds();
        float textLeft = size + 12 * size / 34;
        float fit = Math.Min(1, Math.Min((Width - textLeft - 2) / textBounds.Width, (Height - 2) / textBounds.Height));
        if (fit <= 0) return;
        using var position = new Matrix(fit, 0, 0, fit, textLeft - textBounds.Left * fit, (Height - textBounds.Height * fit) / 2 - textBounds.Top * fit);
        letters.Transform(position);
        var word = letters.GetBounds();
        using var ink = new LinearGradientBrush(word, blue, pink, 15f);
        g.FillPath(ink, letters);
    }

    protected override void OnHandleDestroyed(EventArgs e)
    {
        Microsoft.Win32.SystemEvents.UserPreferenceChanged -= PreferencesChanged;
        _orbit.Stop();
        base.OnHandleDestroyed(e);
    }
    protected override void Dispose(bool disposing)
    {
        if (disposing) _orbit.Dispose();
        base.Dispose(disposing);
    }
}
