"""Exercise the actual ZIP on this Windows host with no Python/Node on PATH.

Does not claim to be a separate OS/VM. Registry registration is tested separately.
"""
import json
import os
import shutil
import struct
import subprocess
import sys
import threading
import uuid
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    version = json.loads((ROOT / 'package.json').read_text())['version']
    archive = ROOT / 'artifacts/releases' / version / f'longwave-{version}-windows-x64.zip'
    folder = ROOT / '.runtime/release-tests' / ('مستخدم مستقل ' + uuid.uuid4().hex[:8])
    unpacked = folder / 'download'
    with zipfile.ZipFile(archive) as package:
        package.extractall(unpacked)
    env = dict(os.environ)
    for name in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV', 'LONGWAVE_HOME'):
        env.pop(name, None)
    env['PATH'] = str(Path(os.environ['WINDIR']) / 'System32')
    env['PYTHONIOENCODING'] = 'utf-8'
    runtime = unpacked / 'payload/runtime/python.exe'
    installer = unpacked / 'payload/install.py'
    target = folder / 'installed'
    output = folder / 'My Audio'

    def execute(args, **kwargs):
        result = subprocess.run([str(a) for a in args], env=env, capture_output=True,
                                timeout=180, creationflags=subprocess.CREATE_NO_WINDOW, **kwargs)
        if result.returncode:
            raise RuntimeError(result.stderr.decode('utf-8', errors='replace') + result.stdout.decode('utf-8', errors='replace'))
        return result

    setup = [runtime, installer, 'install', '--root', target, '--output', output,
             '--media-archive', ROOT / '.runtime/download-cache/media.zip', '--no-register']
    print('Testing first installation…', flush=True)
    execute(setup)
    receipt = json.loads((target / 'installation.json').read_text())
    first = Path(receipt['current'])
    assert (first / 'Longwave-Setup.exe').is_file() and (first / 'START-HERE.html').is_file()
    # Modify local history sentinel; upgrades/rollback/disconnect must preserve it.
    sentinel = target / 'data/preserved.txt'
    sentinel.write_text('Keep my data')
    audio = output / 'preserved.txt'
    audio.write_text('Keep my audio')
    print('Testing side-by-side update…', flush=True)
    execute(setup)
    upgraded = json.loads((target / 'installation.json').read_text())
    assert upgraded['previous'] == str(first)
    assert upgraded['current'] != str(first)
    print('Testing rollback and native messaging…', flush=True)
    execute([runtime, installer, 'rollback', '--root', target, '--no-register'])
    restored = json.loads((target / 'installation.json').read_text())
    assert restored['current'] == str(first)
    config = json.loads((target / 'data/config.json').read_text())
    message = json.dumps({'version': 1, 'command': 'snapshot'}).encode()
    result = execute([first / 'LongwaveHost.exe', config['allowed_origins'][0]],
                     input=struct.pack('=I', len(message)) + message)
    length = struct.unpack('=I', result.stdout[:4])[0]
    reply = json.loads(result.stdout[4:4+length])
    assert reply['ok'] and all(reply['data']['tools'].values()), reply
    assert reply['data']['outputDir'] == str(output.resolve())
    assert reply['data']['version'] == version
    # Chrome keeps stdin open while waiting for a reply. Closing it before reading
    # would hide buffering bugs in an executable bridge.
    interactive = subprocess.Popen([str(first / 'LongwaveHost.exe'), config['allowed_origins'][0]],
                                   env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
    replies = []
    def receive():
        header = interactive.stdout.read(4)
        if len(header) == 4:
            replies.append(json.loads(interactive.stdout.read(struct.unpack('=I', header)[0])))
    try:
        interactive.stdin.write(struct.pack('=I', len(message)) + message)
        interactive.stdin.flush()
        reader = threading.Thread(target=receive, daemon=True)
        reader.start()
        reader.join(timeout=10)
        assert replies and replies[0]['ok'], 'Native host did not respond while stdin remained open.'
    finally:
        interactive.stdin.close()
        try:
            interactive.wait(timeout=5)
        except subprocess.TimeoutExpired:
            interactive.kill()
            interactive.wait()
        interactive.stdout.close()
        interactive.stderr.close()
    assert execute([first / 'LongwaveHost.exe', 'chrome-extension://' + 'a'*32 + '/'], input=b'').stdout == b''
    # Real generated-media pipeline tests run with the bundled interpreter and new tools.
    env['LONGWAVE_TEST_FFMPEG'] = config['ffmpeg']
    env['LONGWAVE_TEST_FFPROBE'] = config['ffprobe']
    print('Testing audio pipeline with the bundled runtime…', flush=True)
    validation = folder / 'validation'
    shutil.copytree(ROOT / 'companion/tests', validation / 'companion/tests', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(first / 'longwave', validation / 'companion/longwave', ignore=shutil.ignore_patterns('__pycache__'))
    (validation / 'release').mkdir()
    for filename in ('install.py', 'download.py'):
        shutil.copy2(first / filename, validation / 'release' / filename)
    tests = execute([first / 'runtime/python.exe', '-m', 'unittest', 'discover',
                     '-s', validation / 'companion/tests', '-v'])
    print(tests.stderr.decode('utf-8', errors='replace'))
    if b'skipped=' in tests.stderr:
        raise RuntimeError('Release tests may not skip integration checks.')
    execute([runtime, installer, 'disconnect', '--root', target, '--no-register'])
    assert sentinel.read_text() == 'Keep my data' and audio.read_text() == 'Keep my audio'
    evidence = {'ok': True, 'version': version, 'systemPythonOnPath': False,
                'systemNodeOnPath': False, 'separateCleanOS': False,
                'checks': ['actual release ZIP', 'Unicode installation path', 'install', 'upgrade',
                           'rollback', 'native executable framing with stdin open', 'origin rejection',
                           'bundled interpreter and media pipeline', 'disconnect preserves data'],
                'root': str(target), 'nativeVersion': reply['data']['version']}
    (ROOT / 'artifacts/release-test-result.json').write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence, indent=2))
    (ROOT / '.runtime/latest-release-test-root.txt').write_text(str(target), encoding='utf-8')


if __name__ == '__main__':
    main()
