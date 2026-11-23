"""Local paths and managed child processes; no shell command interpolation."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .model import UserError


def config(store):
    path = store.root / "config.json"
    if not path.exists():
        return {"output_dir": str(Path.home() / "Downloads" / "Longwave"), "allowed_origins": []}
    return json.loads(path.read_text(encoding="utf-8"))


def tools_status(store):
    settings = config(store)
    import importlib.util
    return {
        "extractor": importlib.util.find_spec("yt_dlp") is not None,
        "ffmpeg": tool_path(settings, "ffmpeg") is not None,
        "ffprobe": tool_path(settings, "ffprobe") is not None,
    }


def tool_path(settings, name):
    supplied = settings.get(name)
    return supplied if supplied and Path(supplied).is_file() else shutil.which(name)


def require_tools(store):
    status = tools_status(store)
    if not all(status.values()):
        missing = ", ".join(k for k, v in status.items() if not v)
        raise UserError("setup_required", f"Finish companion setup. Missing: {missing}.")


def hidden_process_options():
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


def ensure_worker(store):
    # Every connection can safely attempt this: the worker owns an OS lock.
    from .worker import WorkerLock
    with WorkerLock(store.root) as acquired:
        if not acquired:
            return
    worker_python = Path(sys.executable)
    if os.name == "nt" and worker_python.with_name("pythonw.exe").exists():
        worker_python = worker_python.with_name("pythonw.exe")
    env = dict(os.environ, LONGWAVE_HOME=str(store.root))
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    subprocess.Popen([str(worker_python), "-m", "longwave", "worker"], env=env,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, close_fds=True,
                     start_new_session=os.name != "nt", **hidden_process_options())
