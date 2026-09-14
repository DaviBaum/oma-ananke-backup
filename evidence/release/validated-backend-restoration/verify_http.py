"""Read-only verification of the restored backend and unchanged interface bytes."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import urllib.request

OUT = Path(__file__).resolve().parent
ROOT = next(p for p in OUT.parents if (p / "AGENTS.md").is_file())


def digest(value):
    return hashlib.sha256(value).hexdigest()


def main():
    preparation = json.loads((OUT / "preparation.json").read_text(encoding="utf8"))
    base = f"http://127.0.0.1:{preparation['port']}"
    with urllib.request.urlopen(base + "/api/health", timeout=20) as response:
        assert response.status == 200
        raw_health = response.read()
    health = json.loads(raw_health)
    identity = health["server_identity"]
    expected = "oma-independent-checker/2:" + preparation["source_checkpoint"]
    assert health["status"] == "ok"
    assert identity["checker_version"] == identity["current_disk_checker_version"] == expected
    assert identity["source_changed"] is False and identity["startup_environment_matches"] is True
    assert identity["identity_error"] is None
    assert Path(identity["data_directory"]).resolve() == (ROOT / ".oma").resolve()
    assets = {}
    for relative, expected_sha in preparation["interface_files"].items():
        url_path = relative.removeprefix("ui/dist/")
        if url_path == "index.html":
            url_path = ""
        with urllib.request.urlopen(base + "/" + url_path, timeout=20) as response:
            assert response.status == 200
            payload = response.read()
            assert digest(payload) == expected_sha, relative
            assets[relative] = {"url": base + "/" + url_path, "sha256": digest(payload), "bytes": len(payload)}
    assert len(assets) == 6
    (OUT / "health.json").write_bytes(raw_health)
    result = {"status": "RESTORED_BACKEND_HTTP_AND_UNCHANGED_ASSETS_PASS",
        "observed_utc": datetime.now(timezone.utc).isoformat(), "base_url": base,
        "server_identity": identity, "health_sha256": digest(raw_health), "http_assets": assets,
        "preparation_sha256": digest((OUT / "preparation.json").read_bytes()),
        "script_sha256": digest(Path(__file__).read_bytes()), "recovery_enabled": False,
        "scope": "HTTP availability, executable identity and six existing interface assets; no UI refinement or new application regression"}
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"status": result["status"], "base_url": base, "checker_version": expected, "assets": len(assets)}))


if __name__ == "__main__":
    main()
