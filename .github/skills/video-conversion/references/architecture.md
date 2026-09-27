# App Architecture & Extension Points

The app is a thin PySide6 GUI over bundled `ffmpeg`/`ffprobe`. It is organized as a
package so UI, media logic, and FFmpeg orchestration stay separate.

## Layout
```
app.py                      # Entry point: creates QApplication + MainWindow
videoconverter/
├── __init__.py
├── ffmpeg.py               # Tool discovery (ffmpeg/ffprobe/ffplay), probe, duration
├── profiles.py             # FORMATS + PROFILES registries, argument builder (incl. trim)
├── conversion.py           # ConversionController: runs FFmpeg via QProcess, emits signals
├── preview.py              # VideoPreview widget (QMediaPlayer + QVideoWidget)
└── main_window.py          # MainWindow: wires widgets, input/output preview, trim UI
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
- **New container** → append to `FORMATS`; set which profiles it allows.
- **New option (bitrate, scale, fps)** → add a field to the `ConversionJob` dataclass
  and honor it in `build_arguments()`; add a widget in `main_window.py`.
- **Trim** → `ConversionJob.start`/`.end` drive `-ss`/`-to`; duration for progress is
  `end - start` when a range is set.

## Data flow
`MainWindow` gathers UI state → builds a `ConversionJob` → `build_arguments(job)` →
`ConversionController.start(ffmpeg, args, target_duration)` → signals update the
progress bar/log → on success the output is loaded into the output `VideoPreview`.

## Testing without a GUI
`profiles.build_arguments()` and `ffmpeg.probe_media()` are Qt-free and unit-testable.
Validate argument lists by running them against a short sample and re-probing the output.
