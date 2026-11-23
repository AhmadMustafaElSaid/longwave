# Distribution and release operations

The 0.2.0 release candidate adds a Windows x64 distribution that users can install without Node.js, system Python, pip, or a source checkout. It is a separate deliverable from the development environment.

## Supported scope

| Platform                    | Distribution status                                                      |
| --------------------------- | ------------------------------------------------------------------------ |
| Windows 10/11 x64 + Edge    | Standalone candidate and local browser verification                      |
| Windows 10/11 x64 + Chrome  | Same candidate; separate browser validation recorded in release evidence |
| Windows ARM64, macOS, Linux | Not packaged or validated; do not advertise support                      |
| Firefox                     | Requires browser/manifest/native-host adaptation and validation          |
| Android/iOS                 | Not supported by this native-companion design                            |

Cross-platform source abstractions are not proof that an installer runs on every device. New targets require their own native binaries, installer paths, signing, and test matrix.

## What users receive

`longwave-VERSION-windows-x64.zip` contains a bilingual setup executable, its payload, and a bilingual local installation guide. The payload includes the official CPython embeddable runtime and pinned yt-dlp Python source. It does not include a developer environment or user-specific paths/data.

Setup downloads the pinned Gyan FFmpeg archive directly from upstream, validates its SHA-256, and installs matching FFmpeg/ffprobe. Both archive and payload validation fail closed. Build inputs and provenance are recorded in `release/dependencies.json` and the generated release manifest. The downloaded media binaries are not redistributed inside our ZIP.

The candidate installer is **unsigned**. SHA-256 files are integrity evidence, not a publisher signature. Authenticode signing and reputation remain requirements for a smooth general-user release. Do not instruct users to disable Windows protections.

## Installation layout

```text
%LOCALAPPDATA%/Longwave/
  installation.json          Current and previous version paths
  versions/<version>-<id>/   Immutable runtime, companion, extension, media, notices
  data/                     SQLite queue, native-host registration, partial audio
  cache/                    Verified upstream media archive
  setup-lock/               Exclusive installer lock
```

Audio defaults to the user's `Downloads/Longwave`, and the installer offers a folder picker. Chrome and Edge registrations are per-user, restricted to explicit extension identities. No administrator elevation, service, startup entry, forced browser policy, or network command listener is installed.

Installers stage side-by-side versions and health-check them before activation. Activation pauses jobs and waits for the previous worker to stop. Config files are atomically replaced; a registry-write failure restores prior values. Failed staging remains inactive. Re-running setup repairs/reinstalls; it never overwrites a running version.

Rollback switches to the immediately previous installed companion and exposes that version's extension folder. It is intended for versions with the same database/protocol compatibility. Future schema changes must add migration/rollback rules before shipping. Disconnect removes only matching Longwave native-host registrations, stops work, and retains audio/history. Old versions and cache are retained; there is no automatic disk cleanup in this candidate.

The browser extension remains unpacked for candidate testing. Updating the companion does not silently replace a browser-loaded extension: users load the matching new extension folder following the guide. Stable releases should use store-managed extension updates with a compatible companion update policy.

## Build and test

On Windows with development prerequisites:

```powershell
npm ci
npm run setup:media
npm run check
npm test
npm run release:windows
npm run test:release
```

Artifacts are written under `artifacts/releases/<version>/`: Windows setup ZIP, unpacked Chromium ZIP, store-upload ZIP, source ZIP, release manifest, and SHA256SUMS. The source archive uses an explicit allowlist; recordings, installed runtimes, browser profiles, SQLite, and local configuration are excluded.

The release test extracts the actual ZIP into a Unicode path and removes system Python/Node from PATH. It verifies installation, repair/upgrade, rollback, native EXE framing, origin rejection, generated-media processing under the bundled interpreter, and data preservation on disconnect. It does not modify registry keys and does not pretend to be a clean OS/VM. Browser-to-native registration is a separate smoke test. The manually dispatched GitHub workflow runs the package tests on a fresh Windows runner and uploads artifacts; running it remotely still requires a repository.

## Store publishing

Chrome's normal consumer distribution requires Chrome Web Store publication; unpacked loading is a development/testing route. Edge Add-ons uses Partner Center submission. Store review and acceptance are external decisions, not guaranteed by building a ZIP.

1. Reserve Chrome/Edge listings and obtain their extension IDs.
2. Fill `release/store-ids.json` with those IDs, rebuild, and test actual store identities against the companion allowlist. Null IDs are not inferred or granted wildcard access.
3. Host the repository privacy/support pages and candidate download at stable HTTPS URLs.
4. Complete [store listing material](store-listing.md) with real publisher/contact URLs.
5. Sign the installer using the publisher's signing identity; regenerate artifact hashes after signing.
6. Run the clean-machine matrix and upload the store ZIP for review. Do not publish a listing that implies mobile/all-platform support.
7. Publish a versioned GitHub release with changelog, checksums, source, dependency manifest, installation instructions, and explicit supported platforms.

The build generates a separate store-upload ZIP without the unpacked development key. The companion allows the development ID plus only configured store IDs. Do not submit the store package as functional until its store ID has been configured and verified.

Sources: [Chrome distribution](https://developer.chrome.com/docs/extensions/how-to/distribute), [Edge publication](https://learn.microsoft.com/en-us/microsoft-edge/extensions/publish/publish-extension), [CPython embedded runtime](https://www.python.org/downloads/release/python-31410/), [Gyan builds and licensing](https://www.gyan.dev/ffmpeg/builds/).
