# Store submission material

Prepared for publisher submission. [Website](https://ahmadmustafaelsaid.github.io/longwave/) · [Support](https://github.com/AhmadMustafaElSaid/longwave/issues) · [Privacy policy](https://ahmadmustafaelsaid.github.io/longwave/privacy/). Publisher accounts, store IDs, publisher credentials and review remain pending.

## Name

Longwave — SoundCloud audio

## Short description

Save supported public SoundCloud audio locally with a companion designed for long recordings.

## Description

Longwave saves supported public audio to your computer for offline listening in your preferred player. A local companion performs downloads and audio processing, so closing the extension page does not stop a running job.

- Source-format audio or optional MP3 output.
- Persistent queue, progress, pause, conditional resume, and retry.
- English and Arabic interfaces, including right-to-left layout.
- No application-imposed duration limit; available disk space and source conditions apply.
- No account integration, telemetry, or remote audio conversion service.

Requires the separately installed desktop companion for Windows x64, macOS or Linux. A full-length unencrypted public stream must be available. The native download button is optional. Expired stream URLs can require a fresh download. Users can optionally enable a paired phone web interface. Playlists, protected audio and private sessions are unsupported.

Save only audio you own or have permission to retain. Respect copyright, licenses, and platform terms. Public playback availability does not establish download permission. Longwave is not affiliated with SoundCloud.

## Permission explanations

| Permission        | Purpose                                                                                          |
| ----------------- | ------------------------------------------------------------------------------------------------ |
| `nativeMessaging` | Send narrowly validated local download commands and read job status from the installed companion |
| `activeTab`       | Read the current page URL only when the user invokes the extension and selects Use current tab   |
| `storage`         | Save the chosen interface language locally                                                       |

No broad website access, cookies, browsing-history collection, analytics, advertising, or remotely hosted extension code. Track requests are sent by the native companion to SoundCloud/CDNs. Setup fetches pinned tools from the upstream binary host. The extension itself contains its packaged scripts and does not fetch executable code.

## Reviewer test instructions

Install the exact signed companion linked to the submission, then install the store test build whose ID is in its native-host allowlist. Open Longwave and confirm Connected. Use a public full-length track you have permission to save; confirm source output, progress, cancellation, and completed output. For reproducible processing checks without copyrighted music, run the generated-audio integration suite from the source archive.

Do not supply private links, browser cookies, authentication bypass instructions, or misleading claims of guaranteed platform approval. Review possible store-policy restrictions on the actual product behavior before submitting.

## Required release evidence

Record Chrome and Edge versions, exact OS versions/architectures, installer signature, clean-profile connection, uninstall preservation, source/MP3 outputs, long-track results, accessibility findings, dependency provenance, and unresolved limitations. The candidate's existing evidence is not a substitute for tests on the final signed store build.
