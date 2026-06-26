#!/usr/bin/env python3
"""Bootstrap runner for the video-audio-transcriber skill.

This file intentionally uses only the Python standard library. It checks the
runtime, creates a skill-local virtual environment when needed, installs
faster-whisper, and then delegates to transcribe_media.py inside the venv.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

MIN_PYTHON = (3, 9)
REQUIRED_PACKAGES = ["faster-whisper>=1.1.0"]


def skill_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def venv_dir() -> Path:
    custom = os.environ.get("VIDEO_TRANSCRIBER_VENV")
    return Path(custom).expanduser().resolve() if custom else skill_dir() / ".venv"


def venv_python() -> Path:
    if platform.system().lower().startswith("win"):
        return venv_dir() / "Scripts" / "python.exe"
    return venv_dir() / "bin" / "python"


def print_python_install_instructions() -> None:
    print("\nPython 3.9+ with venv/pip is required. Install it with one of these commands:\n")
    print("Ubuntu / Debian / WSL:")
    print("  sudo apt update")
    print("  sudo apt install -y python3 python3-venv python3-pip\n")
    print("macOS with Homebrew:")
    print("  brew install python\n")
    print("Windows PowerShell:")
    print("  winget install Python.Python.3.12\n")


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("$ " + " ".join(quote_arg(part) for part in cmd))
    return subprocess.run(cmd, text=True, check=check)


def quote_arg(arg: str) -> str:
    if any(ch.isspace() for ch in arg) or any(ch in arg for ch in ['"', "'", "(", ")"]):
        return repr(arg)
    return arg


def ensure_base_python() -> None:
    if sys.version_info < MIN_PYTHON:
        print(f"ERROR: Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ required, found {platform.python_version()}.", file=sys.stderr)
        print_python_install_instructions()
        raise SystemExit(2)

    try:
        import venv  # noqa: F401
    except Exception:
        print("ERROR: Python venv module is missing.", file=sys.stderr)
        print_python_install_instructions()
        raise SystemExit(2)


def create_venv() -> None:
    ensure_base_python()
    if venv_python().exists():
        return

    print(f"Creating virtual environment: {venv_dir()}")
    try:
        run([sys.executable, "-m", "venv", str(venv_dir())])
    except subprocess.CalledProcessError:
        print("\nCould not create the virtual environment.", file=sys.stderr)
        print_python_install_instructions()
        raise SystemExit(2)


def package_available(package: str) -> bool:
    py = venv_python()
    if not py.exists():
        return False
    code = "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('faster_whisper') else 1)"
    return subprocess.run([str(py), "-c", code]).returncode == 0


def install_packages() -> None:
    py = venv_python()
    if not py.exists():
        create_venv()

    if package_available("faster_whisper"):
        return

    print("Installing Python dependencies into the skill-local venv...")
    try:
        run([str(py), "-m", "pip", "install", "--upgrade", "pip"])
        run([str(py), "-m", "pip", "install", *REQUIRED_PACKAGES])
    except subprocess.CalledProcessError as exc:
        print("\nDependency installation failed.", file=sys.stderr)
        print("Manual install commands:", file=sys.stderr)
        print(f"  cd {quote_arg(str(skill_dir()))}", file=sys.stderr)
        print("  python3 -m venv .venv", file=sys.stderr)
        print("  . .venv/bin/activate", file=sys.stderr)
        print("  python -m pip install --upgrade pip", file=sys.stderr)
        print("  python -m pip install 'faster-whisper>=1.1.0'", file=sys.stderr)
        raise SystemExit(exc.returncode)


def check_environment(allow_install: bool) -> int:
    print("Video Audio Transcriber dependency check")
    print(f"System: {platform.system()} {platform.release()}")
    print(f"Current Python: {platform.python_version()} at {sys.executable}")
    print(f"Skill directory: {skill_dir()}")
    print(f"Virtual environment: {venv_dir()}")

    ensure_base_python()

    if not venv_python().exists():
        if allow_install:
            create_venv()
        else:
            print("Missing venv. Run without --no-install to create it automatically.")
            return 1

    if not package_available("faster_whisper"):
        if allow_install:
            install_packages()
        else:
            print("Missing package: faster-whisper. Run without --no-install to install it automatically.")
            return 1

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        print(f"Optional ffmpeg CLI found: {ffmpeg}")
    else:
        print("Optional ffmpeg CLI not found. This is usually fine: faster-whisper uses PyAV for decoding.")

    print("OK: dependencies are ready.")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap and run local video/audio transcription with faster-whisper.",
        add_help=True,
    )
    parser.add_argument("--check", action="store_true", help="Check and prepare dependencies, then exit.")
    parser.add_argument("--no-install", action="store_true", help="Do not create venv or install dependencies automatically.")
    parser.add_argument("transcriber_args", nargs=argparse.REMAINDER, help="Arguments passed to transcribe_media.py")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    allow_install = not args.no_install

    if args.check:
        return check_environment(allow_install=allow_install)

    if not args.transcriber_args:
        print("ERROR: provide a file or folder path to transcribe, or use --check.", file=sys.stderr)
        print("Example:")
        print(f"  python3 {quote_arg(str(Path(__file__).resolve()))} /path/to/video.mp4 --language nl --model medium")
        return 2

    check_result = check_environment(allow_install=allow_install)
    if check_result != 0:
        return check_result

    transcriber = skill_dir() / "scripts" / "transcribe_media.py"
    cmd = [str(venv_python()), str(transcriber), *args.transcriber_args]
    result = run(cmd, check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
