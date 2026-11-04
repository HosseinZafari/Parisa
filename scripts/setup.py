"""راه‌اندازی محلی بدون نیاز به کلید API یا دسترسی ابر."""

from pathlib import Path
import os
import shutil
import subprocess
import venv

ROOT = Path(__file__).resolve().parents[1]
os.environ["PYTHONUTF8"] = "1"
BACKEND = ROOT / "backend"
PYTHON = BACKEND / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run(args, cwd=ROOT):
    subprocess.run([str(a) for a in args], cwd=cwd, check=True)


def setup():
    if not (ROOT / ".env").exists():
        shutil.copyfile(ROOT / ".env.example", ROOT / ".env")
    if not PYTHON.exists():
        venv.create(BACKEND / ".venv", with_pip=True)
    uv = shutil.which("uv")
    if uv:
        run(
            [
                uv,
                "pip",
                "install",
                "--python",
                PYTHON,
                "-r",
                BACKEND / "requirements.txt",
            ]
        )
    else:
        run([PYTHON, "-m", "pip", "install", "-r", BACKEND / "requirements.txt"])
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    run(
        [npm, "ci" if (ROOT / "frontend/package-lock.json").exists() else "install"],
        ROOT / "frontend",
    )
    run([PYTHON, "-m", "app.cli", "migrate"], BACKEND)
    print("راه‌اندازی انجام شد. برای اجرا: npm run dev")


if __name__ == "__main__":
    setup()
