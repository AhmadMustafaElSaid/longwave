"""SoundCloud adapter, bounded downloads via yt-dlp, and local FFmpeg processing."""

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from .model import Stopped, UserError, safe_filename
from .runtime import config, hidden_process_options, require_tools, tool_path
from .source import expand_track_url


class QuietLogger:
    # Never persist extractor output: errors can contain signed URLs and headers.
    def debug(self, message):
        pass

    def info(self, message):
        pass

    def warning(self, message):
        pass

    def error(self, message):
        pass


def finite_number(value):
    return value if isinstance(value, (int, float)) and math.isfinite(value) and value >= 0 else None


def select_source(info):
    if info.get("_type", "video") not in {"video", None}:
        raise UserError("unsupported_source", "Choose an individual track, not a playlist.")
    if info.get("availability") in {"private", "premium_only", "subscriber_only", "needs_auth"}:
        raise UserError("restricted", "This track requires access outside the public-track scope.")
    candidates = []
    preview = protected = False
    for fmt in info.get("formats", []):
        identity = str(fmt.get("format_id", "")).lower()
        url = str(fmt.get("url", ""))
        if fmt.get("has_drm") or any(token in identity for token in ("encrypted", "hls-aes", "ctr-", "cbc-")):
            protected = True
            continue
        if "preview" in identity or "/preview/" in url or fmt.get("snipped"):
            preview = True
            continue
        protocol = fmt.get("protocol", "https")
        if protocol not in {"https", "http", "m3u8_native", "m3u8"}:
            continue
        if fmt.get("vcodec") not in {None, "none"} or fmt.get("ext") not in {"mp3", "m4a", "aac", "opus", "ogg"}:
            continue
        if not url.startswith("https://"):
            continue
        candidates.append(fmt)
    if not candidates:
        if preview:
            raise UserError("preview_only", "Only a preview is available. No full track was downloaded.")
        if protected:
            raise UserError("protected", "This track is protected. Longwave does not bypass protection.")
        raise UserError("unsupported_source", "No supported full audio stream is available for this track.")
    return max(candidates, key=lambda f: (finite_number(f.get("abr")) or 0, f.get("protocol") in {"http", "https"}))


def check_media_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise UserError("unsupported_source", "The source returned an unsupported media address.")
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith((".local", ".localhost")) or "." not in host:
        raise UserError("unsupported_source", "Local network media addresses are not supported.")
    import ipaddress
    try:
        if not ipaddress.ip_address(host).is_global:
            raise UserError("unsupported_source", "Local network media addresses are not supported.")
    except ValueError:
        pass


def source_fingerprint(info, source):
    """Conservative reuse: signed URL/manifest changes create a new attempt."""
    url = source["url"]
    check_media_url(url)
    headers = dict(source.get("http_headers") or info.get("http_headers") or {})
    headers["Accept-Encoding"] = "identity"
    common = [str(info.get("id")), str(source.get("format_id")), str(info.get("duration")), url]
    if source.get("protocol", "").startswith("m3u8"):
        with urlopen(Request(url, headers=headers), timeout=20) as response:
            check_media_url(response.url)
            playlist_url = response.url
            raw = response.read(16 * 1024 * 1024 + 1)
        if len(raw) > 16 * 1024 * 1024:
            raise UserError("unsupported_source", "This playlist exceeds the supported metadata size.")
        playlist = raw.decode("utf-8-sig")
        if not playlist.lstrip().startswith("#EXTM3U"):
            raise UserError("source_changed", "The audio source did not return a media playlist.")
        if "#EXT-X-STREAM-INF" in playlist or "#EXT-X-ENDLIST" not in playlist:
            raise UserError("unsupported_source", "This version supports finite media playlists only.")
        for line in playlist.splitlines():
            line = line.strip()
            if line.startswith(("#EXT-X-KEY:", "#EXT-X-SESSION-KEY:")) and not re.search(r"(?:[:,])METHOD=NONE(?:,|$)", line):
                raise UserError("protected", "Encrypted audio is not supported.")
            if line and not line.startswith("#"):
                check_media_url(urljoin(playlist_url, line))
            for uri in re.findall(r'URI="([^"]+)"', line):
                check_media_url(urljoin(playlist_url, uri))
        durations = [float(value) for value in re.findall(r"#EXTINF:([0-9.]+)", playlist)]
        expected = finite_number(info.get("duration"))
        if expected and sum(durations) < expected - max(3, expected * 0.01):
            raise UserError("preview_only", "The available stream is shorter than the full track.")
        # The downloader consumes the exact manifest that passed validation,
        # avoiding a second manifest fetch with potentially different contents.
        source["hls_media_playlist_data"] = playlist
        source["url"] = playlist_url
        if playlist_url != url:
            common.append(playlist_url)
        common.append(hashlib.sha256(raw).hexdigest())
    else:
        try:
            with urlopen(Request(url, headers=headers, method="HEAD"), timeout=20) as response:
                check_media_url(response.url)
                etag = response.headers.get("ETag", "")
                length = response.headers.get("Content-Length", "")
            if not etag or etag.startswith("W/") or not length.isdigit():
                return None
            common.extend([etag, length])
        except UserError:
            raise
        except Exception:
            return None  # No validator: a fresh attempt is safer than appending.
    return hashlib.sha256(json.dumps(common).encode()).hexdigest()


def error_details(exc):
    if isinstance(exc, UserError):
        return {"code": exc.code, "message": str(exc)}
    text = str(exc).lower()
    if "429" in text or "rate limit" in text:
        return {"code": "rate_limited", "message": "SoundCloud is limiting requests. Wait a few minutes, then retry."}
    if "403" in text or "401" in text:
        return {"code": "access_denied", "message": "The source refused access or the link expired. Retry to check availability."}
    if "404" in text or "not found" in text:
        return {"code": "unavailable", "message": "The track or audio source is no longer available."}
    if "disk" in text or "space" in text or isinstance(exc, OSError) and exc.errno == 28:
        return {"code": "disk_full", "message": "There is not enough disk space. Free some space and retry."}
    if "drm" in text:
        return {"code": "protected", "message": "This track is protected. Longwave does not bypass protection."}
    if any(word in text for word in ("timeout", "timed out", "connection", "network", "resolve", "urlopen")):
        return {"code": "network", "message": "The audio service could not be reached. Check your connection and retry."}
    return {"code": "source_failed", "message": "The source could not be processed. Retry, or check for an extractor update."}


def run_job(store, job_id):
    require_tools(store)
    from yt_dlp import YoutubeDL

    settings = config(store)
    job = store.get(job_id)
    output_root = Path(settings["output_dir"]).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    job_root = store.root / "work" / job_id
    job_root.mkdir(parents=True, exist_ok=True)

    def check_stop():
        if store.get(job_id)["desired"] != "running":
            raise Stopped()

    class ManagedYoutubeDL(YoutubeDL):
        def urlopen(self, request):
            # Concurrent fragment work must notice cancellation before starting
            # another request, not only after receiving its first bytes.
            check_stop()
            return super().urlopen(request)

    check_stop()
    store.update(job_id, state="resolving", error=None, speed=None, eta=None)
    canonical_url = expand_track_url(job["url"])
    store.update(job_id, url=canonical_url)
    opts = {
        "quiet": True, "no_warnings": True, "logger": QuietLogger(),
        "noplaylist": True, "socket_timeout": 20, "retries": 3,
        "fragment_retries": 3, "extractor_retries": 2,
        "skip_unavailable_fragments": False, "concurrent_fragment_downloads": 3,
        "cachedir": str(store.root / "extractor-cache"),
        "fixup": "never", "hls_prefer_native": True,
        "ffmpeg_location": str(Path(tool_path(settings, "ffmpeg")).parent),
        "overwrites": False, "continuedl": True,
        "buffersize": 256 * 1024, "noresizebuffer": True,
        "retry_sleep_functions": {"http": lambda n: min(2 ** n, 15), "fragment": lambda n: min(2 ** n, 15)},
    }
    with ManagedYoutubeDL(opts) as ydl:
        info = ydl.extract_info(canonical_url, download=False)
    check_stop()
    if not isinstance(info, dict):
        raise UserError("unavailable", "The track could not be resolved.")
    source = select_source(info)
    duration = finite_number(info.get("duration"))
    total = finite_number(source.get("filesize") or source.get("filesize_approx"))
    estimate = total or ((duration or 0) * (finite_number(source.get("abr")) or 160) * 125)
    # Input plus output plus a reserve. Free space is rechecked during transfer.
    required = max(128 * 1024 * 1024, estimate * 2 + 128 * 1024 * 1024)
    if shutil.disk_usage(job_root).free < required or shutil.disk_usage(output_root).free < required:
        raise UserError("disk_full", "Not enough free space for the source, output, and a safety reserve.")
    fingerprint = source_fingerprint(info, source)
    check_stop()
    previous = store.get(job_id)
    attempt = previous.get("attempt")
    reuse = bool(fingerprint and fingerprint == previous.get("fingerprint") and attempt and (job_root / attempt).is_dir())
    if not reuse:
        attempt = "attempt-" + uuid.uuid4().hex
    attempt_root = job_root / attempt
    attempt_root.mkdir(exist_ok=True)
    note = "Continuing the unchanged source." if reuse else (
        "The source changed or could not be validated. Restarting safely; earlier partial data is retained."
        if previous.get("attempt") else None)
    store.update(job_id, title=str(info.get("title") or "Untitled")[:300],
                 artist=str(info.get("uploader") or "Unknown artist")[:200], duration=duration,
                 codec=source.get("acodec") or source.get("ext"), source_bitrate=finite_number(source.get("abr")),
                 total=total, attempt=attempt, fingerprint=fingerprint, note=note,
                 state="downloading", bytes=previous.get("bytes", 0) if reuse else 0, progress=None)
    last_update = 0.0

    def progress(data):
        nonlocal last_update
        now = time.monotonic()
        if now - last_update < 0.5 and data.get("status") != "finished":
            return
        last_update = now
        check_stop()
        if shutil.disk_usage(job_root).free < 32 * 1024 * 1024:
            raise UserError("disk_full", "Disk space is running low. Free space before resuming.")
        received = finite_number(data.get("downloaded_bytes")) or 0
        size = finite_number(data.get("total_bytes") or data.get("total_bytes_estimate"))
        store.update(job_id, bytes=received, total=size, speed=finite_number(data.get("speed")),
                     eta=finite_number(data.get("eta")), progress=min(100, received / size * 100) if size else None,
                     fragment=data.get("fragment_index"), fragments=data.get("fragment_count"))

    opts.update(outtmpl=str(attempt_root / "source.%(ext)s"), progress_hooks=[progress])
    resolved = {**info, **source}
    resolved.pop("formats", None)
    resolved.pop("requested_formats", None)
    with ManagedYoutubeDL(opts) as ydl:
        source_path = Path(ydl.prepare_filename(resolved))
        ydl.process_info(resolved)
    check_stop()
    if not source_path.is_file() or not source_path.stat().st_size:
        raise UserError("download_failed", "No complete audio file was produced.")
    job = store.get(job_id)
    ext = "mp3" if job["format"] == "mp3" else source.get("ext", "m4a")
    if ext == "aac":
        ext = "m4a"
    # Job IDs make names collision-resistant; finalize within the same filesystem.
    final = output_root / f"{safe_filename(job['artist'] + ' - ' + job['title'])} [{job_id[:8]}].{ext}"
    temporary = output_root / f".{job_id}.partial.{ext}"
    store.update(job_id, state="processing", progress=0, speed=None, eta=None)
    args = [tool_path(settings, "ffmpeg"), "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-protocol_whitelist", "file,pipe",
            "-i", str(source_path), "-map", "0:a:0", "-vn"]
    args += ["-c:a", "libmp3lame", "-q:a", "2"] if job["format"] == "mp3" and source.get("ext") != "mp3" else ["-c:a", "copy"]
    if ext == "m4a":
        args += ["-movflags", "+faststart"]
    args += ["-metadata", "title=" + job["title"], "-metadata", "artist=" + job["artist"],
             "-progress", "pipe:1", str(temporary)]
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               stdin=subprocess.DEVNULL, text=True, **hidden_process_options())

    def conversion_progress():
        for line in process.stdout:
            if line.startswith("out_time_us=") and duration:
                try:
                    ratio = min(99, float(line.split("=", 1)[1]) / 1_000_000 / duration * 100)
                    store.update(job_id, progress=max(0, ratio))
                except (ValueError, OSError):
                    pass

    reader = threading.Thread(target=conversion_progress, daemon=True)
    reader.start()
    try:
        while process.poll() is None:
            check_stop()
            time.sleep(0.2)
        if process.returncode:
            raise UserError("conversion_failed", "Audio processing failed. The downloaded source is retained for retry.")
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        reader.join(timeout=3)
        process.stdout.close()
    check_stop()
    store.update(job_id, state="verifying", progress=None)
    probe = subprocess.run([tool_path(settings, "ffprobe"), "-v", "error", "-protocol_whitelist", "file,pipe", "-show_entries",
                            "format=duration:stream=codec_type,codec_name", "-of", "json", str(temporary)],
                           capture_output=True, text=True, timeout=60, **hidden_process_options())
    try:
        details = json.loads(probe.stdout)
        actual = float(details["format"]["duration"])
        audio = any(stream.get("codec_type") == "audio" for stream in details["streams"])
        if probe.returncode or not audio or not math.isfinite(actual) or actual <= 0:
            raise ValueError()
        if duration and abs(actual - duration) > max(3, duration * 0.005):
            raise ValueError()
    except (ValueError, KeyError, TypeError) as exc:
        raise UserError("verification_failed", "The output duration or audio stream failed validation. The source is retained.") from exc
    check_stop()
    if final.exists():
        raise UserError("file_exists", "The output already exists. Move it before retrying this job.")
    os.replace(temporary, final)
    store.finish(job_id, state="completed", progress=100, output=str(final), speed=None, eta=None, error=None)
