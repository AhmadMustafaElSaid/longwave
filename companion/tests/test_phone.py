import http.client
import json
import sys
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from longwave.phone import PhoneServer, checked_origin
from longwave.service import dispatch
from longwave.store import Store


class PhoneTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = Store(Path(temp.name) / "state")
        self.audio = Path(temp.name) / "audio"
        self.audio.mkdir()
        (self.store.root / "config.json").write_text(json.dumps({"output_dir": str(self.audio)}))
        self.server = PhoneServer(self.store, port=0)
        thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .02}, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(thread.join, 2)
        self.addCleanup(self.server.shutdown)
        self.cookie = ""

    def request(self, path, data=None, method=None, **headers):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        defaults = {"Origin": self.server.origin, "Content-Type": "application/json", "Cookie": self.cookie}
        try:
            conn.request(method or ("POST" if data is not None else "GET"), path,
                         json.dumps(data) if data is not None else None, {**defaults, **headers})
            res = conn.getresponse()
            return res.status, dict(res.getheaders()), res.read()
        finally:
            conn.close()

    def pair(self):
        code = self.server.pairing.display_code
        status, headers, _ = self.request("/api/pair", {"code": code})
        self.assertEqual(status, 200)
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        self.assertIn("SameSite=Strict", headers["Set-Cookie"])
        self.cookie = headers["Set-Cookie"].split(";")[0]
        return code

    def test_pairing_origin_host_expiry_and_replay(self):
        self.assertEqual(self.request("/api/jobs")[0], 401)
        self.assertEqual(self.request("/", Host="elsewhere.invalid")[0], 403)
        code = self.server.pairing.display_code
        self.assertEqual(self.request("/api/pair", {"code": code}, Origin="https://elsewhere.invalid")[0], 403)
        self.pair()
        self.assertEqual(self.request("/api/pair", {"code": code})[0], 403)
        self.assertEqual(self.request("/api/jobs")[0], 200)
        self.server.pairing.expires = 0
        self.assertEqual(self.request("/api/jobs")[0], 401)

    def test_queue_create_is_idempotent_and_controls_are_origin_bound(self):
        self.pair()
        with patch("longwave.phone.dispatch", side_effect=lambda store, msg: dispatch(store, msg, start_worker=lambda _: None)), patch("longwave.service.require_tools"):
            data = dict(command="create", requestId=str(uuid.uuid4()), url="https://soundcloud.com/fixture/track", format="mp3")
            first = json.loads(self.request("/api/jobs", data)[2])
            self.assertEqual(json.loads(self.request("/api/jobs", data)[2]), first)
            for action, state in (("pause", "paused"), ("resume", "queued"), ("cancel", "cancelled")):
                self.assertEqual(json.loads(self.request("/api/jobs", dict(command=action,id=first["id"]))[2])["state"], state)
            self.assertEqual(self.request("/api/jobs", data, Origin="null")[0], 403)
            listing = json.loads(self.request("/api/jobs")[2])["jobs"]
            self.assertEqual(len(listing), 1)
            self.assertNotIn("output", listing[0])
            self.assertNotIn("url", listing[0])

    def test_file_save_seek_head_and_confinement(self):
        job = self.store.create(str(uuid.uuid4()), "https://soundcloud.com/fixture/track", "original")
        file = self.audio / "صوت.mp3"
        file.write_bytes(bytes(range(100)))
        self.store.finish(job["id"], state="completed", output=str(file))
        path = f"/audio/{job['id']}/save"
        self.assertEqual(self.request(path)[0], 401)
        self.pair()
        status, headers, body = self.request(path)
        self.assertEqual((status, body), (200, file.read_bytes()))
        self.assertIn("attachment;", headers["Content-Disposition"])
        self.assertIn("filename*=UTF-8", headers["Content-Disposition"])
        for header, expected in (("bytes=20-29", bytes(range(20,30))), ("bytes=-5", bytes(range(95,100))), ("bytes=99-", bytes([99]))):
            status, headers, body = self.request(path.replace("/save","/listen"), Range=header)
            self.assertEqual((status,body), (206,expected))
            self.assertIn("inline", headers["Content-Disposition"])
        self.assertEqual(self.request(path, Range="bytes=120-")[0], 416)
        self.assertEqual(self.request(path, method="HEAD")[2], b"")
        self.store.update(job["id"], output=str(self.store.root / "config.json"))
        self.assertEqual(self.request(path)[0], 404)

    def test_private_proxy_and_public_assets(self):
        self.assertEqual(checked_origin("https://demo.example:9000/", 8765), "https://demo.example:9000")
        for value in ("http://demo.example", "https://example.com/path", "https://name@demo.example"):
            with self.assertRaises(ValueError):
                checked_origin(value, 8765)
        for path in ("/", "/phone.js", "/phone.css"):
            status, headers, body = self.request(path)
            self.assertEqual(status, 200)
            self.assertTrue(body)
            self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(self.request("/../config.json")[0], 401)
