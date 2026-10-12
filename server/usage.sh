#!/usr/bin/env bash
# Local shared-VM counters only. No billing API and no external notifications.
set -euo pipefail
command -v vnstat >/dev/null || { echo 'Install and start vnstat to collect shared VM usage.'; exit 0; }
vnstat --json m | python3 -c '
import json,sys
data=json.load(sys.stdin)
rx=tx=0
for interface in data.get("interfaces", []):
    months=interface.get("traffic", {}).get("month", [])
    if months:
        current=months[-1];rx+=current.get("rx", 0);tx+=current.get("tx", 0)
print("CULVERT / SHARED VM USAGE")
print("Current collected month: received %.3f GiB / sent %.3f GiB" % (rx/1024**3,tx/1024**3))
print("Shared interface counters since vnStat collection began; not provider billing or per-device usage.")
'
