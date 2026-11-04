import os
import shutil
import signal
import subprocess
import time

from setup import ROOT, BACKEND, PYTHON, run, setup

if not PYTHON.exists() or not (ROOT / "frontend/node_modules").exists():
    setup()
else:
    run([PYTHON, "-m", "app.cli", "migrate"], BACKEND)

processes = []
try:
    options = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    processes.append(
        subprocess.Popen(
            [
                str(PYTHON),
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
                "--no-access-log",
            ],
            cwd=BACKEND,
            **options,
        )
    )
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    processes.append(
        subprocess.Popen(
            [npm, "run", "dev", "--", "--host", "127.0.0.1"],
            cwd=ROOT / "frontend",
            **options,
        )
    )
    print(
        "برنامه: http://localhost:5173\nمستندات رابط: http://127.0.0.1:8000/docs",
        flush=True,
    )
    while all(p.poll() is None for p in processes):
        time.sleep(0.5)
except KeyboardInterrupt:
    pass
finally:
    for process in processes:
        if process.poll() is None:
            if os.name == "nt":
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(process.pid, signal.SIGTERM)
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
