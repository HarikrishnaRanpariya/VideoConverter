# Conversion Algorithms & Encoder Parameters

Agent-facing reference. User-facing version: [../../../../docs/ALGORITHMS.md](../../../../docs/ALGORITHMS.md).

## 1. Remux (stream copy)
`-map 0 -c copy` — repackages existing streams into a new container without decoding.
Lossless, near-instant. Fails if a stream codec is illegal in the target container.

## 2. Transcode (re-encode)
Decode → (optional filter) → re-encode. Lossy, CPU-bound. Controlled by:

### Rate control
- **CRF (constant quality)** — `-crf N`. Preferred for single-file delivery. Lower = better.
  - x264/x265: 18 (near-visually-lossless) → 23 (default) → 28 (small).
  - VP9/AV1: use `-crf` with `-b:v 0` for true constant quality.
- **Bitrate (ABR/CBR)** — `-b:v 4M`. Use when a target file size or streaming ceiling matters.
- **Two-pass** — run `-pass 1` then `-pass 2` with the same `-b:v` for accurate size at
  best quality. Needed for strict size targets.

### Presets & effort
`-preset` (x264/x265: `ultrafast`…`veryslow`) and `-cpu-used`/`-preset` (VP9/AV1) trade
encode time for compression efficiency. `medium` is a safe default.

### Pixel format & chroma subsampling
- `yuv420p` — required for broad H.264/H.265 playback (phones, browsers, TVs).
- `yuv422p10le` — ProRes / editing (10-bit, 4:2:2).
- `yuv444p` — highest chroma fidelity, poor consumer support.
Always set `-pix_fmt yuv420p` on delivery H.264/H.265.

### GOP / keyframes
`-g <frames>` sets keyframe interval (GOP). Smaller = better seeking/streaming, larger =
better compression. `-g` ≈ 2× frame rate is typical for streaming.

## 3. Filters
Applied via `-vf` (video) / `-af` (audio):
- **Scale**: `-vf scale=1280:-2` (keep aspect, height auto to even). Scaler quality via
  `-sws_flags` (`bilinear` fast, `bicubic` default, `lanczos` sharp).
- **FPS**: `-r 30` or `-vf fps=30` for frame-rate conversion.
- **Audio resample**: `-ar 48000` sample rate, `-ac 2` channel count.

## 4. Trimming a range
- Frame-accurate (transcode): `-ss <start> -to <end>` **after** `-i` (output seeking).
- Fast but keyframe-snapped (copy): `-ss <start>` **before** `-i` (input seeking).
- `-t <duration>` is an alternative to `-to <end>`.
- Progress percentage must be computed against `end - start`, not full duration.

## 5. Faststart (MP4/MOV)
`-movflags +faststart` moves the moov atom to the front so the file can start playing
before it fully downloads. Apply on every transcoded MP4/MOV.

## 6. Progress parsing
Run FFmpeg with `-progress pipe:1 -nostats`. Parse `key=value` lines on stdout; use
`out_time` (or `out_time_ms`) ÷ target duration × 100 for the percent. `progress=end`
signals completion.

## Decision guide
1. Same codecs already legal in target container? → **remux** (`-c copy`).
2. Only audio incompatible? → copy video, transcode audio.
3. Need specific size? → **two-pass bitrate**. Otherwise → **CRF**.
4. Editing target? → ProRes/PCM in MOV. Delivery? → H.264/AAC MP4 with faststart.
