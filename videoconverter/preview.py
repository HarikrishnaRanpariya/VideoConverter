"""Reusable video preview widget built on Qt Multimedia.

Degrades gracefully to a message label if QtMultimedia is unavailable so the
converter still runs without the multimedia plugins.
"""

import math
import threading

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from . import ffmpeg

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtMultimediaWidgets import QVideoWidget

    MULTIMEDIA_AVAILABLE = True
except ImportError:  # pragma: no cover - environment dependent
    MULTIMEDIA_AVAILABLE = False


def format_timestamp(milliseconds):
    """Format milliseconds as ``HH:MM:SS.mmm``."""
    milliseconds = max(0, int(milliseconds))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


WAVEFORM_FLOOR_DB = -60.0


def peak_to_height(peak):
    """Map a linear peak (0.0–1.0) to a 0.0–1.0 bar height on a dB scale.

    A dB scale keeps quiet tracks visible while still letting input and output
    be compared on the same absolute axis (0 dBFS = full height).
    """
    if peak <= 0.0:
        return 0.0
    db = 20.0 * math.log10(min(1.0, peak))
    return max(0.0, (db - WAVEFORM_FLOOR_DB) / -WAVEFORM_FLOOR_DB)


class _WaveformSignals(QObject):
    loaded = Signal(int, object)


class AudioWaveform(QWidget):
    """Peak-envelope graph of a file's first audio track with a playhead.

    The waveform is decoded by FFmpeg on a background thread. Clicking or
    dragging emits :attr:`seek_requested` (milliseconds).
    """

    seek_requested = Signal(int)

    _BACKGROUND = QColor(30, 30, 34)
    _WAVE = QColor(90, 160, 230)
    _PLAYED = QColor(140, 205, 255)
    _CENTER = QColor(70, 70, 78)
    _PLAYHEAD = QColor(235, 80, 70)
    _TEXT = QColor(170, 170, 178)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(64)
        self.setMaximumHeight(90)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setToolTip("Audio waveform (dBFS). Click or drag to seek.")

        self._peaks = []
        self._message = "No file loaded"
        self._duration = 0
        self._position = 0
        self._generation = 0
        self._cancel = None

        self._signals = _WaveformSignals(self)
        self._signals.loaded.connect(self._on_loaded)

    # -- Public API ---------------------------------------------------------

    def load(self, file_path):
        """Decode the waveform of ``file_path`` in the background."""
        self._start_generation()
        self._message = "Loading audio waveform…"
        self.update()

        generation = self._generation
        cancel = self._cancel
        signals = self._signals
        points = max(400, min(2000, self.width() * 2))

        def work():
            try:
                peaks = ffmpeg.read_waveform(file_path, points, cancel.is_set)
            except Exception:
                peaks = False
            if peaks is None or cancel.is_set():
                return
            try:
                signals.loaded.emit(generation, peaks)
            except RuntimeError:  # widget already destroyed
                pass

        threading.Thread(target=work, daemon=True).start()

    def clear(self):
        self._start_generation()
        self._message = "No file loaded"
        self._duration = 0
        self._position = 0
        self.update()

    def set_duration(self, milliseconds):
        self._duration = max(0, int(milliseconds))
        self.update()

    def set_position(self, milliseconds):
        self._position = max(0, int(milliseconds))
        self.update()

    def peaks(self):
        return list(self._peaks)

    # -- Internals ----------------------------------------------------------

    def _start_generation(self):
        if self._cancel is not None:
            self._cancel.set()
        self._cancel = threading.Event()
        self._generation += 1
        self._peaks = []

    def _on_loaded(self, generation, peaks):
        if generation != self._generation:
            return
        if peaks is False:
            self._peaks = []
            self._message = "Could not read audio"
        elif not peaks:
            self._peaks = []
            self._message = "No audio track"
        else:
            self._peaks = peaks
            self._message = ""
        self.update()

    def _seek_from_x(self, x):
        if self._duration <= 0 or not self._peaks or self.width() <= 0:
            return
        fraction = min(1.0, max(0.0, x / self.width()))
        self.seek_requested.emit(int(fraction * self._duration))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._seek_from_x(event.position().x())

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._seek_from_x(event.position().x())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width, height = self.width(), self.height()
        painter.fillRect(self.rect(), self._BACKGROUND)

        mid = height / 2.0
        painter.setPen(QPen(self._CENTER, 1))
        painter.drawLine(QPointF(0, mid), QPointF(width, mid))

        if not self._peaks:
            painter.setPen(self._TEXT)
            painter.drawText(
                QRectF(0, 0, width, height),
                Qt.AlignmentFlag.AlignCenter,
                self._message,
            )
            return

        count = len(self._peaks)
        half = mid - 2
        top = QPainterPath()
        top.moveTo(0, mid)
        for index, peak in enumerate(self._peaks):
            x = index * width / max(1, count - 1)
            top.lineTo(x, mid - peak_to_height(peak) * half)
        top.lineTo(width, mid)
        for index in range(count - 1, -1, -1):
            x = index * width / max(1, count - 1)
            top.lineTo(x, mid + peak_to_height(self._peaks[index]) * half)
        top.closeSubpath()

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._WAVE)
        painter.drawPath(top)

        if self._duration > 0:
            playhead_x = min(1.0, self._position / self._duration) * width
            painter.save()
            painter.setClipRect(QRectF(0, 0, playhead_x, height))
            painter.setBrush(self._PLAYED)
            painter.drawPath(top)
            painter.restore()

            painter.setPen(QPen(self._PLAYHEAD, 2))
            painter.drawLine(QPointF(playhead_x, 0), QPointF(playhead_x, height))


class VideoPreview(QWidget):
    """A titled video player with play/pause and a seek slider.

    Emits :attr:`position_changed` (milliseconds) so a trim UI can capture the
    current playhead as a start/end point.
    """

    position_changed = Signal(int)

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self._duration = 0
        self._build_ui(title)

    def _build_ui(self, title):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(title))

        self.waveform = AudioWaveform()

        if not MULTIMEDIA_AVAILABLE:
            notice = QLabel(
                "Video preview is unavailable.\n"
                "Install the Qt Multimedia plugins to enable playback."
            )
            notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
            notice.setMinimumHeight(160)
            layout.addWidget(notice)
            layout.addWidget(self.waveform)
            self._player = None
            self.time_label = QLabel("")
            return

        self._video_widget = QVideoWidget()
        self._video_widget.setMinimumHeight(180)
        layout.addWidget(self._video_widget, stretch=1)
        layout.addWidget(self.waveform)

        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._player.setAudioOutput(self._audio)
        self._player.setVideoOutput(self._video_widget)
        self._player.positionChanged.connect(self._on_position)
        self._player.durationChanged.connect(self._on_duration)
        self.waveform.seek_requested.connect(self._player.setPosition)

        controls = QHBoxLayout()
        self._play_button = QPushButton("Play")
        self._play_button.clicked.connect(self.toggle_play)
        controls.addWidget(self._play_button)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 0)
        self._slider.sliderMoved.connect(self._player.setPosition)
        controls.addWidget(self._slider, stretch=1)

        self.time_label = QLabel("00:00:00.000")
        controls.addWidget(self.time_label)

        layout.addLayout(controls)

    # -- Public API ---------------------------------------------------------

    def load(self, file_path):
        """Load a media file for playback and draw its audio waveform."""
        self.waveform.load(file_path)
        if not self._player:
            return
        from PySide6.QtCore import QUrl

        self._player.setSource(QUrl.fromLocalFile(file_path))
        if hasattr(self, "_play_button"):
            self._play_button.setText("Play")

    def clear(self):
        self.waveform.clear()
        if self._player:
            self._player.setSource("")

    def current_position(self):
        """Current playhead in milliseconds (0 if unavailable)."""
        return self._player.position() if self._player else 0

    def current_timestamp(self):
        return format_timestamp(self.current_position())

    def toggle_play(self):
        if not self._player:
            return
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
            self._play_button.setText("Play")
        else:
            self._player.play()
            self._play_button.setText("Pause")

    def stop(self):
        if self._player:
            self._player.stop()

    # -- Signals ------------------------------------------------------------

    def _on_position(self, position):
        if hasattr(self, "_slider"):
            self._slider.setValue(position)
        self.time_label.setText(format_timestamp(position))
        self.waveform.set_position(position)
        self.position_changed.emit(position)

    def _on_duration(self, duration):
        self._duration = duration
        self.waveform.set_duration(duration)
        if hasattr(self, "_slider"):
            self._slider.setRange(0, duration)
