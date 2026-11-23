"""Real downloader + FFmpeg against generated audio on a loopback fixture server.

Only SoundCloud resolution and the HTTPS eligibility gate are replaced. Production
does not accept local URLs. No real music or user browser data is used.
"""

import functools
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from longwave.engine import run_job
from longwave.protocol import read_message, write_message
from longwave.runtime import hidden_process_options
from longwave.store import Store

ROOT = Path(__file__).resolve().parents[2]
MEDIA_PATHS = ROOT / '.tools/media-paths.json'
MEDIA = json.loads(MEDIA_PATHS.read_text()) if MEDIA_PATHS.exists() else {}
FFMPEG = Path(os.environ.get('LONGWAVE_TEST_FFMPEG') or MEDIA.get('ffmpeg') or 'missing-ffmpeg')
FFPROBE = Path(os.environ.get('LONGWAVE_TEST_FFPROBE') or MEDIA.get('ffprobe') or 'missing-ffprobe')
READY = importlib.util.find_spec("yt_dlp") is not None and FFMPEG.exists() and FFPROBE.exists()


@unittest.skipUnless(READY, "Pipeline checks need the project .venv and npm run setup:media")
class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.media = cls.root / "media"
        cls.media.mkdir()
        cls.source = cls.media / "tone.m4a"
        subprocess.run([str(FFMPEG), "-nostdin", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                        "-i", "sine=frequency=440:sample_rate=44100", "-t", "30", "-ac", "2",
                        "-c:a", "aac", "-b:a", "160k", str(cls.source)], check=True, **hidden_process_options())
        subprocess.run([str(FFMPEG), "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(cls.source),
                        "-c:a", "copy", "-hls_time", "2", "-hls_playlist_type", "vod", "-hls_segment_type", "fmp4",
                        str(cls.media / "tone.m3u8")], check=True, cwd=cls.media, **hidden_process_options())

        class Handler(SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def send_head(self):
                path = Path(self.translate_path(self.path))
                if not path.is_file():
                    self.send_error(404)
                    return None
                size = path.stat().st_size
                start = 0
                range_header = self.headers.get("Range", "")
                if range_header.startswith("bytes="):
                    start = int(range_header.split("=", 1)[1].split("-", 1)[0])
                self.send_response(206 if start else 200)
                self.send_header("Content-Type", "application/vnd.apple.mpegurl" if path.suffix == ".m3u8" else "audio/mp4")
                self.send_header("Content-Length", str(size - start))
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("ETag", '"fixture-v1"')
                if start:
                    self.send_header("Content-Range", f"bytes {start}-{size - 1}/{size}")
                self.end_headers()
                handle = path.open("rb")
                handle.seek(start)
                return handle

            def copyfile(self, source, outputfile):
                try:
                    while chunk := source.read(8192):
                        outputfile.write(chunk)
                        time.sleep(0.01)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(cls.media)))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def setUp(self):
        self.store = Store(self.root / str(uuid.uuid4()))
        self.output = self.store.root / "downloads"
        (self.store.root / "config.json").write_text(json.dumps({"ffmpeg": str(FFMPEG), "ffprobe": str(FFPROBE),
            "output_dir": str(self.output), "allowed_origins": ["chrome-extension://" + "a" * 32 + "/"]}))

    def run_fixture(self, output_format="original", hls=False, existing=None, background=False):
        from yt_dlp import YoutubeDL
        source = {"format_id": "fixture_aac", "ext": "m4a", "protocol": "m3u8_native" if hls else "http",
                  "url": f"http://127.0.0.1:{self.server.server_port}/tone.{'m3u8' if hls else 'm4a'}",
                  "acodec": "mp4a.40.2", "vcodec": "none", "abr": 160}
        info = {"id": "fixture", "title": "Generated tone", "uploader": "Longwave tests", "duration": 30,
                "downloadable": False, "formats": [source], "extractor": "fixture", "webpage_url": "https://soundcloud.com/fixture/tone"}

        class FixtureYDL(YoutubeDL):
            def extract_info(self, *args, **kwargs):
                return info

        job = existing or self.store.create(str(uuid.uuid4()), "https://soundcloud.com/fixture/tone", output_format)
        if background:
            (self.store.root / "fixture-info.json").write_text(json.dumps(info))
            return subprocess.Popen([sys.executable, str(Path(__file__).with_name("fixture_job.py")), str(self.store.root), job["id"]],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **hidden_process_options())
        with patch("yt_dlp.YoutubeDL", FixtureYDL), patch("longwave.engine.select_source", return_value=source), patch("longwave.engine.check_media_url"):
            run_job(self.store, job["id"])
        return self.store.get(job["id"])

    def audio_hash(self, path):
        result = subprocess.run([str(FFMPEG), "-nostdin", "-v", "error", "-i", str(path), "-map", "0:a:0",
                                 "-f", "hash", "-hash", "sha256", "-"], capture_output=True, check=True, **hidden_process_options())
        return result.stdout.strip()

    def test_progressive_original_preserves_decoded_audio(self):
        job = self.run_fixture()
        self.assertEqual(job["state"], "completed")
        self.assertEqual(self.audio_hash(self.source), self.audio_hash(job["output"]))

    def test_hls_to_mp3_produces_verified_file(self):
        job = self.run_fixture("mp3", hls=True)
        self.assertEqual(job["state"], "completed")
        self.assertEqual(Path(job["output"]).suffix, ".mp3")
        self.assertGreater(Path(job["output"]).stat().st_size, 1000)

    def test_pause_and_resume_reuses_validated_partial(self):
        self.check_pause_resume(hls=False)

    def test_hls_pause_and_resume_preserves_full_audio(self):
        self.check_pause_resume(hls=True)

    def check_pause_resume(self, hls):
        # HLS packaging can change AAC priming/edit-list handling. Compare an
        # interrupted HLS transfer with an uninterrupted HLS transfer, not with
        # the pre-segmentation M4A container.
        reference = self.run_fixture(hls=True)["output"] if hls else self.source
        job = self.store.create(str(uuid.uuid4()), "https://soundcloud.com/fixture/tone", "original")
        process = self.run_fixture(existing=job, hls=hls, background=True)
        deadline = time.monotonic() + 10
        while self.store.get(job["id"])["bytes"] == 0 and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertGreater(self.store.get(job["id"])["bytes"], 0)
        self.store.command(job["id"], "pause")
        process.wait(timeout=15)
        self.assertEqual(process.returncode, 0)
        paused = self.store.get(job["id"])
        self.assertEqual(paused["state"], "paused")
        attempt = paused["attempt"]
        self.store.command(job["id"], "resume")
        complete = self.run_fixture(existing=job, hls=hls)
        self.assertEqual(complete["state"], "completed")
        self.assertEqual(complete["attempt"], attempt)
        self.assertEqual(self.audio_hash(reference), self.audio_hash(complete["output"]))

    def test_native_protocol_real_subprocess_and_origin_gate(self):
        import io
        body = io.BytesIO()
        write_message(body, {"version": 1, "command": "snapshot"})
        env = dict(os.environ, PYTHONPATH=str(ROOT / "companion"), LONGWAVE_HOME=str(self.store.root))
        result = subprocess.run([sys.executable, "-m", "longwave", "chrome-extension://" + "a" * 32 + "/"],
                                input=body.getvalue(), capture_output=True, env=env, timeout=20, **hidden_process_options())
        reply = read_message(io.BytesIO(result.stdout))
        self.assertTrue(reply["ok"])
        self.assertTrue(all(reply["data"]["tools"].values()))
        rejected = subprocess.run([sys.executable, "-m", "longwave", "chrome-extension://" + "b" * 32 + "/"],
                                  input=body.getvalue(), capture_output=True, env=env, timeout=20, **hidden_process_options())
        self.assertEqual(rejected.stdout, b"")


if __name__ == "__main__":
    unittest.main()
