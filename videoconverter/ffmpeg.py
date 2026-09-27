"""FFmpeg / FFprobe discovery and inspection helpers (no Qt dependencies)."""

import json
import os
import subprocess
import sys


def application_directory():
    """Directory that contains the bundled ``bin`` folder.

    Uses ``_MEIPASS`` when frozen by PyInstaller, otherwise the project root.
    """
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))

    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def tool_path(tool_name):
    """Return the bundled path for ``ffmpeg``/``ffprobe``/``ffplay``.

    Appends ``.exe`` on Windows so the same code runs during cross-platform
    development.
    """
    binary = f"{tool_name}.exe" if os.name == "nt" else tool_name
    return os.path.join(application_directory(), "bin", binary)


def _no_window_startupinfo():
    """Hide the console window when spawning tools on Windows."""
    if os.name != "nt":
        return None

    startup_info = subprocess.STARTUPINFO()
    startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return startup_info


def available_tools():
    """Return the list of expected tool names that are missing from ``bin``."""
    missing = []

    for tool in ("ffmpeg", "ffprobe"):
        if not os.path.isfile(tool_path(tool)):
            missing.append(os.path.basename(tool_path(tool)))

    return missing


def probe_media(input_file):
    """Return a dict describing the input via ``ffprobe`` JSON output.

    Keys: ``duration`` (float seconds), ``width``, ``height``,
    ``video_codec``, ``audio_codec``. Missing values are ``None`` or ``0.0``.
    """
    ffprobe = tool_path("ffprobe")

    if not os.path.isfile(ffprobe):
        raise FileNotFoundError("ffprobe was not found in the bin folder.")

    command = [
        ffprobe,
        "-v", "error",
        "-show_entries",
        "format=duration:stream=codec_type,codec_name,width,height",
        "-of", "json",
        input_file,
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
        startupinfo=_no_window_startupinfo(),
    )

    data = json.loads(result.stdout or "{}")

    info = {
        "duration": 0.0,
        "width": None,
        "height": None,
        "video_codec": None,
        "audio_codec": None,
    }

    try:
        info["duration"] = float(data.get("format", {}).get("duration", 0.0))
    except (TypeError, ValueError):
        info["duration"] = 0.0

    for stream in data.get("streams", []):
        codec_type = stream.get("codec_type")

        if codec_type == "video" and info["video_codec"] is None:
            info["video_codec"] = stream.get("codec_name")
            info["width"] = stream.get("width")
            info["height"] = stream.get("height")
        elif codec_type == "audio" and info["audio_codec"] is None:
            info["audio_codec"] = stream.get("codec_name")

    return info


def read_duration(input_file):
    """Return the input duration in seconds (0.0 if it cannot be read)."""
    try:
        return probe_media(input_file)["duration"]
    except Exception:
        return 0.0
