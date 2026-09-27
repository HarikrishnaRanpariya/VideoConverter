"""QProcess-based FFmpeg conversion controller and progress parsing."""

from PySide6.QtCore import QObject, QProcess, QTimer, Signal


def time_to_seconds(value):
    """Convert ``HH:MM:SS.microseconds`` into seconds (0.0 on failure)."""
    try:
        hours, minutes, seconds = value.split(":")
        return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
    except (ValueError, AttributeError):
        return 0.0


class ConversionController(QObject):
    """Runs FFmpeg in the background and reports progress, logs, and result."""

    progress = Signal(int)      # 0..100
    log = Signal(str)
    finished = Signal(bool)     # True on success

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process = None
        self._target_duration = 0.0
        self._stdout_buffer = ""

    @property
    def running(self):
        return (
            self._process is not None
            and self._process.state() != QProcess.ProcessState.NotRunning
        )

    def start(self, ffmpeg_path, arguments, target_duration):
        """Launch FFmpeg. ``target_duration`` drives the progress percentage."""
        self._target_duration = max(0.0, float(target_duration))
        self._stdout_buffer = ""

        self._process = QProcess(self)
        self._process.setProgram(ffmpeg_path)
        self._process.setArguments(arguments)
        self._process.setProcessChannelMode(
            QProcess.ProcessChannelMode.SeparateChannels
        )
        self._process.readyReadStandardOutput.connect(self._read_progress)
        self._process.readyReadStandardError.connect(self._read_error)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(
            lambda error: self.log.emit(f"QProcess error: {error}")
        )
        self._process.start()

    def cancel(self):
        if not self.running:
            return

        self.log.emit("Cancelling…")
        process = self._process
        process.terminate()

        def force_stop():
            if process and process.state() != QProcess.ProcessState.NotRunning:
                process.kill()

        QTimer.singleShot(3000, force_stop)

    def _read_progress(self):
        if not self._process:
            return

        text = bytes(self._process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        self._stdout_buffer += text

        while "\n" in self._stdout_buffer:
            line, self._stdout_buffer = self._stdout_buffer.split("\n", 1)
            line = line.strip()

            if not line or "=" not in line:
                continue

            key, value = line.split("=", 1)

            if key == "out_time" and self._target_duration > 0:
                seconds = time_to_seconds(value)
                percent = int(seconds / self._target_duration * 100)
                self.progress.emit(max(0, min(100, percent)))
            elif key == "progress" and value == "end":
                self.progress.emit(100)

    def _read_error(self):
        if not self._process:
            return

        text = bytes(self._process.readAllStandardError()).decode(
            "utf-8", errors="replace"
        )
        if text:
            self.log.emit(text.rstrip())

    def _on_finished(self, exit_code, _exit_status):
        success = exit_code == 0
        if success:
            self.progress.emit(100)
        self.finished.emit(success)
        self._process = None
