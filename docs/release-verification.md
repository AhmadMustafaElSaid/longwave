# 0.2.0-rc.1 release verification

This candidate was built and tested locally on Windows on 2026-11-23. It is an installable Windows x64 distribution, not a signed stable release or a claim of support on every device.

## Verified inputs and artifacts

- CPython 3.14.10 official embeddable x64 ZIP, checked against the SHA-256 published on its release page.
- yt-dlp 2026.10.26 wheel, matched to the pinned PyPI digest and packaged as Python source with notices.
- Matching FFmpeg and ffprobe 9.1 Gyan essentials build, archive checked against upstream SHA-256. These are downloaded directly by setup, not included in the Longwave ZIP.
- Standalone Windows ZIP, Chromium ZIP, separate store-upload ZIP, source ZIP, machine-readable release manifest, and SHA256SUMS.

No user recording, SQLite database, browser profile, or local installation path is included in the runtime/source package. Installer preview rendering substitutes a generic user path.

## Package tests

The actual ZIP was extracted to a new Unicode directory. System Python, Node.js, virtual-environment variables, and project PYTHONPATH were removed from the child environment. The package used its embedded interpreter and installed media executables.

Verified: fresh installation, side-by-side update, restoration of the previous version, native executable response framing, rejection of a non-allowlisted origin, and disconnection preserving both a data sentinel and an audio-folder sentinel. Tests also exercise a native response while the input pipe stays open, matching browser behavior.

The bundled code passed **29 tests without skips**, including the real generated-media pipeline: progressive preservation, HLS assembly/MP3 conversion, progressive and HLS pause/resume equivalence, protocol framing, source selection, and release archive/payload integrity. This is isolation on the same host, not a separate clean OS installation. The prepared GitHub workflow has not yet been run remotely.

## Real browsers

The standalone host was temporarily registered for isolated test profiles, then the original registry values were restored. The UI output directory was asserted to ensure the test connected to the packaged companion rather than the developer installation.

| Browser        | Version       | Result                                                                                           |
| -------------- | ------------- | ------------------------------------------------------------------------------------------------ |
| Microsoft Edge | 158.0.4370.33 | Native Messaging, UI, RTL, keyboard dialog dismissal, popup width, and share-link handoff passed |
| Google Chrome  | 157.0.8103.79 | Same checks passed                                                                               |

Chrome's test uses the extension-debugging CDP pipe in a disposable profile and enables Developer mode there. Normal user profiles and browser policies are unchanged. This is test tooling only and is not shipped inside the extension.

axe-core reported zero violations under WCAG 2 A/AA and 2.1 AA tags for the English workspace, Arabic workspace, and Arabic popup in tested states in both browsers. This does not replace a manual assistive-technology audit.

The installer form was rendered offscreen in English and Arabic and inspected for text clipping and layout. Its installation logic is tested through the same embedded installer entrypoint; interactive installation on a separate user's machine is still needed.

## Remaining release gates

- Publisher Authenticode identity and signed final binaries.
- An actual repository/release URL and public support/privacy URLs.
- Reserved browser-store IDs, store-specific native allowlist tests, and store review.
- Clean Windows 10/11 machine testing, high-DPI and assistive-technology testing, security review, and broader long-duration/crash/sleep/low-disk tests.
- macOS/Linux/ARM64/Firefox packaging; no mobile support is currently claimed.

The previous real 7 h 35 min source test is documented in [verification.md](verification.md). The new package pipeline uses generated audio; it did not redownload that entire recording merely to validate packaging.
