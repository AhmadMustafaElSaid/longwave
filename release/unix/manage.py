"""Register a packaged companion and run its optional phone interface."""

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
LIB = PACKAGE / "lib"
sys.path.insert(0, str(LIB))
from longwave import HOST_NAME
from longwave.model import ACTIVE
from longwave.runtime import config
from longwave.store import Store
from longwave.worker import WorkerLock


def profile_dirs(home, platform):
    if platform == "darwin":
        parent = home / "Library/Application Support"
        profiles = ("Google/Chrome", "Google/ChromeForTesting", "Chromium", "Microsoft Edge")
    else:
        parent = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
        profiles = ("google-chrome", "google-chrome-for-testing", "chromium", "microsoft-edge")
    return [parent / profile / "NativeMessagingHosts" for profile in profiles]


def write_file(path, data, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temp:
        tmp = Path(temp.name)
        try:
            os.fchmod(temp.fileno(), mode)
            temp.write(data.encode("utf-8"))
            temp.flush()
            os.fsync(temp.fileno())
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
    try:
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def quiesce(store):
    marker = store.root / "stop-worker"
    marker.touch()
    for job in store.list():
        if job["state"] in ACTIVE:
            store.command(job["id"], "pause")
    deadline = time.monotonic() + 50
    while time.monotonic() < deadline:
        with WorkerLock(store.root) as acquired:
            if acquired:
                return
        time.sleep(.2)
    marker.unlink(missing_ok=True)
    raise ValueError("A download is still stopping. Retry setup after it pauses.")


def configure(store, output, remove=False):
    settings = config(store)
    host = store.root / "native-host"
    manifests = [directory / (HOST_NAME + ".json") for directory in profile_dirs(Path.home(), sys.platform)]
    for file in manifests:
        if file.exists() and json.loads(file.read_text())["path"] != str(host):
            raise ValueError(f"Another installation owns {file}. Disconnect it before switching.")
    if remove:
        quiesce(store)
        for file in manifests:
            file.unlink(missing_ok=True)
        print("Disconnected. Your saved audio and download queue are in place.")
        return
    for name in ("ffmpeg", "ffprobe"):
        exe = shutil.which(name)
        if not exe:
            raise ValueError(f"Install {name} with your system package manager, then run connect again.")
        subprocess.run([exe, "-version"], check=True, stdout=subprocess.DEVNULL, timeout=15)
        settings[name] = exe
    output = Path(output or settings["output_dir"]).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    origins = json.loads((PACKAGE / "origins.json").read_text())
    settings.update(output_dir=str(output), allowed_origins=origins)
    script = ("#!/bin/sh\nexport LONGWAVE_HOME=" + shlex.quote(str(store.root)) +
              "\nexport PYTHONPATH=" + shlex.quote(str(LIB)) +
              "\nexport PATH=" + shlex.quote(os.pathsep.join(dict.fromkeys([str(Path(settings["ffmpeg"]).parent), "/usr/bin", "/bin"]))) +
              "\nexec " + shlex.quote(sys.executable) + ' -s -P -m longwave "$@"\n')
    manifest = dict(name=HOST_NAME, description="Longwave local audio companion", path=str(host),
                    type="stdio", allowed_origins=origins)
    writes = [(host, script, 0o700), (store.root / "config.json", json.dumps(settings), 0o600)]
    writes += [(path, json.dumps(manifest), 0o600) for path in manifests]
    previous = {p: (p.read_text(), p.stat().st_mode & 0o777) if p.exists() else None for p, _, _ in writes}
    completed = []
    quiesce(store)
    try:
        for p, data, mode in writes:
            write_file(p, data, mode)
            completed.append(p)
    except BaseException:
        for path in reversed(completed):
            if previous[path] is None:
                path.unlink(missing_ok=True)
            else:
                write_file(path, *previous[path])
        raise
    finally:
        (store.root / "stop-worker").unlink(missing_ok=True)
    print(f"Connected. In your browser choose Load unpacked and select:\n{PACKAGE / 'extension'}\nAudio: {output}")


def main():
    if sys.version_info < (3, 11):
        raise SystemExit("Longwave requires Python 3.11 or later.")
    default = (Path.home() / "Library/Application Support/Longwave" if sys.platform == "darwin"
               else Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "longwave")
    os.environ.setdefault("LONGWAVE_HOME", str(default))
    os.environ["PYTHONPATH"] = str(LIB)
    parser = argparse.ArgumentParser(prog="longwave")
    commands = parser.add_subparsers(dest="command", required=True)
    connect = commands.add_parser("connect", help="Connect this install to Chrome, Edge and Chromium")
    connect.add_argument("--output", type=Path)
    commands.add_parser("disconnect", help="Detach browsers and retain your library")
    phone = commands.add_parser("phone", help="Pair a phone with this computer")
    phone.add_argument("--origin")
    phone.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()
    store = Store()
    if args.command == "phone":
        from longwave.phone import serve
        serve(store, args.origin, args.port)
    else:
        lock_dir = store.root / "setup"
        lock_dir.mkdir(exist_ok=True)
        with WorkerLock(lock_dir) as acquired:
            if not acquired:
                raise ValueError("Another Longwave installer is active.")
            configure(store, getattr(args, "output", None), args.command == "disconnect")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        sys.exit(str(exc))
