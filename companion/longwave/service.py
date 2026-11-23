"""Small, validated native command surface."""

import os
import subprocess
from pathlib import Path

from . import PROTOCOL_VERSION, VERSION
from .model import ACTIVE, UserError, identifier, public_job, track_url
from .runtime import config, ensure_worker, hidden_process_options, require_tools, tools_status


def dispatch(store, message, start_worker=ensure_worker):
    if message.get("version") != PROTOCOL_VERSION:
        raise UserError("version_mismatch", "Update the extension and companion to matching versions.")
    command = message.get("command")
    allowed = {"version", "command", "requestId", "url", "format", "id"}
    if set(message) - allowed:
        raise UserError("invalid_request", "Unexpected command fields.")
    if command == "snapshot":
        jobs = store.list()
        if any(job["state"] in ACTIVE for job in jobs):
            start_worker(store)
        return {"version": VERSION, "protocol": PROTOCOL_VERSION, "tools": tools_status(store),
                "outputDir": config(store)["output_dir"], "jobs": [public_job(j) for j in jobs]}
    if command == "create":
        request_id = identifier(message.get("requestId"))
        url = track_url(message.get("url"))
        output_format = message.get("format", "original")
        if output_format not in {"original", "mp3"}:
            raise UserError("invalid_format", "Choose source audio or MP3.")
        require_tools(store)
        job = store.create(request_id, url, output_format)
        start_worker(store)
        return public_job(job)
    if command in {"pause", "resume", "cancel"}:
        if command == "resume":
            require_tools(store)
        job = store.command(identifier(message.get("id")), command)
        if command == "resume":
            start_worker(store)
        return public_job(job)
    if command == "reveal":
        job = store.get(identifier(message.get("id")))
        path = Path(job.get("output") or "").resolve()
        root = Path(config(store)["output_dir"]).resolve()
        if job["state"] != "completed" or not path.is_relative_to(root) or not path.is_file():
            raise UserError("file_missing", "The completed file has been moved or removed.")
        if os.name == "nt":
            subprocess.Popen(["explorer.exe", "/select,", str(path)], **hidden_process_options())
        else:
            raise UserError("unsupported_platform", "Open the output folder in your file manager.")
        return {"revealed": True}
    raise UserError("invalid_request", "Unknown command.")
