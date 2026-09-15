"""Run the exact fully validated coupled-pressure backend; no owner recovery."""
from pathlib import Path
import hashlib
import json
import os

ROOT = Path(__file__).resolve().parent
MANIFEST = Path('C:\\Users\\Davi\\Downloads\\oma\\evidence\\release\\validated-backend-general-tree-update\\e3c3bea38c864d18b46730de92a92187\\live-expected-source.json')
expected = json.loads(MANIFEST.read_text())
SOURCE = Path(expected["source_directory"])
EXPECTED = 'oma-independent-checker/2:edf555760245581599c33a06d99e1010f88f684a5c323ae00e3370f31f73448c'
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
