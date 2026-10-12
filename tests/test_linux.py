"""Linux control-boundary, connection evidence and credential isolation checks."""
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'linux'))
import common
import host

PROFILE = {'user':'Test device', 'server':'203.0.113.7', 'port':443,
    'uuid':'e597d73c-3c66-48f0-a555-cef3017c2108', 'sni':'example.com',
    'publicKey':'A'*43, 'shortId':'abcdef0123456789', 'expectedExitIp':''}


class LinuxTests(unittest.TestCase):
    def test_link_round_trip_and_duplicate_query_rejection(self):
        link = common.create_link(PROFILE)
        self.assertEqual(common.parse_link(link), PROFILE)
        with self.assertRaises(ValueError): common.parse_link(link.replace('#', '&sni=other.example#'))
        with self.assertRaises(ValueError): common.parse_link(link.replace('security=reality', 'security=none'))

    def test_reject_unbounded_or_executable_connection_settings(self):
        for field, value in [('server','203.0.113.7;id'), ('sni','example.com\ncommand'),
            ('port',True), ('port',65536), ('shortId','zz'), ('publicKey','A'*44),
            ('uuid','not-a-uuid'), ('user','A'*257)]:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                common.validate_profile(dict(PROFILE, **{field:value}))
        with self.assertRaises(ValueError): common.validate_profile(dict(PROFILE, executable='/tmp/engine'))

    def test_generated_routing_keeps_vm_endpoint_separate(self):
        result = common.tun_config(PROFILE, 'test-secret')
        self.assertEqual(result['inbounds'][0]['interface_name'], 'culvert')
        endpoint = [r for r in result['route']['rules'] if r.get('outbound')=='direct' and 'ip_cidr' in r]
        self.assertEqual(endpoint, [{'ip_cidr':['203.0.113.7/32'],'port':443,'outbound':'direct'}])
        self.assertEqual(result['outbounds'][0]['server_port'], common.SOCKS_PORT)
        self.assertEqual(result['experimental']['clash_api']['external_controller'], '127.0.0.1:11819')
        self.assertNotIn(PROFILE['uuid'], json.dumps(result))

    def test_private_file_replacement_never_inherits_world_readable_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'profile.json'; path.write_text('old'); path.chmod(0o644)
            common.private_write(path, PROFILE)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(path.read_text()), PROFILE)

    def test_stale_host_cannot_keep_verified_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'status.json'
            path.write_text(json.dumps({'state':'connected','verified':True,'updated':time.time()-30}))
            with patch.object(common, 'status_path', return_value=path):
                result = common.read_status()
            self.assertFalse(result['verified']); self.assertEqual(result['state'], 'unverified')

    def test_stun_evidence_rejects_wrong_transaction_fragment_and_truncation(self):
        transaction = b'0123456789ab'
        header = b'\x00\x00\x00\x01'+b'\x01\x01\x01\x01'+struct.pack('!H',3478)
        packet = struct.pack('!HHI',0x0101,0,0x2112A442)+transaction
        host.validate_stun_response(header+packet, transaction)
        for response in (b'', header+packet[:-1], header+packet+b'junk',
            b'\x00\x00\x01'+header[3:]+packet, header+packet[:-1]+b'z'):
            with self.assertRaises(OSError): host.validate_stun_response(response, transaction)

    def test_lock_replacement_is_one_atomic_nft_transaction(self):
        with patch.object(host.subprocess, 'run') as run:
            run.return_value.returncode = 0
            host.apply_lock(PROFILE)
            self.assertEqual(run.call_count, 2)
            self.assertEqual(run.call_args.args[0], ['nft','-f','-'])
            self.assertTrue(run.call_args.kwargs['input'].startswith('delete table inet culvert\ntable inet culvert'))

    def test_ssh_preferences_reject_command_options_and_relative_paths(self):
        options = common.preferences()
        for changes in ({'ssh_user':'-oProxyCommand=id'}, {'ssh_key':'relative.key'}, {'ssh_port':0}):
            with self.assertRaises(ValueError): common.save_preferences(dict(options, **changes))


if __name__ == '__main__': unittest.main()
