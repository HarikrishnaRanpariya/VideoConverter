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

## Extracting audio (MP3)

The **Extract MP3 audio** mode drops the video entirely and encodes just the
sound to an MP3:

```
-i input.mp4 -vn -map 0:a:0 -c:a libmp3lame -q:a 2 output.mp3
```

`-vn` removes video; `-q:a 2` is high-quality VBR (~190 kbps). Trimming works,
so you can export just a clip's audio. (Fails if the source has no audio.)

## Loudness normalization (EBU R128)

Loudness is measured in **LUFS** (ITU-R BS.1770: K-weighted, gated), not peak
level, because that is what listeners perceive and what platforms normalize to.
The app uses FFmpeg's `loudnorm` filter in **two passes**:

1. **Measure** — the first audio track (only the trimmed range, if set) is
   decoded with no output:
   ```
   -ss S -to E -i in -map 0:a:0 -vn -af loudnorm=I=-14:TP=-1:LRA=11:print_format=json -f null -
   ```
   (`-ss`/`-to` go *before* `-i` here: as output options they trim after the
   filter, so the audio before the start point would be measured too.)
   This reports integrated loudness (`input_i`), true peak (`input_tp`),
   loudness range (`input_lra`), gating threshold, and `target_offset`.
2. **Apply** — the measured values are fed back so `loudnorm` can apply a single
   clean **linear gain** instead of its real-time dynamic mode:
   ```
   -filter:a:0 loudnorm=I=-14:TP=-1:LRA=<max(target, measured)>:measured_I=…:measured_TP=…:measured_LRA=…:measured_thresh=…:offset=…:linear=true -ar:a:0 48000
   ```

Details that matter for quality:

- **Linear vs dynamic.** Linear mode only engages if `measured_LRA ≤ target LRA`
  and the gain won't push the true peak over the ceiling. The app widens the
  target LRA to the source's own range so dynamics are never compressed just
  to satisfy LRA. If the gain *would* exceed the true-peak ceiling, `loudnorm`
  falls back to dynamic mode (look-ahead true-peak limiting) — the log shows
  `Normalization Type: Linear` or `Dynamic`.
- **Sample rate.** `loudnorm` upsamples to 192 kHz internally for true-peak
  detection, so the output is resampled back (`-ar`): 44.1/48 kHz sources keep
  their rate; Opus always uses 48 kHz.
- **Silence** (≤ −70 LUFS) is never amplified; normalization is skipped.
- **Remux** can't normalize (audio must be re-encoded).

| Preset | Integrated | True peak | Use |
|--------|-----------:|----------:|-----|
| Streaming | −14 LUFS | −1 dBTP | YouTube, Spotify, social |
| Podcast | −16 LUFS | −1 dBTP | Apple Podcasts, mobile |
| Broadcast | −23 LUFS | −1 dBTP | EBU R128 TV/radio |

## Decision summary

```
Do the codecs already fit the target container?
├─ Yes → Remux (fast, lossless)
└─ No  → Transcode
          ├─ Need an exact file size? → Two-pass bitrate
          └─ Otherwise               → CRF (constant quality)
```
