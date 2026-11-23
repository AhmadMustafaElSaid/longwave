using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Threading.Tasks;
using System.Windows.Forms;

internal class Setup : Form {
    readonly string folder = AppDomain.CurrentDomain.BaseDirectory;
    readonly Button install = new Button(), disconnect = new Button(), rollback = new Button();
    readonly Button guide = new Button(), browse = new Button();
    readonly TextBox destination = new TextBox();
    readonly Label status = new Label(), intro = new Label(), outputLabel = new Label();
    readonly CheckBox consent = new CheckBox();
    readonly ProgressBar progress = new ProgressBar();
    bool busy, arabic;
    string installedExtension;

    string TextFor(string english, string arabicText) { return arabic ? arabicText : english; }
    Setup() {
        arabic = System.Globalization.CultureInfo.CurrentUICulture.TwoLetterISOLanguageName == "ar";
        Text = "Longwave — Setup";
        ClientSize = new Size(620, 575); FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false; StartPosition = FormStartPosition.CenterScreen;
        BackColor = Color.FromArgb(246,248,243); Font = new Font("Segoe UI", 10);
        AutoScaleMode = AutoScaleMode.Dpi;
        var header = new Panel { BackColor = Color.FromArgb(21,46,43), Bounds = new Rectangle(0,0,620,96) };
        header.Controls.Add(new Label { Text = "longwave.", ForeColor = Color.FromArgb(209,229,194),
            Font = new Font("Segoe UI", 28, FontStyle.Bold), AutoSize = true, Location = new Point(28,20) });
        var language = new Button { Text = "English / العربية", Bounds = new Rectangle(440,34,150,34), FlatStyle = FlatStyle.Flat,
            ForeColor = Color.White, BackColor = header.BackColor };
        language.Click += (s,e) => { arabic = !arabic; Translate(); }; header.Controls.Add(language);
        Controls.Add(header);
        intro.Bounds = new Rectangle(28,116,560,64); Controls.Add(intro);
        outputLabel.Bounds = new Rectangle(28,194,560,24); Controls.Add(outputLabel);
        destination.Text = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Downloads", "Longwave");
        try {
            string settings = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Longwave", "data", "config.json");
            if (File.Exists(settings)) {
                var saved = new System.Web.Script.Serialization.JavaScriptSerializer().Deserialize<System.Collections.Generic.Dictionary<string,object>>(File.ReadAllText(settings));
                if (saved.ContainsKey("output_dir") && saved["output_dir"] is string) destination.Text = (string)saved["output_dir"];
            }
        } catch { /* Fresh setup remains available if local settings are damaged. */ }
        destination.Bounds = new Rectangle(28,224,454,30); Controls.Add(destination);
        browse.Bounds = new Rectangle(492,221,98,34); Controls.Add(browse);
        browse.Click += (s,e) => { using (var picker = new FolderBrowserDialog()) {
            picker.SelectedPath = destination.Text; if (picker.ShowDialog() == DialogResult.OK) destination.Text = picker.SelectedPath; } };
        consent.Bounds = new Rectangle(28,278,560,54); Controls.Add(consent);
        consent.CheckedChanged += (s,e) => install.Enabled = consent.Checked && !busy;
        var licenses = new LinkLabel { Text = "Licenses / التراخيص", Bounds = new Rectangle(28,337,560,26), LinkColor = Color.FromArgb(17,105,88) };
        licenses.LinkClicked += (s,e) => Process.Start(new ProcessStartInfo(Path.Combine(folder, "LICENSES.txt")) { UseShellExecute = true });
        Controls.Add(licenses);
        status.Bounds = new Rectangle(28,374,560,44); Controls.Add(status);
        progress.Bounds = new Rectangle(28,426,560,8); Controls.Add(progress);
        install.Bounds = new Rectangle(28,452,270,42); install.BackColor = Color.FromArgb(18,108,89); install.ForeColor = Color.White;
        install.FlatStyle = FlatStyle.Flat; install.Enabled = false; Controls.Add(install);
        guide.Bounds = new Rectangle(312,452,276,42); Controls.Add(guide);
        guide.Click += (s,e) => {
            if (installedExtension != null) Clipboard.SetText(installedExtension);
            Process.Start(new ProcessStartInfo(Path.Combine(folder,"START-HERE.html")) { UseShellExecute = true });
        };
        disconnect.Bounds = new Rectangle(28,510,270,32); rollback.Bounds = new Rectangle(312,510,276,32);
        Controls.Add(disconnect); Controls.Add(rollback);
        install.Click += async (s,e) => await Execute("install");
        disconnect.Click += async (s,e) => await Execute("disconnect");
        rollback.Click += async (s,e) => await Execute("rollback");
        FormClosing += (s,e) => { if (busy) e.Cancel = true; };
        Translate();
    }
    void Translate() {
        RightToLeft = arabic ? RightToLeft.Yes : RightToLeft.No;
        RightToLeftLayout = arabic;
        destination.RightToLeft = RightToLeft.No;
        intro.Text = TextFor("Save long audio on this computer.\nSetup includes its own runtime. No Python or Node.js required.",
            "احفظ المقاطع الطويلة على هذا الجهاز.\nالتثبيت مستقل ولا يحتاج إلى Python أو Node.js.");
        outputLabel.Text = TextFor("Save audio to", "مجلد حفظ الصوت");
        browse.Text = TextFor("Browse…", "اختيار…");
        consent.Text = TextFor("Download verified FFmpeg tools from gyan.dev (about 114 MB).\nSetup uses this account only. Upgrades pause active downloads.",
            "تنزيل أدوات FFmpeg المتحقق منها من gyan.dev (نحو 114 MB).\nالتثبيت لهذا الحساب فقط. التحديث يوقف التنزيلات مؤقتًا.");
        install.Text = TextFor("Install / update", "تثبيت / تحديث");
        guide.Text = TextFor("Extension installation guide", "دليل تثبيت الإضافة");
        disconnect.Text = TextFor("Disconnect companion", "فصل التطبيق المرافق");
        rollback.Text = TextFor("Restore previous version", "استعادة الإصدار السابق");
        if (!busy) status.Text = TextFor("Windows 10/11 · 64-bit · Chrome and Edge", "Windows 10/11 · ‏64-bit · Chrome وEdge");
    }
    async Task Execute(string action) {
        if (action == "install" && (!Path.IsPathRooted(destination.Text) || string.IsNullOrWhiteSpace(destination.Text))) {
            status.Text = TextFor("Choose an absolute output folder.", "اختر مسارًا كاملًا لمجلد الحفظ."); return;
        }
        busy = true; install.Enabled = disconnect.Enabled = rollback.Enabled = browse.Enabled = destination.Enabled = false;
        progress.Style = ProgressBarStyle.Marquee;
        string finalError = "";
        try {
            string payload = Directory.Exists(Path.Combine(folder,"payload","runtime")) ? Path.Combine(folder,"payload") : folder;
            var start = new ProcessStartInfo(Path.Combine(payload,"runtime","python.exe"));
            start.Arguments = Host.Quote(Path.Combine(payload,"install.py")) + " " + action;
            if (action == "install") start.Arguments += " --output " + Host.Quote(destination.Text);
            start.UseShellExecute = false; start.CreateNoWindow = true;
            start.RedirectStandardOutput = start.RedirectStandardError = true;
            start.StandardOutputEncoding = start.StandardErrorEncoding = System.Text.Encoding.UTF8;
            start.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
            int code = await Task.Run(() => {
                using (var child = new Process { StartInfo = start }) {
                    child.OutputDataReceived += (s,e) => { if (!string.IsNullOrWhiteSpace(e.Data)) BeginInvoke((Action)(() => {
                        if (!e.Data.StartsWith("EXTENSION=")) status.Text = e.Data;
                        else { installedExtension = e.Data.Substring(10); guide.Text = TextFor("Copy path + open guide", "نسخ المسار وفتح الدليل"); }
                    })); };
                    child.ErrorDataReceived += (s,e) => { if (!string.IsNullOrWhiteSpace(e.Data)) finalError = e.Data; };
                    child.Start(); child.BeginOutputReadLine(); child.BeginErrorReadLine(); child.WaitForExit(); return child.ExitCode;
                }
            });
            status.Text = code == 0 ? TextFor("Done. Use the guide button to copy the extension folder and continue.",
                "تم. استخدم زر الدليل لنسخ مسار الإضافة والمتابعة.") : finalError;
        } catch (Exception error) { status.Text = error.Message; }
        finally { busy = false; progress.Style = ProgressBarStyle.Blocks; install.Enabled = consent.Checked;
            disconnect.Enabled = rollback.Enabled = browse.Enabled = destination.Enabled = true; }
    }
    [STAThread] static void Main(string[] args) {
        Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
        var form = new Setup();
        if (args.Length >= 2 && args[0] == "--render-preview") {
            form.destination.Text = @"C:\Users\You\Downloads\Longwave";
            if (args.Length == 3 && args[2] == "ar") { form.arabic = true; form.Translate(); }
            form.StartPosition = FormStartPosition.Manual;
            form.Location = new Point(-32000,-32000); form.ShowInTaskbar = false;
            form.Show(); Application.DoEvents();
            using (var bitmap = new Bitmap(form.Width, form.Height)) {
                form.DrawToBitmap(bitmap, new Rectangle(Point.Empty, bitmap.Size)); bitmap.Save(args[1]); }
            form.Dispose(); return;
        }
        Application.Run(form);
    }
}
