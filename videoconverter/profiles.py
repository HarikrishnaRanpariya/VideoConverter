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
    audio_only: bool = False           # True => drop video, extract audio


# --- Registries ------------------------------------------------------------

FORMATS = [
    OutputFormat("MP4", "mp4", "MP4 video (*.mp4)"),
    OutputFormat("MOV", "mov", "MOV video (*.mov)"),
    OutputFormat("MKV", "mkv", "Matroska video (*.mkv)"),
    OutputFormat("WebM", "webm", "WebM video (*.webm)"),
    OutputFormat("MP3", "mp3", "MP3 audio (*.mp3)"),
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
    Profile(
        key="mp3_audio",
        label="Extract MP3 audio (drop video)",
        containers=["MP3"],
        audio_args=["-c:a", "libmp3lame", "-q:a", "2"],
        audio_only=True,
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


# Codecs that can be stream-copied (remuxed) into each container.
_REMUX_VIDEO = {
    "MP4": {"h264", "hevc", "av1", "mpeg4", "mjpeg"},
    "MOV": {"h264", "hevc", "prores", "mjpeg", "dnxhd"},
    "MKV": {"h264", "hevc", "av1", "vp9", "vp8", "prores", "mjpeg", "mpeg4"},
    "WebM": {"vp8", "vp9", "av1"},
}
_REMUX_AUDIO = {
    "MP4": {"aac", "ac3", "mp3", "alac", "eac3"},
    "MOV": {"aac", "pcm_s16le", "pcm_s24le", "alac", "ac3"},
    "MKV": {"aac", "ac3", "eac3", "mp3", "opus", "vorbis", "flac", "pcm_s16le"},
    "WebM": {"opus", "vorbis"},
}


def remux_incompatibilities(format_name, video_codec, audio_codec):
    """Return human-readable reasons a remux (stream copy) would fail.

    Empty list means the codecs are copyable into the target container.
    """
    problems = []
    allowed_v = _REMUX_VIDEO.get(format_name)
    if allowed_v is not None and video_codec:
        if video_codec.lower() not in allowed_v:
            problems.append(f"video codec '{video_codec}'")

    allowed_a = _REMUX_AUDIO.get(format_name)
    if allowed_a is not None and audio_codec:
        if audio_codec.lower() not in allowed_a:
            problems.append(f"audio codec '{audio_codec}'")

    return problems


# --- Loudness normalization (EBU R128 / ITU-R BS.1770) ------------------------

@dataclass(frozen=True)
class LoudnessPreset:
    """An integrated-loudness delivery target for FFmpeg's ``loudnorm``."""

    key: str
    label: str
    integrated: float   # target integrated loudness, LUFS
    true_peak: float    # maximum true peak, dBTP
    lra: float          # target loudness range, LU


LOUDNESS_PRESETS = [
    LoudnessPreset("streaming", "−14 LUFS · YouTube / Spotify / social", -14.0, -1.0, 11.0),
    LoudnessPreset("podcast", "−16 LUFS · Apple Podcasts / mobile", -16.0, -1.0, 11.0),
    LoudnessPreset("broadcast", "−23 LUFS · EBU R128 broadcast TV", -23.0, -1.0, 15.0),
]

# Below this the input is effectively silent and must not be amplified.
LOUDNESS_SILENCE_LUFS = -70.0


def loudness_preset_by_key(key):
    for preset in LOUDNESS_PRESETS:
        if preset.key == key:
            return preset
    return None


def _clamp(value, low, high):
    return max(low, min(high, float(value)))


def loudnorm_filter(preset, measured=None, print_format=None):
    """Build a ``loudnorm`` filter string for ``preset``.

    Without ``measured`` this is a single-pass (dynamic) normalization. With
    the pass-1 measurement (keys ``input_i``, ``input_tp``, ``input_lra``,
    ``input_thresh``, ``target_offset``) it becomes the accurate second pass,
    which applies a pure linear gain whenever the true-peak ceiling allows.
    """
    options = [
        f"I={preset.integrated:g}",
        f"TP={preset.true_peak:g}",
    ]

    if measured:
        measured_lra = _clamp(measured["input_lra"], 0.0, 99.0)
        # loudnorm only stays linear when measured LRA <= target LRA, so widen
        # the target to the source's own range rather than compressing it.
        target_lra = _clamp(max(preset.lra, measured_lra), 1.0, 50.0)
        options += [
            f"LRA={target_lra:g}",
            f"measured_I={_clamp(measured['input_i'], -99.0, 0.0):.2f}",
            f"measured_TP={_clamp(measured['input_tp'], -99.0, 99.0):.2f}",
            # 0 means "not measured" to loudnorm; a steady tone really is 0 LU.
            f"measured_LRA={max(0.01, measured_lra):.2f}",
            f"measured_thresh={_clamp(measured['input_thresh'], -99.0, 0.0):.2f}",
            f"offset={_clamp(measured['target_offset'], -99.0, 99.0):.2f}",
            "linear=true",
        ]
    else:
        options.append(f"LRA={preset.lra:g}")

    if print_format:
        options.append(f"print_format={print_format}")

    return "loudnorm=" + ":".join(options)


def loudnorm_output_rate(profile, input_rate=None):
    """Sample rate to resample to after ``loudnorm`` (it upsamples to 192 kHz)."""
    if "libopus" in profile.audio_args:
        return 48000
    if input_rate in (44100, 48000):
        return input_rate
    return 48000



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
    loudness_key: Optional[str] = None  # LoudnessPreset key; None keeps level
    loudness_measured: Optional[dict] = None  # pass-1 loudnorm measurement
    input_sample_rate: Optional[int] = None

    @property
    def has_range(self):
        return bool(self.start or self.end)


def _audio_filter_args(job, profile):
    if not job.loudness_key:
        return []

    preset = loudness_preset_by_key(job.loudness_key)
    if preset is None:
        raise ValueError(f"Unknown loudness preset '{job.loudness_key}'.")

    rate = loudnorm_output_rate(profile, job.input_sample_rate)
    # Only the first audio track is measured, so only that track is normalized.
    return [
        "-filter:a:0", loudnorm_filter(preset, job.loudness_measured, "summary"),
        "-ar:a:0", str(rate),
    ]


def build_arguments(job: ConversionJob):
    """Build the FFmpeg argument list for a job (excluding the binary path)."""
    profile = profile_by_key(job.profile_key)
    fmt = format_by_name(job.format_name)

    if profile is None or fmt is None:
        raise ValueError("Unknown profile or format.")

    if profile.copy and job.loudness_key:
        raise ValueError(
            "Loudness normalization re-encodes the audio, so it can't be used "
            "with Remux. Choose an encoding mode such as H.264 / AAC."
        )

    arguments = ["-y", "-nostdin", "-i", job.input_file]

    # Output-side seeking => frame-accurate for transcode, keyframe-snapped for copy.
    if job.start:
        arguments += ["-ss", job.start]
    if job.end:
        arguments += ["-to", job.end]

    if profile.copy:
        arguments += ["-map", "0", "-c", "copy"]
    elif profile.audio_only:
        # Drop video; take the first audio stream and encode it.
        arguments += ["-vn", "-map", "0:a:0"]
        arguments += list(profile.audio_args)
        arguments += _audio_filter_args(job, profile)
    else:
        arguments += ["-map", "0:v:0", "-map", "0:a?"]
        arguments += list(profile.video_args)

        if job.scale_height:
            arguments += ["-vf", f"scale=-2:{job.scale_height}"]

        arguments += list(profile.audio_args)
        arguments += _audio_filter_args(job, profile)

        if profile.faststart and fmt.extension in ("mp4", "mov"):
            arguments += ["-movflags", "+faststart"]

    arguments += ["-progress", "pipe:1", "-nostats", job.output_file]
    return arguments
