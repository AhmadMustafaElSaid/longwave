"""One detached, serial worker per installation. Browser lifetime is irrelevant."""

import os
import time
import json
import subprocess
import sys

from .engine import error_details, run_job
from .model import Stopped
from .store import Store
from .runtime import hidden_process_options
from .process_guard import guard_process_tree


def execute_job(store, job_id):
    """One process per job releases all extractor file handles on interruption."""
    try:
        run_job(store, job_id)
    except Stopped:
        store.finish(job_id, state=store.get(job_id)["desired"], speed=None, eta=None)
    except Exception as exc:
        store.finish(job_id, state="failed", error=error_details(exc), speed=None, eta=None)


class WorkerLock:
    def __init__(self, root):
        self.path = root / "worker.lock"
        self.file = None

    def __enter__(self):
        self.file = open(self.path, "a+b")
        self.file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            self.file = None
            return False
        return True

    def __exit__(self, *args):
        if self.file:
            if os.name == "nt":
                import msvcrt
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            self.file.close()


def run_worker():
    store = Store()
    with WorkerLock(store.root) as acquired:
        if not acquired:
            return
        guarded = guard_process_tree()
        (store.root / "worker-info.json").write_text(json.dumps({"pid": os.getpid(), "started": time.time(), "processTreeGuard": guarded}), encoding="utf-8")
        store.recover()
        while True:
            if (store.root / "stop-worker").exists():
                return
            pending = [job for job in reversed(store.list()) if job["state"] == "queued" and job["desired"] == "running"]
            if not pending:
                time.sleep(1)
                continue
            job = pending[0]
            process = subprocess.Popen([sys.executable, "-m", "longwave", "run-job", job["id"]],
                                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, **hidden_process_options())
            code = process.wait()
            if code != 0 and store.get(job["id"])["state"] not in {"completed", "paused", "cancelled", "failed"}:
                store.finish(job["id"], state="failed", error={"code": "worker_stopped",
                             "message": "The audio process stopped unexpectedly. Retry to recover the partial download."})
