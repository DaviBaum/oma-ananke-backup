"""Actual local HTTP upload probe; never represents a native file-chooser test."""
import hashlib
import http.client
import json
import time
import urllib.parse
import uuid
from pathlib import Path

root = Path(__file__).resolve().parents[2]
records = []
for name in ("arc.ifc", "mep.ifc"):
    source = root / "data" / "ifc-bench" / "projects" / "duplex" / name
    with source.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    key = uuid.uuid4().hex
    query = urllib.parse.urlencode({"filename": name, "idempotency_key": key})
    connection = http.client.HTTPConnection("127.0.0.1", 8765, timeout=120)
    started = time.perf_counter()
    with source.open("rb") as body:
        connection.request("POST", f"/api/uploads?{query}", body=body,
                           headers={"Content-Type": "application/octet-stream", "Content-Length": str(source.stat().st_size)})
    response = connection.getresponse()
    payload = json.loads(response.read())
    assert response.status in (200, 201), payload
    assert payload["sha256"] == digest and payload["size_bytes"] == source.stat().st_size, payload
    assert payload["status"] == "UPLOADED" and payload["engineering_checks"] == "NOT_RUN", payload
    record = {"source": str(source), "method": "actual raw-byte HTTP upload", "http_status": response.status, "receipt": payload,
              "elapsed_ms": (time.perf_counter() - started) * 1000, "idempotency_key": key}
    records.append(record)
    connection.close()

evidence = {"kind": "oma_real_upload_probe_v1", "records": records,
            "browser_chooser": "Opened native chooser and observed multiple-file support; automated selection blocked by Chrome extension file-URL permission. No successful browser File selection is claimed."}
(root / "ui" / "qa" / "duplex-upload-receipts.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
print(json.dumps(evidence, indent=2))
