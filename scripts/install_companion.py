"""Register an isolated developer companion for Chrome and Edge on Windows."""

import argparse
import importlib.util
import json
import os
import re
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "companion"))
from longwave import HOST_NAME
from longwave.runtime import tool_path
from longwave.store import Store, home_dir


def install(data_root, output_root):
    if os.name != "nt":
        raise SystemExit("This developer installer currently supports Windows only.")
    import winreg
    identity = ROOT / "dist" / "extension-id.txt"
    if not identity.exists():
        raise SystemExit("Build the extension first: npm run build")
    extension_id = identity.read_text().strip()
    if not re.fullmatch(r"[a-p]{32}", extension_id):
        raise SystemExit("The generated extension ID is invalid. Rebuild the extension.")
    if importlib.util.find_spec("yt_dlp") is None:
        raise SystemExit("Run this script using the project .venv after installing companion/requirements.txt.")
    paths_file = ROOT / '.tools/media-paths.json'
    supplied = json.loads(paths_file.read_text()) if paths_file.exists() else {"ffmpeg": None, "ffprobe": None}
    selected = {name: tool_path(supplied, name) for name in supplied}
    if not all(selected.values()):
        raise SystemExit("FFmpeg/ffprobe are missing. Run npm run setup:media or add both executables to PATH.")
    for name, executable in selected.items():
        try:
            subprocess.run([executable, "-version"], check=True, capture_output=True, timeout=10,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        except (OSError, subprocess.SubprocessError) as exc:
            raise SystemExit(f"{name} could not run. Repair its download before installing the companion.") from exc
    data_root = Path(data_root).resolve()
    output_root = Path(output_root).resolve()
    for value in (str(ROOT), str(data_root), sys.executable):
        if any(c in value for c in '%"\r\n'):
            raise SystemExit("The developer launcher does not support percent signs or quotes in installation paths.")
    data_root.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)
    origin = f"chrome-extension://{extension_id}/"
    settings = {**selected, "output_dir": str(output_root), "allowed_origins": [origin]}
    (data_root / "config.json").write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    stop = data_root / "stop-worker"
    if stop.exists():
        stop.unlink()
    launcher = data_root / "longwave-host.cmd"
    launcher.write_text(
        '@echo off\n@chcp 65001 >nul\n'
        f'set "PYTHONPATH={ROOT / "companion"}"\n'
        f'set "LONGWAVE_HOME={data_root}"\n'
        f'"{sys.executable}" -m longwave %*\n', encoding="utf-8")
    manifest = {"name": HOST_NAME, "description": "Longwave local audio companion", "path": str(launcher),
                "type": "stdio", "allowed_origins": [origin]}
    manifest_path = data_root / "native-host.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for browser in ("Google\\Chrome", "Microsoft\\Edge"):
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"Software\\{browser}\\NativeMessagingHosts\\{HOST_NAME}") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, str(manifest_path))
    Store(data_root)
    print(f"Companion registered for Chrome and Edge.\nExtension ID: {extension_id}\nData: {data_root}\nAudio: {output_root}")


def uninstall(data_root):
    if os.name != "nt":
        raise SystemExit("This uninstaller currently supports Windows only.")
    import winreg
    store = Store(data_root)
    for job in store.list():
        if job["state"] in {"queued", "resolving", "downloading", "processing", "verifying"}:
            store.command(job["id"], "pause")
    (store.root / "stop-worker").touch()
    for browser in ("Google\\Chrome", "Microsoft\\Edge"):
        try:
            path = f"Software\\{browser}\\NativeMessagingHosts\\{HOST_NAME}"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
                registered, _ = winreg.QueryValueEx(key, "")
            if Path(registered).resolve() == (store.root / "native-host.json").resolve():
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
        except FileNotFoundError:
            pass
    print("Companion disconnected. Downloads and partial files were preserved.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=home_dir())
    parser.add_argument("--output", type=Path, default=Path.home() / "Downloads" / "Longwave")
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()
    uninstall(args.home) if args.uninstall else install(args.home, args.output)
