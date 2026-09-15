"""Run the exact fully validated coupled-pressure backend; no owner recovery."""
from pathlib import Path
import hashlib
import json
import os

ROOT = Path(__file__).resolve().parent
MANIFEST = Path('C:\\Users\\Davi\\Downloads\\oma\\evidence\\release\\validated-backend-f73-update\\dd31cd72c26c467d9c1b7de0af7c126b\\live-expected-source.json')
expected = json.loads(MANIFEST.read_text())
SOURCE = Path(expected["source_directory"])
EXPECTED = 'oma-independent-checker/2:f73a8793ae0df76d9ec53400cec18b05d2731f63c735b225c2246fee62df6b21'
assert expected["checker_version"] == EXPECTED
assert os.environ["PYTHONPATH"] == str(SOURCE) and os.environ["OMA_EXECUTABLE_BUILD"] == EXPECTED
assert {p.relative_to(SOURCE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in SOURCE.rglob("*.py")} == expected["files"]
assert len(expected["files"]) == 114

import uvicorn
import oma
from oma.api import create_app
from oma.build_identity import checker_version

assert Path(oma.__file__).resolve() == (SOURCE / "oma/__init__.py").resolve()
assert checker_version() == EXPECTED
uvicorn.run(create_app(ROOT, recover=False),
    host="127.0.0.1", port=8768, log_level="info", access_log=False)
