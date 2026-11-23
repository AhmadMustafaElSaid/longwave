# Release operations

[GitHub Releases](https://github.com/AhmadMustafaElSaid/longwave/releases) distributes Longwave. The Windows, macOS and Linux packages contain the same MV3 extension and a native companion with exact allowed extension identities. Phone access uses an existing installation and private HTTPS. Installation and removal details are in the [user guide](install.md).

## Build and publish

1. Update the npm package, companion version, localized version text, changelog and release notes. The pipeline checks the tag against the source version.
2. Push the change to the release branch and inspect the hosted Windows, macOS and Ubuntu jobs. The workflow installs exact npm and Python dependencies, tests the generated audio pipeline, tests package registration and validates phone and desktop browser flows.
3. Tag the verified commit with `v<version>`. A tag build creates platform assets again, computes SHA-256 over the entire asset set, obtains a GitHub workload-identity attestation, and verifies every signed subject before publishing the completed release draft.
4. Keep published assets immutable. Ship fixes from a new commit and version. The workflow can repair its own partially uploaded draft; an attempt to overwrite a published release fails.

The Windows ZIP carries the embedded CPython runtime and pinned extractor. Setup downloads a hash-checked FFmpeg/ffprobe archive. The Debian installer depends on distro Python and FFmpeg. The portable Unix bundle and macOS package contain the extractor and rely on installed Python and FFmpeg. The native macOS package installs under `/usr/local/lib/longwave`; the portable archive can live in the user's own directory.

## Signing identities

The release provenance ties the asset digest to the GitHub workflow and source revision. Verify it with `gh attestation verify <file> --repo AhmadMustafaElSaid/longwave`. GitHub also accepts the downloaded bundle using `--bundle provenance.jsonl`.

Windows builds can sign both setup and native host using an enrolled publisher certificate. Supply its thumbprint as `LONGWAVE_SIGNING_THUMBPRINT` and the SDK SignTool path as `LONGWAVE_SIGNTOOL`. The build timestamps and verifies both signatures before computing hashes. The Windows asset manifest records the actual Authenticode outcome.

On a signing-enabled Mac, `LONGWAVE_MAC_INSTALLER_IDENTITY` selects the Developer ID Installer keychain identity. `LONGWAVE_NOTARY_PROFILE` enables submission through the configured Apple keychain profile. The script checks the submission result, staples the ticket and validates the output. The public hosted workflow currently has neither publisher credential configured.

## Browser stores

The ready-to-upload ZIP omits the unpacked development key. Reserve a listing, record its assigned Chrome or Edge ID in `release/store-ids.json`, then verify the matching host allowlist and packaged extension before submission. Developer registration, platform review and the publisher’s rights to distribute the integration are prerequisites for each listing. [Store listing draft](store-listing.md) · [Chrome publication](https://developer.chrome.com/docs/webstore/publish) · [Microsoft Edge publication](https://learn.microsoft.com/en-us/microsoft-edge/extensions/publish/publish-extension)
