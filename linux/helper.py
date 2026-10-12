#!/usr/bin/env python3
"""Root-owned, polkit-approved systemd control boundary. Accepts bounded profiles, never engine configs."""
import json, os, pwd, subprocess, sys
from pathlib import Path
from common import private_write, validate_profile


def main():
    if os.geteuid() != 0: raise ValueError('System authorization is required.')
    uid = int(os.environ.get('PKEXEC_UID', os.environ.get('SUDO_UID', '-1')))
    if uid <= 0: raise ValueError('Run through pkexec from your desktop account.')
    account = pwd.getpwuid(uid)
    if len(sys.argv) != 2 or sys.argv[1] not in ('connect', 'disconnect'): raise ValueError('Invalid control request.')
    base = Path('/run/culvert'); base.mkdir(mode=0o755, exist_ok=True)
    runtime = base / str(uid); runtime.mkdir(mode=0o750, exist_ok=True); os.chown(runtime, 0, account.pw_gid)
    if sys.argv[1] == 'connect':
        data = sys.stdin.read(16385)
        if len(data) > 16384: raise ValueError('Connection request is too large.')
        request = json.loads(data)
        if set(request) != {'profile', 'network_lock', 'autoheal'}: raise ValueError('Invalid control settings.')
        if type(request['network_lock']) is not bool or type(request['autoheal']) is not bool: raise ValueError('Invalid control options.')
        request['profile'] = validate_profile(request['profile'])
        existing = base / 'active-user'
        if existing.exists() and existing.read_text().strip() != str(uid): raise ValueError('Another desktop user is running Culvert. Disconnect it first.')
        private_write(Path('/var/lib/culvert') / str(uid) / 'connection.json', request)
        subprocess.run(['systemctl', 'restart', f'culvert@{uid}.service'], check=True, capture_output=True)
        print('Culvert host started.')
    else:
        subprocess.run(['systemctl', 'stop', f'culvert@{uid}.service'], check=True, capture_output=True)
        active = base / 'active-user'
        if not active.exists() or active.read_text().strip() == str(uid):
            subprocess.run(['nft', 'delete', 'table', 'inet', 'culvert'], capture_output=True)
            active.unlink(missing_ok=True)
        private_write(runtime / 'status.json', {'state': 'disconnected', 'verified': False, 'message': 'Normal internet restored.', 'updated': __import__('time').time()})
        os.chown(runtime / 'status.json', 0, account.pw_gid); os.chmod(runtime / 'status.json', 0o640)
        print('Normal internet restored.')

if __name__ == '__main__':
    try: main()
    except Exception as error:
        print(str(error) if isinstance(error, (ValueError, FileNotFoundError)) else 'The system tunnel operation failed. Check Culvert diagnostics.'); sys.exit(1)
