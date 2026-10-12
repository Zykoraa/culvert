#!/usr/bin/env python3
"""Verify a Linux release archive against Culvert's embedded independent public trust."""
import subprocess,sys,tempfile
from pathlib import Path
if len(sys.argv)!=3: raise SystemExit('Usage: verify-update.py <Culvert-linux-x86_64.tar.gz> <archive.sig>')
archive=Path(sys.argv[1]);signature=Path(sys.argv[2]).read_bytes()
if len(signature)!=64: raise SystemExit('Invalid signature length.')
def integer(value):
    raw=value.lstrip(b'\0') or b'\0'
    if raw[0]&128:raw=b'\0'+raw
    return b'\x02'+bytes([len(raw)])+raw
values=integer(signature[:32])+integer(signature[32:]);der=b'\x30'+bytes([len(values)])+values
with tempfile.NamedTemporaryFile() as output:
    output.write(der);output.flush()
    result=subprocess.run(['openssl','dgst','-sha256','-verify',str(Path(__file__).parent/'release-public-key.pem'),'-signature',output.name,str(archive)],capture_output=True,text=True)
if result.returncode:raise SystemExit('Signature verification failed. Do not install this archive.')
print('Verified Culvert Linux release signature.')
