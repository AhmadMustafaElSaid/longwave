using System;
using System.Diagnostics;
using System.IO;

// Native Messaging shim. Forward byte streams without decoding or logging.
internal static class Host {
    static async System.Threading.Tasks.Task Forward(Stream source, Stream destination) {
        byte[] buffer = new byte[8192];
        int count;
        while ((count = await source.ReadAsync(buffer, 0, buffer.Length)) != 0) {
            await destination.WriteAsync(buffer, 0, count);
            await destination.FlushAsync();
        }
    }
    internal static string Quote(string value) {
        var result = new System.Text.StringBuilder("\"");
        int slashes = 0;
        foreach (char character in value) {
            if (character == '\\') { slashes++; continue; }
            result.Append('\\', character == '"' ? slashes * 2 + 1 : slashes);
            result.Append(character); slashes = 0;
        }
        result.Append('\\', slashes * 2); result.Append('"');
        return result.ToString();
    }
    private static int Main(string[] args) {
        string folder = AppDomain.CurrentDomain.BaseDirectory;
        var start = new ProcessStartInfo(Path.Combine(folder, "runtime", "python.exe"));
        start.UseShellExecute = false;
        start.CreateNoWindow = true;
        start.RedirectStandardInput = true;
        start.RedirectStandardOutput = true;
        start.RedirectStandardError = true;
        start.WorkingDirectory = folder;
        start.Arguments = "-m longwave";
        foreach (string arg in args) start.Arguments += " " + Quote(arg);
        start.EnvironmentVariables["LONGWAVE_HOME"] = Path.GetFullPath(Path.Combine(folder, "..", "..", "data"));
        try { using (var child = Process.Start(start)) {
            var input = System.Threading.Tasks.Task.Run(async () => {
                try { await Forward(Console.OpenStandardInput(), child.StandardInput.BaseStream); }
                finally { child.StandardInput.Close(); }
            });
            var output = Forward(child.StandardOutput.BaseStream, Console.OpenStandardOutput());
            var errors = child.StandardError.BaseStream.CopyToAsync(Stream.Null);
            child.WaitForExit();
            output.GetAwaiter().GetResult(); errors.GetAwaiter().GetResult();
            return child.ExitCode;
        } }
        catch { return 1; }
    }
}
