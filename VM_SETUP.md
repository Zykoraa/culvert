# Culvert 2.4.4 — Oracle VM and Xray setup guide

This guide covers the Culvert Oracle Linux VM, the Windows Owner app, and the
VLESS/REALITY tunnel between them. Start with the existing-VM section if Xray is
already installed. The fresh-VM bootstrap deliberately refuses to replace an
existing Xray configuration.

## 1. Identify the correct VM

The deployment inspected on **October 13, 2026** was:

| Item | Culvert deployment |
| --- | --- |
| Oracle instance | Culvert |
| Region | US Midwest (Chicago), `us-chicago-1` |
| Shape | `VM.Standard.A1.Flex`, ARM64, 2 OCPUs, 12 GB RAM |
| Operating system | Oracle Linux 9 |
| Public IPv4 | `147.224.134.253` |
| Private IPv4 | `10.0.0.176` |
| SSH user and port | `opc`, TCP `22` |
| Tunnel entry point | TCP `443` on the Culvert public IPv4 |
| REALITY cover/SNI | `www.apple.com`, destination `www.apple.com:443` |
| Native IPv6 | No global IPv6 address/default route at inspection |
| Root filesystem | 30 GB; about 19 GB free at inspection |

These are deployment details, not installer defaults. Recheck the Oracle
instance's Networking tab if an address is reassigned or the VM is replaced.
The separate **Conduit** instance has public IPv4 `147.224.209.249` and private
IPv4 `10.0.0.30`. Do Culvert administration against the Culvert address above.

The inspected VCN is `vcn-20260917-0022` and subnet is `subnet-20260917-0022`
(`10.0.0.0/24`). These resources are shared with Conduit. Inspect associations
before changing shared routes or security lists; use a Culvert-specific network
security group if a new rule should apply only to Culvert.

## 2. Understand the connection

```text
Windows applications, including Discord TCP and UDP
    -> Culvert sing-box TUN adapter
    -> local Xray SOCKS listener at 127.0.0.1:11808
    -> VLESS + REALITY + Vision over TCP 443
    -> Xray on the Culvert Oracle VM
    -> the destination website, message gateway or voice server
```

SSH is a separate administration connection. Its private key signs your SSH
login; it is not the VLESS UUID or a REALITY key. Installing a client does not
create its server identity. Each device imports its own complete connection
link or previous profile. Run one full-device tunnel at a time.

## 3. Configure Oracle networking

In Oracle Cloud, open **Compute → Instances → Culvert → Networking** and verify
the instance name and public IPv4 before following the VNIC/subnet links.

1. The primary VNIC must have the intended private IPv4 and a public IPv4.
2. Its subnet must support public access. The effective route table needs an
   IPv4 `0.0.0.0/0` route to an enabled internet gateway in the VCN.
3. A subnet security list or attached network security group must allow the
   traffic below. Retain existing rules needed by the Oracle image.
4. Check the guest's firewalld rules as well. A cloud rule alone does not open
   a guest firewall port, and a guest rule alone does not open the cloud network.

| Direction | Source/destination | Protocol/port | Purpose |
| --- | --- | --- | --- |
| Stateful ingress | Your authorized administrator public IPv4/CIDR | TCP destination 22; source port any | SSH administration |
| Stateful ingress | Intended client public CIDRs, or `0.0.0.0/0` for roaming clients | TCP destination 443; source port any | VLESS/REALITY clients |
| Stateful egress | `0.0.0.0/0` | All protocols | Websites, DNS, destination voice UDP and package downloads |

Stateful rules permit response traffic for an allowed connection. SSH source
restrictions must match the public address from which your SSH connection
actually exits; a tunnel may change that address.

The client-to-VM transport is TCP 443. Discord voice UDP is carried inside that
tunnel and sent outward by the VM. This deployment does not require public
inbound UDP 443 or inbound Discord voice ports on the VM. A destination such
as `discord.media:2087` is an outbound connection from the server.

No public Xray management API, SOCKS listener, or recorder dashboard port is
required. If the separate Vigil receiver is installed, its `127.0.0.1:9100`
listener is a separate service and is not part of the Culvert tunnel setup.

## 4. Prepare SSH on Windows

Use the private key supplied for the Culvert VM. Its `.pub` file is the public
key and cannot authenticate your login by itself. The examples use a convenient
local filename; substitute the real path to your own key.

```powershell
$serverIpv4 = '147.224.134.253'
$keyPath = 'C:\Culvert keys\culvert.key'
ssh -i "$keyPath" -o IdentitiesOnly=yes "opc@$serverIpv4"
```

On a first connection, verify the host-key fingerprint against a trusted Oracle
console session before accepting it. The server can display its SSH public-key
fingerprint with `sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`.

If OpenSSH reports that the private-key permissions are too open, restrict that
specific file to your Windows account. These commands do not change a folder:

```powershell
$account = [Security.Principal.WindowsIdentity]::GetCurrent().Name
icacls "$keyPath" /inheritance:r
icacls "$keyPath" /grant:r "${account}:(R)"
icacls "$keyPath" /remove:g '*S-1-1-0' '*S-1-5-11' '*S-1-5-32-545'
```

Retry SSH. If TCP 22 is blocked by the current local network, use an authorized
network that permits SSH or an already working Culvert connection. Restarting
Xray interrupts an SSH session that is itself travelling through Culvert.

## 5. Download the server tools

The public Culvert repository and release downloads do not require a GitHub
personal access token. On the VM, install the basic tools first:

```bash
sudo dnf install -y curl unzip jq python3 openssl
```

Then download the release:

```bash
mkdir -p ~/culvert-release-2.4.4
cd ~/culvert-release-2.4.4
curl -fL https://github.com/Zykoraa/culvert/releases/download/v2.4.4/Culvert-Server-2.4.4.zip -o Culvert-Server-2.4.4.zip
curl -fL https://github.com/Zykoraa/culvert/releases/download/v2.4.4/Culvert-Server-2.4.4.zip.sig -o Culvert-Server-2.4.4.zip.sig
curl -fL https://github.com/Zykoraa/culvert/releases/download/v2.4.4/SHA256SUMS.txt -o SHA256SUMS.txt
sha256sum --check --ignore-missing SHA256SUMS.txt
```

Extract the verified server package:

```bash
unzip -q Culvert-Server-2.4.4.zip -d tools
cd tools
```

The checksum check must report the server ZIP as OK. The release also publishes
`Culvert-Server-2.4.4.zip.sig`, signed by Culvert's release key. If you already
have a trusted Culvert checkout, its `linux/verify-update.py` and colocated
`linux/release-public-key.pem` can verify that file:

```bash
python3 /path/to/trusted/culvert/linux/verify-update.py Culvert-Server-2.4.4.zip Culvert-Server-2.4.4.zip.sig
```

Run that command from the directory containing the downloaded ZIP/signature.
The verifier's success message says "Linux release" because it is shared with
the Linux package; the signature check also accepts the server ZIP.

## 6A. Existing Culvert VM: apply the server fix

The current Culvert VM is already bootstrapped. Preserve its enrolled users and
REALITY keys. From the extracted tools directory:

```bash
sudo bash server/enable-hostname-routing.sh
sudo /usr/local/bin/xray run -test -c /usr/local/etc/xray/config.json
systemctl is-active xray
```

The upgrade script selects exactly one VLESS inbound on TCP 443, adds Conduit's
hostname-routing setting, validates the candidate, saves a protected backup
under `/var/backups/culvert`, and restarts Xray. It restores the previous config
if restart fails. An already matching config is left running without a restart.
Enrolled users, REALITY keys and existing routing rules are preserved.

This fix was applied to the current VM and verified with Discord messages and
voice on October 13, 2026. Reconnect the client after an actual server restart.

## 6B. Fresh VM only: bootstrap Xray

For a replacement/new Oracle Linux 9 VM, first complete Oracle networking and
SSH above. Check the architecture with `uname -m`; the bootstrap supports
`aarch64` and `x86_64` and downloads the corresponding pinned Xray archive.

From the extracted tools directory, substitute that new VM's public IPv4:

```bash
sudo bash server/bootstrap.sh YOUR_NEW_VM_PUBLIC_IPV4 opc
```

The script installs the pinned, hash-checked Xray executable, creates the `xray`
service account, generates a new UUID and REALITY key pair/short ID, writes a
protected server config and owner profile, opens guest TCP 443 when firewalld is
active, and enables Xray plus the watchdog. It does not configure Oracle's VCN,
route table or cloud firewall rules. It refuses an existing Xray config.

The private owner profile is `/home/opc/.config/culvert/profile.json`. A new VM
generates a new identity; use that VM's profile and links for its clients.

## 7. Xray settings reference

The release pins **Xray 26.7.28** and **sing-box 1.13.19**. Windows engine hashes
are in `engines.lock.json`; the server bootstrap pins both ARM64/x86_64 archive
hashes. The current VM uses the ARM64 Xray build. Engine upgrades require the
repository's evaluation and release checks, rather than replacing one binary
independently while debugging a connection.

### Server configuration

| Field | Culvert value/meaning |
| --- | --- |
| Config | `/usr/local/etc/xray/config.json` |
| Executable | `/usr/local/bin/xray` |
| Service | `xray.service`, user/group `xray` |
| Listener | `0.0.0.0`, port `443` |
| Protocol | `vless` |
| Client authentication | Separate UUID in `settings.clients` for each enrolled device |
| Client flow | `xtls-rprx-vision` |
| VLESS decryption field | `none`; transport security is provided by REALITY |
| Transport | `tcp` in this pinned configuration |
| Security | `reality` |
| REALITY destination | `www.apple.com:443` |
| REALITY server names | `www.apple.com` |
| REALITY private key | Generated for this VM; remains server-side |
| REALITY short IDs | Generated server values; client must use an accepted value |
| Hostname routing | `sniffing.enabled: true`, `destOverride: [http, tls, quic]` |
| `routeOnly` | Omitted, so the default `false` permits destination override |
| Internet outbound | `freedom`, tag `direct` |
| Blocked outbound | `blackhole`, tag `blocked` |
| Routing strategy | `AsIs`; preserved from Culvert's bootstrap |
| Destination restrictions | Explicit private/local/multicast CIDRs routed to `blocked` |
| Logging | Warning level; inspect service journal for failures |

The following is an illustration, **not a ready-to-run credential file**:

```json
{
  "log": { "loglevel": "warning" },
  "inbounds": [{
    "listen": "0.0.0.0",
    "port": 443,
    "protocol": "vless",
    "sniffing": { "enabled": true, "destOverride": ["http", "tls", "quic"] },
    "settings": {
      "clients": [{ "id": "__DEVICE_UUID__", "flow": "xtls-rprx-vision", "email": "culvert-owner" }],
      "decryption": "none"
    },
    "streamSettings": {
      "network": "tcp",
      "security": "reality",
      "realitySettings": {
        "show": false,
        "dest": "www.apple.com:443",
        "xver": 0,
        "serverNames": ["www.apple.com"],
        "privateKey": "__SERVER_REALITY_PRIVATE_KEY__",
        "shortIds": ["__SHORT_ID__"]
      }
    }
  }],
  "outbounds": [
    { "protocol": "freedom", "tag": "direct" },
    { "protocol": "blackhole", "tag": "blocked" }
  ],
  "routing": {
    "domainStrategy": "AsIs",
    "rules": [{
      "type": "field",
      "ip": ["0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8", "169.254.0.0/16", "172.16.0.0/12", "192.168.0.0/16", "224.0.0.0/4", "::1/128", "fc00::/7", "fe80::/10"],
      "outboundTag": "blocked"
    }]
  }
}
```

The configuration file contains device identities and the server's REALITY
private key. It is owned by `root:xray`, mode `640`. The owner profile is mode
`600` for `opc`. Backups contain credentials too; preserve their access controls.
No live UUID, private key or short ID is embedded in this guide or the release.

### Keys, identities and recovery

The SSH private key, VLESS UUID and REALITY key pair have different jobs:

- **SSH private key:** authenticates VM administration as `opc`. It stays on the
  administration PC. Client devices do not need it.
- **VLESS UUID:** identifies an enrolled device in Xray's client list. Generating
  a UUID with `xray uuid` alone does not authorize it on the server.
- **REALITY private/public keys:** the private key remains in the VM's protected
  Xray config; the paired public key is included in client profiles. The
  bootstrap's `xray x25519` call generates a new pair for a fresh deployment.
- **Short ID:** the client's value must be accepted by this server's
  `shortIds` list. The bootstrap generates it along with the new deployment.
- **Complete device link/profile:** combines server, port, UUID, SNI, REALITY
  public key and short ID. Treat the complete link as a device credential.

Use the existing owner profile or a protected backup to recover an existing
installation. A new bootstrap generates new credentials rather than discovering
the old ones. Changing the server's REALITY key requires updating its clients;
changing one device UUID requires updating that device's profile.

This setup uses a public REALITY cover destination and does not require an ACME
certificate or a domain you own. Keep the VM and PC clocks synchronized. On the
VM, `timedatectl status` and `chronyc tracking` help inspect time synchronization.

### Client configuration

| Field | Culvert value/meaning |
| --- | --- |
| Server | Imported Culvert public IPv4 and TCP port 443 |
| UUID | Must match this device's server-side client entry |
| Flow/encryption | `xtls-rprx-vision`, VLESS `encryption: none` |
| REALITY serverName | Matches the selected server cover, initially `www.apple.com` |
| REALITY publicKey | Paired with this VM's REALITY private key |
| REALITY shortId | An accepted server short ID |
| Fingerprint / spiderX | `chrome` / `/` |
| Local SOCKS | `127.0.0.1:11808`, UDP enabled, local only |
| DNS | Cloudflare DoH over the proxy; `prefer_ipv4` |
| TUN | `culvert`; `172.20.0.1/30`, `fdfe:dcba:9877::1/126` |
| TUN MTU/stack | `1400`, `gvisor`; automatic and strict routes enabled |
| Server loop guard | Imported server IPv4/TCP port routed directly to the physical uplink |
| QUIC | UDP destination port 443 rejected by the client policy |
| XUDP | `mux.enabled: true`, `concurrency: -1`, `xudpConcurrency: 16`, `xudpProxyUDP443: reject` |

`concurrency: -1` disables ordinary TCP multiplexing while keeping the configured
XUDP behavior. Preserve this tested pair of settings when matching Conduit.
Changing the client to a system web proxy does not replace the full-device TUN
needed to carry Discord voice traffic.

### Why hostname routing fixed Discord

An application can request AAAA records and choose IPv6 even when DNS prefers
IPv4. Previously the Culvert VM had no native IPv6 route and its server omitted
Conduit's hostname-routing setting. The resulting Discord voice WebSocket could
fail even though an IPv4 website health check passed.

With HTTP/TLS/QUIC destination override enabled, Xray can recover the visible
hostname and make the outgoing connection using the server's usable address
family. This is the server behavior used by Conduit. It does not decrypt HTTPS
application content, provision native IPv6, or guarantee every protocol exposes
a usable hostname. Literal IPv6 destinations and IPv6-only services still need
native IPv6 egress. No permanent client AAAA suppression is part of this release.

## 8. Import the owner profile and set VM access

On the Windows administration PC, download the private profile from the correct
VM to a local folder you control:

```powershell
$serverIpv4 = '147.224.134.253'
$keyPath = 'C:\Culvert keys\culvert.key'
scp -i "$keyPath" -o IdentitiesOnly=yes "opc@${serverIpv4}:.config/culvert/profile.json" .\culvert-profile.json
```

1. Install/open the **Owner** edition from this release.
2. Disconnect the other full-device tunnel.
3. In Culvert, choose **Import previous profile** and select that downloaded
   JSON. Existing enrolled users keep their saved identity when upgrading.
4. Under **Settings → VM access**, choose SSH user `opc`, port `22`, and the
   actual Culvert private-key file on this PC. Save the settings.
5. Connect and approve the normal elevated tunnel host prompt.
6. Verify exit IPv4 `147.224.134.253`, then test messages and voice in Discord.

The Windows app encrypts the saved profile for the current Windows user under
`%LOCALAPPDATA%\Culvert\secrets\profile.dpapi`. A downloaded plain JSON profile
remains a credential file; remove the temporary copy after a successful import
and keep any needed recovery copy in private storage.

**Import from v2rayN** imports its selected/generated server. On a PC where
v2rayN points at Conduit, that imports Conduit. Use the Culvert VM's profile or
device link when the intended exit is Culvert. Imported v2rayN profiles do not
enable Culvert's owner server-administration tools.

## 9. Enroll additional devices

Use the Owner app's device-management controls to add a uniquely labelled device
and export its connection link. Give that private link only to the intended
device. Install Client there, import the link, connect, and test the actual app.
That device needs neither your SSH private key nor a separate VM.

Owner device operations use `/usr/local/bin/culvert-devices` through SSH with
`sudo -n`. The default Oracle `opc` account supports passwordless sudo; a custom
administration account must have the required approved sudo access. Device jobs
can continue if the tunnel/SSH connection drops during a server restart; refresh
their status before resubmitting an uncertain operation.

Legacy manual helpers also exist:

```bash
sudo /usr/local/bin/add-user.sh --dry-run laptop-2
sudo /usr/local/bin/add-user.sh laptop-2
sudo /usr/local/bin/del-user.sh --dry-run laptop-2
sudo /usr/local/bin/del-user.sh laptop-2
```

Run only the intended add or revoke action. Adding prints the new UUID; it does
not itself enroll a Windows app or construct every field of a complete link.
Revoking that device removes its server access and interrupts active service.

## 10. Cover settings, usage and watchdog

The active initial REALITY cover is Apple. Server cover information lives in
`/usr/local/etc/xray/cover-profiles.json`. Owner tools use these server helpers:

| Helper | Purpose |
| --- | --- |
| `get-cover.sh` | Inspect active profile and live REALITY destination |
| `vet-cover.sh` | Test a cover candidate before switching |
| `set-cover.sh` | Change the server's destination and accepted SNI names |
| `confirm-cover.sh` | Confirm a working timed cover change |
| `/home/opc/usage.sh` | Owner server usage readout |
| `tunnel-watchdog.timer` | Periodically check/recover Xray service/listener |

A cover change affects the server's devices. Their client SNI must match the
server; use the Owner workflow and test one change at a time. A service/listener
watchdog cannot prove Discord, every destination, or the whole network works.

## 11. Verify and troubleshoot

On the VM, these commands inspect configuration/service state without printing
the REALITY private key or device UUIDs:

```bash
/usr/local/bin/xray version
sudo /usr/local/bin/xray run -test -c /usr/local/etc/xray/config.json
systemctl is-active xray
systemctl is-enabled xray
sudo ss -ltnp 'sport = :443'
sudo journalctl -u xray -n 80 --no-pager
sudo firewall-cmd --list-all
systemctl status tunnel-watchdog.timer --no-pager
sudo jq '.inbounds[] | {port, protocol, sniffing}' /usr/local/etc/xray/config.json
```

Check ordinary IPv4 egress from the VM:

```bash
curl -4 --fail --max-time 10 https://api.ipify.org
```

On Windows while Culvert is connected, verify the observed IPv4 exit:

```powershell
curl.exe -4 --fail --max-time 10 https://api.ipify.org
```

Both should show the Culvert public IPv4 for this deployment. Then test Discord
messages and voice. A TCP connection or an HTTP response from `discord.com`
alone does not prove the desktop message gateway or voice path.

| Symptom | Check next |
| --- | --- |
| SSH timeout | Correct VM/IP, Oracle TCP 22 rule, guest ssh service/firewall and local network restrictions |
| SSH "unprotected private key" | Permissions on that exact key file |
| Permission denied (publickey) | Private key belongs to this VM and SSH user is `opc` |
| TCP 443 unreachable | Public IP, VNIC route/IGW, cloud ingress, guest firewall and Xray listener |
| TCP works but REALITY fails | Device UUID, public/private key pairing, short ID, SNI and client/server clock |
| Websites load but Discord voice/messages fail | Server hostname override, real Discord logs, TUN active, UDP/XUDP policy and one tunnel at a time |
| Exit is Conduit | Wrong imported profile or selected v2rayN server |
| Owner tools fail | Owner edition, native Culvert profile, VM access key/user/port and `sudo -n` |
| Xray restart fails | Validate config; check journal, root:xray ownership, mode 640 and SELinux context |

Keep SELinux and firewalld enabled. When correcting configuration permissions:

```bash
sudo chown root:xray /usr/local/etc/xray/config.json
sudo chmod 640 /usr/local/etc/xray/config.json
sudo restorecon /usr/local/etc/xray/config.json
sudo /usr/local/bin/xray run -test -c /usr/local/etc/xray/config.json
```

Restart Xray only after a successful validation. A restart briefly interrupts
all clients, including an administration SSH session carried by the tunnel.
Hostname-upgrade backups are protected under `/var/backups/culvert`; legacy
user/cover helpers may also have `config.json.bak.*` backups. Select and validate
the intended backup before restoring it; do not replace the current identity
with a freshly generated one to troubleshoot an unrelated connection problem.

If Windows traffic remains blocked after a tunnel failure, use Culvert's
**Disconnect** or **Restore normal internet** control. Enabling the optional
network lock affects the whole PC. Closing the dashboard to the tray does not
disconnect the tunnel.

## 12. Release files and references

The 2.4.4 release includes Owner/Client Windows installers and signed update
bundles, signed Linux and server archives, signed update feeds, this standalone
guide, and `SHA256SUMS.txt`. Windows bundles and the Linux archive also include
this guide. Installers contain no enrolled identity or SSH/REALITY private key.
The server ZIP includes the public server scripts; its bootstrap downloads the
pinned Xray build appropriate to the VM architecture.

Configuration sources: `server/bootstrap.sh`, `configs/xray.template.json`,
`configs/singbox-tun.json`, and `engines.lock.json` in the tagged repository.

- [Culvert release 2.4.4](https://github.com/Zykoraa/culvert/releases/tag/v2.4.4)
- [Oracle security rules](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/securityrules.htm)
- [Oracle security lists](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/securitylists.htm)
- [Xray inbound hostname detection and destination override](https://xtls.github.io/en/config/inbound.html)
- [Xray transport and REALITY fields](https://xtls.github.io/en/config/transport.html)
- [Xray outbound, multiplexing and XUDP fields](https://xtls.github.io/en/config/outbound.html)
- [sing-box DNS policy](https://sing-box.sagernet.org/configuration/dns/)

The deployment snapshot and live Discord verification above apply to October
13, 2026. Download integrity, unit tests and CI do not establish continuous
application availability, Wi-Fi roaming behavior or performance on every PC.
