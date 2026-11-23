# Contributing

Use Node.js 22+ and Python 3.11+. Follow README.md for setup. Keep browser-specific code in the extension adapter, SoundCloud extraction in the source/audio adapter, and durable transitions in the journal.

Before submitting a change, run `npm run check`, `npm test`, `npm run format:check`, and `npm run build`. Changes to UI or native messaging also need `npm run test:browser` on Windows with a registered companion. Tests must not depend on downloading copyrighted recordings: generate fixtures locally. Live-source checks are opt-in and must report what was actually observed.

Use explicit error codes and bounded retry/concurrency. Never collect a complete long recording into a browser Blob or PCM buffer. Do not log tokens, cookies, signed media URLs, or private links. Do not add silent format fallback, missing-fragment skipping, DRM bypass, or authentication circumvention.

For protocol changes, update both sides and tests. Keep the protocol-version check. For dependency changes, pin versions, update the lockfile, inspect licenses, and rerun the relevant source/format tests. Do not commit local audio, virtual environments, browser profiles, cache files, or native registration files.

Describe the user-visible problem, changed behavior, verification performed, and remaining limitations. Avoid reliability claims unsupported by a recorded test.
