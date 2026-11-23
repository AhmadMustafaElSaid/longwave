# Release roadmap

## Implemented developer slice

- Chromium extension, bilingual popup/workspace, real Native Messaging integration.
- Windows source installer with narrowly scoped native-host registration.
- Public track/share-link resolution, clear-stream selection, queue persistence.
- Isolated local audio jobs, conditional resume, bounded HLS concurrency.
- Source preservation, MP3 conversion, output validation.
- Local generated-audio tests, browser smoke checks, automated accessibility checks.
- Standalone Windows x64 candidate with embedded runtime, bilingual setup, side-by-side updates, rollback, and disconnection.
- Matching FFmpeg/ffprobe 9.1 with pinned hashes, distribution artifacts, and a release workflow.

## Before a public production release

1. Complete security review of pinned runtime/media dependencies and maintain provenance/notices.
2. Sign the installer with the publisher's identity, add cache management, and finish clean-machine validation.
3. Validate native messaging, pause/crash recovery, low disk, sleep/wake, and browser updates on actual Chrome and Edge release matrices.
4. Publish measured 4-, 7-, and 10-hour results with memory and output verification; a single live test is not a universal reliability claim.
5. Improve signed-URL refresh recovery using source identity evidence rather than unsafe query stripping.
6. Fully localize diagnostic messages, add accessible background status announcements, and test assistive technology manually.
7. Complete threat-model and dependency review, privacy/store disclosures, branding review, and platform-terms review.

## Later

Firefox, macOS/Linux installers, controlled bulk queues, metadata/artwork editing, per-job destination selection, and optional accelerated exports. These are not advertised as shipped features.
