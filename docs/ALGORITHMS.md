# Video Conversion Algorithms

How the app turns one video into another. A concise, agent-oriented version is in
[.github/skills/video-conversion/references/algorithms.md](../.github/skills/video-conversion/references/algorithms.md).

Every conversion is one of two fundamental operations: **remux** (repackage) or
**transcode** (re-encode). The app builds the right FFmpeg command for each.

## 1. Remux (stream copy)

The video and audio streams are copied byte-for-byte into a new container — no
decoding, no quality loss, and it finishes almost instantly.

```
Input.mkv ──(copy streams)──> Output.mp4
```

- **When it works:** only if every stream's codec is legal in the target
  container (e.g. H.264 + AAC → MP4).
- **When it fails:** an incompatible codec (e.g. VP9 → MP4). The app then asks
  you to choose a re-encoding mode.
- FFmpeg: `-map 0 -c copy`

## 2. Transcode (re-encode)

Each stream is decoded, optionally filtered (resized, resampled), and encoded
again with a new codec. This is slower and slightly lossy but produces the exact
codec/quality you need.

```
Input ──decode──> raw frames ──[scale/fps]──> encode(H.264) ──> Output.mp4
```

### Rate control — how quality/size is decided

| Method | FFmpeg | Use when |
|--------|--------|----------|
| **CRF (constant quality)** | `-crf 20` | You want consistent quality; size varies. **Default here.** |
| **Bitrate (ABR/CBR)** | `-b:v 4M` | You need a target size or streaming ceiling. |
| **Two-pass** | `-pass 1` then `-pass 2` | You need an exact file size at best quality. |

Lower CRF = higher quality and bigger files. Typical H.264 range: 18 (excellent)
to 28 (small). The app uses sensible defaults per mode.

### Presets

`-preset medium` balances speed and compression. Slower presets (`slow`,
`veryslow`) squeeze out smaller files for the same quality at the cost of time.

### Pixel format & chroma subsampling

Color is stored as brightness (luma) plus color (chroma). Consumer video uses
`yuv420p` (color at quarter resolution) because eyes are less sensitive to color
detail — and because most players require it. Editing formats like ProRes use
`yuv422p10le` (more color, 10-bit) for higher fidelity.

### Faststart (MP4/MOV)

`-movflags +faststart` moves the file's index to the front so playback can begin
before the whole file downloads. The app adds this automatically for MP4/MOV
transcodes.

## 3. Scaling (resolution change)

Choosing a lower resolution applies a scaling filter:

```
-vf scale=-2:720
```

`720` is the target height; `-2` computes a width that keeps the aspect ratio and
stays even (required by most codecs). Downscaling reduces size and encode time.

## 4. Trimming a range

When you select a start and end, the app adds seek options:

```
-i input.mp4 -ss 00:00:05.000 -to 00:00:20.000 …
```

Placing `-ss`/`-to` **after** the input makes a **frame-accurate** cut when
re-encoding. With **Remux** (copy), cuts can only land on keyframes, so the start
may shift slightly — choose a re-encoding mode for an exact cut. Progress is
measured against the length of the selected range.

## 5. Progress reporting

FFmpeg is run with `-progress pipe:1 -nostats`. The app reads the `out_time`
value it prints, divides by the target duration, and updates the progress bar.
`progress=end` marks completion.

## Decision summary

```
Do the codecs already fit the target container?
├─ Yes → Remux (fast, lossless)
└─ No  → Transcode
          ├─ Need an exact file size? → Two-pass bitrate
          └─ Otherwise               → CRF (constant quality)
```
