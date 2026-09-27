"""Download media from a URL using the official standalone yt-dlp binary.

Reliability comes from keeping yt-dlp current: the binary is fetched into a
writable folder on first use and can be refreshed on demand (this mirrors how
commercial downloaders stay working as sites change). It is run as a subprocess
and uses the bundled FFmpeg to merge streams.

This is an alternative *input source*; the downloaded file feeds the normal
conversion pipeline. It downloads only content the user is permitted to
download and does not bypass any access restriction, DRM, or login gate.
"""

import os
import re
import stat
import subprocess
import sys
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from urllib.request import urlretrieve

from PySide6.QtCore import QObject, Signal

from . import ffmpeg

_RELEASE = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/{asset}"
_PERCENT = re.compile(r"([\d.]+)%")


def normalize_url(url):
    """Reduce a YouTube URL to the single target video.

    Strips playlist/radio parameters (``list``, ``start_radio``, ``index`` …)
    so a pasted mix/playlist link downloads only the one video, keeping just
    ``v`` (and ``t`` if present). Non-YouTube URLs are returned unchanged.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return url

    host = (parsed.netloc or "").lower()
    if "youtube.com" in host:
        query = parse_qs(parsed.query)
        keep = {}
        if "v" in query:
            keep["v"] = query["v"][0]
        if "t" in query:
            keep["t"] = query["t"][0]
        return urlunparse(parsed._replace(query=urlencode(keep)))
    if "youtu.be" in host:
        return urlunparse(parsed._replace(query=""))
    return url


def _tools_dir():
    directory = os.path.join(os.path.expanduser("~"), ".videoconverter", "bin")
    os.makedirs(directory, exist_ok=True)
    return directory


def _release_asset():
    if sys.platform.startswith("win"):
        return "yt-dlp.exe"
    if sys.platform == "darwin":
        return "yt-dlp_macos"
    return "yt-dlp_linux"


def binary_path():
    name = "yt-dlp.exe" if os.name == "nt" else "yt-dlp"
    return os.path.join(_tools_dir(), name)


def download_ytdlp(log=None):
    """Fetch the latest yt-dlp binary for this OS into the tools folder."""
    url = _RELEASE.format(asset=_release_asset())
    dest = binary_path()
    if log:
        log(f"Fetching latest yt-dlp: {url}")

    tmp = dest + ".tmp"
    urlretrieve(url, tmp)
    os.replace(tmp, dest)

    if os.name != "nt":
        mode = os.stat(dest).st_mode
        os.chmod(dest, mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return dest


def ensure_ytdlp(log=None):
    """Return the yt-dlp binary path, downloading it if not present yet."""
    dest = binary_path()
    if not os.path.isfile(dest):
        download_ytdlp(log)
    return dest


def ytdlp_version(path):
    try:
        result = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            startupinfo=ffmpeg._no_window_startupinfo(),
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


class DownloadWorker(QObject):
    """Runs a single yt-dlp download, reporting progress/result via signals."""

    progress = Signal(int)          # 0..100
    log = Signal(str)
    finished = Signal(bool, str)    # (success, output_path_or_error)

    def __init__(self, url, dest_dir):
        super().__init__()
        self._url = url
        self._dest_dir = dest_dir

    def run(self):
        try:
            binary = ensure_ytdlp(self.log.emit)
        except Exception as error:
            self.finished.emit(False, f"Could not obtain yt-dlp: {error}")
            return

        ffmpeg_dir = os.path.join(ffmpeg.application_directory(), "bin")
        url = normalize_url(self._url)
        outtmpl = os.path.join(self._dest_dir, "%(title).80s.%(ext)s")

        command = [
            binary, url,
            "--no-playlist",
            "-f", "bv*+ba/b",
            "--merge-output-format", "mp4",
            "--ffmpeg-location", ffmpeg_dir,
            "-o", outtmpl,
            "--newline",
            "--no-warnings",
            "--retries", "3",
            "--progress-template", "download:PROGRESS %(progress._percent_str)s",
            "--print", "after_move:FINAL %(filepath)s",
        ]

        self.log.emit(f"Downloading: {url}")
        final_path = None
        errors = []

        try:
            proc = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                startupinfo=ffmpeg._no_window_startupinfo(),
            )
        except Exception as error:
            self.finished.emit(False, str(error))
            return

        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            if line.startswith("PROGRESS"):
                match = _PERCENT.search(line)
                if match:
                    try:
                        self.progress.emit(
                            max(0, min(100, int(float(match.group(1)))))
                        )
                    except ValueError:
                        pass
            elif line.startswith("FINAL "):
                final_path = line[len("FINAL "):].strip()
            else:
                errors.append(line)
                self.log.emit(line)

        code = proc.wait()
        if code == 0 and final_path and os.path.isfile(final_path):
            self.progress.emit(100)
            self.finished.emit(True, final_path)
        else:
            message = "\n".join(errors[-6:]) or f"yt-dlp exited with code {code}"
            self.finished.emit(False, message)


class UpdateWorker(QObject):
    """Downloads/refreshes the yt-dlp binary to the latest release."""

    log = Signal(str)
    finished = Signal(bool, str)    # (success, version_or_error)

    def run(self):
        try:
            path = download_ytdlp(self.log.emit)
            self.finished.emit(True, ytdlp_version(path))
        except Exception as error:
            self.finished.emit(False, str(error))
