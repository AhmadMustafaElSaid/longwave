# Longwave

Save a permitted SoundCloud track for offline listening in your own player. Longwave handles long recordings on your computer, keeps the available audio format or exports MP3, and continues working when you close the browser.

**[Download Longwave](https://github.com/AhmadMustafaElSaid/longwave/releases/latest)** · [Installation](docs/install.md) · [دليل الاستخدام بالعربية](docs/quickstart-ar.md) · [Builds and tests](https://github.com/AhmadMustafaElSaid/longwave/actions/workflows/release.yml)

![Longwave downloads workspace](docs/images/dashboard.png)

## Choose your device

| Device                            | Install or connect                                                                                                                                                                                       |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Windows 10/11 x64                 | Extract the Windows ZIP and run **Longwave-Setup.exe**. Setup includes Python and fetches checksum-verified FFmpeg tools.                                                                                |
| Debian / Ubuntu with Python 3.11+ | Install the `.deb` with APT and run `longwave connect`.                                                                                                                                                  |
| macOS or other Linux desktops     | Install Python 3.11+ and FFmpeg, extract the Unix archive to a permanent folder, then run `./longwave connect`. macOS also has an installer package.                                                     |
| Android / iPhone                  | Open your computer’s paired web interface over a private HTTPS connection. Queue a track, play it at up to 2× or save it on the phone. The computer must be running until the file has been transferred. |

On a desktop, open `chrome://extensions` or `edge://extensions`, enable **Developer mode** and choose **Load unpacked**. Select the **extension** directory shown by the companion. The public distribution channel is GitHub Releases. Installation currently requires these manual browser steps. [Installation, verification and phone pairing](docs/install.md)

## Saving audio without a download button

Paste the SoundCloud track URL or the entire share message into Longwave. Choose **Source audio** to preserve the available stream, or **MP3** for players that require it. A full-length, publicly playable, unencrypted rendition can work when the creator’s download button is absent. Previews, private sessions, subscription-only audio and protected streams are unsupported.

Public playback and permission to retain a copy are separate. Save recordings you own or have permission to keep, and respect the license and platform terms. Longwave is independent of SoundCloud. [SoundCloud terms](https://soundcloud.com/terms-of-use)

## Long recordings

The queue and partial files live on disk. The native companion runs one job at a time with up to three HLS fragment requests. The browser receives small progress messages. It never buffers a complete track. A closed popup or an MV3 service-worker restart does not interrupt a running job.

- Pause, resume or retry from the bilingual workspace. Resuming a validated unchanged source reuses partial progress. A changed playlist or expiring signed source can require a fresh transfer.
- Before exposing a file, the companion verifies the audio stream and duration with ffprobe, then renames the completed output. Audio quality is limited by the available rendition.
- Playback speed is a player setting. Select 2× in your external player or in the paired phone player. The saved file retains its original speed.
- Storage, source availability and network stability determine practical limits. Source, output and previous interrupted attempts can coexist. After a reboot, open Longwave to restart the worker. The queue accepts 20 unfinished jobs and shows up to 100 items.

The original live check saved one 7 h 35 min public track whose native download flag was off. Generated 4-, 7- and 10-hour progressive transfers exercise the full job on every release, including duration validation and decoding near the start, middle and end. The Linux report accompanies each release. [Live and generated test evidence](docs/verification.md)

## Architecture

| Component                           | Responsibility                                                                                    |
| ----------------------------------- | ------------------------------------------------------------------------------------------------- |
| `extension/`                        | Manifest V3 popup and workspace, typed native messages, English and Arabic RTL.                   |
| `companion/longwave/`               | SoundCloud resolution, source eligibility, SQLite journal, worker, FFmpeg and ffprobe.            |
| `companion/longwave/phone.py`       | Optional loopback server, one-device pairing, streaming downloads and HTTP ranges for seeking.    |
| `release/`                          | Windows setup and executable host, Unix registration, pinned runtime and extractor inputs.        |
| `scripts/` and `.github/workflows/` | Package builds, isolated installs, browser checks, endurance cases and signed release provenance. |

The extension requests native messaging, local preference storage and gesture-scoped access to the current tab. Phone access is off until the user starts it. [Architecture](docs/architecture.md) · [Privacy](PRIVACY.md)

## Build and test

Use Node.js 22+ and Python 3.11+. On Windows, use PowerShell from the checkout.

```powershell
npm ci
npm run setup:media
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r companion\requirements.txt
npm run verify
npm run release:windows
npm run test:release
python scripts/test_release_browser.py
```

On macOS or Linux, install Python and FFmpeg, then use a virtual environment.

```sh
npm ci
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r companion/requirements.txt
export LONGWAVE_TEST_FFMPEG="$(command -v ffmpeg)" LONGWAVE_TEST_FFPROBE="$(command -v ffprobe)"
npm run build
python scripts/test_suite.py
python scripts/package_unix.py
python scripts/test_unix_package.py
```

For Debian packaging add `--deb` to the package command. Build the optional native macOS installer with `python scripts/package_macos.py`. `npm run preview` starts a simulated interface for design work. The stricter release test command fails if any media tests are skipped. Mobile browser checks use Playwright Chromium or WebKit. [Release workflow](.github/workflows/release.yml) · [Release operations](docs/distribution.md)

## Project

[Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md) · [Security reports](SECURITY.md) · [Support](https://github.com/AhmadMustafaElSaid/longwave/issues) · [Roadmap](docs/roadmap.md)

Original project code is MIT licensed. Third-party components retain their own terms. [License](LICENSE) · [Third-party notices](THIRD_PARTY_NOTICES.md)
