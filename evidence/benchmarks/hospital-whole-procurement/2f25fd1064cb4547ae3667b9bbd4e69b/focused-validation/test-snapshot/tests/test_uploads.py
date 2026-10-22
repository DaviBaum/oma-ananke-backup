from pathlib import Path
import hashlib

from fastapi.testclient import TestClient
import pytest

from oma.api import create_app


IFC = b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n"


def test_upload_retry_bytes_conflict_and_missing_asset_recovery(tmp_path):
    app = create_app(tmp_path / "engine")
    with TestClient(app) as client:
        url = "/api/uploads?filename=building.ifc&idempotency_key=upload-1"
        headers = {"Content-Type": "application/octet-stream"}
        response = client.post(url, content=IFC, headers=headers)
        assert response.status_code == 201, response.text
        receipt = response.json()
        assert receipt["sha256"] == hashlib.sha256(IFC).hexdigest()
        assert receipt["engineering_checks"] == "NOT_RUN"
        path = Path(receipt["path"])
        assert path.read_bytes() == IFC
        assert client.post(url, content=IFC, headers=headers).json() == receipt
        assert client.post(url, content=IFC + b"\n", headers=headers).status_code == 409
        path.unlink()
        assert client.post(url, content=IFC, headers=headers).json() == receipt
        assert path.read_bytes() == IFC
        path.write_bytes(b"corrupted immutable upload")
        assert client.post(url, content=IFC, headers=headers).status_code == 422
        assert not list((tmp_path / "engine" / "uploads").glob(".pending-*"))


@pytest.mark.parametrize("name", ["../bad.ifc", "C:\\bad.ifc", "CON.test.ifc", 'bad".ifc', "bad\n.ifc", "test.txt"])
def test_upload_rejects_nonlocal_or_invalid_windows_names(tmp_path, name):
    with TestClient(create_app(tmp_path / "engine")) as client:
        response = client.post("/api/uploads", params={"filename": name}, content=IFC,
                               headers={"Content-Type": "application/octet-stream"})
        assert response.status_code == 422


def test_upload_enforces_actual_stream_limit_and_cleans_partial_file(tmp_path, monkeypatch):
    import oma.uploads as uploads
    monkeypatch.setattr(uploads, "MAX_BYTES", 40)
    app = create_app(tmp_path / "engine")
    with TestClient(app) as client:
        headers = {"Content-Type": "application/octet-stream"}
        response = client.post("/api/uploads?filename=big.ifc", content=iter([IFC[:30], IFC[30:]]), headers=headers)
        assert response.status_code == 413
        assert not list((tmp_path / "engine" / "uploads").glob(".pending-*"))
        assert client.post("/api/uploads?filename=bad.ifc", content=b"<html>invalid response</html>", headers=headers).status_code == 422
        monkeypatch.setattr(uploads, "MAX_BYTES", 4 * 1024**3)
        assert client.post("/api/uploads?filename=bad.ifc", content=IFC).status_code == 415
        assert client.post("/api/uploads?filename=bad.ifc", content=b"", headers=headers).status_code == 413
