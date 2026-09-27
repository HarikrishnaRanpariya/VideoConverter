---
name: video-conversion
description: 'Deep video container/codec and FFmpeg conversion expertise for the Amrut Audio Video Converter PySide6 desktop app (Windows + macOS). Use when adding or changing conversion profiles, output formats, codecs, MP3/audio extraction, trim/clip range selection, video preview, URL download (yt-dlp), bitrate/quality/scaling options, or when diagnosing FFmpeg argument, remux compatibility, or encoding-quality problems. Covers container↔codec compatibility and the remux pre-flight guard, stream-copy (remux) vs transcode, audio-only extraction, CRF/bitrate/two-pass rate control, GOP/keyframes, pixel formats and chroma subsampling, scaling filters, faststart, and how this app builds and runs FFmpeg via QProcess.'
argument-hint: 'e.g. "add a WebM/VP9 profile" or "make trim frame-accurate"'
---

# Video Conversion (Amrut Audio Video Converter)

Expert guidance for extending and debugging the Amrut Audio Video Converter desktop
application — a PySide6 GUI (Windows + macOS) that acts as a front end for bundled
`ffmpeg` and `ffprobe`. The GUI never encodes video itself: it inspects the input with
`ffprobe`, builds correct FFmpeg argument lists, runs FFmpeg via `QProcess`, and reports
progress/logs. A separate module downloads media from URLs via a self-updating `yt-dlp`.

## When to Use
- Adding or changing a conversion **profile** (codec/quality settings).
- Adding or changing an output **format/container** (MP4, MOV, MKV, WebM, MP3, …).
- Adding an **audio-only extraction** profile (e.g. MP3/M4A/WAV/FLAC).
- Implementing or fixing **trim / clip range** selection (`-ss` / `-to`).
- Implementing or fixing **video preview** of input/output files.
- Implementing or fixing **URL download** (yt-dlp) or its self-update.
- Diagnosing the **remux pre-flight guard** (blocking incompatible stream copies).
- Adding options: bitrate, CRF, resolution/scaling, frame rate.
- Diagnosing FFmpeg failures, remux/container incompatibility, or poor output quality.

## Core Mental Model
1. **Container ≠ codec.** A container (`.mp4`, `.mkv`) is a wrapper; the codecs
   (H.264, AAC…) are the payload. A conversion may change only the container
   (remux), only the codecs (transcode), or both.
2. **Remux (stream copy) is nearly free and lossless** but only works when the target
   container supports every stream's codec. Transcode re-encodes and always costs time
   and some quality.
3. Prefer the **cheapest operation** that satisfies the request: copy > transcode audio
   only > transcode video. Never re-encode a stream you can copy.

Detailed knowledge lives in reference files — load them as needed:
- Containers, codecs, and the compatibility matrix → [references/formats.md](./references/formats.md)
- Conversion algorithms and encoder parameters → [references/algorithms.md](./references/algorithms.md)
- App architecture and extension points → [references/architecture.md](./references/architecture.md)

## Keep documentation in sync (required)
Whenever you change code, update the docs in the **same change** so they never
drift:
- New/changed **profile, format, codec, or option** → update the Features list in
  [../../../readme.md](../../../readme.md) and the mode/format lists in
  [../../../docs/USER_GUIDE.md](../../../docs/USER_GUIDE.md).
- New **codec/container** behavior → update [../../../docs/FORMATS.md](../../../docs/FORMATS.md)
  and [../../../docs/ALGORITHMS.md](../../../docs/ALGORITHMS.md) (and the matching
  reference files under `references/`).
- New **module or architectural change** → update the architecture diagram in
  `readme.md` and [references/architecture.md](./references/architecture.md).
- New **download / build** behavior → update
  [../../../docs/URL_DOWNLOAD.md](../../../docs/URL_DOWNLOAD.md) and the build/setup
  sections of `readme.md`.
Treat a code change as incomplete until the corresponding docs are updated.

## Procedure: add a new conversion profile
1. Read [references/algorithms.md](./references/algorithms.md) to pick codecs and rate
   control (CRF vs bitrate vs two-pass) and pixel format.
2. Check container support in [references/formats.md](./references/formats.md) — confirm
   the codecs are legal in the target container(s).
3. Add the profile to `PROFILES` in [../../../videoconverter/profiles.py](../../../videoconverter/profiles.py):
   define its label, allowed containers, and the encoder argument list.
4. If the codec is container-locked (e.g. ProRes → MOV, VP9/Opus → WebM/MKV), restrict
   `containers` and let the UI disable incompatible format choices.
5. Verify: run `ffmpeg` with the built args on a short sample, then `ffprobe` the output
   to confirm codecs, pixel format, and duration.
6. **Update docs** (see “Keep documentation in sync”): add the mode to the
   `readme.md` Features list and `docs/USER_GUIDE.md`; if it introduces a new
   codec/container, update `docs/FORMATS.md` and `docs/ALGORITHMS.md`.

## Procedure: add a new output container
1. Add it to `FORMATS` in `profiles.py` (name, extension, file-dialog filter).
2. Map which profiles are legal for it (compatibility matrix in `formats.md`).
3. For MP4/MOV add `-movflags +faststart` when transcoding so the file is streamable.
4. Update `_REMUX_VIDEO`/`_REMUX_AUDIO` in `profiles.py` so the pre-flight guard
   knows which codecs may be stream-copied into the new container.
5. **Update docs**: add the container to `readme.md`, `docs/USER_GUIDE.md`, and the
   `docs/FORMATS.md` container table.

## Procedure: add an audio-only (extraction) profile
1. Add an audio container to `FORMATS` (e.g. MP3/M4A/WAV/FLAC).
2. Add a `Profile` with `audio_only=True`, an empty `video_args`, and the audio
   encoder (e.g. `-c:a libmp3lame -q:a 2`). `build_arguments` emits
   `-vn -map 0:a:0` for these; trim still applies, scaling/faststart do not.
3. Restrict `containers` to the audio format so the UI filters correctly.
4. **Update docs**: add the extraction mode to `readme.md` and `docs/USER_GUIDE.md`.

## Procedure: trim / clip a range
1. Collect start and end as `HH:MM:SS.mmm`.
2. For **frame-accurate transcode**, place `-ss <start>` and `-to <end>` as *output*
   options (after `-i`). This decodes from the nearest keyframe and cuts exactly.
3. For **stream copy (remux)**, exact cuts are limited to keyframe boundaries; document
   that the cut may snap to the nearest keyframe, or force a transcode for accuracy.
4. Always recompute progress against the *clip* duration (`end - start`), not the full
   input duration.

## Quality & correctness checklist
- Video for web/mobile: `libx264 -crf 18–23 -pix_fmt yuv420p` (+ `+faststart` for MP4).
- Never output `yuv444`/`yuv422` into a consumer H.264 MP4 meant for broad playback.
- Audio: `aac -b:a 160–192k` for delivery; PCM only for editing/interchange.
- Copy streams with `-c copy` whenever the container already supports them.
- Validate every new argument list with `ffprobe` before shipping.

## Anti-patterns
- Re-encoding when a remux would do (slow, lossy, pointless).
- Putting `-ss` only *before* `-i` for a transcode that must be frame-accurate.
- Hard-coding codec choices in the UI instead of the `profiles.py` registry.
- Assuming any codec fits any container (see the matrix — AV1 in a plain MOV, etc.).
