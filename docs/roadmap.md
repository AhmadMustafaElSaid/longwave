# Release roadmap

## Public distribution

The desktop companion is distributed through GitHub Releases for Windows x64, macOS and Linux. The tag workflow builds and tests the downloadable packages, signs their provenance and publishes the verified assets. Mobile browsers can pair with the companion over a private HTTPS endpoint. [Release operations](distribution.md) · [Test coverage](verification.md)

## Publisher-dependent distribution

- Enroll the Windows publisher identity and sign setup and native host. Enroll an Apple Developer ID Installer identity and notarization profile for the macOS package.
- Reserve Chrome and Edge listing IDs, test each store extension identity with the companion and submit with accurate disclosures.
- Assess standalone mobile applications separately. iOS software that facilitates downloads from providers such as SoundCloud requires explicit authorization from the source under Apple's review rules. [Apple App Review Guidelines §5.2.3](https://developer.apple.com/app-store/review/guidelines/#intellectual-property)

## Further verification and product work

Test sleep/wake, full disks and sudden OS shutdown on physical machines, add partial-cache management and improve diagnostics in Arabic. Test assistive technology and physical Android/iOS devices. Firefox needs its own native-host registration and manifest compatibility work.
