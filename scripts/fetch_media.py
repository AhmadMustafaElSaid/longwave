"""Fetch the same pinned media build used by the public installer for development."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'release'))
from download import extract, fetch

if __name__ == '__main__':
    media = json.loads((ROOT / 'release/dependencies.json').read_text())['media']
    archive = fetch(media['url'], media['sha256'], ROOT / '.runtime/download-cache/media.zip')
    target = ROOT / '.tools' / ('ffmpeg-' + media['version'])
    extract(archive, target)
    matches = list(target.glob('*/bin/ffmpeg.exe'))
    if len(matches) != 1:
        raise SystemExit('Unexpected media archive layout.')
    settings = {name: str(matches[0].with_name(name + '.exe')) for name in ('ffmpeg', 'ffprobe')}
    (ROOT / '.tools/media-paths.json').write_text(json.dumps(settings, indent=2))
    print('Development media tools ready: ' + str(matches[0].parent))
