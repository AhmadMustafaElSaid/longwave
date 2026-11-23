# Installing Longwave

[Download a release](https://github.com/AhmadMustafaElSaid/longwave/releases). Pick the asset for the computer that will process your audio.

| Computer                          | Installation                                                                                                                                                                                                    |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Windows x64                       | Extract the Windows ZIP, open **Longwave-Setup.exe**, choose a destination and select **Install**. Use **Copy path + open guide** for the extension folder.                                                     |
| Ubuntu / Debian with Python 3.11+ | Run `sudo apt install ./longwave-0.3.0-all.deb` from the download folder. Run `longwave connect`. APT installs Python and FFmpeg with the package.                                                              |
| macOS or other Linux desktops     | Install Python 3.11+ and FFmpeg using your system package manager. On macOS with Homebrew, run `brew install python ffmpeg`. Extract the Unix archive to a permanent folder and run `./longwave connect` there. |

Open `chrome://extensions` or `edge://extensions`, enable Developer mode and choose **Load unpacked**. Select the directory printed by setup. Open Longwave, paste a permitted track link and choose **Source audio** or **MP3**. The full-length public stream is used when available. Set the speed in your local player.

On macOS and Linux, `connect --output "/path/to/Audio"` sets the audio folder. Run the new version's `connect` after updating or the previous version's `connect` to restore it. Active transfers pause before the switch. `disconnect` removes your browser registrations and preserves your library. Store package identities are granted individually.

## Download from your phone

The phone interface uses a Longwave installation on a computer you control. That computer handles the long transfer. Once it finishes, the phone can play at 1× or 2×, or save the file for offline listening. Pairing grants access to that installation's queue and its completed audio. Keep the pairing code private.

1. Install a private HTTPS reverse proxy between your phone and the computer. On a private Tailscale network, `tailscale serve http://127.0.0.1:8765` displays the HTTPS address. Keep Serve running. Your phone must be on the same tailnet. Use a separate origin dedicated to Longwave.
2. On Linux or macOS run `longwave phone --origin https://YOUR-PRIVATE-HOST` (use `./longwave` from an extracted archive). On Windows run `Phone.cmd --origin https://YOUR-PRIVATE-HOST` in the installed version folder. Keep this terminal open.
3. Open the displayed origin in Safari or Chrome and enter the single-use pairing code. A code lasts ten minutes. A session lasts twelve hours. Select **Save to phone** on a finished download. Stopping phone access closes the session while the existing queue keeps working.

To try it on the same machine, omit `--origin` and use the displayed loopback address. The phone service binds to IPv4 loopback. Only an explicitly configured HTTPS proxy provides access from another device. Longwave does not operate a public download relay.

## Verify a download

Download `SHA256SUMS.txt` with your package. Use `Get-FileHash -Algorithm SHA256 .\your-package.zip` on Windows, `sha256sum your-package.deb` on Linux or `shasum -a 256 your-package.tar.gz` on macOS. Compare the complete digest and filename with the matching entry. Verify the release workflow identity with `gh attestation verify your-package --repo AhmadMustafaElSaid/longwave`, using the actual filename.

The optional macOS package places the launcher at `/usr/local/lib/longwave/longwave`. Run it with `connect` after installing Python and FFmpeg. The current Windows setup has no Authenticode publisher signature. The macOS package has no Developer ID signature or notarization. On managed computers follow your organization's installation policy. The portable Unix archive can be installed in your user directory.

Use audio you own or have permission to retain, subject to the platform terms. [Privacy](https://github.com/AhmadMustafaElSaid/longwave/blob/main/PRIVACY.md) · [Help and issues](https://github.com/AhmadMustafaElSaid/longwave/issues) · [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve).
