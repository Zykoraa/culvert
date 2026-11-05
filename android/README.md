# Culvert on Android

Use [v2rayNG](https://github.com/2dust/v2rayNG/releases) to connect an Android
phone to an existing Culvert server. The Android app is maintained and released
by v2rayNG. This guide covers Culvert's standard VLESS/REALITY device links.

## Connect the phone

1. In Culvert Owner, enroll a device for the phone and copy its connection link.
   See [device enrollment in the VM guide](../VM_SETUP.md). Treat the link as a
   password and transfer it privately to the phone.
2. Install v2rayNG from its official releases. Choose the APK for the phone's
   CPU architecture, such as `arm64-v8a` for a Galaxy Z Fold8.
3. Copy the device link on the phone. In v2rayNG, tap **+ → Import from Clipboard**
   and select the imported profile.
4. Start the connection in **VPN mode** and accept Android's connection prompt.
   Android uses a VPN interface to send phone traffic to v2rayNG. The connection
   to the Culvert server uses VLESS/REALITY.
5. Run v2rayNG's connection test, then check the phone's public IP against the
   Culvert server's expected exit IP.

## Use USB Ethernet and share over Wi-Fi

Use an Ethernet network where you are authorized to connect and run the tunnel.

1. Plug in the USB Ethernet adapter with v2rayNG stopped. Temporarily turn off
   Wi-Fi and mobile data on the phone, then confirm that a browser can reach
   the internet over Ethernet.
2. Start v2rayNG and verify the phone's exit IP again.
3. Enable the phone's Wi-Fi hotspot. Join it from a client with its own tunnel
   and proxy disabled. Check that client's public IP independently. Repeat for
   IPv4 and IPv6 where available, and verify DNS if DNS routing matters to
   your setup.
4. Stop v2rayNG and repeat the client check. If the client still has internet
   through the Ethernet exit, the hotspot falls back to the underlying network
   when the tunnel stops.

Android manages [tethering](https://source.android.com/docs/core/ota/modular-system/tethering)
separately from the phone's VPN. Automatic hotspot forwarding depends on the
phone's firmware and settings. A successful phone connection verifies only the
phone's path. If the hotspot bypasses v2rayNG, use a tunnel on each client or a
router configured to send its clients through the tunnel.

A Galaxy Z Fold8 running Android 17 and One UI 9 was used for setup. The
operator reported success with the hotspot workflow. Automatic forwarding and
behavior after a tunnel drop should be checked on each setup.

## If Ethernet shows as connected but has no internet

With v2rayNG stopped, check whether the phone gets an IPv4 address and a gateway.
A live Ethernet link can still fail DHCP. During setup, one jack repeatedly
offered a lease and rejected the subsequent request with a DHCP NAK. An alternate
authorized jack worked. If the failure persists, give the network administrator
the jack, adapter MAC address, and time of the attempt so they can check DHCP logs.
