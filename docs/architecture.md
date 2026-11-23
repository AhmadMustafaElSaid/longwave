# Architecture and recovery contract

The optional phone interface runs a loopback HTTP server with an explicit private HTTPS origin for remote access. Pairing grants one expiring browser session. Commands use the same service and SQLite queue as the extension. Audio responses support byte ranges and 128 KiB reads. On Unix a running job inherits the supervisor's file lock to prevent concurrent writes after an unexpected supervisor exit.

## Components

The Chromium extension uses plain TypeScript and native DOM controls. A framework is unnecessary for one form and a local queue. Browser-specific calls live in the background adapter. There is no content script, web-request interception, persistent page scraping, or hosted backend.

`service.py` validates native commands. `store.py` owns transactional state. `source.py` resolves share links through an allowlisted redirect path. `engine.py` isolates the pinned yt-dlp API and performs stream selection, fingerprinting, download, processing, and validation. `worker.py` runs one supervised process per track. `process_guard.py` contains the Windows-only process-tree behavior.

Native messages carry version 1, an enumerated command, and only the fields required for that command. Requests have a 64 KiB limit. The host manifest allows a fixed extension origin; the host checks that origin again. It never accepts executable paths, shell arguments, arbitrary download domains, or destination paths from an extension message.

## Ownership and lifecycle

- The browser owns presentation and temporary command delivery.
- SQLite owns the authoritative queue. A separate desired state records pause/cancel requests without racing progress writes.
- A detached supervisor owns execution. One OS lock is held for its lifetime.
- A per-job process owns extractor and file handles. It exits on completion, failure, pause, or cancellation.
- Windows Job Object membership makes child processes terminate if the supervisor exits, when assignment succeeds. `worker-info.json` records whether the guard was established.
- Reopening the workspace checks the queue and starts a missing supervisor. There is no boot-time service.

SQLite transactions are committed and connections explicitly closed. Create requests have a persistent idempotency key; resolving a share link does not change its original request identity. Active duplicate links are coalesced. At most 20 unfinished jobs are accepted.

## Source and format contract

Inputs are HTTPS SoundCloud track pages or supported share links. A source is accepted based on the availability of a full unencrypted audio rendition, not the native download flag. No cookies or authenticated browser sessions are imported. Only the selected clear source is passed to the downloader.

HLS must be a finite media playlist. The adapter checks encryption tags, segment addresses, and total duration. It supplies the already-checked playlist through the pinned downloader's `hls_media_playlist_data` interface, preventing a second manifest fetch from silently changing the accepted source. Master/live playlists fail with an actionable unsupported-source result.

Source-preserving output remuxes audio without re-encoding where possible. AAC is stored in M4A. MP3 selection transcodes through libmp3lame only when needed. Conversion runs locally, with FFmpeg network protocols disabled. ffprobe checks that audio exists and that duration is consistent with the resolved track before finalization.

## Resume semantics

A job records its attempt directory and a source fingerprint, never a complete audio buffer. HLS identity includes track/rendition identity, duration, source URL, final redirected playlist URL when different, and the playlist-body hash. Direct-file reuse requires a strong ETag and a known length.

Exact matches reuse the downloader's `.part`/fragment checkpoint. Any uncertain identity creates a separate attempt. This intentionally means newly signed SoundCloud URLs often restart rather than resume. A future source-specific refresh protocol must compare immutable segment identity or content validators before relaxing this rule.

Old attempts are retained; they are not mixed into a new rendition. Cancel does not erase audio or partial data. The live application has no deletion command. A future cleanup UI must distinguish history removal, partial-cache removal, and deletion of completed audio.

## Resource bounds

Only one track runs at a time, with at most three concurrent fragment transfers and 256 KiB network buffers. The downloader can read an individual fragment into memory, so this is not a claim that all possible HLS inputs have constant memory use; tested SoundCloud fragments are small. Playlist metadata is limited to 16 MiB. Whole-track browser Blobs, PCM buffers, and WebAssembly encoding are absent.

Disk checks reserve space for input, output, and a margin, then check free space during transfer. Estimates are not guarantees, especially across volumes or for uncertain source sizes. Processing failures retain the source. Output is finalized with a same-filesystem rename; a job-specific filename avoids accidental overwrites. Output validation is not cryptographic proof against an upstream reference hash.

## Cross-browser and distribution

Chrome and Edge share the MV3 bundle and separate native-host registry entries. Firefox needs its own manifest/background adapter and native registration and is not packaged yet. The local source installation uses Python and npm-distributed media binaries. Standalone, signed installers and updated media-tool builds are prerequisites for a public production release.

## Accepted trade-offs

- Python plus a pinned maintained extractor gets a working source path sooner than a new Go extractor. The protocol keeps a future engine replacement possible.
- Native Messaging avoids a local HTTP command server and its authentication surface.
- Per-job processes cost some startup time and memory but release file handles deterministically.
- Conditional safe restarts take precedence over silently appending incompatible audio.
- A source-format file is the fast default; mandatory MP3 conversion would add CPU, disk use, and generation loss.
