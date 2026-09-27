"""Format/profile registries and FFmpeg argument construction (no Qt)."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class OutputFormat:
    """A target container."""

    name: str          # UI label, e.g. "MP4"
    extension: str     # file extension without dot, e.g. "mp4"
    file_filter: str   # Qt file-dialog filter


@dataclass(frozen=True)
class Profile:
    """A codec recipe and the containers it is allowed to target."""

    key: str
    label: str
    containers: List[str]              # allowed format names
    video_args: List[str] = field(default_factory=list)
    audio_args: List[str] = field(default_factory=list)
    copy: bool = False                 # True => stream copy (remux)
    faststart: bool = False            # add +faststart for MP4/MOV


# --- Registries ------------------------------------------------------------

FORMATS = [
    OutputFormat("MP4", "mp4", "MP4 video (*.mp4)"),
    OutputFormat("MOV", "mov", "MOV video (*.mov)"),
    OutputFormat("MKV", "mkv", "Matroska video (*.mkv)"),
    OutputFormat("WebM", "webm", "WebM video (*.webm)"),
]


PROFILES = [
    Profile(
        key="remux",
        label="Remux – copy video and audio (fast, lossless)",
        containers=["MP4", "MOV", "MKV"],
        copy=True,
    ),
    Profile(
        key="h264",
        label="H.264 / AAC – universal compatibility",
        containers=["MP4", "MOV", "MKV"],
        video_args=[
            "-c:v", "libx264",
            "-crf", "20",
            "-preset", "medium",
            "-pix_fmt", "yuv420p",
        ],
        audio_args=["-c:a", "aac", "-b:a", "192k"],
        faststart=True,
    ),
    Profile(
        key="h265",
        label="H.265 / AAC – smaller files, modern devices",
        containers=["MP4", "MOV", "MKV"],
        video_args=[
            "-c:v", "libx265",
            "-crf", "24",
            "-preset", "medium",
            "-pix_fmt", "yuv420p",
            "-tag:v", "hvc1",
        ],
        audio_args=["-c:a", "aac", "-b:a", "192k"],
        faststart=True,
    ),
    Profile(
        key="vp9",
        label="VP9 / Opus – open web (WebM)",
        containers=["WebM", "MKV"],
        video_args=[
            "-c:v", "libvpx-vp9",
            "-crf", "31",
            "-b:v", "0",
            "-pix_fmt", "yuv420p",
        ],
        audio_args=["-c:a", "libopus", "-b:a", "128k"],
    ),
    Profile(
        key="prores",
        label="ProRes 422 / PCM – video editing (MOV)",
        containers=["MOV", "MKV"],
        video_args=[
            "-c:v", "prores_ks",
            "-profile:v", "2",
            "-pix_fmt", "yuv422p10le",
        ],
        audio_args=["-c:a", "pcm_s16le"],
    ),
]


def format_by_name(name):
    for fmt in FORMATS:
        if fmt.name == name:
            return fmt
    return None


def profile_by_key(key):
    for profile in PROFILES:
        if profile.key == key:
            return profile
    return None


def profiles_for_format(format_name):
    return [p for p in PROFILES if format_name in p.containers]


def formats_for_profile(profile_key):
    profile = profile_by_key(profile_key)

    if not profile:
        return list(FORMATS)

    return [f for f in FORMATS if f.name in profile.containers]


# --- Job + argument builder ------------------------------------------------

@dataclass
class ConversionJob:
    input_file: str
    output_file: str
    profile_key: str
    format_name: str
    start: Optional[str] = None   # "HH:MM:SS.mmm" or None
    end: Optional[str] = None     # "HH:MM:SS.mmm" or None
    scale_height: Optional[int] = None  # e.g. 720 to downscale; None keeps size

    @property
    def has_range(self):
        return bool(self.start or self.end)


def build_arguments(job: ConversionJob):
    """Build the FFmpeg argument list for a job (excluding the binary path)."""
    profile = profile_by_key(job.profile_key)
    fmt = format_by_name(job.format_name)

    if profile is None or fmt is None:
        raise ValueError("Unknown profile or format.")

    arguments = ["-y", "-nostdin", "-i", job.input_file]

    # Output-side seeking => frame-accurate for transcode, keyframe-snapped for copy.
    if job.start:
        arguments += ["-ss", job.start]
    if job.end:
        arguments += ["-to", job.end]

    if profile.copy:
        arguments += ["-map", "0", "-c", "copy"]
    else:
        arguments += ["-map", "0:v:0", "-map", "0:a?"]
        arguments += list(profile.video_args)

        if job.scale_height:
            arguments += ["-vf", f"scale=-2:{job.scale_height}"]

        arguments += list(profile.audio_args)

        if profile.faststart and fmt.extension in ("mp4", "mov"):
            arguments += ["-movflags", "+faststart"]

    arguments += ["-progress", "pipe:1", "-nostats", job.output_file]
    return arguments
