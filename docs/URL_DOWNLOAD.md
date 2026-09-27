# URL Download → Convert

This feature lets you paste a media URL (YouTube and many other sites), download
the video with **yt-dlp**, and then run it through the normal conversion
pipeline — so every mode (H.264/H.265/VP9/ProRes, MKV/WebM, **MP3 extraction**),
plus trim and downscaling, works on the downloaded file.

Reliability comes from **keeping yt-dlp current**: the app fetches the official
standalone `yt-dlp` binary at first use and can refresh it on demand via
**Update downloader** (sites change often, so a frozen copy would eventually
break — this mirrors how commercial downloaders stay working).

> ⚠️ **Legal notice.** Downloading third-party content may violate a site's
> Terms of Service or copyright law. Only download content you own or have the
> right to use. This feature downloads only permitted content and does **not**
> bypass DRM, login gates, or any access restriction.

## User flow

1. Paste a URL into the **Video URL** field and click **Download**.
2. The app downloads the best available video+audio to a temporary folder,
   using the bundled FFmpeg to merge streams into a single file.
3. On success the downloaded file is loaded as the **input** (preview + probe),
   and a default output name is filled in.
4. Choose a **Mode / Format** (and optionally trim / downscale) and click
   **Convert** exactly as with a local file.

```
URL ──► yt-dlp (background thread) ──► temp file ──► input pipeline ──► Convert ──► output
                     │
                     └─ uses bundled FFmpeg to merge video+audio
```

## Architecture

The download is just a **new input source**; the conversion engine is unchanged.

```
videoconverter/
├── downloader.py     # DownloadWorker (QObject): runs yt-dlp off the UI thread
├── main_window.py    # URL row + Download button; wires worker to a QThread
├── ffmpeg.py         # provides the bundled FFmpeg location for yt-dlp merges
├── profiles.py       # unchanged — builds the FFmpeg conversion args
└── conversion.py     # unchanged — runs the conversion
```

### `downloader.py`
- The official **standalone yt-dlp binary** is fetched into `~/.videoconverter/bin`
  (`ensure_ytdlp`) on first use and refreshed by `download_ytdlp` /
  `UpdateWorker`. Per-OS asset: `yt-dlp_macos`, `yt-dlp.exe`, or `yt-dlp_linux`.
- `DownloadWorker(url, dest_dir)` is a `QObject` with signals
  `progress(int)`, `log(str)`, and `finished(bool, str)`.
- `run()` invokes the binary as a subprocess with:
  - `-f "bv*+ba/b"` — best video+audio, else best single stream.
  - `--merge-output-format mp4` — one playable file.
  - `--ffmpeg-location <app>/bin` — reuse the bundled FFmpeg for merging.
  - `--no-playlist` — never expand a mix/playlist.
  - `--progress-template` / `--print after_move:filepath` — clean progress and
    the final output path parsed from stdout.
- `normalize_url()` strips YouTube playlist/radio params so a pasted mix link
  targets only the single video.

### Threading
`main_window.start_download()` moves a `DownloadWorker` onto a `QThread` so the
UI stays responsive; **Update downloader** runs an `UpdateWorker` the same way.
Signals update the shared progress bar and log; on `finished(True, path)` the
file is loaded via `_load_input_file()` — the same helper used by **Browse**.

### Failure handling
Network errors, private/age-restricted/geo-blocked videos, and missing files all
surface through `finished(False, message)`, shown in a dialog and the log.

## Packaging notes
- **yt-dlp is not bundled.** The app downloads the official standalone binary at
  runtime into `~/.videoconverter/bin`, so the build stays small and the
  downloader is always updatable independently of the app.
- **Keeping it current:** click **Update downloader** (or it self-fetches on
  first use). This is the sanctioned way to match commercial downloader
  reliability — for content you are allowed to download.
- Requires network access on first download and when updating.
