"""End-to-end smoke test for the VideoConverter conversion engine.

Runs on any OS that has the real ffmpeg/ffprobe binaries in ``bin`` (on Windows
they are ``ffmpeg.exe``/``ffprobe.exe``). It is Qt-free: it validates the parts
of the app that do the actual work — argument building, conversion, and output
verification — without needing the GUI.

Usage (from the project root):
    python tests/smoke_test.py

Exit code 0 means every case passed.
"""

import os
import subprocess
import sys
import tempfile

# Make the project root importable when run as ``python tests/smoke_test.py``.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from videoconverter import ffmpeg, profiles  # noqa: E402


def _run(command):
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        startupinfo=ffmpeg._no_window_startupinfo(),
    )


def make_source(path, seconds=4):
    """Create a synthetic H.264/AAC MP4 so remux and transcode both apply."""
    command = [
        ffmpeg.tool_path("ffmpeg"),
        "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={seconds}:size=320x240:rate=30",
        "-f", "lavfi", "-i", f"sine=frequency=1000:duration={seconds}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest",
        path,
    ]
    result = _run(command)
    if result.returncode != 0:
        raise RuntimeError(f"Could not build source clip:\n{result.stderr}")


def convert(job):
    args = [ffmpeg.tool_path("ffmpeg")] + profiles.build_arguments(job)
    return _run(args)


def check(label, condition, detail=""):
    mark = "PASS" if condition else "FAIL"
    print(f"[{mark}] {label}" + (f" — {detail}" if detail and not condition else ""))
    return condition


def main():
    missing = ffmpeg.available_tools()
    if missing:
        print("Cannot run: missing tools in bin/: " + ", ".join(missing))
        print("Place the real ffmpeg/ffprobe binaries in the bin folder first.")
        return 1

    passed = True
    with tempfile.TemporaryDirectory() as work:
        source = os.path.join(work, "source.mp4")
        make_source(source, seconds=4)
        src_info = ffmpeg.probe_media(source)
        passed &= check(
            "probe source", src_info["duration"] > 3.5,
            f"duration={src_info['duration']}",
        )

        cases = [
            ("remux -> MOV", "remux", "MOV", "mov", None, None, None),
            ("remux -> MKV", "remux", "MKV", "mkv", None, None, None),
            ("h264 -> MP4", "h264", "MP4", "mp4", "h264", None, None),
            ("h265 -> MP4", "h265", "MP4", "mp4", "hevc", None, None),
            ("vp9  -> WebM", "vp9", "WebM", "webm", "vp9", None, None),
            ("prores-> MOV", "prores", "MOV", "mov", "prores", None, None),
            # Trim: convert seconds 1..3 => ~2s output.
            ("h264 trim 1-3s", "h264", "MP4", "mp4", "h264",
             "00:00:01.000", "00:00:03.000"),
            # Downscale to 120px height.
            ("h264 scale 120", "h264", "MP4", "mp4", "h264", None, None),
        ]

        for row in cases:
            label, key, fmt, ext = row[0], row[1], row[2], row[3]
            expect_vcodec, start, end = row[4], row[5], row[6]
            scale = 120 if label.endswith("scale 120") else None

            out = os.path.join(work, f"{key}_{fmt}.{ext}")
            job = profiles.ConversionJob(
                input_file=source,
                output_file=out,
                profile_key=key,
                format_name=fmt,
                start=start,
                end=end,
                scale_height=scale,
            )
            result = convert(job)
            if not check(f"{label}: ffmpeg exit 0", result.returncode == 0,
                         result.stderr[-400:]):
                passed = False
                continue
            if not check(f"{label}: output exists", os.path.isfile(out)):
                passed = False
                continue

            info = ffmpeg.probe_media(out)

            if expect_vcodec:
                passed &= check(
                    f"{label}: video codec == {expect_vcodec}",
                    info["video_codec"] == expect_vcodec,
                    f"got {info['video_codec']}",
                )
            if start and end:
                passed &= check(
                    f"{label}: duration ~2s",
                    1.5 <= info["duration"] <= 2.6,
                    f"got {info['duration']}",
                )
            if scale:
                passed &= check(
                    f"{label}: height == {scale}",
                    info["height"] == scale,
                    f"got {info['height']}",
                )

    print()
    print("RESULT:", "ALL PASSED" if passed else "FAILURES DETECTED")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
