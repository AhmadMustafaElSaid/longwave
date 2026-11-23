"""Assemble portable macOS/Linux clients from the built extension and pinned wheel."""

import argparse
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "release"))
from download import digest, extract, fetch


def extractor_wheel():
    dep = json.loads((ROOT / "release/dependencies.json").read_text())["extractor"]
    cache = ROOT / ".runtime/download-cache/extractor.whl"
    if cache.is_file() and digest(cache) == dep["sha256"]:
        return cache
    with urllib.request.urlopen(dep["metadataUrl"], timeout=30) as response:
        wheel = next(entry for entry in json.load(response)["urls"] if entry["filename"].endswith(".whl")
                     and entry["digests"]["sha256"] == dep["sha256"])
    return fetch(wheel["url"], dep["sha256"], cache)


def contents(package):
    shutil.copytree(ROOT / "release/unix", package, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(ROOT / "companion/longwave", package / "lib/longwave", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    extract(extractor_wheel(), package / "lib")
    shutil.copytree(ROOT / "dist/chromium", package / "extension")
    shutil.copy2(ROOT / "LICENSE", package)
    shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.md", package)
    shutil.copy2(ROOT / "docs/install.md", package / "INSTALL.md")
    ids = {(ROOT / "dist/extension-id.txt").read_text().strip()}
    ids.update(value for value in json.loads((ROOT / "release/store-ids.json").read_text()).values() if value)
    if not all(re.fullmatch("[a-p]{32}", value) for value in ids):
        raise ValueError("Invalid native host extension identity.")
    (package / "origins.json").write_text(json.dumps([f"chrome-extension://{i}/" for i in sorted(ids)]))
    (package / "longwave").chmod(0o755)


def archive(folder, target):
    # Normalise metadata so a rebuild does not embed a builder's account or absolute path.
    with target.open("wb") as raw, gzip.GzipFile(fileobj=raw, filename="", mode="wb", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            for path in [folder, *sorted(folder.rglob("*"))]:
                member = tar.gettarinfo(str(path), str(path.relative_to(folder.parent)).replace(os.sep, "/"))
                member.mtime = member.uid = member.gid = 0
                member.uname = member.gname = ""
                member.mode = 0o755 if path.is_dir() or path == folder / "longwave" else 0o644
                if path.is_file():
                    with path.open("rb") as data:
                        tar.addfile(member, data)
                else:
                    tar.addfile(member)


def debian(package, output, version):
    deb = package.parent / "deb"
    shutil.copytree(package, deb / "usr/lib/longwave")
    launcher = deb / "usr/bin/longwave"
    launcher.parent.mkdir(parents=True)
    launcher.write_text('#!/bin/sh\nexec /usr/lib/longwave/longwave "$@"\n')
    launcher.chmod(0o755)
    control = deb / "DEBIAN/control"
    control.parent.mkdir()
    control.write_text(f"""Package: longwave
Version: {version.replace("-", "~")}
Architecture: all
Maintainer: AhmadMustafaElSaid <117285037+AhmadMustafaElSaid@users.noreply.github.com>
Depends: python3 (>= 3.11), ffmpeg
Homepage: https://github.com/AhmadMustafaElSaid/longwave
Description: Local audio companion for Longwave
 Manage permitted SoundCloud audio downloads from the browser or a paired phone.
""")
    subprocess.run(["dpkg-deb", "--root-owner-group", "--build", str(deb), str(output / f"longwave-{version}-all.deb")], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deb", action="store_true")
    args = parser.parse_args()
    version = json.loads((ROOT / "package.json").read_text())["version"]
    output = ROOT / "artifacts" / "releases" / version
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp) / "longwave"
        contents(folder)
        archive(folder, output / f"longwave-{version}-unix.tar.gz")
        if args.deb:
            debian(folder, output, version)
