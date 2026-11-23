# Third-party components

Longwave original source uses MIT. External components retain their own terms.

| Component                                                 | Role                    | License and source                                                                                                                                                                                                                             |
| --------------------------------------------------------- | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CPython 3.14.10                                           | Private runtime         | PSF license; official archive LICENSE.txt retained. [Source](https://www.python.org/downloads/release/python-31410/)                                                                                                                           |
| yt-dlp 2026.10.26                                         | Extraction and transfer | Unlicense; original Python wheel/source and license files included, not a frozen executable. [Source](https://github.com/yt-dlp/yt-dlp/tree/2026.10.26)                                                                                        |
| FFmpeg / ffprobe 9.1                                      | Media processing        | Gyan GPLv3 essentials build, downloaded directly from upstream by setup, not bundled or re-hosted. [Binaries and source references](https://github.com/GyanD/codexffmpeg/releases/tag/9.1), [legal information](https://ffmpeg.org/legal.html) |
| TypeScript, Playwright, axe-core, Prettier, type packages | Development/testing     | Exact versions in package-lock.json; inspect upstream package licenses. Not companion runtime dependencies.                                                                                                                                    |

Pinned hashes and provenance are in release/dependencies.json and the generated release manifest. Setup retains the upstream media README/license files. Longwave MIT licensing does not replace GPL, PSF, or Unlicense terms.

The earlier preview used FFmpeg 6.1.1 and ffprobe 4.0.2 from npm packages. Those dependencies have been removed and are not used in the release candidate. Native executables are excluded from Git and the extension archive.

SCDL was inspected as a design reference. Its implementation and LAME/WebAssembly bundle were not copied into Longwave. The research report identifies the inspected revision.
