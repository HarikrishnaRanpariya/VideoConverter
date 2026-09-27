# App Architecture & Extension Points

The app is a thin PySide6 GUI over bundled `ffmpeg`/`ffprobe`. It is organized as a
package so UI, media logic, and FFmpeg orchestration stay separate.

## Layout
```
app.py                      # Entry point: creates QApplication + MainWindow
videoconverter/
├── __init__.py             # App name, version, author, copyright metadata
├── ffmpeg.py               # Tool discovery (ffmpeg/ffprobe/ffplay), probe, duration
├── profiles.py             # FORMATS + PROFILES, argument builder (trim/audio), remux checks
├── conversion.py           # ConversionController: runs FFmpeg via QProcess, emits signals
├── downloader.py           # yt-dlp binary fetch/update + DownloadWorker/UpdateWorker (QThread)
├── preview.py              # VideoPreview widget (QMediaPlayer + QVideoWidget)
└── main_window.py          # MainWindow: wires widgets, previews, trim, folder pickers
```

## Responsibilities
- **ffmpeg.py** — pure functions, no Qt. `tool_path()` resolves the bundled binary
  (adds `.exe` on Windows), `probe_media()` returns codecs/duration/resolution via
  `ffprobe -show_streams -of json`, `read_duration()` returns seconds.
- **profiles.py** — pure data + one function. `FORMATS` describes containers;
  `PROFILES` describes codec recipes and which containers each allows.
  `build_arguments(job)` produces the FFmpeg argv list, including `-ss/-to` trim and
  `-progress pipe:1`.
- **conversion.py** — `ConversionController(QObject)` owns the `QProcess`, parses
  progress, and emits `progress(int)`, `log(str)`, `finished(bool)`. No widgets.
- **preview.py** — reusable player with play/pause, a seek slider, and
  `set_start()/set_end()` helpers used by the trim UI.
- **main_window.py** — only wiring/layout; delegates all real work to the modules above.

## Extension points
- **New codec profile** → append to `PROFILES` in `profiles.py`.
- **New container** → append to `FORMATS`; set which profiles it allows; update
  `_REMUX_VIDEO`/`_REMUX_AUDIO` so the remux pre-flight guard stays correct.
- **Audio extraction** → add an `audio_only=True` profile; `build_arguments`
  emits `-vn -map 0:a:0` and skips scaling/faststart.
- **New option (bitrate, scale, fps)** → add a field to the `ConversionJob` dataclass
  and honor it in `build_arguments()`; add a widget in `main_window.py`.
- **Trim** → `ConversionJob.start`/`.end` drive `-ss`/`-to`; duration for progress is
  `end - start` when a range is set.
- **URL download** → `downloader.py`; `DownloadWorker` runs the standalone yt-dlp
  binary, `UpdateWorker` refreshes it. Both run on a `QThread` from `main_window.py`.

## Data flow
`MainWindow` gathers UI state → builds a `ConversionJob` → `build_arguments(job)` →
`ConversionController.start(ffmpeg, args, target_duration)` → signals update the
progress bar/log → on success the output is loaded into the output `VideoPreview`.

## Testing without a GUI
`profiles.build_arguments()` and `ffmpeg.probe_media()` are Qt-free and unit-testable.
Validate argument lists by running them against a short sample and re-probing the output.
