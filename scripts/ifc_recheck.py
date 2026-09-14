"""CLI wrapper for installed fresh-process IFC recheck."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from oma.ifc.recheck import recheck
if __name__ == "__main__":
    recheck(sys.argv[1])
