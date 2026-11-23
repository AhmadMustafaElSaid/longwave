"""Test-only subprocess adapter. Never included in a companion distribution."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from longwave.store import Store
from longwave.worker import execute_job
from yt_dlp import YoutubeDL

store = Store(sys.argv[1])
info = json.loads((store.root / "fixture-info.json").read_text())


class FixtureYDL(YoutubeDL):
    def extract_info(self, *args, **kwargs):
        return info


with patch("yt_dlp.YoutubeDL", FixtureYDL), patch("longwave.engine.select_source", return_value=info["formats"][0]), patch("longwave.engine.check_media_url"):
    execute_job(store, sys.argv[2])
