# Containers, Codecs & Compatibility

Agent-facing reference. For the user-facing version see [../../../../docs/FORMATS.md](../../../../docs/FORMATS.md).

## Containers (wrappers)

| Container | Ext | Typical video | Typical audio | Notes |
|-----------|-----|---------------|---------------|-------|
| MP4 (ISO BMFF) | `.mp4`, `.m4v` | H.264, H.265, AV1 | AAC, AC-3 | Universal delivery. Use `+faststart`. No Opus/Vorbis in strict MP4. |
| QuickTime | `.mov` | H.264, H.265, ProRes, MJPEG | AAC, PCM | Apple/editing. Only container for ProRes here. |
| Matroska | `.mkv` | Anything (H.264/5, AV1, VP9) | Anything (Opus, FLAC, AAC…) | Most permissive; not ideal for hardware players. |
| WebM | `.webm` | VP8, VP9, AV1 | Opus, Vorbis | Open web. **No H.264/AAC.** |
| AVI | `.avi` | MJPEG, MPEG-4 ASP | MP3, PCM | Legacy; avoid for modern codecs. |
| MPEG-TS | `.ts` | H.264, H.265 | AAC, AC-3 | Streaming/broadcast, resilient to cuts. |
| GIF | `.gif` | palette (256 colors) | none | Animation only; use palettegen for quality. |

## Video codecs

| Codec | Encoder | Strengths | Cost | Container fit |
|-------|---------|-----------|------|---------------|
| H.264 / AVC | `libx264` | Universal compatibility | Low–med | MP4, MOV, MKV, TS |
| H.265 / HEVC | `libx265` | ~2× efficiency of H.264 | High | MP4, MOV, MKV, TS |
| AV1 | `libsvtav1`/`libaom-av1` | Best efficiency, royalty-free | High | MP4, MKV, WebM |
| VP9 | `libvpx-vp9` | Open, good web efficiency | High | WebM, MKV |
| VP8 | `libvpx` | Older open web | Med | WebM, MKV |
| ProRes | `prores_ks` | Edit-friendly, near-lossless | Low CPU/high size | MOV |
| MJPEG | `mjpeg` | Simple intra-frame | Low | MOV, AVI |

## Audio codecs

| Codec | Encoder | Use | Container fit |
|-------|---------|-----|---------------|
| AAC | `aac` | Default delivery | MP4, MOV, MKV, TS |
| AC-3 | `ac3` | Surround/broadcast | MP4, MOV, MKV, TS |
| Opus | `libopus` | Best modern web audio | WebM, MKV |
| Vorbis | `libvorbis` | Legacy web | WebM, MKV |
| MP3 | `libmp3lame` | Legacy universal | MP4(ish), MKV, AVI |
| FLAC | `flac` | Lossless archive | MKV, FLAC |
| PCM | `pcm_s16le` | Editing/interchange | MOV, WAV, MKV |

## Compatibility matrix (video codec × container)

`✓` legal · `~` allowed but non-standard/poor support · `✗` illegal

| Codec ↓ / Container → | MP4 | MOV | MKV | WebM | AVI |
|---|---|---|---|---|---|
| H.264 | ✓ | ✓ | ✓ | ✗ | ~ |
| H.265 | ✓ | ✓ | ✓ | ✗ | ✗ |
| AV1 | ✓ | ~ | ✓ | ✓ | ✗ |
| VP9 | ~ | ✗ | ✓ | ✓ | ✗ |
| ProRes | ✗ | ✓ | ✓ | ✗ | ✗ |
| MJPEG | ~ | ✓ | ✓ | ✗ | ✓ |

Audio quick rule: **AAC** everywhere except WebM; **Opus/Vorbis** for WebM; **PCM** for MOV editing.

## Remux legality
A `-c copy` remux succeeds only when **every** input stream's codec appears `✓` for the
target container. If any stream is `✗`, either drop/transcode that stream or pick a
different container (MKV accepts almost anything).
