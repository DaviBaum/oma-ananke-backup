"""Run the validated local Hospital-clearance backend; no owner recovery."""
from pathlib import Path
import hashlib
import json
import os

ROOT = Path(__file__).resolve().parent
MANIFEST = Path('C:\\Users\\Davi\\Downloads\\oma\\evidence\\release\\validated-backend-hospital-update\\19be511c32ca447da2c213f0ce377940\\live-expected-source.json')
expected = json.loads(MANIFEST.read_text())
SOURCE = Path(expected["source_directory"])
EXPECTED = 'oma-independent-checker/2:06aa865600b4ab2dc8f42f77b2cb5f82816dec99bbf8a1ff5f67673fb44c1949'
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
