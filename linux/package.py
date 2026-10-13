#!/usr/bin/env python3
"""Create a credential-free Linux distribution from an explicit source allowlist."""
import hashlib,json,subprocess,sys,tarfile
from pathlib import Path
root=Path(__file__).resolve().parent.parent
subprocess.run([sys.executable,str(root/'linux/fetch-engines.py')],check=True)
version='2.4.3';folder=root/'dist';folder.mkdir(exist_ok=True)
output=folder/f'Culvert-linux-x86_64-{version}.tar.gz'
files=[p for p in (root/'linux').iterdir() if p.suffix in ('.py','.sh','.json','.pem','.service','.md','.txt')]
files += [root/'configs/singbox-tun.json',*[root/'assets'/name for name in ('Culvert.ico','Culvert.png','Culvert-mark.png','Culvert.svg','Culvert-mark.svg')],root/'cores/linux/xray',root/'cores/linux/sing-box']
files += [root/'licenses'/name for name in ('Xray.txt','sing-box.txt','Linux-engines.md')]
required=[root/'linux'/name for name in ('release-public-key.pem','README.md','app.py','host.py','helper.py','install.sh','install-system.sh','verify-update.py')]
if any(path not in files or not path.is_file() for path in required):raise SystemExit('Missing required Linux distribution or public trust file.')
with tarfile.open(output,'w:gz',compresslevel=6) as archive:
    for path in sorted(files):
        if path.suffix in ('.key','.dpapi') or path.name=='profile.json':raise SystemExit('Private file rejected')
        archive.add(path,arcname='Culvert-linux/'+str(path.relative_to(root)),recursive=False)
print(output)
