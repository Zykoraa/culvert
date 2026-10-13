# Match Conduit's server hostname routing

Culvert keeps Conduit's `prefer_ipv4` DNS policy and dual-stack TUN configuration.
Preferring IPv4 does not stop an application from selecting an IPv6 address.
Conduit's Xray server recognizes HTTP, TLS and QUIC hostnames and uses the
hostname for the outgoing connection. This lets hostname-based traffic use
the server's working IPv4 route even when the client selected an IPv6 address.

Older Culvert bootstraps omitted this inbound `sniffing` setting. Discord voice
could repeatedly fail its TLS/WebSocket connection when the application chose
an IPv6 address but the VM had no native IPv6 route. New servers receive the
same hostname-routing setting as Conduit from `bootstrap.sh`.

## Upgrade an existing Culvert VM

From this checkout on the intended Culvert VM, run:

```bash
sudo bash server/enable-hostname-routing.sh
```

The script requires exactly one VLESS inbound on TCP 443, validates the candidate
config with Xray, saves a protected backup under `/var/backups/culvert`, and
restarts Xray. If restart fails, it restores the previous config. It preserves
enrolled users, REALITY keys and existing routing rules. Restarting Xray briefly
interrupts tunnel traffic; use a direct SSH path or reconnect afterward.

Reconnect Culvert, then test Discord messages and voice. Keep the client DNS
setting at `prefer_ipv4`; permanently suppressing AAAA responses is not required
for this server fix. A basic IPv4 health check alone does not validate the
application's hostname-routing path.

This setting does not provision native IPv6 on the VM. Literal IPv6 destinations
without a recognized hostname, and IPv6-only services, still require native
IPv6 egress. Conduit's existing VM can work for Discord without that feature.
