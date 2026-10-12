#!/usr/bin/env python3
"""Systemd tunnel host. UI lifetime is independent; nftables rules belong only to Culvert."""
import fcntl, ipaddress, json, os, pwd, secrets, signal, socket, struct, subprocess, sys, time, urllib.request
from pathlib import Path
from common import ROOT, SOCKS_PORT, API_PORT, private_write, tun_config, validate_profile, xray_config


def command(*args, timeout=8):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=True).stdout.strip()


def apply_lock(profile):
    script = f'''table inet culvert {{
 chain output {{ type filter hook output priority -150; policy drop;
 oifname "lo" accept
 oifname "culvert" accept
 ip daddr {profile['server']} tcp dport {profile['port']} accept
 udp sport 68 udp dport 67 accept
 udp sport 546 udp dport 547 accept
 meta l4proto ipv6-icmp icmpv6 type {{ nd-router-solicit, nd-router-advert, nd-neighbor-solicit, nd-neighbor-advert }} accept
 }}
}}'''
    # Replace our table in a single nft transaction: no gap in the optional lock.
    if subprocess.run(['nft', 'list', 'table', 'inet', 'culvert'], capture_output=True).returncode == 0:
        script = 'delete table inet culvert\n' + script
    subprocess.run(['nft', '-f', '-'], input=script, capture_output=True, text=True, check=True)


def receive_exact(sock, count):
    data = b''
    while len(data) < count:
        part = sock.recv(count - len(data))
        if not part: raise OSError('Proxy closed')
        data += part
    return data


def validate_stun_response(response, transaction):
    if len(response) < 4 or response[:3] != b'\x00\x00\x00': raise OSError('Invalid SOCKS UDP response')
    if response[3] == 1: offset = 10
    elif response[3] == 4: offset = 22
    elif response[3] == 3 and len(response) >= 5: offset = 7 + response[4]
    else: raise OSError('Invalid address type')
    packet = response[offset:]
    if len(packet) < 20 or packet[:2] != b'\x01\x01' or packet[4:8] != b'\x21\x12\xa4\x42' or packet[8:20] != transaction:
        raise OSError('Invalid STUN response')
    length = struct.unpack('!H', packet[2:4])[0]
    if length % 4 or length + 20 != len(packet): raise OSError('Truncated STUN response')


def udp_probe():
    """A STUN binding request over SOCKS5 UDP, with transaction and response validation."""
    with socket.create_connection(('127.0.0.1', SOCKS_PORT), 3) as control:
        control.settimeout(3); control.sendall(b'\x05\x01\x00')
        if receive_exact(control, 2) != b'\x05\x00': raise OSError('SOCKS authentication failed')
        control.sendall(b'\x05\x03\x00\x01\x00\x00\x00\x00\x00\x00')
        reply = receive_exact(control, 4)
        if reply[:3] != b'\x05\x00\x00': raise OSError('UDP association failed')
        if reply[3] == 1: address = socket.inet_ntoa(receive_exact(control, 4))
        elif reply[3] == 3: address = receive_exact(control, receive_exact(control, 1)[0]).decode()
        else: raise OSError('Unsupported UDP relay')
        port = struct.unpack('!H', receive_exact(control, 2))[0]
        if address == '0.0.0.0': address = '127.0.0.1'
        transaction = secrets.token_bytes(12)
        stun = struct.pack('!HHI', 1, 0, 0x2112A442) + transaction
        header = b'\x00\x00\x00\x01' + socket.inet_aton('162.159.207.1') + struct.pack('!H', 3478)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            udp.settimeout(3); start = time.monotonic(); udp.sendto(header + stun, (address, port)); response, _ = udp.recvfrom(4096)
        validate_stun_response(response, transaction)
        return round((time.monotonic() - start) * 1000, 1)


def health(profile):
    result = {'exit': None, 'dns': False, 'udp': False, 'route4': False, 'route6': False, 'latency': None}
    try:
        result['exit'] = command('curl', '--fail', '--silent', '--max-time', '4', '--socks5-hostname', f'127.0.0.1:{SOCKS_PORT}', 'https://api.ipify.org', timeout=5)
        result['exit'] = str(ipaddress.ip_address(result['exit']))
    except Exception: pass
    try:
        command('curl', '--fail', '--silent', '--max-time', '4', '--socks5-hostname', f'127.0.0.1:{SOCKS_PORT}', 'https://one.one.one.one/cdn-cgi/trace', timeout=5)
        result['dns'] = True
    except Exception: pass
    try: result['latency'] = udp_probe(); result['udp'] = True
    except Exception: pass
    for family, target in [('4', '1.1.1.1'), ('6', '2606:4700:4700::1111')]:
        try: result['route' + family] = json.loads(command('ip', '-' + family, '-j', 'route', 'get', target))[0].get('dev') == 'culvert'
        except Exception: pass
    expected = profile['expectedExitIp'] or profile['server']
    result['verified'] = result['exit'] == expected and all(result[k] for k in ('dns', 'udp', 'route4', 'route6'))
    return result


class Host:
    def __init__(self, uid):
        self.uid = uid; self.gid = pwd.getpwuid(uid).pw_gid; self.runtime = Path('/run/culvert') / str(uid)
        request = json.loads((Path('/var/lib/culvert') / str(uid) / 'connection.json').read_text())
        self.profile = validate_profile(request['profile']); self.lock = bool(request['network_lock']); self.autoheal = bool(request['autoheal'])
        self.children = []; self.logs = []; self.running = True; self.secret = secrets.token_urlsafe(32); self.current = {}; self.failures = 0
        self.last_health = 0; self.probes = {}; self.started = time.time(); self.restarts = 0

    def status(self, state, message):
        value = {'state': state, 'message': message, 'verified': self.probes.get('verified', False) if state == 'connected' else False,
            'updated': time.time(), 'started': self.started, 'network_lock': self.lock, 'health': self.probes, 'restarts': self.restarts}
        try:
            value['received'] = int(Path('/sys/class/net/culvert/statistics/rx_bytes').read_text())
            value['sent'] = int(Path('/sys/class/net/culvert/statistics/tx_bytes').read_text())
        except OSError: value.update(received=0, sent=0)
        try:
            request = urllib.request.Request(f'http://127.0.0.1:{API_PORT}/connections', headers={'Authorization': 'Bearer ' + self.secret})
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=.5) as response: connections = json.load(response).get('connections', [])[:200]
            value['connections'] = [{'host': c.get('metadata', {}).get('host') or c.get('metadata', {}).get('destinationIP', ''),
                'port': c.get('metadata', {}).get('destinationPort', ''), 'network': c.get('metadata', {}).get('network', ''),
                'download': c.get('download', 0), 'upload': c.get('upload', 0)} for c in connections]
        except Exception: value['connections'] = []
        private_write(self.runtime / 'status.json', value)
        os.chown(self.runtime / 'status.json', 0, self.gid); os.chmod(self.runtime / 'status.json', 0o640)
        self.current = value

    def stop_cores(self):
        for child in reversed(self.children):
            if child.poll() is None:
                child.terminate()
                try: child.wait(timeout=4)
                except subprocess.TimeoutExpired: child.kill(); child.wait()
        self.children.clear()
        for log in self.logs: log.close()
        self.logs.clear()

    def start_cores(self):
        self.stop_cores(); self.probes = {}; self.status('connecting', 'Starting your private tunnel…')
        private_write(self.runtime / 'xray.json', xray_config(self.profile))
        private_write(self.runtime / 'sing-box.json', tun_config(self.profile, self.secret))
        for name, args in [('xray', ['run', '-test', '-c', str(self.runtime / 'xray.json')]), ('sing-box', ['check', '-c', str(self.runtime / 'sing-box.json')])]:
            subprocess.run([str(ROOT / 'cores/linux' / name), *args], capture_output=True, check=True, timeout=8)
        if self.lock: apply_lock(self.profile)
        for name, filename in [('xray', 'xray.json'), ('sing-box', 'sing-box.json')]:
            fd = os.open(self.runtime / (name + '.log'), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            log = os.fdopen(fd, 'w'); self.logs.append(log)
            self.children.append(subprocess.Popen([str(ROOT / 'cores/linux' / name), 'run', '-c', str(self.runtime / filename)], stdout=log, stderr=log))
            time.sleep(1)
            if self.children[-1].poll() is not None: raise RuntimeError('A tunnel engine could not start.')
        self.last_health = 0

    def run(self):
        guard = open('/run/culvert/host.lock', 'a')
        try: fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.status('faulted', 'Another Culvert tunnel is active.'); return
        active = Path('/run/culvert/active-user'); active.write_text(str(self.uid)); active.chmod(0o600)
        def stop(*_): self.running = False
        signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
        try:
            while self.running:
                try:
                    if not self.children or any(child.poll() is not None for child in self.children): self.start_cores()
                    if time.monotonic() - self.last_health >= 10:
                        self.probes = health(self.profile); self.last_health = time.monotonic()
                        self.failures = 0 if self.probes['verified'] else self.failures + 1
                    verified = self.probes.get('verified', False)
                    self.status('connected' if verified else 'unverified', 'Sampled exit, DNS, UDP and IPv4/IPv6 routes verified.' if verified else 'Tunnel is running. Some connection evidence is unavailable.')
                    if self.autoheal and self.failures >= 3:
                        self.restarts += 1; self.failures = 0; self.stop_cores()
                        self.status('recovering', 'Recovering after failed connection checks…')
                        for _ in range(min(60, 5 * self.restarts)):
                            if not self.running: break
                            time.sleep(1)
                    else: time.sleep(1)
                except Exception:
                    self.stop_cores(); self.probes = {}; self.status('faulted', 'Tunnel startup failed. Check the profile or restore normal internet.')
                    if not self.autoheal: break
                    for _ in range(15):
                        if not self.running: break
                        time.sleep(1)
        finally:
            self.stop_cores()
            # A deliberate systemctl stop restores normal traffic. SIGKILL cannot clear the persistent lock;
            # the independently callable disconnect helper repairs it on the next request.
            if not self.running:
                subprocess.run(['nft', 'delete', 'table', 'inet', 'culvert'], capture_output=True)
                self.probes = {}; self.status('disconnected', 'Normal internet restored.')
                active.unlink(missing_ok=True)
            guard.close()


if __name__ == '__main__':
    if os.geteuid() != 0 or len(sys.argv) != 2: raise SystemExit('Use the installed Culvert system service.')
    Host(int(sys.argv[1])).run()
