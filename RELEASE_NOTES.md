Culvert preserves Conduit's Windows tunnel client and owner tools in an independent application.

- Black and crimson dashboard with an original tunnel mascot, animated orbit and matching tray/installer icon.
- Native Linux x86_64 / Wayland client for Hyprland, with pinned engines and signature-verifiable Linux archives. See linux/README.md for platform scope and setup.
- Separate installation, saved identity, runtime, autostart, IPC, TUN adapter, local proxy port and network-lock identifiers.
- Independent signed update trust and Culvert download feeds.
- Owner VM access settings for a separate SSH username, port and private key file.
- Fresh-VM bootstrap and the existing device enrollment, cover switching, watchdog and usage tools.

Install Owner on the PC used to administer your VM, then import that VM's personal device link. Under Settings → VM access, select the SSH private key on that PC. Each Client device needs its own link.

This first Culvert release retains version 2.4.3 to identify the copied Conduit baseline. Conduit installations and servers are separate. Run one full-device tunnel at a time.
