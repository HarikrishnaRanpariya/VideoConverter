"""Reusable video preview widget built on Qt Multimedia.

Degrades gracefully to a message label if QtMultimedia is unavailable so the
converter still runs without the multimedia plugins.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

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

        if not MULTIMEDIA_AVAILABLE:
            notice = QLabel(
                "Video preview is unavailable.\n"
                "Install the Qt Multimedia plugins to enable playback."
            )
            notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
            notice.setMinimumHeight(160)
            layout.addWidget(notice)
            self._player = None
            self.time_label = QLabel("")
            return

        self._video_widget = QVideoWidget()
        self._video_widget.setMinimumHeight(180)
        layout.addWidget(self._video_widget, stretch=1)

        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._player.setAudioOutput(self._audio)
        self._player.setVideoOutput(self._video_widget)
        self._player.positionChanged.connect(self._on_position)
        self._player.durationChanged.connect(self._on_duration)

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
        """Load a media file for playback."""
        if not self._player:
            return
        from PySide6.QtCore import QUrl

        self._player.setSource(QUrl.fromLocalFile(file_path))
        if hasattr(self, "_play_button"):
            self._play_button.setText("Play")

    def clear(self):
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
        self.position_changed.emit(position)

    def _on_duration(self, duration):
        self._duration = duration
        if hasattr(self, "_slider"):
            self._slider.setRange(0, duration)
