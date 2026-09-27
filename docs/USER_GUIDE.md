# Amrut Audio Video Converter — User Guide

A desktop app (Windows and macOS) for converting, previewing, trimming, and
downloading video — and extracting audio. It is a friendly front end for FFmpeg,
so you never touch the command line.

_Copyright © 2026 Harikrishna Ranpariya._

---

## 1. Getting started

- **Windows:** launch `VideoConverter.exe`.
- **macOS:** open `VideoConverter.app` (Amrut Audio Video Converter).
- From source: `python app.py`.

If a warning says **FFmpeg not found**, make sure `ffmpeg` and `ffprobe`
(`.exe` on Windows) are in the `bin` folder next to the app.

## 2. The window at a glance

| Area | What it does |
|------|--------------|
| **Input video** | The file to convert. Click **Browse** to pick it. |
| **Video URL** | Paste a link and click **Download** to fetch a video (see §6). |
| **Update downloader** | Refreshes the download engine (yt-dlp) so URLs keep working. |
| **Output folder** | Where the result is saved. **Browse** picks a folder; the filename is auto-filled. |
| **Input / Output preview** | Play the source and the finished result inside the app. |
| **Mode** | The conversion recipe (see §3). |
| **Format** | The output container (MP4, MOV, MKV, WebM, MP3). |
| **Resolution** | Keep original size or downscale (1080p, 720p, …). |
| **Trim** | Convert only a chosen part of the video. |
| **Convert / Cancel** | Start or stop the conversion. |
| **Progress + log** | Live percentage and the raw FFmpeg messages. |

## 3. Converting a video

1. **Browse** to your input video (or download one — see §6). It loads into the
   left preview and its details appear in the log.
2. Choose a **Mode**:
   - **Remux** — rewraps the file into a new container. Instant and lossless,
     but only works when the codecs already fit the target format.
   - **H.264 / AAC** — best all-round choice for phones, browsers, and TVs.
   - **H.265 / AAC** — smaller files; needs a modern device.
   - **VP9 / Opus** — open web format (WebM).
   - **ProRes / PCM** — high quality for video editing (MOV).
   - **Extract MP3 audio** — saves just the audio as an MP3 (see §5).
3. Pick a **Format**. Only formats compatible with the chosen mode are shown.
4. Optionally pick a lower **Resolution** to shrink the file.
5. Choose an **Output folder** (Browse), then click **Convert**. The finished
   file appears in the right-hand preview when done.

## 4. Trimming (converting only part of a video)

1. Tick **Convert only a selected range**.
2. Play the input preview and pause where you want to start.
3. Click **Use input position** next to **Start** to capture that time.
4. Do the same for **End** (or type times as `HH:MM:SS.mmm`).
5. Click **Convert** — only the selected section is exported, and the progress
   bar tracks the length of that section.

> Tip: with **Remux**, a trim cut may snap to the nearest keyframe. For an exact
> cut, choose a re-encoding mode such as **H.264 / AAC**.

## 5. Extracting audio (MP3)

1. Set **Mode = Extract MP3 audio (drop video)** — the Format locks to **MP3**.
2. Choose an **Output folder** and click **Convert**.
3. The video track is discarded and a high-quality MP3 is written. Trimming
   works here too. (A video with no audio track can't be extracted.)

## 6. Downloading from a URL

> ⚠️ Only download content you have the right to use. Downloading third-party
> videos may violate a site's Terms of Service or copyright. The app does not
> bypass DRM, private, or login-gated content.

1. Paste a link into **Video URL**.
2. Click **Download** and choose a **download folder** when prompted.
3. Progress shows in the bar/log; on success the file loads as the input.
4. Pick a Mode/Format and **Convert** as usual.

**Keeping downloads reliable:** sites change often. If a download starts failing,
click **Update downloader** to fetch the latest engine, then try again.

## 7. Choosing where files are saved

- **Output folder → Browse** opens a *folder* picker (no filename needed); the
  output name is generated automatically and can be edited in the text box.
- **Downloads** prompt for a folder each time and remember your last choice.
- Defaults: **Windows → Videos**, **macOS → Movies** (then Downloads).

## 8. Previewing results

- The **left** preview shows your input; the **right** preview loads the
  converted file automatically when done.
- Use **Play/Pause** and drag the slider to seek.

> If a preview shows "Video preview is unavailable", the Qt Multimedia plugins
> are missing from the build — conversion still works.

## 9. Troubleshooting

| Symptom | Fix |
|---------|-----|
| "FFmpeg not found" | Put `ffmpeg`/`ffprobe` in the `bin` folder. |
| "Remux not possible" | Codecs don't fit the container — accept the **Convert to MP4** offer, or pick MKV. |
| Conversion failed | Open the FFmpeg log; it shows the exact error. |
| Output won't play elsewhere | Use **H.264 / AAC** into **MP4** for best compatibility. |
| Download fails | Click **Update downloader**; check the log for the reason. |
| MP3 extraction fails | The source has no audio track. |

For codec/format details see [FORMATS.md](./FORMATS.md); for how conversions
work see [ALGORITHMS.md](./ALGORITHMS.md); for the download feature see
[URL_DOWNLOAD.md](./URL_DOWNLOAD.md).
