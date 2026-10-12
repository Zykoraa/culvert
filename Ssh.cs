#if OWNER_BUILD
using System.Diagnostics;
namespace Culvert;
internal static class Ssh
{
    public static bool KeyPresent => File.Exists(OwnerSshPreferences.ResolveKey(OwnerSshPreferences.Read()));
    public static async Task<(int code, string output)> RunAsync(string remoteCommand, int timeoutMs = 30000, string? input = null)
    {
        var options = OwnerSshPreferences.Read();
        string keyPath = OwnerSshPreferences.ResolveKey(options);
        if (!File.Exists(keyPath)) return (-1, "Set your private key under Settings → VM access first.");
        var profile = Profile.Load();
        if (profile.Imported != null) return (-1, "Owner server administration is unavailable for an imported v2rayN server.");
        if (!profile.IsValid) return (-1, "Invalid connection profile.");
        var psi = new ProcessStartInfo("ssh.exe") { UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardOutput = true, RedirectStandardError = true, RedirectStandardInput = true };
        foreach (var arg in new[] { "-i", keyPath, "-p", options.Port.ToString(System.Globalization.CultureInfo.InvariantCulture),
            "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
            "-o", "UserKnownHostsFile=" + Path.Combine(AppPaths.DataDir, "ssh-known-hosts"),
            "-o", "ConnectTimeout=8", options.User + "@" + profile.Server, remoteCommand }) psi.ArgumentList.Add(arg);
        try
        {
            using var process = Process.Start(psi)!;
            var stdout = process.StandardOutput.ReadToEndAsync();
            var stderr = process.StandardError.ReadToEndAsync();
            using var timeout = new CancellationTokenSource(timeoutMs);
            try
            {
                if (input != null) await process.StandardInput.WriteAsync(input.AsMemory(), timeout.Token);
                process.StandardInput.Close();
                await process.WaitForExitAsync(timeout.Token);
            }
            catch (OperationCanceledException)
            {
                try { process.Kill(entireProcessTree: true); } catch { }
                return (-1, "Server request timed out. The operation may still finish; refresh its status.");
            }
            var output = (await stdout).Trim();
            var error = (await stderr).Trim();
            return (process.ExitCode, process.ExitCode == 0 ? output : (output.Length > 0 ? output : error));
        }
        catch (Exception ex) { return (-1, ex.Message); }
    }
}
#endif
