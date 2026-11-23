# Verification evidence

Local verification: 2026-11-22–23, Windows, Node.js 24.22.0, Python 3.15, Edge 158.0.4370.33. This records a working developer preview, not a claim of production certification.

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

The successful run is evidence for this particular 7.6-hour source. A full 4/7/10-hour performance matrix, peak memory measurements of the complete process tree, deliberate OS-crash tests, and full-file decoding remain release work. Sampled process memory during development is not reported as a peak-memory benchmark.

## Automated checks

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
