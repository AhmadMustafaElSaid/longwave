# Security

The release workflow checks package contents, runs integration tests and signs build provenance. The Windows release manifest separately records Authenticode status. Installer inputs are pinned and verified before activation.

The extension cannot submit arbitrary shell commands, executable locations, or filesystem destinations to the companion. Input is restricted to supported SoundCloud links. Commands are validated and versioned, native message size is limited, and both browser registration and the native host check extension identity.

Audio jobs run with the current user's privileges. Filenames are sanitized, job-specific, and finalized in the configured destination. Media processing has network protocols disabled. Source URLs, metadata, and media remain untrusted input. The optional phone server binds to loopback and checks host, pairing session and POST origin. Use a dedicated origin on a private network. A paired phone can manage the queue and read completed audio.

Remaining release risks include media-tool versions, extractor changes, redirects within the upstream delivery chain, source freshness on resume, and Windows environments where a process-tree Job Object cannot be assigned. Browser-only deployment and native binary distribution need separate reviews.

Report a suspected vulnerability directly to the maintainer through [private vulnerability reporting](https://github.com/AhmadMustafaElSaid/longwave/security/advisories/new). Include the affected version and operating system. Omit private track links, access tokens, raw databases and personal browser profiles.
