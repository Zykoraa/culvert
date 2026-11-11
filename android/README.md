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

## Check hotspot routing over USB Ethernet

Use an Ethernet network where you are authorized to connect and run the tunnel.
Android manages [tethering](https://source.android.com/docs/core/ota/modular-system/tethering)
separately from the phone's VPN. Whether hotspot clients use the tunnel depends
on the phone's forwarding behavior.

1. With v2rayNG stopped, plug in USB Ethernet and turn off Wi-Fi and mobile data
   on the phone. Check that the phone can reach the internet over Ethernet.
2. Turn on the hotspot. Connect a client with its own tunnel and proxy disabled.
   Check that it can browse and record its public IP as the baseline.
3. Start v2rayNG and verify that the phone shows the Culvert exit IP. Check the
   client again. If it still shows the baseline IP, it bypasses Culvert. If it
   loses internet access, hotspot forwarding is failing with the tunnel active.
   Repeat for IPv4 and IPv6 where available and check DNS separately.
4. If the client shows the Culvert exit IP, stop v2rayNG and test again to see
   whether the client falls back to the Ethernet connection.

On a Galaxy Z Fold8 running Android 17 and One UI 9, Culvert worked on the
phone, but a follow-up test with another PC did not establish hotspot
forwarding through Culvert. For full-device coverage, run Culvert on the PC or
use a router configured to send its clients through the tunnel.

## If Ethernet shows as connected but has no internet

With v2rayNG stopped, check whether the phone gets an IPv4 address and a gateway.
A live Ethernet link can still fail DHCP. During setup, one jack repeatedly
offered a lease and rejected the subsequent request with a DHCP NAK. An alternate
authorized jack worked. If the failure persists, give the network administrator
the jack, adapter MAC address, and time of the attempt so they can check DHCP logs.
