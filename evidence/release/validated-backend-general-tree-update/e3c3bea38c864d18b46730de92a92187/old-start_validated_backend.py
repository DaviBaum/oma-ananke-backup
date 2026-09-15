"""Run the exact fully validated coupled-pressure backend; no owner recovery."""
from pathlib import Path
import hashlib
import json
import os

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT.parent / "evidence/release/validated-backend-shared-tree-update/c304a60d38e9455d8b61fe74c8c5cb83/live-expected-source.json"
expected = json.loads(MANIFEST.read_text())
SOURCE = Path(expected["source_directory"])
EXPECTED = "oma-independent-checker/2:33a20d125bba02a298d12048a5b6227e51a98d8a043b999097d94a8d88b67b95"
assert expected["checker_version"] == EXPECTED
assert os.environ["PYTHONPATH"] == str(SOURCE) and os.environ["OMA_EXECUTABLE_BUILD"] == EXPECTED
assert {p.relative_to(SOURCE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in SOURCE.rglob("*.py")} == expected["files"]
assert len(expected["files"]) == 112

import uvicorn
import oma
from oma.api import create_app
from oma.build_identity import checker_version

assert Path(oma.__file__).resolve() == (SOURCE / "oma/__init__.py").resolve()
assert checker_version() == EXPECTED
uvicorn.run(create_app(ROOT, recover=False),
    host="127.0.0.1", port=8768, log_level="info", access_log=False)
