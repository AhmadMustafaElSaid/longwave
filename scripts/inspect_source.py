"""Read-only SoundCloud feasibility check; never prints media URLs or tokens."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "companion"))
from longwave.engine import QuietLogger, error_details, select_source
from longwave.model import track_url
from longwave.source import expand_track_url

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    args = parser.parse_args()
    from yt_dlp import YoutubeDL
    try:
        with YoutubeDL({"quiet": True, "no_warnings": True, "logger": QuietLogger(), "noplaylist": True,
                        "socket_timeout": 15, "extractor_retries": 1, "cachedir": False}) as ydl:
            info = ydl.extract_info(expand_track_url(args.url), download=False)
        source = select_source(info)
        print(json.dumps({"ok": True, "id": info.get("id"), "title": info.get("title"),
                          "duration": info.get("duration"), "format": source.get("format_id"),
                          "license": info.get("license"),
                          "codec": source.get("acodec"), "protocol": source.get("protocol"),
                          "bitrate": source.get("abr")}, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": error_details(exc)}))
        sys.exit(1)
