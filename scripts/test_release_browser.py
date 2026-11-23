"""Temporarily register an isolated release host, test browser(s), restore registry."""
import json
import os
import subprocess
import sys
import winreg
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'release'))
from install import register

target = Path((ROOT / '.runtime/latest-release-test-root.txt').read_text())
receipt = json.loads((target / 'installation.json').read_text())
config = json.loads((target / 'data/config.json').read_text())
keys = [f'Software\\{browser}\\NativeMessagingHosts\\app.longwave.companion'
        for browser in ('Google\\Chrome', 'Microsoft\\Edge')]
backups = {}
for path in keys:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            backups[path] = winreg.QueryValueEx(key, '')
    except FileNotFoundError:
        backups[path] = None

results = []
try:
    register(target / 'data/native-host.json')
    env = dict(os.environ, LONGWAVE_EXTENSION=str(Path(receipt['current']) / 'extension'),
               LONGWAVE_EXPECTED_OUTPUT=config['output_dir'])
    browsers = {'edge': 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
                'chrome': 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe'}
    for name, executable in browsers.items():
        if not Path(executable).is_file():
            results.append({'browser': name, 'result': 'not installed'})
            continue
        env['LONGWAVE_BROWSER'] = executable
        result = subprocess.run(['node', 'scripts/browser-smoke.mjs'], cwd=ROOT, env=env,
                                capture_output=True, text=True, timeout=120)
        print(name + ':\n' + result.stdout + result.stderr, flush=True)
        results.append({'browser': name, 'ok': result.returncode == 0, 'output': result.stdout + result.stderr})
finally:
    for path, old in backups.items():
        if old is None:
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
            except FileNotFoundError:
                pass
        else:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
                winreg.SetValueEx(key, '', 0, old[1], old[0])
    (ROOT / 'artifacts/release-browser-results.json').write_text(json.dumps(results, indent=2))

if any(result.get('ok') is False for result in results):
    sys.exit(1)
