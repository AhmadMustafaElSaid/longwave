"""Build a self-contained Windows x64 release with pinned upstream inputs."""

import json
import os
import shutil
import subprocess
import sys
import urllib.request
import uuid
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'release'))
from download import digest, extract, fetch


def zip_tree(folder, target):
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(folder.rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(folder))


def main():
    if os.name != 'nt':
        raise SystemExit('Build the Windows package on Windows.')
    version = json.loads((ROOT / 'package.json').read_text())['version']
    sys.path.insert(0, str(ROOT / 'companion'))
    from longwave import VERSION
    if VERSION != version:
        raise SystemExit('Extension and companion versions must match.')
    dependencies = json.loads((ROOT / 'release/dependencies.json').read_text())
    cache = ROOT / '.runtime/download-cache'
    work = ROOT / '.runtime/release-build' / uuid.uuid4().hex
    bundle = work / 'Longwave'
    payload = bundle / 'payload'
    payload.mkdir(parents=True)
    python = dependencies['python']
    archive = fetch(python['url'], python['sha256'], cache / 'python.zip')
    extract(archive, payload / 'runtime')
    pth = next((payload / 'runtime').glob('python*._pth'))
    runtime_zip = next((payload / 'runtime').glob('python*.zip')).name
    pth.write_text(f'{runtime_zip}\n.\n..\nLib/site-packages\n', encoding='ascii')
    extractor = dependencies['extractor']
    with urllib.request.urlopen(extractor['metadataUrl'], timeout=30) as response:
        metadata = json.load(response)
    wheels = [entry for entry in metadata['urls'] if entry['filename'].endswith('.whl')
              and entry['digests']['sha256'] == extractor['sha256']]
    if len(wheels) != 1:
        raise SystemExit('The pinned extractor wheel was not found.')
    wheel = fetch(wheels[0]['url'], extractor['sha256'], cache / 'extractor.whl')
    extract(wheel, payload / 'runtime/Lib/site-packages')
    shutil.copytree(ROOT / 'companion/longwave', payload / 'longwave',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copytree(ROOT / 'dist/chromium', payload / 'extension')
    for name in ('install.py', 'download.py', 'dependencies.json'):
        shutil.copy2(ROOT / 'release' / name, payload / name)
    identity = (ROOT / 'dist/extension-id.txt').read_text().strip()
    origins = [f'chrome-extension://{identity}/']
    store_ids_path = ROOT / 'release/store-ids.json'
    if store_ids_path.exists():
        import re
        for identity in json.loads(store_ids_path.read_text()).values():
            if identity is None:
                continue
            if not re.fullmatch('[a-p]{32}', identity):
                raise SystemExit('A store extension ID is invalid.')
            origins.append(f'chrome-extension://{identity}/')
    (payload / 'package.json').write_text(json.dumps({'version': version, 'origins': sorted(set(origins))}, indent=2))
    compiler = Path(os.environ['WINDIR']) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    subprocess.run([str(compiler), '/nologo', '/target:exe', '/main:Host', '/platform:x64',
                    '/out:' + str(payload / 'LongwaveHost.exe'), str(ROOT / 'release/Host.cs')], check=True)
    subprocess.run([str(compiler), '/nologo', '/target:winexe', '/main:Setup', '/platform:x64',
                    '/reference:System.Windows.Forms.dll', '/reference:System.Drawing.dll',
                    '/reference:System.Web.Extensions.dll',
                    '/out:' + str(bundle / 'Longwave-Setup.exe'), str(ROOT / 'release/Host.cs'),
                    str(ROOT / 'release/Setup.cs')], check=True)
    for source, destination in (('release/START-HERE.html', 'START-HERE.html'),
                                ('release/LICENSES.txt', 'LICENSES.txt'), ('LICENSE', 'LICENSE')):
        shutil.copy2(ROOT / source, bundle / destination)
    shutil.copy2(ROOT / 'THIRD_PARTY_NOTICES.md', bundle / 'THIRD_PARTY_NOTICES.md')
    checksums = {str(p.relative_to(payload)).replace('\\', '/'): digest(p)
                 for p in sorted(payload.rglob('*')) if p.is_file()}
    (payload / 'files.sha256.json').write_text(json.dumps(checksums, indent=2), encoding='utf-8')
    output = ROOT / 'artifacts/releases' / version
    output.mkdir(parents=True, exist_ok=True)
    zip_tree(bundle, output / f'longwave-{version}-windows-x64.zip')
    zip_tree(ROOT / 'dist/chromium', output / f'longwave-{version}-chromium.zip')
    # Store upload has no unpacked-development key. Store IDs are configured after reservation.
    store_extension = work / 'store-extension'
    shutil.copytree(ROOT / 'dist/chromium', store_extension)
    manifest = json.loads((store_extension / 'manifest.json').read_text())
    manifest.pop('key', None)
    (store_extension / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    zip_tree(store_extension, output / f'longwave-{version}-store-upload.zip')
    source = work / 'source'
    source.mkdir()
    for name in ('extension', 'companion', 'scripts', 'release', 'docs', '.github'):
        shutil.copytree(ROOT / name, source / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in ('package.json', 'package-lock.json', 'tsconfig.json', 'README.md', 'LICENSE', 'CHANGELOG.md',
                 'THIRD_PARTY_NOTICES.md', 'SECURITY.md', 'PRIVACY.md', 'CONTRIBUTING.md',
                 '.gitignore', '.editorconfig', '.prettierignore', '.prettierrc.json'):
        shutil.copy2(ROOT / name, source / name)
    zip_tree(source, output / f'longwave-{version}-source.zip')
    report = {'version': version, 'platform': 'windows-x64', 'channel': 'release-candidate',
              'signed': False, 'dependencies': dependencies,
              'assets': {p.name: {'sha256': digest(p), 'bytes': p.stat().st_size}
                         for p in sorted(output.glob('*.zip'))}}
    (output / 'release-manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    (output / 'SHA256SUMS.txt').write_text(''.join(f'{v["sha256"]}  {k}\n' for k,v in report['assets'].items()))
    print('BUNDLE=' + str(bundle))
    print('RELEASE=' + str(output))
    (ROOT / '.runtime/latest-release-bundle.txt').write_text(str(bundle))


if __name__ == '__main__':
    main()
