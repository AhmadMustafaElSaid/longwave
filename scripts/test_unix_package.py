"""Exercise the extracted release as an isolated user on macOS or Linux."""
import io
import json
import os
import pathlib
import struct
import subprocess
import sys
import tarfile
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
version = json.loads((ROOT / "package.json").read_text())["version"]
archive = ROOT / "artifacts/releases" / version / f"longwave-{version}-unix.tar.gz"
with tempfile.TemporaryDirectory() as temp:
    work = pathlib.Path(temp)
    with tarfile.open(archive) as tar:
        tar.extractall(work, filter="data")
    package = work / "longwave"
    profile = work / "profile"
    state, output = work / "state", work / "My Audio"
    env = dict(os.environ, HOME=str(profile), XDG_CONFIG_HOME=str(profile / ".config"),
               LONGWAVE_HOME=str(state), LONGWAVE_PYTHON=sys.executable)
    launcher = str(package / "longwave")
    def cmd(args, **opts):
        return subprocess.run(args, env=env, check=True, timeout=60, capture_output=True, **opts)
    cmd([launcher, "connect", "--output", str(output)])
    manifests = list(profile.rglob("app.longwave.companion.json"))
    assert len(manifests) == 4
    manifest = json.loads(manifests[0].read_text())
    message = json.dumps({"version":1,"command":"snapshot"}).encode()
    frame = struct.pack("=I", len(message)) + message
    def snapshot():
        response = io.BytesIO(cmd([manifest["path"], manifest["allowed_origins"][0]], input=frame).stdout)
        size, = struct.unpack("=I", response.read(4))
        return json.loads(response.read(size))
    result = snapshot()
    assert result["ok"] and result["data"]["version"] == version and all(result["data"]["tools"].values()), result
    assert pathlib.Path(result["data"]["outputDir"]).samefile(output)
    assert not cmd([manifest["path"], "chrome-extension://"+"b"*32+"/"], input=frame).stdout
    marker = output / "existing.mp3"
    marker.write_bytes(b"preserved")
    cmd([launcher, "connect"])
    assert snapshot()["ok"] and marker.read_bytes() == b"preserved"
    cmd([launcher, "disconnect"])
    assert all(not m.exists() for m in manifests) and marker.read_bytes() == b"preserved"
    print(f"{sys.platform} {version}: connected, verified native protocol, upgrade, disconnect and retained audio.")
