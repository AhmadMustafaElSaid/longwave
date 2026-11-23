# Changelog

## 0.3.0 — public multi-platform release

- Package the companion for Windows x64, Debian/Ubuntu and macOS, plus a portable Unix archive. Include per-user Chrome, Edge and Chromium native-host registration on Unix.
- Pair a phone over private HTTPS, submit downloads, seek through completed audio, change playback speed and save a local copy.
- Exercise three operating systems, Windows native messaging, mobile Chromium/WebKit browser flows and generated 4-, 7- and 10-hour transfers in the release pipeline.
- Add SHA-256 checksums and GitHub-signed build provenance to published releases, with optional Windows publisher signing and macOS signing/notarization support for enrolled identities.

## 0.2.0-rc.1 — standalone Windows release candidate

- Ship a self-contained Windows x64 setup package with CPython 3.14.10 and pinned yt-dlp source. End users need no developer environment.
- Add English/Arabic installer UI, folder selection, side-by-side installation, update/repair, rollback, and disconnection that preserves audio/history.
- Replace old npm media packages with matching FFmpeg/ffprobe 9.1, obtained directly from upstream after SHA-256 verification.
- Add a native executable bridge with binary framing and immediate flushing for open browser connections.
- Add archive/payload integrity checks, traversal rejection, package tests with system runtimes removed from PATH, and separate browser validation.
- Generate Windows, extension, store-upload, and source ZIPs, a dependency manifest, and asset checksums. Add a manually dispatched release build workflow.
- Prepare bilingual user instructions, distribution operations, privacy disclosures, and store submission material.

Candidate limits: unsigned installer, unpacked browser installation, no published store listing, Windows x64 only, manual companion updates, conditional stream resume, retained partial/cache data, and some English-only diagnostics. This is not an audited stable release.

## 0.1.0 — developer preview

- Introduced the TypeScript MV3 extension and durable Python companion.
- Verified a public 7 h 35 min track with the creator download flag disabled.
- Added generated-audio pipeline tests and bilingual browser UI.
