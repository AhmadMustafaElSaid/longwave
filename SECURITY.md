# Security

This is a release candidate. Do not describe it as audited or hardened for production. The Windows installer is unsigned; published hashes do not substitute for publisher signing. Installer inputs are pinned and archive/payload integrity is checked before activation.

The extension cannot submit arbitrary shell commands, executable locations, or filesystem destinations to the companion. Input is restricted to supported SoundCloud links. Commands are validated and versioned, native message size is limited, and both browser registration and the native host check extension identity.

Audio work runs with the current user's privileges, never administrator privileges. There is no local network command listener. Filenames are sanitized, job-specific, and finalized in the configured destination. Media processing has network protocols disabled. Source URLs, metadata, and media remain untrusted input.

Remaining release risks include media-tool versions, extractor changes, redirects within the upstream delivery chain, source freshness on resume, and Windows environments where a process-tree Job Object cannot be assigned. Browser-only deployment and native binary distribution need separate reviews.

For a suspected vulnerability, contact the repository maintainer privately using GitHub's private vulnerability reporting feature once enabled. Do not post credentials, private track links, signed media URLs, raw databases, or personal browser profiles in public issues. There is no dedicated security mailbox configured yet.
