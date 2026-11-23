"""Release security boundaries; no network or registry changes."""
import importlib.util
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

RELEASE = Path(__file__).resolve().parents[2] / 'release'
sys.path.insert(0, str(RELEASE))
from download import digest, extract, fetch
from install import validate_payload


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def archive(self, entry):
        archive = self.root / 'fixture.zip'
        with zipfile.ZipFile(archive, 'w') as zipped:
            zipped.writestr(entry, b'test')
        return archive

    def test_archive_cannot_escape_or_create_alternate_streams(self):
        for entry in ('../outside', '/absolute', 'C:/absolute', 'safe/file:stream', '..\\outside'):
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                extract(self.archive(entry), self.root / 'output')
        self.assertFalse((self.root / 'outside').exists())

    def test_valid_archive_extracts_nested_files(self):
        extract(self.archive('nested/file.txt'), self.root / 'output')
        self.assertEqual((self.root / 'output/nested/file.txt').read_bytes(), b'test')

    def test_validated_download_cache_does_not_fetch(self):
        cached = self.root / 'cached.zip'
        cached.write_bytes(b'pinned')
        with patch('download.urllib.request.urlopen') as network:
            self.assertEqual(fetch('https://example.test/pinned', digest(cached), cached), cached)
        network.assert_not_called()

    def test_bad_download_is_never_activated(self):
        class Response(io.BytesIO):
            url = 'https://example.test/file'
            headers = {'Content-Length': '3'}
        target = self.root / 'package.zip'
        with patch('download.urllib.request.urlopen', return_value=Response(b'bad')):
            with self.assertRaises(ValueError):
                fetch('https://example.test/file', '0' * 64, target, lambda _: None)
        self.assertFalse(target.exists())
        self.assertFalse(target.with_suffix('.zip.partial').exists())

    def test_payload_corruption_and_traversal_are_rejected(self):
        payload = self.root / 'payload'
        payload.mkdir()
        source = payload / 'test.py'
        source.write_text('valid')
        checks = payload / 'files.sha256.json'
        checks.write_text(json.dumps({'test.py': digest(source)}))
        validate_payload(payload)
        source.write_text('modified')
        with self.assertRaises(ValueError):
            validate_payload(payload)
        checks.write_text(json.dumps({'../outside': '0' * 64}))
        with self.assertRaises(ValueError):
            validate_payload(payload)


if __name__ == '__main__':
    unittest.main()
