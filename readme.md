# Video Converter

A Windows desktop application for converting, previewing, and trimming video
files. It is a GUI front end for **FFmpeg** built with **PySide6 (Qt)** — the app
inspects your video with `ffprobe`, builds the correct FFmpeg command, runs it in
the background, and shows live progress. It never encodes video itself.

## Features

- Convert to **MP4, MOV, MKV, WebM**.
- Conversion modes: **Remux** (lossless copy), **H.264/AAC**, **H.265/AAC**,
  **VP9/Opus**, **ProRes/PCM**.
- **In-app video preview** of both the input and the converted output.
- **Trim**: convert only a selected portion of the video, capturing start/end
  from the preview playhead.
- Optional **downscaling** (2160p → 480p).
- Live progress bar, full FFmpeg log, and cancel support.
- Only offers **valid format/codec combinations** (see [docs/FORMATS.md](docs/FORMATS.md)).

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | How to use the application. |
| [docs/FORMATS.md](docs/FORMATS.md) | Container/codec architecture and valid combinations. |
| [docs/ALGORITHMS.md](docs/ALGORITHMS.md) | How remux and transcode conversions work. |
| [.github/skills/video-conversion/](.github/skills/video-conversion/SKILL.md) | Agent skill: deep FFmpeg/codec knowledge for extending the app. |

## Architecture

The app is a thin Qt GUI over separated, testable modules.

```
app.py                      # Entry point: QApplication + MainWindow
videoconverter/
├── ffmpeg.py               # Tool discovery + ffprobe inspection (no Qt)
├── profiles.py             # FORMATS/PROFILES registries + argument builder (no Qt)
├── conversion.py           # ConversionController: QProcess + progress parsing
├── preview.py              # VideoPreview widget (Qt Multimedia)
└── main_window.py          # Layout and wiring
bin/                        # Bundled ffmpeg / ffprobe (+ optional ffplay)
docs/                       # User + format + algorithm documentation
```

Design principles:

- **Separation of concerns** — media logic (`ffmpeg.py`, `profiles.py`) is Qt-free
  and unit-testable; only `main_window.py`/`preview.py` touch widgets.
- **Data-driven** — adding a codec/format means editing the `PROFILES`/`FORMATS`
  registries in `profiles.py`, not the UI.
- **Non-blocking** — FFmpeg runs via `QProcess`, keeping the UI responsive.

See [architecture reference](.github/skills/video-conversion/references/architecture.md)
for extension points.

## Requirements

- **Windows** and **macOS** are both supported targets (Linux runs from source).
- FFmpeg binaries in `bin/`, named per platform. Both sets can coexist:
  - Windows: `bin/ffmpeg.exe`, `bin/ffprobe.exe`
  - macOS/Linux: `bin/ffmpeg`, `bin/ffprobe` (no extension, and executable)
- Qt Multimedia plugins for in-app preview (bundled by PyInstaller; the app still
  converts without them).

> Use **static** FFmpeg builds so the bundled app runs on machines without
> Homebrew/system libraries. On macOS a Homebrew `ffmpeg` depends on Homebrew
> dylibs and may not run when copied into another machine's app bundle.

## Run from source

Windows:

```bat
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
python app.py
```

macOS / Linux:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Place the matching FFmpeg binaries in `bin/` first (see Requirements). On
macOS/Linux mark them executable: `chmod +x bin/ffmpeg bin/ffprobe`.

## Build a native application

The same spec builds for whichever OS you run it on — it selects the correct
FFmpeg binaries and produces the right bundle type.

Windows (produces `dist/VideoConverter/VideoConverter.exe`):

```bat
pyinstaller VideoConverter.spec
```

macOS (produces `dist/VideoConverter.app`):

```bash
pyinstaller VideoConverter.spec
```

The spec bundles the platform's FFmpeg binaries and the Qt Multimedia plugins
needed for preview. UPX compression is applied on Windows only. Build on the
target OS — PyInstaller does not cross-compile.

### Build helpers

- `python build.py` — verifies prerequisites, then builds for the current OS.
- `python build.py --check` — only checks that FFmpeg + PyInstaller are ready.
- `make install | run | test | build | clean` — convenience targets (macOS/Linux).
- **CI**: [.github/workflows/build.yml](.github/workflows/build.yml) builds Windows
  and macOS artifacts on native runners (downloading static FFmpeg automatically)
  and uploads them on every push/PR.

## Extending

1. Load the **video-conversion** skill (type `/` in chat, or it loads
   automatically) for codec/format guidance.
2. Add a `Profile` or `OutputFormat` to
   [videoconverter/profiles.py](videoconverter/profiles.py).
3. Verify the generated arguments by running FFmpeg on a short sample and
   re-probing the output with `ffprobe`.
