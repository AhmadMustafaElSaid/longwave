"""Build and inspect the macOS installer, optionally sign and notarize it."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from package_unix import ROOT, contents


def main():
    if sys.platform != "darwin":
        raise SystemExit("Build the macOS installer on macOS.")
    version = json.loads((ROOT / "package.json").read_text())["version"]
    target = ROOT / "artifacts/releases" / version / f"longwave-{version}-macos.pkg"
    target.parent.mkdir(parents=True, exist_ok=True)
    identity = os.environ.get("LONGWAVE_MAC_INSTALLER_IDENTITY")
    profile = os.environ.get("LONGWAVE_NOTARY_PROFILE")
    if profile and not identity:
        raise ValueError("Notarization requires a Developer ID Installer signing identity.")
    with tempfile.TemporaryDirectory() as temp:
        payload = Path(temp) / "package"
        contents(payload)
        command = ["pkgbuild","--root",str(payload),"--install-location","/usr/local/lib/longwave",
                   "--identifier","io.github.ahmadmustafaelsaid.longwave","--version",version]
        if identity:
            command.extend(["--sign",identity,"--timestamp"])
        subprocess.run([*command,str(target)],check=True)
        if identity:
            subprocess.run(["pkgutil","--check-signature",str(target)],check=True)
        if profile:
            reply = subprocess.check_output(["xcrun","notarytool","submit",str(target),
                   "--keychain-profile",profile,"--wait","--output-format","json"])
            if json.loads(reply).get("status") != "Accepted":
                raise ValueError("Apple did not accept the installer for notarization.")
            subprocess.run(["xcrun","stapler","staple",str(target)],check=True)
            subprocess.run(["xcrun","stapler","validate",str(target)],check=True)
        expanded = Path(temp) / "expanded"
        subprocess.run(["pkgutil","--expand-full",str(target),str(expanded)],check=True)
        assert (expanded / "Payload/extension/manifest.json").is_file()
        assert os.access(expanded / "Payload/longwave", os.X_OK)
        print(f"{target.name}: checked package contents; Developer ID={bool(identity)}, notarized={bool(profile)}")


if __name__ == "__main__":
    main()
