"""Untrusted-input validation and the public job contract."""

import re
from urllib.parse import unquote, urlsplit

ACTIVE = {"queued", "resolving", "downloading", "processing", "verifying"}
TERMINAL = {"completed", "failed", "cancelled"}


class UserError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class Stopped(Exception):
    pass


def track_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise UserError("invalid_url", "Enter a public SoundCloud track link.")
    try:
        url = urlsplit(value.strip())
        parts = unquote(url.path).strip("/").split("/")
        if (url.scheme == "https" and url.hostname == "on.soundcloud.com" and url.port in {None, 443}
                and not url.username and not url.password and len(parts) == 1
                and re.fullmatch(r"[A-Za-z0-9]{4,128}", parts[0])):
            return "https://on.soundcloud.com/" + parts[0]
        valid = (
            url.scheme == "https"
            and url.hostname in {"soundcloud.com", "www.soundcloud.com", "m.soundcloud.com"}
            and url.port in {None, 443}
            and not url.username and not url.password
            and len(parts) == 2
            and all(re.fullmatch(r"[a-zA-Z0-9_-]+", p) for p in parts)
            and parts[0] not in {"discover", "search", "you", "settings", "stations", "stream"}
            and parts[1] not in {"sets", "tracks", "albums", "reposts", "likes", "popular-tracks"}
        )
    except ValueError:
        valid = False
    if not valid:
        raise UserError("invalid_url", "Use a public SoundCloud track link or an on.soundcloud.com share link.")
    return "https://soundcloud.com/" + "/".join(parts)


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f-]{36}", value):
        raise UserError("invalid_request", "Invalid request identifier.")
    import uuid
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise UserError("invalid_request", "Invalid request identifier.") from exc


def public_job(job):
    keys = {
        "id", "url", "format", "state", "desired", "title", "artist", "duration",
        "bytes", "total", "speed", "eta", "progress", "created", "updated",
        "error", "output", "note", "codec", "source_bitrate", "fragment", "fragments",
    }
    return {key: value for key, value in job.items() if key in keys}


def safe_filename(value):
    import unicodedata
    value = unicodedata.normalize("NFC", str(value))
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")[:120]
    if not value or value.split(".")[0].upper() in {
        "CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }:
        value = "audio_" + value
    return value.rstrip(" .")
