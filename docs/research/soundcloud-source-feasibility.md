# SoundCloud source feasibility and long-track design

Reviewed: 2026-11-22. Historical status at review time: source-code review completed; live extraction and performance were not yet verified. The subsequent implementation and real-track results are recorded in [verification evidence](../verification.md).

## Product scope

The user's primary requirement is to save public, playable SoundCloud tracks that do not expose a native download button, including 4-, 7-, and 10-hour recordings. Requiring a creator-enabled download URL would miss that requirement. The earlier competitor report's narrower recommendation is reference material, not a user instruction.

The proposed technical scope includes publicly available, unencrypted, full-length audio streams. Native download availability is metadata, not an eligibility condition. Exclude DRM, paid-access bypass, private-account access, and geographic restriction circumvention. A preview must never be presented as a full download. Technical availability is separate from copyright permission and platform terms; existing software is evidence of implementation, not permission or guaranteed store acceptance.

## Reproducible source references

The files below were read through the GitHub connector. Their branch versions were compared with their commit-pinned versions and matched exactly.

| Project       | Commit                                     | Inspected files                                                                        |
| ------------- | ------------------------------------------ | -------------------------------------------------------------------------------------- |
| nyo/scdl      | `2bd3e0e9efa1e99da1f2d0c334c0a9c6354ed277` | `index.js`, `manifest.json`; also reviewed root `LICENSE` and `wasm/README.md` on main |
| yt-dlp/yt-dlp | `a38fc9a11f9dc519964ea710225ec1944c6444e0` | `yt_dlp/extractor/soundcloud.py`; also reviewed root `LICENSE` on master               |

- [SCDL implementation](https://github.com/nyo/scdl/blob/2bd3e0e9efa1e99da1f2d0c334c0a9c6354ed277/index.js)
- [SCDL manifest](https://github.com/nyo/scdl/blob/2bd3e0e9efa1e99da1f2d0c334c0a9c6354ed277/manifest.json)
- [yt-dlp SoundCloud extractor](https://github.com/yt-dlp/yt-dlp/blob/a38fc9a11f9dc519964ea710225ec1944c6444e0/yt_dlp/extractor/soundcloud.py)

## What SCDL actually does

1. `findClientIdInDocument` (lines 1548-1573) discovers the web client's identifier in public script assets. This is coupled to SoundCloud's frontend implementation, not a stable integration contract.
2. `resolveTrack` (613-640) resolves a page URL through the web API and checks that the result is a track.
3. `fetchStreamData` (537-606) selects media transcodings, preferring MP3 and falling back to AAC HLS. The download flow (1068-1106) does not require the creator-download flag.
4. Progressive media is read into an entire ArrayBuffer. HLS uses Promise.all over all listed fragments, retains the fragment buffers, then builds a Blob and another ArrayBuffer (211-268).
5. AAC is fully decoded with OfflineAudioContext.decodeAudioData (438-486), encoded through LAME in chunks, and all encoded output chunks are retained before final assembly. Chunked encoding does not make the overall pipeline bounded in memory.
6. Metadata and artwork are added before a browser save. The transfer and processing run in a content script, with no independent durable job engine.

The manifest is Firefox MV2, and the AAC path uses Firefox-specific `content.fetch`. This is not a drop-in Chrome/Edge MV3 implementation. The HLS reader is also a narrow parser: treating all non-comment lines as media URLs does not implement master playlists, byte-range segments, discontinuities, and general HLS validation.

SCDL's error handling can attribute failure to protection when encrypted alternatives are present and clear-source requests fail. Our implementation must preserve the actual failure category: request failure alone is not proof of DRM.

## Why the memory model is unsuitable

Calculated estimates, not benchmark results. At 44.1 kHz, stereo, float32 PCM:

`decoded bytes = duration seconds * 44,100 * 2 * 4`

| Duration | Audio at 160 kbps | Decoded PCM alone |
| -------- | ----------------: | ----------------: |
| 4 hours  |          0.288 GB |        5.08032 GB |
| 7 hours  |          0.504 GB |        8.89056 GB |
| 10 hours |          0.720 GB |       12.70080 GB |

These are decimal GB. PCM excludes compressed input, encoded output, copies, decoder state, browser overhead, and artwork. A runtime may fail before allocating the theoretical buffer. At 320 kbps, a ten-hour MP3 adds about 1.44 GB of output. The bottleneck is whole-track decoding and buffering, not simply the number of hours or JavaScript versus native code.

## Cross-check against yt-dlp

The inspected extractor separates original-file downloading (lines 260-295) from stream extraction (301-373). The latter is not conditioned on the original-download flag. It also identifies previews (357-359), recognizes multiple codecs, and distinguishes some protected and geographically blocked sources.

This independently supports the proposed source model at the code level. It does not establish that a particular track still resolves today. yt-dlp also supports paths outside our proposed scope, so unrestricted delegation would be inappropriate: a future adapter must select only supported public, unencrypted, full-length sources and return structured outcomes.

Use yt-dlp as a reference and potential feasibility-spike tool behind an adapter, not as a reason to promise every SoundCloud URL will work. Choosing it as a distributed dependency requires a separate packaging and update decision. No executable was installed or run during this review.

## Proposed architecture after review

For the complete long-track feature, recommend a browser extension plus a local companion. A companion is a recommendation pending user alignment, not an accepted requirement.

- **Extension:** current-page/link input, explicit user action, metadata preview, queue and progress, capability-aware controls. Browser-managed downloads remain useful for directly downloadable media.
- **Source resolver:** page URL to stable track identity, selected rendition, codec/container, duration, preview/protection status, and ephemeral source URL. Isolate this volatile adapter from the transfer engine. Do not log signed URLs, tokens, or credentials.
- **Companion:** bounded transfer buffers, disk-backed checkpoints, fragment scheduling, cancellation, retry, free-space checks, container processing, and optional MP3 conversion.
- **IPC:** versioned Native Messaging commands and events, no audio payloads. Validate messages and extension identity. A browser-owned native host is not inherently independent of browser shutdown.
- **Processing:** preserve AAC in a player-compatible M4A container where suitable; transcode to MP3 only when selected. Never label transcoding to a higher bitrate as restored source quality.

If installation must remain extension-only, investigate a dedicated extension page with a supported streaming file destination. That route needs a separate browser capability and lifecycle spike; it must not inherit the companion's recovery promises. Do not assemble multi-hour HLS audio using whole-file Blobs or assume chrome.downloads assembles a playlist into audio.

### HLS recovery must be fragment-aware

HTTP byte-range resume alone does not solve HLS recovery. Maintain track and rendition identity, playlist timeline, initialization-segment identity, segment sequence/range metadata, and verified completed files. Bound the number of queued and active segments. Start with one active transfer and increase only after measurement.

On URL expiry, re-resolve the same source through the normal supported path, then compare identities and timeline before reusing fragments. A changed URL can represent identical media; an unchanged sequence number alone does not prove identical media. When identity cannot be established, stop or restart safely rather than combine incompatible fragments.

Download each fragment to a temporary file, finalize it after transfer validation, and reconcile disk files with the job journal on startup. Preserve initialization data, timestamps, and required discontinuities. Let a tested media tool remux the completed local input; concatenating bytes and changing the extension is not a universal container strategy.

Implement an explicit finite-VOD subset initially. Detect and report unsupported playlist features rather than silently produce broken output. Reference: [HLS RFC 8216](https://www.rfc-editor.org/rfc/rfc8216.html).

### Output and error contracts

Resolver outcomes: available full stream, preview only, protected, authentication required, unavailable/removed, region restricted, unsupported source, rate limited, network failure, and source-layout change. Do not map all HTTP 403/404 responses to DRM.

Track stages separately: resolving, queued, downloading, paused, retrying, assembling, converting, completed, failed, cancelled. A completed network stage is not a completed playable file. Validate output duration and codec and test seeking near the beginning, middle, and end. Show 2x playback guidance for external players rather than baking acceleration into every output.

## Reuse and licenses

- SCDL's root license is MIT. Retain its copyright and license notice if copying substantial code. [License](https://github.com/nyo/scdl/blob/main/LICENSE)
- Its encoder dependency is separately identified as LAME under LGPL; the root MIT label does not cover all bundled dependencies. The build notes also identify other upstream contributions. [Build provenance](https://github.com/nyo/scdl/blob/main/wasm/README.md)
- yt-dlp's root source license is the Unlicense; distribution decisions must also account for the selected executable's bundled dependencies. [License](https://github.com/yt-dlp/yt-dlp/blob/master/LICENSE)
- FFmpeg licensing depends on the actual build and enabled components. Record exact versions, configuration, notices, and corresponding source obligations before distributing binaries. [FFmpeg licensing](https://ffmpeg.org/legal.html)

Recommendation: implement the extension architecture independently; reuse maintained media tooling only behind narrow interfaces after checking the actual artifacts. No third-party source has been copied into the project.

## Next implementation milestone

Before a full downloader or polished UI:

1. Resolve a public playable track with native downloading disabled. Record sanitized source metadata, codec, full/preview status, and available supported transport.
2. Demonstrate a short end-to-end download from an unencrypted full source and validate playback, duration, and seeking.
3. Exercise the same pipeline on generated HLS fixtures: master/media playlist handling, initialization segments, byte ranges, interrupted fragments, expired URLs, changed renditions, unsupported encryption, and previews.
4. Measure a long permitted sample and a multi-gigabyte deterministic fixture. Publish success, memory, duration, and recovery evidence separately from source-code observations.
5. Only then implement the selected browser/companion production path and distribution packaging.

The remaining architectural choice is whether users may install a local companion. Resolve that before committing to a transfer implementation. Go was not available on PATH during this review; Node.js, Python, and Git were detected. No installation or system configuration was changed.

## Verification limits

- Completed: read source and manifests, checked pinned-file equality, inspected declared licenses, calculated memory estimates.
- Not completed: live SoundCloud extraction, downloading audio, launching SCDL, long-track benchmarking, FFmpeg output verification, or browser-store acceptance review.
- Local Git network discovery failed with a resolver error; connected GitHub reads supplied the inspected sources and commit metadata. This did not block the source review.

The finding is architectural feasibility with specific engineering risks, not a claim that the finished product or ten-hour download path has been demonstrated.
