"""Resolve share links without handing arbitrary redirects to an extractor."""

from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .model import UserError, track_url


class SoundCloudRedirects(HTTPRedirectHandler):
    max_redirections = 5

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Validation occurs BEFORE following a redirect. Drop tracking queries.
        safe_url = track_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, safe_url)


def expand_track_url(value):
    value = track_url(value)
    if urlsplit(value).hostname != "on.soundcloud.com":
        return value
    opener = build_opener(SoundCloudRedirects())
    with opener.open(Request(value, method="HEAD", headers={"User-Agent": "Longwave/0.1"}), timeout=20) as response:
        expanded = track_url(response.url)
    if urlsplit(expanded).hostname == "on.soundcloud.com":
        raise UserError("unresolved_link", "This share link could not be resolved. Paste the full track-page link instead.")
    return expanded
