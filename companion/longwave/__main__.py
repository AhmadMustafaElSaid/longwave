import json
import os
import sys

from .engine import error_details
from .model import UserError
from .protocol import read_message, write_message
from .runtime import config
from .service import dispatch
from .store import Store


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "worker":
        from .worker import run_worker
        run_worker()
        return
    store = Store()
    if len(sys.argv) == 3 and sys.argv[1] == "run-job":
        from .model import identifier
        from .worker import execute_job
        execute_job(store, identifier(sys.argv[2]))
        return
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        print(json.dumps(dispatch(store, {"version": 1, "command": "snapshot"}), indent=2))
        return
    # Chromium supplies the calling origin. This is additional to its manifest allowlist.
    origin = next((arg for arg in sys.argv[1:] if arg.startswith("chrome-extension://")), None)
    if origin not in config(store).get("allowed_origins", []):
        return
    if os.name == "nt":
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    while True:
        try:
            message = read_message(sys.stdin.buffer)
            if message is None:
                return
            result = dispatch(store, message)
            write_message(sys.stdout.buffer, {"ok": True, "data": result})
        except UserError as exc:
            write_message(sys.stdout.buffer, {"ok": False, "error": error_details(exc)})
            if exc.code == "invalid_message":
                return
        except Exception:
            write_message(sys.stdout.buffer, {"ok": False, "error": {
                "code": "internal", "message": "The local companion encountered an error. Reopen Longwave and retry."}})
            return


if __name__ == "__main__":
    main()
