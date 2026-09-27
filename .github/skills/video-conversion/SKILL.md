---
name: video-conversion
description: 'Deep video container/codec and FFmpeg conversion expertise for the VideoConverter PySide6 desktop app. Use when adding or changing conversion profiles, output formats, codecs, trim/clip range selection, video preview, bitrate/quality/scaling options, or when diagnosing FFmpeg argument, remux compatibility, or encoding-quality problems. Covers container↔codec compatibility, stream-copy (remux) vs transcode, CRF/bitrate/two-pass rate control, GOP/keyframes, pixel formats and chroma subsampling, scaling filters, faststart, and how this app builds and runs FFmpeg via QProcess.'
argument-hint: 'e.g. "add a WebM/VP9 profile" or "make trim frame-accurate"'
---

# Video Conversion (VideoConverter app)

Expert guidance for extending and debugging the VideoConverter desktop application — a
PySide6 GUI that acts as a front end for bundled `ffmpeg` and `ffprobe`. The GUI never
encodes video itself: it inspects the input with `ffprobe`, builds correct FFmpeg
argument lists, runs FFmpeg via `QProcess`, and reports progress/logs.

## When to Use
- Adding or changing a conversion **profile** (codec/quality settings).
- Adding or changing an output **format/container** (MP4, MOV, MKV, WebM, …).
- Implementing or fixing **trim / clip range** selection (`-ss` / `-to`).
- Implementing or fixing **video preview** of input/output files.
- Adding options: bitrate, CRF, resolution/scaling, frame rate, audio extraction.
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

## Procedure: add a new output container
1. Add it to `FORMATS` in `profiles.py` (name, extension, file-dialog filter).
2. Map which profiles are legal for it (compatibility matrix in `formats.md`).
3. For MP4/MOV add `-movflags +faststart` when transcoding so the file is streamable.

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
