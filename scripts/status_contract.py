"""Check a running Java or Python status fixture through its public HTTP contract."""

import json
import os
import urllib.error
import urllib.request

base = os.environ.get("STATUS_URL", "http://127.0.0.1:8001")
for service, expected in {
    "atlas": "degraded",
    "nova": "operational",
    "orion": "outage",
    "vpn": "operational",
}.items():
    with urllib.request.urlopen(f"{base}/services/{service}", timeout=5) as response:
        value = json.load(response)
        assert value["service_id"] == service and value["status"] == expected
try:
    urllib.request.urlopen(f"{base}/services/unknown", timeout=5)
except urllib.error.HTTPError as error:
    assert error.code == 404
else:
    raise AssertionError("Unknown services must fail")
print("Status contract: 5 checks passed")
