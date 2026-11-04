import sys
from setup import BACKEND, PYTHON, run

run([PYTHON, "-m", "app.cli", *sys.argv[1:]], BACKEND)
