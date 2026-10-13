#!/usr/bin/env bash
# Bootstrap a NEW Oracle Linux 9 VM. Existing Xray installations are never replaced.
# sudo bash bootstrap.sh <public-ip> [owner-ssh-user]
# Run from a directory containing the other server/ scripts.
set -euo pipefail
PUBLIC_IP="${1:?Supply the new VM public IPv4 address}"
OWNER="${2:-opc}"
ROOT="$(cd -- "$(dirname -- "$0")" && pwd)"
[ "$(id -u)" = 0 ] || { echo 'Run with sudo' >&2; exit 1; }
[[ "$OWNER" =~ ^[a-zA-Z_][a-zA-Z0-9_-]{0,31}$ ]] || exit 1
getent passwd "$OWNER" >/dev/null
[ ! -e /usr/local/etc/xray/config.json ] || { echo 'An Xray config already exists; refusing to replace it.' >&2; exit 1; }
case "$(uname -m)" in
  aarch64) ARCH=arm64-v8a; SHA256=f5698bb218ada3b4022db26fafc39601c5f53b46b19eb76c9616325985807501 ;;
  x86_64) ARCH=64; SHA256=8195d909f1109b8f3d99eefe401a3c451d7bf4af71f24d3815420f77e5dd2a40 ;;
  *) echo 'Unsupported architecture' >&2; exit 1 ;;
esac
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
curl --fail --location --max-time 120 "https://github.com/XTLS/Xray-core/releases/download/v26.7.28/Xray-linux-$ARCH.zip" -o "$STAGE/xray.zip"
echo "$SHA256  $STAGE/xray.zip" | sha256sum --check --status
unzip -q "$STAGE/xray.zip" -d "$STAGE/core"
getent group xray >/dev/null || groupadd --system xray
id xray >/dev/null 2>&1 || useradd --system --gid xray --home-dir /var/lib/culvert --shell /sbin/nologin xray
install -m 755 "$STAGE/core/xray" /usr/local/bin/xray
install -d -m 750 -o root -g xray /usr/local/etc/xray
install -m 644 "$ROOT/cover-profiles.json" /usr/local/etc/xray/cover-profiles.json
for script in add-user.sh del-user.sh set-cover.sh get-cover.sh confirm-cover.sh vet-cover.sh enable-hostname-routing.sh; do
  install -m 755 "$ROOT/$script" "/usr/local/bin/$script"
done
install -m 755 "$ROOT/culvert-devices.py" /usr/local/bin/culvert-devices
python3 - "$PUBLIC_IP" "$OWNER" <<'PY'
import base64, ipaddress, json, os, pathlib, pwd, re, secrets, subprocess, sys, uuid
address = str(ipaddress.IPv4Address(sys.argv[1]))
owner = pwd.getpwnam(sys.argv[2])
keys = subprocess.check_output(['/usr/local/bin/xray', 'x25519'], text=True)
def value(pattern):
    match = re.search(pattern, keys, re.M | re.I)
    if not match: raise RuntimeError('Unexpected Xray key format')
    return match.group(1)
private = value(r'^Private(?:Key| key):\s*(\S+)')
public = value(r'^(?:Password(?: \(PublicKey\))?|PublicKey|Public key):\s*(\S+)')
identity, short = str(uuid.uuid4()), secrets.token_hex(8)
config = {'log': {'loglevel': 'warning'}, 'inbounds': [{'listen': '0.0.0.0', 'port': 443, 'protocol': 'vless',
    'sniffing': {'enabled': True, 'destOverride': ['http', 'tls', 'quic']},
    'settings': {'clients': [{'id': identity, 'flow': 'xtls-rprx-vision', 'email': 'culvert-owner'}], 'decryption': 'none'},
    'streamSettings': {'network': 'tcp', 'security': 'reality', 'realitySettings': {'show': False, 'dest': 'www.apple.com:443',
        'xver': 0, 'serverNames': ['www.apple.com'], 'privateKey': private, 'shortIds': [short]}}}],
    'outbounds': [{'protocol': 'freedom', 'tag': 'direct'}, {'protocol': 'blackhole', 'tag': 'blocked'}],
    'routing': {'domainStrategy': 'AsIs', 'rules': [{'type': 'field', 'ip': ['geoip:private'], 'outboundTag': 'blocked'}]}}
# Explicit CIDRs keep the server independent of geodata downloads.
config['routing']['rules'][0]['ip'] = ['0.0.0.0/8', '10.0.0.0/8', '100.64.0.0/10', '127.0.0.0/8', '169.254.0.0/16', '172.16.0.0/12', '192.168.0.0/16', '224.0.0.0/4', '::1/128', 'fc00::/7', 'fe80::/10']
path = pathlib.Path('/usr/local/etc/xray/config.json')
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
with os.fdopen(fd, 'w') as stream: json.dump(config, stream, indent=2)
import grp
os.chown(path, 0, grp.getgrnam('xray').gr_gid)
profile = {'user': 'Culvert owner', 'server': address, 'port': 443, 'uuid': identity, 'sni': 'www.apple.com', 'publicKey': public, 'shortId': short, 'expectedExitIp': address}
folder = pathlib.Path(owner.pw_dir) / '.config' / 'culvert'
folder.mkdir(parents=True, exist_ok=True, mode=0o700)
os.chown(folder, owner.pw_uid, owner.pw_gid)
profile_path = folder / 'profile.json'
fd = os.open(profile_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as stream: json.dump(profile, stream, indent=2)
os.chown(profile_path, owner.pw_uid, owner.pw_gid)
PY
restorecon -RF /usr/local/bin/xray /usr/local/etc/xray || true
/usr/local/bin/xray run -test -c /usr/local/etc/xray/config.json >/dev/null
cat > /etc/systemd/system/xray.service <<'UNIT'
[Unit]
Description=Culvert VLESS REALITY server
After=network-online.target
Wants=network-online.target
[Service]
User=xray
Group=xray
ExecStart=/usr/local/bin/xray run -c /usr/local/etc/xray/config.json
Restart=on-failure
RestartSec=3
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
NoNewPrivileges=true
ProtectHome=true
ProtectSystem=strict
PrivateTmp=true
LimitNOFILE=1048576
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now xray
if systemctl is-active --quiet firewalld; then
  firewall-cmd --permanent --add-port=443/tcp
  firewall-cmd --add-port=443/tcp
fi
bash "$ROOT/install-watchdog.sh"
OWNER_HOME="$(getent passwd "$OWNER" | cut -d: -f6)"
install -o "$OWNER" -g "$(id -gn "$OWNER")" -m 755 "$ROOT/usage.sh" "$OWNER_HOME/usage.sh"
echo 'Culvert server installed. The private owner profile is in ~/.config/culvert/profile.json.'
echo 'The cloud network must also allow inbound TCP 443.'
