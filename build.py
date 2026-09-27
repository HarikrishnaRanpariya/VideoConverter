"""Cross-platform build helper for VideoConverter.

Runs the correct PyInstaller build for the current OS after verifying the
FFmpeg binaries are present. PyInstaller cannot cross-compile, so run this on
the OS you want to build for.

Usage:
    python build.py            # build for the current OS
    python build.py --check    # only verify prerequisites
"""

import argparse
import os
import subprocess
import sys

from videoconverter import ffmpeg

_ARTIFACT = {
    "win32": "dist/VideoConverter/VideoConverter.exe",
    "darwin": "dist/VideoConverter.app",
}


def check_prerequisites():
    missing = ffmpeg.available_tools()
    if missing:
        expected = ", ".join(missing)
        print(f"ERROR: missing FFmpeg binaries in bin/: {expected}")
        print("Add static ffmpeg/ffprobe for this OS to the bin folder first.")
        return False

    try:
        subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--version"],
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: PyInstaller is not installed. Run: pip install -r requirements.txt")
        return False

    return True


def build():
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "VideoConverter.spec", "--noconfirm"]
    )
    if result.returncode != 0:
        return result.returncode

    artifact = _ARTIFACT.get(sys.platform, "dist/VideoConverter/")
    print()
    if os.path.exists(artifact):
        print(f"Build succeeded: {artifact}")
    else:
        print(f"Build finished; see the dist/ folder (expected: {artifact}).")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="only verify prerequisites"
    )
    args = parser.parse_args()

    if not check_prerequisites():
        return 1
    if args.check:
        print("Prerequisites OK.")
        return 0
    return build()


if __name__ == "__main__":
    sys.exit(main())
