"""Culvert's bounded Linux profile, engine configuration and owner SSH operations."""
from __future__ import annotations
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import urllib.parse
import uuid

ROOT = Path(__file__).resolve().parent.parent
CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'culvert'
STATE = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'culvert'
SYSTEM_ROOT = Path('/opt/culvert')
SOCKS_PORT = 11808
API_PORT = 11819


def private_write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def validate_profile(value):
    if not isinstance(value, dict): raise ValueError('Invalid connection profile.')
    fields = {'user', 'server', 'port', 'uuid', 'sni', 'publicKey', 'shortId', 'expectedExitIp'}
    if set(value) - fields - {'imported'}: raise ValueError('Unsupported connection settings.')
    if value.get('imported'): raise ValueError('Import a personal VLESS / REALITY link for the Linux client.')
    result = {name: str(value.get(name, '')) for name in fields - {'port'}}
    for name, limit in [('user', 256), ('server', 253), ('sni', 253), ('publicKey', 43), ('shortId', 16), ('uuid', 36), ('expectedExitIp', 45)]:
        if len(result[name]) > limit or any(ord(c) < 32 for c in result[name]): raise ValueError('Invalid ' + name)
    result['server'] = str(ipaddress.IPv4Address(result['server']))
    result['uuid'] = str(uuid.UUID(result['uuid']))
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}', result['publicKey']): raise ValueError('Invalid REALITY public key.')
    if not re.fullmatch(r'(?:[0-9a-fA-F]{2}){1,8}', result['shortId']): raise ValueError('Invalid REALITY short ID.')
    if not re.fullmatch(r'(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z0-9-]{2,63}', result['sni']): raise ValueError('Invalid cover server name.')
    if result['expectedExitIp']: result['expectedExitIp'] = str(ipaddress.IPv4Address(result['expectedExitIp']))
    port = value.get('port', 443)
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535: raise ValueError('Invalid server port.')
    result['port'] = port
    return result


def parse_link(text):
    if len(text) > 8192: raise ValueError('Connection link is too large.')
    uri = urllib.parse.urlsplit(text.strip())
    if uri.scheme != 'vless' or not uri.username or uri.password: raise ValueError('Paste a personal vless:// connection link.')
    query = urllib.parse.parse_qs(uri.query, strict_parsing=True)
    def one(name):
        values = query.get(name, [])
        if len(values) != 1: raise ValueError('Missing or duplicate ' + name)
        return values[0]
    if one('security') != 'reality' or one('flow') != 'xtls-rprx-vision' or one('type') not in ('tcp', 'raw'): raise ValueError('Use VLESS / REALITY / Vision over TCP.')
    return validate_profile({'user': urllib.parse.unquote(uri.fragment) or 'Culvert device', 'server': uri.hostname,
        'port': uri.port or 443, 'uuid': uri.username, 'sni': one('sni'), 'publicKey': one('pbk'), 'shortId': one('sid')})


def create_link(profile):
    p = validate_profile(profile)
    query = urllib.parse.urlencode({'encryption': 'none', 'flow': 'xtls-rprx-vision', 'security': 'reality',
        'sni': p['sni'], 'fp': 'chrome', 'pbk': p['publicKey'], 'sid': p['shortId'], 'type': 'tcp'})
    return f"vless://{p['uuid']}@{p['server']}:{p['port']}?{query}#" + urllib.parse.quote(p['user'])


def load_profile():
    # A Secret Service is optional on minimal Hyprland sessions. Never claim file storage is encrypted.
    try:
        encrypted = subprocess.run(['secret-tool', 'lookup', 'application', 'culvert', 'kind', 'profile'], capture_output=True, text=True, timeout=2)
        if encrypted.returncode == 0 and encrypted.stdout.strip(): return validate_profile(json.loads(encrypted.stdout))
    except (OSError, subprocess.TimeoutExpired, ValueError): pass
    try: return validate_profile(json.loads((CONFIG / 'profile.json').read_text()))
    except (OSError, ValueError): return None


def save_profile(profile):
    p = validate_profile(profile)
    try:
        result = subprocess.run(['secret-tool', 'store', '--label=Culvert device connection', 'application', 'culvert', 'kind', 'profile'],
            input=json.dumps(p), capture_output=True, text=True, timeout=8)
        if result.returncode == 0:
            (CONFIG / 'profile.json').unlink(missing_ok=True)
            return 'Saved in your desktop keyring.'
    except (OSError, subprocess.TimeoutExpired): pass
    private_write(CONFIG / 'profile.json', p)
    return 'Saved locally with owner-only file permissions (no desktop keyring available).'


def preferences():
    defaults = {'ssh_user': 'opc', 'ssh_port': 22, 'ssh_key': str(Path.home() / '.ssh/culvert.key'), 'network_lock': False, 'autoheal': True, 'autostart': False, 'animations': True}
    try:
        value = json.loads((CONFIG / 'settings.json').read_text())
        if isinstance(value, dict): defaults.update({k: v for k, v in value.items() if k in defaults})
    except (OSError, ValueError): pass
    return defaults


def save_preferences(options):
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_-]{0,31}', options['ssh_user']): raise ValueError('Invalid SSH username.')
    if not isinstance(options['ssh_port'], int) or not 1 <= options['ssh_port'] <= 65535: raise ValueError('Invalid SSH port.')
    if not Path(options['ssh_key']).is_absolute() or any(ord(c) < 32 for c in options['ssh_key']): raise ValueError('Select an absolute private-key file path.')
    private_write(CONFIG / 'settings.json', options)


def xray_config(profile):
    p = validate_profile(profile)
    return {'log': {'loglevel': 'warning'}, 'inbounds': [{'listen': '127.0.0.1', 'port': SOCKS_PORT, 'protocol': 'socks', 'settings': {'udp': True}}],
        'outbounds': [{'tag': 'proxy', 'protocol': 'vless', 'settings': {'vnext': [{'address': p['server'], 'port': p['port'],
            'users': [{'id': p['uuid'], 'encryption': 'none', 'flow': 'xtls-rprx-vision'}]}]},
            'streamSettings': {'network': 'tcp', 'security': 'reality', 'realitySettings': {'serverName': p['sni'], 'fingerprint': 'chrome', 'publicKey': p['publicKey'], 'shortId': p['shortId'], 'spiderX': '/'}},
            'mux': {'enabled': True, 'concurrency': -1, 'xudpConcurrency': 16, 'xudpProxyUDP443': 'reject'}}]}


def tun_config(profile, api_secret=''):
    p = validate_profile(profile)
    result = json.loads((ROOT / 'configs/singbox-tun.json').read_text())
    for rule in result['route']['rules']:
        if rule.get('outbound') == 'direct' and 'ip_cidr' in rule:
            rule['ip_cidr'] = [p['server'] + '/32']; rule['port'] = p['port']
    if api_secret: result['experimental'] = {'clash_api': {'external_controller': f'127.0.0.1:{API_PORT}', 'secret': api_secret}}
    return result


def ssh_command(remote, profile=None, input=None, timeout=30):
    p = validate_profile(profile or load_profile() or {})
    options = preferences()
    save_preferences(options)  # Validate persisted settings before constructing the invocation.
    key = Path(options['ssh_key'])
    if not key.is_file(): raise ValueError('Choose your VM private key under Settings first.')
    CONFIG.mkdir(parents=True, exist_ok=True, mode=0o700)
    args = ['ssh', '-i', str(key), '-p', str(options['ssh_port']), '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
        '-o', 'StrictHostKeyChecking=accept-new', '-o', f'UserKnownHostsFile={CONFIG / "ssh-known-hosts"}', '-o', 'ConnectTimeout=8',
        options['ssh_user'] + '@' + p['server'], remote]
    result = subprocess.run(args, input=input, capture_output=True, text=True, timeout=timeout)
    if result.returncode: raise RuntimeError('VM request failed. Check the SSH key, username and server access.')
    return result.stdout.strip()


def device_request(request):
    result = json.loads(ssh_command('sudo -n /usr/local/bin/culvert-devices', input=json.dumps(request), timeout=15))
    if 'error' in result: raise ValueError(result['error'])
    return result


def status_path(): return Path('/run/culvert') / str(os.getuid()) / 'status.json'


def read_status():
    try:
        value = json.loads(status_path().read_text())
        import time
        if time.time() - value.get('updated', 0) > 20 and value.get('state') not in ('disconnected', 'faulted'):
            value.update(state='unverified', verified=False, message='Host evidence is stale. Reconnect or restore normal internet.')
        return value
    except (OSError, ValueError): return {'state': 'disconnected', 'verified': False, 'message': 'Ready when you are.'}


def privileged(action, profile=None):
    helper = SYSTEM_ROOT / 'linux/helper.py'
    if not helper.is_file(): raise RuntimeError('Finish system setup first. Culvert needs its installed tunnel helper.')
    payload = None
    if action == 'connect':
        options = preferences()
        payload = json.dumps({'profile': validate_profile(profile or load_profile() or {}), 'network_lock': bool(options['network_lock']), 'autoheal': bool(options['autoheal'])})
    result = subprocess.run(['pkexec', '/usr/bin/python3', str(helper), action], input=payload, capture_output=True, text=True, timeout=90)
    if result.returncode: raise RuntimeError(result.stdout.strip() or 'System authorization was canceled or the tunnel helper could not start.')
    return result.stdout.strip()
