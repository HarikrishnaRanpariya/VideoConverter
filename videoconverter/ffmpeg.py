"""FFmpeg / FFprobe discovery and inspection helpers (no Qt dependencies)."""

import array
import atexit
import json
import os
import subprocess
import sys
import tempfile
import threading

# Background ffmpeg helpers (waveform, loudness) that must not outlive the app.
_active_processes = set()
_active_lock = threading.Lock()


def _track(process):
    with _active_lock:
        _active_processes.add(process)


def _untrack(process):
    with _active_lock:
        _active_processes.discard(process)


@atexit.register
def _kill_active_processes():
    with _active_lock:
        processes = list(_active_processes)
    for process in processes:
        if process.poll() is None:
            process.kill()


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
    ``video_codec``, ``audio_codec``, ``sample_rate`` (int Hz).
    Missing values are ``None`` or ``0.0``.
    """
    ffprobe = tool_path("ffprobe")

    if not os.path.isfile(ffprobe):
        raise FileNotFoundError("ffprobe was not found in the bin folder.")

    command = [
        ffprobe,
        "-v", "error",
        "-show_entries",
        "format=duration:stream=codec_type,codec_name,width,height,sample_rate",
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
        "sample_rate": None,
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
            try:
                info["sample_rate"] = int(stream.get("sample_rate"))
            except (TypeError, ValueError):
                info["sample_rate"] = None

    return info


_LOUDNORM_KEYS = ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")


class NoAudioError(RuntimeError):
    """The file has no audio stream to measure."""


def parse_loudnorm_json(text):
    """Extract the measurement dict from ``loudnorm=print_format=json`` stderr.

    Values are floats; a silent input reports ``-inf`` loudness.
    """
    start = text.rfind('"input_i"')
    if start < 0:
        return None
    open_brace = text.rfind("{", 0, start)
    close_brace = text.find("}", start)
    if open_brace < 0 or close_brace < 0:
        return None

    try:
        raw = json.loads(text[open_brace:close_brace + 1])
        return {key: float(raw[key]) for key in _LOUDNORM_KEYS}
    except (ValueError, KeyError, TypeError):
        return None


def measure_loudness(
    input_file,
    loudnorm="loudnorm=I=-23:TP=-1:LRA=11",
    start=None,
    end=None,
    duration=0.0,
    progress=None,
    cancelled=None,
):
    """Measure the first audio track with FFmpeg's ``loudnorm`` (pass 1).

    ``start``/``end`` (``HH:MM:SS.mmm``) restrict the measurement to the same
    range a trimmed conversion will encode. ``progress(fraction)`` is called
    as decoding advances when ``duration`` (seconds) is known. Returns the
    :func:`parse_loudnorm_json` dict, ``None`` if ``cancelled()`` became true,
    and raises :class:`NoAudioError` / ``RuntimeError`` on failure.
    """
    ffmpeg_path = tool_path("ffmpeg")

    if not os.path.isfile(ffmpeg_path):
        raise FileNotFoundError("ffmpeg was not found in the bin folder.")

    # Input-side seeking: output-side -ss/-to trims *after* -af, so loudnorm
    # would also measure the audio before the start point.
    command = [ffmpeg_path, "-hide_banner", "-nostdin"]
    if start:
        command += ["-ss", start]
    if end:
        command += ["-to", end]
    command += [
        "-i", input_file,
        "-map", "0:a:0",
        "-vn", "-sn", "-dn",
        "-af", f"{loudnorm}:print_format=json",
        "-progress", "pipe:1", "-nostats",
        "-f", "null", "-",
    ]

    # stderr goes to a temp file so a chatty input can never fill the pipe.
    with tempfile.TemporaryFile() as stderr_file:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=stderr_file,
            startupinfo=_no_window_startupinfo(),
        )
        _track(process)

        try:
            for raw_line in process.stdout:
                if cancelled is not None and cancelled():
                    process.kill()
                    return None

                line = raw_line.decode("utf-8", errors="replace").strip()
                if progress and duration > 0 and line.startswith("out_time_us="):
                    try:
                        seconds = int(line.split("=", 1)[1]) / 1_000_000
                    except ValueError:
                        continue
                    progress(max(0.0, min(1.0, seconds / duration)))
        finally:
            if process.poll() is None and cancelled is not None and cancelled():
                process.kill()
            process.stdout.close()
            return_code = process.wait()
            _untrack(process)

        if cancelled is not None and cancelled():
            return None

        stderr_file.seek(0)
        stderr = stderr_file.read().decode("utf-8", errors="replace")

    if return_code != 0:
        if "matches no streams" in stderr:
            raise NoAudioError("The file has no audio track.")
        raise RuntimeError(stderr.strip()[-600:] or "ffmpeg failed")

    result = parse_loudnorm_json(stderr)
    if result is None:
        raise RuntimeError("Could not read the loudness measurement.")
    return result


WAVEFORM_SAMPLE_RATE = 8000
_WAVEFORM_WINDOW = 80  # samples per raw peak (10 ms at 8 kHz)


def read_waveform(input_file, points=1000, cancelled=None):
    """Return the first audio track's peak envelope as ``points`` floats.

    Each value is the absolute peak (0.0–1.0 of full scale) for one slice of
    the file, so input and output loudness can be compared directly. The
    audio is decoded to 8 kHz mono 16-bit PCM and streamed, so memory stays
    small even for long files.

    Returns ``[]`` when the file has no audio, or ``None`` if ``cancelled``
    (a zero-argument callable) returned ``True`` while decoding.
    """
    ffmpeg_path = tool_path("ffmpeg")

    if not os.path.isfile(ffmpeg_path):
        raise FileNotFoundError("ffmpeg was not found in the bin folder.")

    command = [
        ffmpeg_path,
        "-v", "error",
        "-nostdin",
        "-i", input_file,
        "-map", "0:a:0?",
        "-vn", "-sn", "-dn",
        "-ac", "1",
        "-ar", str(WAVEFORM_SAMPLE_RATE),
        "-f", "s16le",
        "-acodec", "pcm_s16le",
        "pipe:1",
    ]

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        startupinfo=_no_window_startupinfo(),
    )
    _track(process)

    window_bytes = _WAVEFORM_WINDOW * 2
    raw_peaks = []
    pending = b""

    try:
        while True:
            if cancelled is not None and cancelled():
                process.kill()
                return None

            chunk = process.stdout.read(window_bytes * 256)
            if not chunk:
                break

            data = pending + chunk
            usable = len(data) - (len(data) % window_bytes)
            pending = data[usable:]
            raw_peaks.extend(_window_peaks(data[:usable], _WAVEFORM_WINDOW))

        if len(pending) >= 2:
            usable = len(pending) - (len(pending) % 2)
            raw_peaks.extend(_window_peaks(pending[:usable], usable // 2))
    finally:
        if process.poll() is None:
            process.kill()
        process.stdout.close()
        process.wait()
        _untrack(process)

    return _resample_peaks(raw_peaks, points)


def _window_peaks(data, window):
    """Absolute peak (0.0–1.0) for each ``window`` samples of s16le ``data``."""
    samples = array.array("h")
    samples.frombytes(data)
    if sys.byteorder == "big":
        samples.byteswap()

    peaks = []
    for start in range(0, len(samples), window):
        block = samples[start:start + window]
        if block:
            peak = max(max(block), -min(block))
            peaks.append(min(1.0, peak / 32768.0))
    return peaks


def _resample_peaks(raw_peaks, points):
    """Reduce (by max) or keep ``raw_peaks`` so the result has ≤ ``points``."""
    if not raw_peaks or points <= 0:
        return []
    if len(raw_peaks) <= points:
        return list(raw_peaks)

    result = []
    total = len(raw_peaks)
    for index in range(points):
        start = index * total // points
        end = max(start + 1, (index + 1) * total // points)
        result.append(max(raw_peaks[start:end]))
    return result


def read_duration(input_file):
    """Return the input duration in seconds (0.0 if it cannot be read)."""
    try:
        return probe_media(input_file)["duration"]
    except Exception:
        return 0.0
