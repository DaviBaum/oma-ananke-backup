"""Restore the fully validated fixed-section backend without recovering owners."""
from pathlib import Path
import uvicorn
from oma.api import create_app
from oma.build_identity import checker_version

EXPECTED = "oma-independent-checker/2:52bd5d29217117127da6dc0576a1626c8512ae7e145132ba9f9ef7b8ed12ea52"
assert checker_version() == EXPECTED
uvicorn.run(create_app(Path(__file__).resolve().parent, recover=False),
    host="127.0.0.1", port=8768, log_level="info", access_log=False)
