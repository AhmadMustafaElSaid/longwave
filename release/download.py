"""Pinned HTTPS downloads and bounded, traversal-safe archive extraction."""

import hashlib
import os
import shutil
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

MAX_DOWNLOAD = 256 * 1024 * 1024
MAX_EXPANDED = 1024 * 1024 * 1024


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def fetch(url, expected, destination, progress=print):
    destination = Path(destination)
    if destination.exists() and digest(destination) == expected:
        return destination
    if not url.startswith('https://') or len(expected) != 64:
        raise ValueError('A pinned HTTPS source is required.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + '.partial')
    received, last = 0, -1
    try:
        with urllib.request.urlopen(url, timeout=30) as response, partial.open('wb') as output:
            if not response.url.startswith('https://'):
                raise ValueError('An insecure download redirect was rejected.')
            total = int(response.headers.get('Content-Length', '0'))
            if total > MAX_DOWNLOAD:
                raise ValueError('Download exceeds the package limit.')
            while chunk := response.read(256 * 1024):
                received += len(chunk)
                if received > MAX_DOWNLOAD:
                    raise ValueError('Download exceeds the package limit.')
                output.write(chunk)
                percent = received * 100 // total if total else received // (1024 * 1024)
                if percent // 10 != last:
                    progress('Downloading: ' + (f'{percent}%' if total else f'{percent} MB'))
                    last = percent // 10
        if digest(partial) != expected:
            raise ValueError('Package checksum mismatch. Installation stopped; retry from the official release.')
        os.replace(partial, destination)
        return destination
    finally:
        partial.unlink(missing_ok=True)


def extract(archive, destination):
    destination = Path(destination).resolve()
    with zipfile.ZipFile(archive) as zipped:
        entries = zipped.infolist()
        if sum(entry.file_size for entry in entries) > MAX_EXPANDED:
            raise ValueError('Expanded package exceeds the size limit.')
        for entry in entries:
            name = PurePosixPath(entry.filename.replace('\\', '/'))
            target = (destination / str(name)).resolve()
            if (name.is_absolute() or '..' in name.parts or ':' in str(name)
                    or not target.is_relative_to(destination)
                    or (entry.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError('Unsafe archive entry was rejected.')
        for entry in entries:
            target = destination / entry.filename
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with zipped.open(entry) as source, target.open('wb') as output:
                    shutil.copyfileobj(source, output, 256 * 1024)
