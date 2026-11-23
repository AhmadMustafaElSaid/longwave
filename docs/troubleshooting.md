# Troubleshooting

## “Setup needed”

Standalone users: extract the complete ZIP, run `Longwave-Setup.exe`, and load the extension folder shown by setup. Keep that installed folder in place. Developer users: run the source installer using `.venv/Scripts/python.exe` after `npm run build`. Reload the extension. Its browser ID must match the registered allowlist.

If you installed with a custom `--home`, continue using it for maintenance and uninstall. Source moves require rerunning the installer from the new location. A public-store build may have a different extension ID and will need a corresponding host registration.

## Missing or invalid media tools

Standalone setup downloads the pinned Gyan archive and checks its SHA-256 before installing matching FFmpeg/ffprobe. A checksum mismatch stops setup. Retry from the complete official package; do not edit checksums to bypass validation.

For development, run `npm run setup:media`, then rerun the developer installer. Tool paths are recorded in `.tools/media-paths.json`; old npm binary packages are no longer used.

## Link not accepted

Use an individual public track link or an `https://on.soundcloud.com/...` share link. Playlist, profile, private-token, non-HTTPS, and unrelated URLs are rejected. Pasting a SoundCloud sharing message into the URL field extracts its single SoundCloud link automatically.

## Download restarts when resumed

SoundCloud may issue a different signed URL when resolving the same track again. The initial resume policy is deliberately conservative: if identity cannot be established, a new attempt starts. The UI says this explicitly, and old partial files remain in the companion's `work` directory. This is a known limitation, not proof that the original audio changed.

## Pausing takes a moment

Network operations have a 20-second timeout. Pause is cooperative and can wait for an outstanding request. The UI distinguishes a requested pause from a completed pause. Do not manually edit the job database during transfer.

## Worker stopped or machine restarted

Open the Longwave workspace. It restarts a missing worker and reconciles unfinished state. If a job is marked failed, choose Retry. There is no startup task or system service.

## Output is M4A rather than MP3

Source audio preserves the available stream without a lossy second encoding. Select MP3 when your player needs it. Use the player's speed control for 2× playback; the file is not permanently sped up.

## Freeing partial-cache space

Pause or cancel unfinished work first and disconnect the companion if necessary. Wait until its worker has exited before removing its `work` subdirectory. This removes resumable source files, not completed output in the configured audio folder. Automatic cache management is planned; the current application never deletes completed audio.

## Reporting a problem

Include the application/extractor version, browser/OS, public error code, stage, approximate track duration, and whether restarting worked. Do not include cookies, signed CDN URLs, private links, raw SQLite databases, or the browser profile. See SECURITY.md for sensitive reports.
