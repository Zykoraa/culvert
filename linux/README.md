# Culvert on Linux

Native Qt 6 desktop client for x86_64 Linux, including Wayland and Hyprland.
It uses Culvert's independent VM identity, Xray/REALITY transport and sing-box
full-device routing. Conduit is separate; run one full-device tunnel at a time.

## Install

Download the Linux archive and its `.sig` from
[Culvert releases](https://github.com/Zykoraa/culvert/releases). Verify with a
previously trusted copy of `linux/verify-update.py` and its release public key:

```sh
python3 linux/verify-update.py Culvert-linux-x86_64-2.4.3.tar.gz Culvert-linux-x86_64-2.4.3.tar.gz.sig
tar -xzf Culvert-linux-x86_64-2.4.3.tar.gz
cd Culvert-linux
bash linux/install.sh
```

Dependencies: Python 3.11+, PySide6 / Qt 6 Wayland, systemd, polkit and a running
authentication agent, nftables, iproute2, curl, OpenSSH and OpenSSL. A Secret
Service keyring and StatusNotifier tray are optional. Arch / Hyprland packages:

```sh
sudo pacman -S python-pyside6 qt6-wayland polkit nftables iproute2 curl openssh openssl
```

Start your preferred polkit authentication agent in the Hyprland session.
Open **Culvert** from your app launcher or run `~/.local/bin/culvert`.
Choose **Settings → Finish system setup** once. This installs root-owned
engines and a systemd helper in `/opt/culvert`; the dashboard runs unelevated.
Each Connect / Disconnect operation uses the normal system authorization prompt.

Import your personal Culvert `vless://` device link. For owner administration,
choose your VM's private SSH key under Settings. Keys and device links never
belong in the repository. Changing or revoking devices can reconnect VM users.

## Wayland and Hyprland

When `WAYLAND_DISPLAY` is set, Culvert selects Qt's native Wayland platform.
It does not need XWayland. An explicit `QT_QPA_PLATFORM` override is respected.
The app ID is `culvert`; it appears in your normal launcher and a compatible
StatusNotifier tray such as Waybar's tray. Without a tray, closing the dashboard
quits its interface; the system tunnel keeps running. Reopen Culvert to control
it. Small tiled windows can scroll their content. Floating the window gives
the dashboard more room. No Hyprland configuration is changed by installation.

The original mascot's orbit animates only while the dashboard is visible and
active. Turn it off in Settings. Its motion never indicates tunnel health.

## Connection evidence and recovery

The dashboard samples exit address, proxied HTTPS/DNS, SOCKS UDP/STUN and
IPv4/IPv6 routes. Verification applies to those samples, not every app or route.
Live connections and traffic history stay local. Diagnostics omit credentials
and destination history. Automatic recovery restarts failed engines.

Network lock is **off by default**. Enabling it blocks ordinary host outbound
traffic when the tunnel fails; loopback, Culvert's TUN, the VM's TCP endpoint,
DHCP and IPv6 neighbor discovery remain allowed. It affects the whole PC.
**Restore normal internet** stops the host and removes only Culvert's nftables
table. Emergency terminal recovery (replace 1000 with your desktop UID):

```sh
pkexec /usr/bin/python3 /opt/culvert/linux/helper.py disconnect
# Administrator fallback if the helper is damaged:
sudo systemctl stop culvert@1000.service
sudo nft delete table inet culvert
```

The helper accepts bounded connection fields, never arbitrary engine JSON or
shell commands. Root-owned per-user runtime profiles are mode 600; readable
status is limited to that user's primary group. The interface uses Secret
Service for its saved profile when available; otherwise it explicitly reports
owner-only **unencrypted** mode-600 local storage in `~/.config/culvert`.

## Platform scope

Windows keeps Conduit's original features, including its wider v2rayN imports,
WFP network lock, protected profiles and automatic signed update workflow.
This first Linux version supports personal IPv4 VLESS/REALITY/Vision/TCP links,
full-device IPv4/IPv6 routing, optional nftables lock, diagnostics, owner device
management, cover switching, shared VM usage and login startup. Linux updates
use manually downloaded, signature-verified archives; it does not yet import
VMess/Trojan/Shadowsocks or provide Windows installer/repair behavior.

The bundled Xray and sing-box engines are unmodified, pinned by archive and
binary SHA-256 in `engines.lock.json`. Their licenses and source links ship in
`licenses`. Qt / PySide6 come from your system package manager.

## Build

```sh
python3 linux/fetch-engines.py
python3 -m unittest discover -s tests -p 'test_*.py'
python3 linux/package.py
```

Brand vectors are `assets/Culvert.svg` and `assets/Culvert-mark.svg`. Regenerate
PNG/ICO exports with `python3 linux/render-brand.py` (requires PySide6 and Pillow).
