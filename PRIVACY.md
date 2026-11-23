# Privacy

Longwave processes audio locally. There is no Longwave account, analytics endpoint, advertising, telemetry, hosted conversion server, or developer-operated backend.

The companion contacts SoundCloud and its media delivery hosts to resolve and download requested tracks. These services receive ordinary network information, including your IP address. Standalone setup fetches media tools from gyan.dev and its delivery redirects. Source builds also contact python.org and PyPI. No automatic update checker or telemetry runs.

The extension stores its language preference. The companion stores public source-page URLs, track metadata, job status, output paths, and a source fingerprint in a local SQLite database. Its work directory holds partial/downloaded audio and the downloader's resume files. Finished files go to the folder chosen at setup. These files are not synced by Longwave.

Signed media URLs are used in memory and are not deliberately logged or returned to the UI. The pinned extractor may maintain its local technical cache. Longwave does not import browser cookies, passwords, authenticated accounts, or browsing history. “Use current tab” reads the active tab URL following the extension's user gesture.

Phone access starts only when you launch it. The server listens on the computer's loopback interface. When you configure a private HTTPS proxy, that proxy and one paired browser can access the queue and completed files. The pairing code and session expire and are held in memory. The browser stores a session cookie and language preference. Saving a file creates a copy on the phone. Stopping the server invalidates the session. Your network and proxy providers handle traffic according to their own policies.

## Extension permissions

| Permission        | Purpose                                                 |
| ----------------- | ------------------------------------------------------- |
| `nativeMessaging` | Commands to the locally installed companion             |
| `activeTab`       | Capture the current track-page URL after a user gesture |
| `storage`         | Remember the interface language                         |

No content script or all-sites host permission is requested. The native host's allowlist is specific to the extension ID. Uninstall disconnects the host but preserves history, partials, and output until you choose to remove them.
