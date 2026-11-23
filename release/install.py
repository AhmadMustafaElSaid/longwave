"""Per-user release installation, repair, rollback, and disconnection.

No registry writes occur until all downloaded files pass their pinned hashes and
the staged runtime passes its health check. User audio/history are never deleted.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

from download import extract, fetch

HOST = 'app.longwave.companion'
BROWSERS = ('Google\\Chrome', 'Microsoft\\Edge')


def validate_payload(payload):
    from download import digest
    payload = Path(payload).resolve()
    checks = json.loads((payload / 'files.sha256.json').read_text())
    if not checks or not isinstance(checks, dict):
        raise ValueError('Missing payload checksums.')
    for relative, expected in checks.items():
        path = (payload / relative).resolve()
        if not path.is_relative_to(payload) or not path.is_file() or digest(path) != expected:
            raise ValueError('Release payload failed verification. Extract a fresh official package.')


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.new')
    temp.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    os.replace(temp, path)


def run(args, **kwargs):
    return subprocess.run([str(arg) for arg in args], check=True, capture_output=True,
                          text=True, timeout=60, creationflags=subprocess.CREATE_NO_WINDOW, **kwargs)


def register(manifest):
    import winreg
    changed = []
    try:
        for browser in BROWSERS:
            key_path = f'Software\\{browser}\\NativeMessagingHosts\\{HOST}'
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                    old = winreg.QueryValueEx(key, '')[0]
            except FileNotFoundError:
                old = None
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValueEx(key, '', 0, winreg.REG_SZ, str(manifest))
            changed.append((key_path, old))
    except Exception:
        for key_path, old in reversed(changed):
            if old is None:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
            else:
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                    winreg.SetValueEx(key, '', 0, winreg.REG_SZ, old)
        raise


def pause_worker(data):
    from longwave.store import Store
    from longwave.model import ACTIVE
    from longwave.worker import WorkerLock
    store = Store(data)
    for job in store.list():
        if job['state'] in ACTIVE:
            store.command(job['id'], 'pause')
    stop = store.root / 'stop-worker'
    stop.touch()
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        with WorkerLock(store.root) as acquired:
            if acquired:
                return
        time.sleep(0.25)
    stop.unlink(missing_ok=True)
    raise RuntimeError('A download is still stopping. Wait a minute and run setup again.')


def activate(root, version_dir, output, register_host=True):
    data = root / 'data'
    receipt_path = root / 'installation.json'
    previous = json.loads(receipt_path.read_text()) if receipt_path.exists() else None
    package = json.loads((version_dir / 'package.json').read_text())
    manifest = data / 'native-host.json'
    settings = data / 'config.json'
    backups = {path: path.read_bytes() if path.exists() else None for path in (manifest, settings, receipt_path)}
    prior_config = json.loads(settings.read_text()) if settings.exists() else {}
    output = Path(output or prior_config.get('output_dir') or Path.home() / 'Downloads' / 'Longwave').resolve()
    output.mkdir(parents=True, exist_ok=True)
    pause_worker(data)
    try:
        atomic_json(settings, {'ffmpeg': str(version_dir / 'media/bin/ffmpeg.exe'),
                              'ffprobe': str(version_dir / 'media/bin/ffprobe.exe'),
                              'output_dir': str(output), 'allowed_origins': package['origins']})
        atomic_json(manifest, {'name': HOST, 'description': 'Longwave local audio companion',
                              'path': str(version_dir / 'LongwaveHost.exe'), 'type': 'stdio',
                              'allowed_origins': package['origins']})
        atomic_json(receipt_path, {'version': package['version'], 'current': str(version_dir),
                                  'previous': previous['current'] if previous else None,
                                  'installed': time.time(), 'registered': register_host})
        if register_host:
            register(manifest)
    except Exception:
        for path, content in backups.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                restore = path.with_name(path.name + '.restore')
                restore.write_bytes(content)
                os.replace(restore, path)
        raise
    finally:
        (data / 'stop-worker').unlink(missing_ok=True)
    print('Installed successfully. Paused downloads can be resumed in Longwave.', flush=True)
    print('EXTENSION=' + str(version_dir / 'extension'), flush=True)
    return version_dir


def install(payload, root, output=None, media_archive=None, register_host=True):
    payload, root = Path(payload).resolve(), Path(root).resolve()
    if not (payload / 'package.json').is_file():
        raise ValueError('The release payload is missing. Extract the complete ZIP before running setup.')
    validate_payload(payload)
    package = json.loads((payload / 'package.json').read_text())
    dependencies = json.loads((payload / 'dependencies.json').read_text())
    media = dependencies['media']
    cache = root / 'cache' / (media['sha256'] + '.zip')
    if media_archive:
        from download import digest
        if digest(media_archive) != media['sha256']:
            raise ValueError('Media package checksum mismatch.')
        archive = Path(media_archive)
    else:
        print('Downloading verified audio tools from gyan.dev…', flush=True)
        archive = fetch(media['url'], media['sha256'], cache, lambda text: print(text, flush=True))
    versions = root / 'versions'
    versions.mkdir(parents=True, exist_ok=True)
    # Never overwrite a loaded version. Failed staging stays inspectable and inert.
    stage = versions / (package['version'] + '-' + uuid.uuid4().hex[:12])
    print('Preparing the private runtime…', flush=True)
    shutil.copytree(payload, stage, ignore=shutil.ignore_patterns('media', 'media-unpacked', '__pycache__'))
    # Keep maintenance UI after users discard the downloaded ZIP.
    source_bundle = payload.parent if payload.name == 'payload' else payload
    for name in ('Longwave-Setup.exe', 'START-HERE.html', 'LICENSES.txt', 'LICENSE', 'THIRD_PARTY_NOTICES.md'):
        if (source_bundle / name).is_file():
            shutil.copy2(source_bundle / name, stage / name)
    extract(archive, stage / 'media-unpacked')
    candidates = list((stage / 'media-unpacked').glob('*/bin/ffmpeg.exe'))
    if len(candidates) != 1:
        raise ValueError('Audio archive layout is not recognized.')
    # Keep upstream README/LICENSE with the installed executables.
    shutil.move(str(candidates[0].parent.parent), str(stage / 'media'))
    for name in ('ffmpeg', 'ffprobe'):
        result = run([stage / 'media/bin' / (name + '.exe'), '-version'])
        if f'{name} version {media["version"]}' not in result.stdout:
            raise ValueError('Audio tool version does not match the pinned release.')
    result = run([stage / 'runtime/python.exe', '-c',
                  'import ssl,sqlite3,yt_dlp; from longwave import VERSION; print(VERSION)'])
    if result.stdout.strip() != package['version']:
        raise ValueError('The staged companion failed its version check.')
    return activate(root, stage, output, register_host)


def disconnect(root, register_host=True):
    pause_worker(root / 'data')
    if register_host:
        import winreg
        for browser in BROWSERS:
            key_path = f'Software\\{browser}\\NativeMessagingHosts\\{HOST}'
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                    registered = Path(winreg.QueryValueEx(key, '')[0]).resolve()
                if registered == (root / 'data/native-host.json').resolve():
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
            except FileNotFoundError:
                pass
    print('Disconnected. Audio, history, and installed versions are preserved.', flush=True)


def main():
    if os.name != 'nt' or sys.maxsize <= 2 ** 32:
        raise SystemExit('This package supports 64-bit Windows 10/11.')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install', 'rollback', 'disconnect'))
    parser.add_argument('--payload', type=Path, default=Path(__file__).parent)
    parser.add_argument('--root', type=Path, default=Path(os.environ['LOCALAPPDATA']) / 'Longwave')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--media-archive', type=Path)
    parser.add_argument('--no-register', action='store_true', help='Isolated installation tests only')
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    from longwave.worker import WorkerLock
    # Separate lock from the worker: two installers may not stage/activate together.
    locks = root / 'setup-lock'
    locks.mkdir(exist_ok=True)
    with WorkerLock(locks) as acquired:
        if not acquired:
            raise RuntimeError('Another Longwave setup is running.')
        if args.action == 'install':
            install(args.payload, root, args.output, args.media_archive, not args.no_register)
        elif args.action == 'disconnect':
            disconnect(root, not args.no_register)
        else:
            receipt = json.loads((root / 'installation.json').read_text())
            previous = Path(receipt.get('previous') or '').resolve()
            if not previous.is_relative_to(root / 'versions') or not (previous / 'package.json').is_file():
                raise ValueError('No previous version is available to restore.')
            activate(root, previous, None, not args.no_register)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('Setup failed: ' + str(exc), file=sys.stderr, flush=True)
        sys.exit(1)
