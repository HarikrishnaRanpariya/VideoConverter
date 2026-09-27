# Video Converter — User Guide

A simple Windows desktop app for converting video files, previewing them, and
trimming a portion before conversion. It is a friendly front end for FFmpeg — you
never touch the command line.

## 1. Getting started

1. Launch **VideoConverter.exe** (or run `python app.py` from source).
2. If a warning says FFmpeg was not found, make sure `ffmpeg` and `ffprobe`
   (`.exe` on Windows) are present in the `bin` folder next to the app.

## 2. The window at a glance

| Area | What it does |
|------|--------------|
| **Input video** | The file you want to convert. Click **Browse** to pick it. |
| **Output file** | Where the result is saved. A name is suggested automatically. |
| **Input / Output preview** | Play the source and the finished result inside the app. |
| **Mode** | The conversion recipe (see below). |
| **Format** | The output container (MP4, MOV, MKV, WebM). |
| **Resolution** | Keep the original size or downscale (1080p, 720p, …). |
| **Trim** | Convert only a chosen part of the video. |
| **Convert / Cancel** | Start or stop the conversion. |
| **Progress + log** | Live percentage and the raw FFmpeg messages. |

## 3. Converting a video

1. **Browse** to your input video. It loads into the left preview and its
   details appear in the log.
2. Choose a **Mode**:
   - **Remux** — just rewraps the file into a new container. Instant and
     lossless, but only works when the codecs already fit the target format.
   - **H.264 / AAC** — best all-round choice for phones, browsers, and TVs.
   - **H.265 / AAC** — smaller files, needs a modern device.
   - **VP9 / Opus** — open web format (WebM).
   - **ProRes / PCM** — high quality for video editing (MOV).
3. Pick a **Format**. Only formats that work with the chosen mode are shown.
4. Optionally pick a lower **Resolution** to shrink the file.
5. Click **Convert**. Watch the progress bar; the finished file appears in the
   right-hand preview when done.

## 4. Trimming (converting only part of a video)

1. Tick **Convert only a selected range**.
2. Play the input preview and pause at the point you want to start.
3. Click **Use input position** next to **Start** to capture that time.
4. Do the same for **End** (or type times as `HH:MM:SS.mmm`).
5. Click **Convert** — only the selected section is exported, and the progress
   bar tracks the length of that section.

> Tip: When trimming with **Remux**, the cut may snap to the nearest keyframe.
> For an exact cut, choose a re-encoding mode such as **H.264 / AAC**.

## 5. Previewing results

- The **left** preview always shows your input.
- The **right** preview loads the converted file automatically when a
  conversion finishes, so you can check it immediately.
- Use **Play/Pause** and drag the slider to seek.

> If the previews show "Video preview is unavailable", the Qt Multimedia
> playback plugins are missing from the build — conversion still works.

## 6. Troubleshooting

| Symptom | Fix |
|---------|-----|
| "FFmpeg not found" | Put `ffmpeg`/`ffprobe` in the `bin` folder. |
| Conversion failed | Open the FFmpeg log; it explains the exact error. |
| Remux fails | The codecs don't fit the format — pick a re-encoding mode. |
| Output won't play elsewhere | Use **H.264 / AAC** into **MP4** for best compatibility. |

For codec/format details see [FORMATS.md](./FORMATS.md); for how conversions
work see [ALGORITHMS.md](./ALGORITHMS.md).
