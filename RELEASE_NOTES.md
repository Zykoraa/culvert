# Culvert 2.4.5

This patch also corrects the 2.4.4 server ZIP's Python line endings. Linux shell and Python sources are pinned to LF in Git and checked inside the actual archive, so the installed device helper launches correctly on Oracle Linux.

This release brings Culvert's server hostname routing into line with Conduit and includes a complete Oracle VM/Xray setup guide. The client retains `prefer_ipv4`, the existing dual-stack TUN, and the same pinned engines.

## Discord server fix

The old Culvert bootstrap omitted the HTTP/TLS/QUIC hostname override used by Conduit's server. An application could choose an IPv6 address and fail its message or voice connection on a VM without native IPv6 egress. New bootstraps now include the setting. Existing servers can apply it with `sudo bash server/enable-hostname-routing.sh`; the script validates, backs up and preserves the enrolled identity, and rolls back if restarting Xray fails. Repeated runs do not restart an already configured server.

The current Culvert VM has already received this fix. Discord messages and voice were verified with the original client IPv4 preference restored. No permanent AAAA suppression or native IPv6 provisioning is included.

## Setup documentation and downloads

- [Read the detailed Oracle VM and Xray guide](https://github.com/Zykoraa/culvert/blob/v2.4.5/VM_SETUP.md).
- [Download the standalone guide](https://github.com/Zykoraa/culvert/releases/download/v2.4.5/Culvert-VM-Setup-2.4.5.md).
- [Download the server tools](https://github.com/Zykoraa/culvert/releases/download/v2.4.5/Culvert-Server-2.4.5.zip), with a detached Culvert release signature.

The guide covers the specific Culvert VM snapshot, Oracle routes/security rules, guest firewalld, SSH/key permissions, fresh versus existing VM setup, all deployed Xray/REALITY/Vision/XUDP settings, per-device links, owner tools, logs, verification and recovery. Live credentials are omitted. Windows installers/update bundles and the Linux archive also contain the guide.

## Installation

Use Owner on the administration PC and Client on other Windows devices. Installers contain no enrolled identity; import the correct Culvert VM profile or a personal device link. Existing saved profiles remain in the per-user encrypted store. Stop the other full-device tunnel before connecting.

The separate server ZIP contains the public scripts and guide. For an existing Xray server, use the hostname-routing upgrade script; the fresh bootstrap deliberately refuses to overwrite an existing config. A server restart briefly interrupts all connected clients.

## Engines and verification

Xray remains pinned to 26.7.28 and sing-box to 1.13.19. Windows update bundles/feeds and Linux/server archives use Culvert's independent release trust. SHA256SUMS.txt covers all published assets. Setup still has no Windows Authenticode publisher certificate; Windows may show an unknown publisher prompt.

The release workflow validates source and history, engine hashes, application behavior, Linux packaging, Windows installation/repair/uninstall, embedded guide installation, and the server ZIP's exact source contents and shell line endings.
