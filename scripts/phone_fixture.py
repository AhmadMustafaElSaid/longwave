"""Serve a disposable phone library containing two seconds of generated PCM."""
import hashlib
import json
import os
import sys
import tempfile
import threading
import uuid
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "companion"))
from longwave.phone import PhoneRequest, PhoneServer
from longwave.store import Store

with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    store = Store(root / "state")
    (store.root / "config.json").write_text(json.dumps({"output_dir": str(root)}))
    file = root / "Longwave test.wav"
    with wave.open(str(file), "wb") as wav:
        wav.setparams((1, 2, 8000, 16000, "NONE", "PCM"))
        wav.writeframes(bytes(32000))
    job = store.create(str(uuid.uuid4()), "https://soundcloud.com/fixture/tone", "original")
    store.finish(job["id"], state="completed", title="Test recording", output=str(file))
    with PhoneServer(store, port=0) as server:
        if os.environ.get("LONGWAVE_FIXTURE_TRACE"):
            class FixtureRequest(PhoneRequest):
                def send_response(self, code, message=None):
                    if self.path.startswith("/audio/"):
                        print(f"Fixture media request: {self.command} {self.path.rsplit('/',1)[-1]} {code}",
                              file=sys.stderr, flush=True)
                    super().send_response(code, message)
            server.RequestHandlerClass = FixtureRequest
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        print(json.dumps(dict(origin=server.origin,code=server.pairing.display_code,
                             sha256=hashlib.sha256(file.read_bytes()).hexdigest())), flush=True)
        sys.stdin.buffer.read(1)
        server.shutdown()
        thread.join()
