# Video File Format Architecture

This guide explains how video files are structured and which combinations are
valid, so you can choose the right output format in the app. A technical, agent
oriented version lives in
[.github/skills/video-conversion/references/formats.md](../.github/skills/video-conversion/references/formats.md).

## Containers vs. codecs

A video file has two independent layers:

- **Container (a.k.a. format/wrapper)** — the outer file structure that holds
  the streams together, plus metadata, timestamps, and chapters. Examples:
  `.mp4`, `.mov`, `.mkv`, `.webm`. The file extension names the container.
- **Codec** — the algorithm that actually compresses a stream. Each video and
  audio stream inside the container is encoded with a codec (H.264, AAC, …).

> A `.mp4` file is *not* a codec. It is a box that commonly holds H.264 video
> and AAC audio — but it can hold other codecs too.

```
┌───────────────────────── Container (.mp4) ─────────────────────────┐
│  Metadata (duration, faststart index, chapters)                    │
│  ┌───────────── Video stream ─────────────┐  ┌──── Audio stream ──┐│
│  │  Codec: H.264 (yuv420p, 1920x1080, 30fps)│  │ Codec: AAC 192kbps ││
│  └──────────────────────────────────────────┘  └────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

## Containers supported by this app

| Container | Extension | Best for | Notes |
|-----------|-----------|----------|-------|
| **MP4** | `.mp4` | Delivery to phones, browsers, TVs | Add "faststart" for streaming. Doesn't hold Opus/Vorbis. |
| **MOV** | `.mov` | Apple ecosystem, video editing | Only container here for ProRes. |
| **MKV** | `.mkv` | Archiving, mixing any codecs | Extremely flexible; some hardware players struggle. |
| **WebM** | `.webm` | Open web video | Only VP8/VP9/AV1 video and Opus/Vorbis audio — no H.264/AAC. |

## Video codecs

| Codec | Compatibility | Efficiency | Typical use |
|-------|---------------|------------|-------------|
| **H.264 / AVC** | Universal | Good | Default for sharing and playback |
| **H.265 / HEVC** | Modern devices | ~2× H.264 | Smaller files at same quality |
| **VP9** | Web/Android | High | YouTube-style web video |
| **AV1** | Newest devices | Highest | Future-proof web video |
| **ProRes** | Editing software | Low (large files) | Editing masters |

## Audio codecs

| Codec | Compatibility | Use |
|-------|---------------|-----|
| **AAC** | Universal | Default delivery audio |
| **Opus** | Web | Best quality-per-bitrate for WebM |
| **PCM** | Editing | Uncompressed audio for editing |

## Why some combinations are blocked

The app only lets you pick a **format** that is valid for the chosen **mode**,
because not every codec fits every container:

- **ProRes** must go into **MOV** (or MKV) — never MP4.
- **VP9 / Opus** must go into **WebM** (or MKV) — never MP4/MOV.
- **H.264 / AAC** fits **MP4, MOV, MKV** — but not WebM.

This is why, for example, choosing the ProRes mode restricts the format list to
MOV/MKV. Picking an invalid pairing would produce a file that won't play, so the
app prevents it.

## Choosing a format quickly

| Goal | Mode | Format |
|------|------|--------|
| Share anywhere | H.264 / AAC | MP4 |
| Smallest modern file | H.265 / AAC | MP4 |
| Open web video | VP9 / Opus | WebM |
| Edit in a video editor | ProRes / PCM | MOV |
| Just change the wrapper | Remux | MP4 / MOV / MKV |
