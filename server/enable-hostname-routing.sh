#!/usr/bin/env bash
# Upgrade an existing Culvert server to Conduit's hostname-routing behavior.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo 'Run with sudo.' >&2; exit 1; }
CFG=/usr/local/etc/xray/config.json
XRAY=/usr/local/bin/xray
command -v jq >/dev/null || { echo 'jq is required.' >&2; exit 1; }
[ -x "$XRAY" ] || { echo 'Xray executable is missing.' >&2; exit 1; }
[ -f "$CFG" ] || { echo 'Xray config is missing.' >&2; exit 1; }
[ "$(jq '[.inbounds[] | select(.protocol == "vless" and .port == 443)] | length' "$CFG")" = 1 ] || {
  echo 'Expected one VLESS inbound on port 443; inspect the config manually.' >&2; exit 1;
}
if jq -e '.inbounds[] | select(.protocol == "vless" and .port == 443) | .sniffing == {enabled: true, destOverride: ["http", "tls", "quic"]}' "$CFG" >/dev/null; then
  echo 'Hostname routing already matches Conduit; no restart needed.'
  exit 0
fi
TMP="$(mktemp --suffix=.json)"
trap 'rm -f "$TMP"' EXIT
chmod 600 "$TMP"
jq '(.inbounds[] | select(.protocol == "vless" and .port == 443) | .sniffing) = {enabled: true, destOverride: ["http", "tls", "quic"]}' "$CFG" > "$TMP"
"$XRAY" run -test -c "$TMP" >/dev/null
install -d -m 700 /var/backups/culvert
BACKUP="$(mktemp /var/backups/culvert/xray-before-hostname-routing.XXXXXXXX.json)"
cp --preserve=mode,ownership "$CFG" "$BACKUP"
install -o root -g xray -m 640 "$TMP" "$CFG.next"
mv -f "$CFG.next" "$CFG"
restorecon "$CFG" >/dev/null 2>&1 || true
# An SSH session through this tunnel drops during restart; finish verification.
trap '' HUP
if ! systemctl restart xray || ! systemctl is-active --quiet xray; then
  cp --preserve=mode,ownership "$BACKUP" "$CFG"
  restorecon "$CFG" >/dev/null 2>&1 || true
  systemctl restart xray
  echo 'Xray restart failed; restored the previous config.' >&2
  exit 1
fi
echo 'Hostname routing enabled. Credentials and existing routing rules were preserved.'
