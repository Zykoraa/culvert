#!/usr/bin/env bash
# Install only Culvert's fixed helper/service and pinned engine files. Never run the GUI as root.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo 'Run with sudo, or choose Finish system setup inside Culvert.' >&2; exit 1; }
SOURCE="$(cd -- "$(dirname -- "$0")/.." && pwd)"
for tool in python3 systemctl nft curl ip pkexec; do command -v "$tool" >/dev/null || { echo "Missing system dependency: $tool" >&2; exit 1; }; done
for path in /opt/culvert /opt/culvert/linux /opt/culvert/cores /opt/culvert/cores/linux /var/lib/culvert /run/culvert; do
  [ ! -L "$path" ] || { echo 'Refusing a linked system install path.' >&2; exit 1; }
done
python3 - "$SOURCE" <<'PY'
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]);pins=json.loads((root/'linux/engines.lock.json').read_text())
for name,pin in pins.items():
    path=root/'cores/linux'/name
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=pin['binary_sha256']:
        raise SystemExit('Missing or modified Linux engine. Run linux/fetch-engines.py first.')
PY
install -d -m 755 /opt/culvert/linux /opt/culvert/configs /opt/culvert/assets /opt/culvert/cores/linux
for file in common.py host.py helper.py app.py engines.lock.json release-public-key.pem; do install -m 644 "$SOURCE/linux/$file" "/opt/culvert/linux/$file"; done
for file in xray sing-box; do install -m 755 "$SOURCE/cores/linux/$file" "/opt/culvert/cores/linux/$file"; done
install -m 644 "$SOURCE/configs/singbox-tun.json" /opt/culvert/configs/singbox-tun.json
for file in Culvert.ico Culvert.png Culvert-mark.png; do install -m 644 "$SOURCE/assets/$file" "/opt/culvert/assets/$file"; done
install -m 644 "$SOURCE/linux/culvert@.service" /etc/systemd/system/culvert@.service
install -d -m 700 /var/lib/culvert
install -d -m 755 /run/culvert
systemctl daemon-reload
printf 'Culvert system helper installed. Run the interface as your ordinary desktop user.\n'
