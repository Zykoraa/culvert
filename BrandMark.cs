using System.Drawing.Drawing2D;
using System.Reflection;

namespace Culvert;

/// <summary>The original tunnel mascot. Its orbit is decorative, never connection evidence.</summary>
internal static class BrandMark
{
    private static readonly Image Mascot = Load();
    private static Image Load()
    {
        using var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("Culvert-mark.png")
            ?? throw new InvalidOperationException("Culvert mascot resource is missing.");
        using var source = Image.FromStream(stream);
        return new Bitmap(source);
    }
    public static void Draw(Graphics g, RectangleF bounds, float angle)
    {
        float size = Math.Min(bounds.Width, bounds.Height), inset = size * .055f;
        var ring = new RectangleF(bounds.X + inset, bounds.Y + inset, size - inset * 2, size - inset * 2);
        Color red = SystemInformation.HighContrast ? SystemColors.WindowText : DashboardTheme.Blue;
        Color light = SystemInformation.HighContrast ? SystemColors.WindowText : DashboardTheme.Pink;
        using var track = new Pen(SystemInformation.HighContrast ? SystemColors.GrayText : Color.FromArgb(76, 35, 47), Math.Max(1, size * .008f));
        g.DrawEllipse(track, ring);
        using var arc = new Pen(red, Math.Max(1.4f, size * .023f)) { StartCap = LineCap.Round, EndCap = LineCap.Round };
        g.DrawArc(arc, ring, angle, 88);
        arc.Color = light; g.DrawArc(arc, ring, angle + 180, 88);
        for (int i = 0; i < 2; i++)
        {
            double radians = (angle + i * 180) * Math.PI / 180;
            float diameter = size * .064f;
            float x = ring.X + ring.Width / 2 + (float)Math.Cos(radians) * ring.Width / 2;
            float y = ring.Y + ring.Height / 2 + (float)Math.Sin(radians) * ring.Height / 2;
            using var dot = new SolidBrush(i == 0 ? red : light);
            g.FillEllipse(dot, x - diameter / 2, y - diameter / 2, diameter, diameter);
        }
        g.InterpolationMode = InterpolationMode.HighQualityBicubic;
        g.DrawImage(Mascot, bounds.X + size * .10f, bounds.Y + size * .10f, size * .80f, size * .80f);
    }
}
