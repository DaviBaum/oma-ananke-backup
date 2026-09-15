"""Run a source-pinned test checkpoint while other developers continue edits."""
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from oma.build_identity import frozen_environment

if __name__ == "__main__":
    env = frozen_environment(Path(".oma") / "test-builds")
    print("Testing immutable executable:", env["OMA_EXECUTABLE_BUILD"], flush=True)
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", "-o", "pythonpath=", *sys.argv[1:]], env=env))
