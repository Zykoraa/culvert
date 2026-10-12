#!/usr/bin/env python3
"""Download only pinned upstream Linux x86_64 engines and verify archive hashes."""
import hashlib, io, json, os, platform, tarfile, urllib.request, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if platform.machine() != 'x86_64': raise SystemExit('This Linux package targets x86_64.')
folder = ROOT / 'cores/linux'; folder.mkdir(parents=True, exist_ok=True)
pins = json.loads((ROOT / 'linux/engines.lock.json').read_text())
for name, pin in pins.items():
    data = urllib.request.urlopen(pin['archive'], timeout=90).read()
    if hashlib.sha256(data).hexdigest() != pin['sha256']: raise SystemExit('Upstream archive digest mismatch: ' + name)
    if name == 'xray':
        with zipfile.ZipFile(io.BytesIO(data)) as archive: binary = archive.read('xray')
    else:
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            member = next(m for m in archive.getmembers() if m.isfile() and m.name.endswith('/sing-box'))
            binary = archive.extractfile(member).read()
    path = folder / name; path.write_bytes(binary); path.chmod(0o755)
    print('Verified ' + name + ' ' + pin['version'])
