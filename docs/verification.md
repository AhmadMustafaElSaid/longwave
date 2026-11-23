# Verification evidence

## Release 0.3.0

On Ubuntu 24.04 under WSL2, three generated constant-bitrate 24 kbps MP3 recordings were transferred over loopback through the job process, written to disk and validated. Each output decoded at the beginning, midpoint and near the end. Linux RSS samples sum the job and its children at 50 ms intervals. They include shared pages counted per process and exclude the fixture server. The timings describe this local setup.

| Generated duration | ffprobe duration | Output bytes | Job elapsed | Highest sampled tree RSS |
| ------------------ | ---------------- | ------------ | ----------- | ------------------------ |
| 4 h                | 14,400.048 s     | 43,200,432   | 24.38 s     | 115,760 KiB              |
| 7 h                | 25,200.048 s     | 75,600,432   | 36.28 s     | 98,072 KiB               |
| 10 h               | 36,000.048 s     | 108,000,432  | 50.69 s     | 101,280 KiB              |

The portable archive connected using an isolated Unix profile and handled native message framing, update and disconnect with file preservation. The Windows source suite passed 33 tests with zero skips. A Chromium 157 mobile-viewport test paired a browser, downloaded a byte-identical WAV fixture, played it at 2×, switched to Arabic and passed the selected automated axe checks. Tagged builds repeat the OS matrix and publish the Linux measurements alongside their assets. Physical handset coverage remains open. [Workflow runs](https://github.com/AhmadMustafaElSaid/longwave/actions/workflows/release.yml)

## Hosted installation and phone checks

The hosted macOS runner also installed the PKG with Apple's system installer, opened the installed extension in Chrome 157 and passed the WebKit 27.2 mobile-viewport playback and save checks. On an Android 15 emulator, stock Chrome paired with the fixture server and placed a SHA-256-identical audio file into the system Downloads directory. [Hosted platform tests](https://github.com/AhmadMustafaElSaid/longwave/actions/runs/45156668531)

## Earlier live-track environment

The following observations were recorded on 2026-11-22–23 using Windows, Node.js 24.22.0, Python 3.15 and Edge 158.0.4370.33.

## Real long-track run

This run used one public full-length audio stream. The table records the measured source and output properties.

| Check                   | Observed result                                                                                      |
| ----------------------- | ---------------------------------------------------------------------------------------------------- |
| Creator download option | SoundCloud metadata returned `downloadable: false`                                                   |
| Source                  | Public full-length clear AAC HLS, approximately 96 kbps                                              |
| Source duration         | 27,332.393 seconds (7 h 35 min 32 s)                                                                 |
| Saved output            | AAC in M4A, stereo, 44.1 kHz                                                                         |
| Output duration         | 27,332.395 seconds                                                                                   |
| Final file size         | 332,701,891 bytes (332.7 MB decimal)                                                                 |
| Completion              | Native job reached `completed`; output exists and ffprobe identifies its audio stream                |
| Playback spot checks    | FFmpeg decoded ten-second windows at 0, 13,660, and 27,320 seconds without errors                    |
| Browser independence    | The test browser was closed after submission; the detached companion continued and completed the job |
| Process ownership       | Windows process-tree Job Object assignment succeeded in this run                                     |

Output SHA-256:

```text
01a9b42f17ba5c30d1aba7096f11c92f448b81a453b1c180b291c93a768c64d4
```

The hash identifies this local output; it is not a comparison with a creator-provided master. The recording and partial files are excluded from Git. The track's license metadata was `all-rights-reserved`; technical availability is not a rights grant.

During development, the initial one-fragment-at-a-time worker was paused and replaced with the three-fragment implementation. A newly resolved signed source changed the fingerprint, so Longwave **restarted the download safely**, retaining the first partial attempt. This live run does not demonstrate byte-resume across changing SoundCloud URLs. Resume equivalence is verified separately against stable local fixtures.

The live result covers this particular 7.6-hour source. The generated-duration matrix above measures progressive local transfer. Sleep/wake, abrupt full-OS shutdown, full-file decoding of long recordings and a live 10-hour HLS case remain unmeasured.

## Earlier developer-preview checks

- `npm run check`: strict TypeScript validation passed.
- `npm test`: **24 tests passed, zero skipped** in the configured environment.
- `npm run build`: unpacked Manifest V3 extension built successfully.
- `npm run test:browser`: real Edge extension and registered Native Messaging host passed.

The 19 unit tests cover URL boundaries, filename safety, framing, source selection when `downloadable` is false, preview/protection rejection, source fingerprints, idempotence after URL resolution, queue state transitions, worker recovery, exclusive locking, and error redaction.

The five pipeline tests use generated audio and real yt-dlp/FFmpeg/ffprobe. They cover progressive source preservation by decoded-audio hash, HLS-to-MP3 conversion, native protocol/origin checks, progressive pause/resume, and HLS pause/resume equivalence to an uninterrupted HLS baseline. Only source resolution and the local-fixture HTTPS gate are replaced.

Browser checks cover connection, enabled download control, Arabic RTL, Escape dismissal of the setup dialog, popup width, share-link preservation when opening the workspace, and absence of page exceptions. Each smoke run uses a fresh profile so an old cached extension worker cannot mask a code change.

axe-core reported **zero violations** under `wcag2a`, `wcag2aa`, and `wcag21aa` tags for the English workspace, Arabic workspace, and Arabic popup in the tested completed-job state. This is an automated check of those states, not a complete accessibility conformance audit.

## Reproduce

Follow the [setup instructions](../README.md), then run the documented checks. Register the native companion before the browser test. Browser screenshots are written under ignored `artifacts/`; generated-media fixtures are temporary and contain no music.

Use your own permitted public track for live testing. Avoid submitting the same job just to refresh a screenshot. Live service availability and signed URLs can change between runs.

See the [release roadmap](roadmap.md) for remaining production gates.
