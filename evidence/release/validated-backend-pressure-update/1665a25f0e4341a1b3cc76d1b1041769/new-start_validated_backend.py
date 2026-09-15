"""Run the exact fully validated coupled-pressure backend; no owner recovery."""
from pathlib import Path
import hashlib
import json
import os

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT.parent / "evidence/release/validated-backend-pressure-update/1665a25f0e4341a1b3cc76d1b1041769/live-expected-source.json"
expected = json.loads(MANIFEST.read_text())
SOURCE = Path(expected["source_directory"])
EXPECTED = "oma-independent-checker/2:5e8fe9659cfde60f84f5cf93f38a1959428b3e7522de741e905d1f505db2b73c"
assert expected["checker_version"] == EXPECTED
assert os.environ["PYTHONPATH"] == str(SOURCE) and os.environ["OMA_EXECUTABLE_BUILD"] == EXPECTED
assert {p.relative_to(SOURCE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in SOURCE.rglob("*.py")} == expected["files"]
assert len(expected["files"]) == 107

import uvicorn
import oma
from oma.api import create_app
from oma.build_identity import checker_version

assert Path(oma.__file__).resolve() == (SOURCE / "oma/__init__.py").resolve()
assert checker_version() == EXPECTED
uvicorn.run(create_app(ROOT, recover=False),
    host="127.0.0.1", port=8768, log_level="info", access_log=False)
