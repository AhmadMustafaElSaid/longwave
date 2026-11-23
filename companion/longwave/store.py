"""Small transactional job journal. Media bytes never enter SQLite."""

import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from .model import ACTIVE, UserError


def home_dir():
    override = os.environ.get("LONGWAVE_HOME")
    if override:
        return Path(override).resolve()
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share"))
    return base / "Longwave"


class Store:
    def __init__(self, root=None):
        self.root = Path(root or home_dir()).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            self.root.chmod(0o700)
        self.path = self.root / "jobs.sqlite3"
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL, data TEXT NOT NULL)")

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute("PRAGMA synchronous=FULL")
            with db:
                yield db
        finally:
            db.close()

    def list(self):
        with self.connection() as db:
            rows = db.execute("""SELECT data FROM jobs ORDER BY
                CASE WHEN json_extract(data, '$.state') IN
                ('queued','resolving','downloading','processing','verifying','paused') THEN 0 ELSE 1 END,
                rowid DESC LIMIT 100""").fetchall()
        return [json.loads(row[0]) for row in rows]

    def get(self, job_id):
        with self.connection() as db:
            row = db.execute("SELECT data FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise UserError("not_found", "This download no longer exists.")
        return json.loads(row[0])

    def create(self, request_id, url, output_format):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT data FROM jobs WHERE request_id=?", (request_id,)).fetchone()
            if existing:
                job = json.loads(existing[0])
                if job.get("request_url", job["url"]) != url or job["format"] != output_format:
                    raise UserError("request_conflict", "This request identifier was already used.")
                return job
            active_count = 0
            for row in db.execute("SELECT data FROM jobs"):
                job = json.loads(row[0])
                active_count += job["state"] in ACTIVE | {"paused"}
                if url in {job["url"], job.get("request_url")} and job["format"] == output_format and job["state"] in ACTIVE | {"paused"}:
                    return job
            if active_count >= 20:
                raise UserError("queue_full", "The queue holds up to 20 unfinished downloads. Finish or cancel one before adding more.")
            now = time.time()
            job = dict(id=str(uuid.uuid4()), url=url, request_url=url, format=output_format, state="queued",
                       desired="running", title=url.rsplit("/", 1)[-1].replace("-", " "),
                       artist="SoundCloud", duration=None, bytes=0, total=None, speed=None,
                       eta=None, progress=None, created=now, updated=now, error=None,
                       output=None, note=None, codec=None, source_bitrate=None)
            db.execute("INSERT INTO jobs VALUES (?,?,?)", (job["id"], request_id, json.dumps(job)))
        return job

    def update(self, job_id, **changes):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT data FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise UserError("not_found", "This download no longer exists.")
            job = json.loads(row[0])
            job.update(changes, updated=time.time())
            db.execute("UPDATE jobs SET data=? WHERE id=?", (json.dumps(job), job_id))
        return job

    def command(self, job_id, action):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT data FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise UserError("not_found", "This download no longer exists.")
            job = json.loads(row[0])
            state = job["state"]
            if action == "pause" and state in ACTIVE:
                job["desired"] = "paused"
                if state == "queued":
                    job["state"] = "paused"
            elif action == "resume" and state in {"paused", "failed"}:
                job.update(desired="running", state="queued", error=None, speed=None, eta=None)
            elif action == "cancel" and state in ACTIVE | {"paused", "failed"}:
                job["desired"] = "cancelled"
                if state in {"queued", "paused", "failed"}:
                    job["state"] = "cancelled"
            else:
                raise UserError("invalid_transition", "This action is not available in the current state.")
            job["updated"] = time.time()
            db.execute("UPDATE jobs SET data=? WHERE id=?", (json.dumps(job), job_id))
        return job

    def recover(self):
        # Called only while holding the exclusive worker lock.
        for job in self.list():
            if job["state"] in ACTIVE - {"queued"}:
                state = "queued" if job["desired"] == "running" else job["desired"]
                self.update(job["id"], state=state, speed=None, eta=None,
                            note="Recovered after the local worker stopped. Checking the source before continuing.")

    def finish(self, job_id, **changes):
        # A user cancellation racing with completion must win.
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            job = json.loads(db.execute("SELECT data FROM jobs WHERE id=?", (job_id,)).fetchone()[0])
            job.update(changes, updated=time.time())
            if job["desired"] != "running":
                job["state"] = job["desired"]
            db.execute("UPDATE jobs SET data=? WHERE id=?", (json.dumps(job), job_id))
        return job
