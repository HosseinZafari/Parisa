from setup import BACKEND, PYTHON, ROOT, run
import os
import shutil

run([PYTHON, "-m", "pytest", "-q"], BACKEND)
run(
    [shutil.which("npm.cmd" if os.name == "nt" else "npm"), "run", "check"],
    ROOT / "frontend",
)
run(
    [shutil.which("npm.cmd" if os.name == "nt" else "npm"), "run", "build"],
    ROOT / "frontend",
)
