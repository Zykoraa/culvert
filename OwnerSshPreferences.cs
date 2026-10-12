#if OWNER_BUILD
using System.Text.Json;

namespace Culvert;

internal sealed record OwnerSshOptions(string User = "opc", int Port = 22, string KeyPath = "");

internal static class OwnerSshPreferences
{
    internal static string DefaultKeyPath => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".ssh", "culvert.key");
    private static string SettingsPath => Path.Combine(AppPaths.DataDir, "owner-ssh.json");
    internal static string ResolveKey(OwnerSshOptions options) => options.KeyPath.Length == 0 ? DefaultKeyPath : options.KeyPath;
    internal static bool Valid(OwnerSshOptions options) => options.User.Length is > 0 and <= 32 &&
        options.User.All(c => char.IsAsciiLetterOrDigit(c) || c is '_' or '-') &&
        options.Port is > 0 and <= 65535 && options.KeyPath.Length <= 1024 &&
        !options.KeyPath.Any(char.IsControl) && (options.KeyPath.Length == 0 || Path.IsPathFullyQualified(options.KeyPath));
    internal static OwnerSshOptions Read()
    {
        try
        {
            if (new FileInfo(SettingsPath).Length > 4096) return new();
            var options = JsonSerializer.Deserialize<OwnerSshOptions>(File.ReadAllText(SettingsPath));
            return options != null && Valid(options) ? options : new();
        }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException or JsonException or ArgumentException or NullReferenceException)
        { return new(); }
    }
    internal static void Save(OwnerSshOptions options)
    {
        if (!Valid(options)) throw new InvalidDataException("Enter a valid SSH username, port and absolute key path.");
        string temporary = SettingsPath + ".new";
        try
        {
            File.WriteAllText(temporary, JsonSerializer.Serialize(options), AppPaths.Utf8NoBom);
            File.Move(temporary, SettingsPath, true);
        }
        finally { if (File.Exists(temporary)) File.Delete(temporary); }
    }
}
#endif
