import io
import json
import struct
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from longwave.engine import error_details, select_source, source_fingerprint
from longwave.model import UserError, safe_filename, track_url
from longwave.protocol import MAX_MESSAGE, read_message, write_message
from longwave.service import dispatch
from longwave.store import Store
from longwave.worker import WorkerLock
from longwave.source import SoundCloudRedirects


class InputTests(unittest.TestCase):
    def test_track_url_normalizes_without_tracking_parameters(self):
        self.assertEqual(track_url("https://www.soundcloud.com/artist/track?utm_source=test"), "https://soundcloud.com/artist/track")

    def test_rejects_untrusted_or_nontrack_urls(self):
        for url in ("http://soundcloud.com/a/b", "https://soundcloud.com.evil.org/a/b", "https://soundcloud.com@localhost/a/b",
                    "https://soundcloud.com/a/sets/list", "https://soundcloud.com/a/b/s-secret", "file:///a/b",
                    "https://soundcloud.com/a/%2e%2e", "https://soundcloud.com:4430/a/b", "https://soundcloud.com/a/tracks"):
            with self.subTest(url=url), self.assertRaises(UserError):
                track_url(url)

    def test_windows_filename_safety(self):
        for value in ("CON", "LPT1.txt", "../../x", " hello. ", "a\x00b", ""):
            result = safe_filename(value)
            self.assertNotIn("/", result)
            self.assertNotIn("\\", result)
            self.assertFalse(result.endswith((".", " ")))
            self.assertTrue(result)
        self.assertEqual(safe_filename("CON"), "audio_CON")

    def test_share_links_and_external_redirect_rejection(self):
        self.assertEqual(track_url("https://on.soundcloud.com/Abc123?utm_source=share"), "https://on.soundcloud.com/Abc123")
        with self.assertRaises(UserError):
            track_url("https://on.soundcloud.com/a/b")
        with self.assertRaises(UserError):
            SoundCloudRedirects().redirect_request(None, None, 302, "Found", {}, "http://127.0.0.1/private")


class ProtocolTests(unittest.TestCase):
    def test_unicode_roundtrip(self):
        stream = io.BytesIO()
        write_message(stream, {"title": "مقطع طويل"})
        stream.seek(0)
        self.assertEqual(read_message(stream), {"title": "مقطع طويل"})

    def test_oversize_and_truncated_frames(self):
        for frame in (struct.pack("=I", MAX_MESSAGE + 1), struct.pack("=I", 5) + b"{}", b"\x01"):
            with self.subTest(frame=frame), self.assertRaises(UserError):
                read_message(io.BytesIO(frame))

    def test_nonobject_and_malformed_json(self):
        for body in (b"[]", b"null", b"{"):
            with self.assertRaises(UserError):
                read_message(io.BytesIO(struct.pack("=I", len(body)) + body))
        self.assertIsNone(read_message(io.BytesIO()))


class JobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)

    def create(self, request=None):
        return self.store.create(request or str(uuid.uuid4()), "https://soundcloud.com/artist/track", "original")

    def test_idempotence_survives_reopen(self):
        request = str(uuid.uuid4())
        job = self.create(request)
        reopened = Store(self.temp.name)
        self.assertEqual(reopened.create(request, job["url"], "original")["id"], job["id"])
        self.assertEqual(len(reopened.list()), 1)
        reopened.update(job["id"], url="https://soundcloud.com/artist/resolved")
        self.assertEqual(reopened.create(request, job["url"], "original")["id"], job["id"])
        with self.assertRaises(UserError):
            reopened.create(request, job["url"], "mp3")

    def test_duplicate_active_track_is_not_downloaded_twice(self):
        self.assertEqual(self.create()["id"], self.create()["id"])

    def test_pause_resume_cancel_state_machine(self):
        job = self.create()
        self.assertEqual(self.store.command(job["id"], "pause")["state"], "paused")
        self.assertEqual(self.store.command(job["id"], "resume")["state"], "queued")
        self.store.update(job["id"], state="downloading")
        self.store.command(job["id"], "cancel")
        result = self.store.finish(job["id"], state="completed")
        self.assertEqual(result["state"], "cancelled")
        with self.assertRaises(UserError):
            self.store.command(job["id"], "resume")

    def test_worker_restart_recovers_state(self):
        job = self.create()
        self.store.update(job["id"], state="processing")
        self.store.recover()
        self.assertEqual(self.store.get(job["id"])["state"], "queued")
        self.store.update(job["id"], state="downloading", desired="paused")
        self.store.recover()
        self.assertEqual(self.store.get(job["id"])["state"], "paused")

    def test_protocol_rejects_path_and_arbitrary_commands(self):
        for message in ({"version": 2, "command": "snapshot"}, {"version": 1, "command": "execute"},
                        {"version": 1, "command": "create", "path": "C:\\Windows"}):
            with self.assertRaises(UserError):
                dispatch(self.store, message, start_worker=lambda _: None)

    def test_worker_lock_is_exclusive_and_released(self):
        with WorkerLock(self.store.root) as first:
            self.assertTrue(first)
            with WorkerLock(self.store.root) as second:
                self.assertFalse(second)
        with WorkerLock(self.store.root) as third:
            self.assertTrue(third)


class SourceTests(unittest.TestCase):
    def fmt(self, **changes):
        return {"url": "https://cdn.example.test/audio", "ext": "m4a", "protocol": "m3u8_native",
                "format_id": "hls_aac", "abr": 160, "vcodec": "none", **changes}

    def test_download_disabled_does_not_block_full_stream(self):
        info = {"downloadable": False, "formats": [self.fmt()]}
        self.assertEqual(select_source(info)["format_id"], "hls_aac")

    def test_preview_or_protection_never_silently_succeeds(self):
        for fmt, code in ((self.fmt(format_id="hls_aac_preview"), "preview_only"),
                          (self.fmt(format_id="hls-aes_aac"), "protected"),
                          (self.fmt(has_drm=True), "protected")):
            with self.subTest(code=code), self.assertRaises(UserError) as caught:
                select_source({"formats": [fmt]})
            self.assertEqual(caught.exception.code, code)

    def test_supported_best_full_audio_selected(self):
        low = self.fmt(abr=64)
        high = self.fmt(abr=160)
        preview = self.fmt(abr=320, format_id="preview")
        self.assertEqual(select_source({"formats": [low, preview, high]})["abr"], 160)

    def test_error_messages_redact_urls(self):
        result = error_details(Exception("HTTP Error 403: https://cdn.test/audio?token=secret"))
        self.assertEqual(result["code"], "access_denied")
        self.assertNotIn("secret", json.dumps(result))
        self.assertNotEqual(result["code"], "protected")

    def test_hls_fingerprint_detects_change_and_rejects_encryption(self):
        class Response(io.BytesIO):
            url = "https://cdn.example.test/media.m3u8"
        playlist = b"#EXTM3U\n#EXTINF:10,\na.m4s\n#EXT-X-ENDLIST\n"
        info = {"id": "1", "duration": 10}
        with patch("longwave.engine.urlopen", side_effect=lambda *a, **k: Response(playlist)):
            one = source_fingerprint(info, self.fmt())
            self.assertEqual(one, source_fingerprint(info, self.fmt()))
            selected = self.fmt()
            source_fingerprint(info, selected)
            self.assertEqual(selected["hls_media_playlist_data"], playlist.decode())
        with patch("longwave.engine.urlopen", side_effect=lambda *a, **k: Response(playlist.replace(b"a.m4s", b"b.m4s"))):
            self.assertNotEqual(one, source_fingerprint(info, self.fmt()))
        with patch("longwave.engine.urlopen", return_value=Response(playlist + b'#EXT-X-KEY:METHOD=AES-128,URI="key"\n')):
            with self.assertRaises(UserError) as caught:
                source_fingerprint(info, self.fmt())
            self.assertEqual(caught.exception.code, "protected")

    def test_playlist_preview_and_missing_end_are_rejected(self):
        class Response(io.BytesIO):
            url = "https://cdn.example.test/media.m3u8"
        for playlist in (b"#EXTM3U\n#EXTINF:30,\na.m4s\n#EXT-X-ENDLIST\n", b"#EXTM3U\n#EXTINF:100,\na.m4s\n"):
            with patch("longwave.engine.urlopen", return_value=Response(playlist)), self.assertRaises(UserError):
                source_fingerprint({"id": "1", "duration": 100}, self.fmt())


if __name__ == "__main__":
    unittest.main()
