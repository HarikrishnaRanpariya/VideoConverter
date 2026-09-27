"""Main application window: wiring, layout, previews, and trim controls."""

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import ffmpeg, profiles
from .conversion import ConversionController, time_to_seconds
from .preview import VideoPreview


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Converter")
        self.resize(1080, 760)

        self.input_duration = 0.0
        self.controller = ConversionController(self)
        self.controller.progress.connect(self._on_progress)
        self.controller.log.connect(self._append_log)
        self.controller.finished.connect(self._on_finished)

        self._build_ui()
        self._check_tools()
        self._refresh_formats_for_profile()

    # -- UI construction ----------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        root.addLayout(self._build_file_row())
        root.addWidget(self._build_previews())
        root.addWidget(self._build_options())
        root.addWidget(self._build_trim())
        root.addLayout(self._build_action_row())
        root.addWidget(self.progress_bar_widget())
        root.addWidget(self.status_label_widget())
        root.addWidget(QLabel("FFmpeg log:"))
        root.addWidget(self._build_log())

    def _build_file_row(self):
        grid = QGridLayout()

        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Select an input video")
        input_button = QPushButton("Browse")
        input_button.clicked.connect(self.select_input)

        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Select the output file")
        output_button = QPushButton("Browse")
        output_button.clicked.connect(self.select_output)

        grid.addWidget(QLabel("Input video:"), 0, 0)
        grid.addWidget(self.input_edit, 0, 1)
        grid.addWidget(input_button, 0, 2)
        grid.addWidget(QLabel("Output file:"), 1, 0)
        grid.addWidget(self.output_edit, 1, 1)
        grid.addWidget(output_button, 1, 2)
        return grid

    def _build_previews(self):
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)

        self.input_preview = VideoPreview("Input preview")
        self.output_preview = VideoPreview("Output preview")
        layout.addWidget(self.input_preview)
        layout.addWidget(self.output_preview)
        return box

    def _build_options(self):
        group = QGroupBox("Conversion")
        grid = QGridLayout(group)

        self.profile_combo = QComboBox()
        for profile in profiles.PROFILES:
            self.profile_combo.addItem(profile.label, profile.key)
        self.profile_combo.currentIndexChanged.connect(
            self._refresh_formats_for_profile
        )

        self.format_combo = QComboBox()
        self.format_combo.currentIndexChanged.connect(
            self._update_output_extension
        )

        self.scale_combo = QComboBox()
        self.scale_combo.addItem("Keep original size", None)
        for height in (2160, 1440, 1080, 720, 480):
            self.scale_combo.addItem(f"{height}p", height)

        grid.addWidget(QLabel("Mode:"), 0, 0)
        grid.addWidget(self.profile_combo, 0, 1)
        grid.addWidget(QLabel("Format:"), 1, 0)
        grid.addWidget(self.format_combo, 1, 1)
        grid.addWidget(QLabel("Resolution:"), 2, 0)
        grid.addWidget(self.scale_combo, 2, 1)
        return group

    def _build_trim(self):
        group = QGroupBox("Trim (optional)")
        layout = QGridLayout(group)

        self.trim_check = QCheckBox("Convert only a selected range")
        self.trim_check.toggled.connect(self._toggle_trim)

        self.start_edit = QLineEdit("00:00:00.000")
        self.end_edit = QLineEdit("00:00:00.000")
        self.start_edit.setEnabled(False)
        self.end_edit.setEnabled(False)

        self.use_start_button = QPushButton("Use input position")
        self.use_start_button.clicked.connect(
            lambda: self.start_edit.setText(
                self.input_preview.current_timestamp()
            )
        )
        self.use_end_button = QPushButton("Use input position")
        self.use_end_button.clicked.connect(
            lambda: self.end_edit.setText(
                self.input_preview.current_timestamp()
            )
        )
        self.use_start_button.setEnabled(False)
        self.use_end_button.setEnabled(False)

        layout.addWidget(self.trim_check, 0, 0, 1, 3)
        layout.addWidget(QLabel("Start:"), 1, 0)
        layout.addWidget(self.start_edit, 1, 1)
        layout.addWidget(self.use_start_button, 1, 2)
        layout.addWidget(QLabel("End:"), 2, 0)
        layout.addWidget(self.end_edit, 2, 1)
        layout.addWidget(self.use_end_button, 2, 2)
        return group

    def _build_action_row(self):
        layout = QHBoxLayout()
        layout.addStretch()

        self.convert_button = QPushButton("Convert")
        self.convert_button.clicked.connect(self.start_conversion)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.controller.cancel)
        self.cancel_button.setEnabled(False)

        layout.addWidget(self.convert_button)
        layout.addWidget(self.cancel_button)
        return layout

    def progress_bar_widget(self):
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        return self.progress_bar

    def status_label_widget(self):
        self.status_label = QLabel("Ready")
        return self.status_label

    def _build_log(self):
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setPlaceholderText(
            "FFmpeg information and errors will appear here."
        )
        return self.log_edit

    # -- Behavior -----------------------------------------------------------

    def _check_tools(self):
        missing = ffmpeg.available_tools()
        if missing:
            QMessageBox.warning(
                self,
                "FFmpeg not found",
                "The following files were not found in the bin folder:\n\n"
                + "\n".join(missing),
            )

    def _current_profile_key(self):
        return self.profile_combo.currentData()

    def _current_format_name(self):
        return self.format_combo.currentData()

    def _refresh_formats_for_profile(self):
        profile_key = self._current_profile_key()
        allowed = profiles.formats_for_profile(profile_key)
        previous = self._current_format_name()

        self.format_combo.blockSignals(True)
        self.format_combo.clear()
        for fmt in allowed:
            self.format_combo.addItem(fmt.name, fmt.name)

        index = self.format_combo.findData(previous)
        if index >= 0:
            self.format_combo.setCurrentIndex(index)
        self.format_combo.blockSignals(False)

        self._update_output_extension()

    def _update_output_extension(self):
        output_path = self.output_edit.text().strip()
        format_name = self._current_format_name()
        fmt = profiles.format_by_name(format_name) if format_name else None

        if output_path and fmt:
            root, _ = os.path.splitext(output_path)
            self.output_edit.setText(f"{root}.{fmt.extension}")

    def _toggle_trim(self, enabled):
        for widget in (
            self.start_edit,
            self.end_edit,
            self.use_start_button,
            self.use_end_button,
        ):
            widget.setEnabled(enabled)

    def select_input(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select input video",
            "",
            "Video files (*.mp4 *.mov *.mkv *.avi *.webm *.m4v);;All files (*.*)",
        )
        if not file_path:
            return

        self.input_edit.setText(file_path)
        self.input_preview.load(file_path)

        try:
            info = ffmpeg.probe_media(file_path)
            self.input_duration = info["duration"]
            self._append_log(
                "Input: "
                f"{info.get('video_codec')} / {info.get('audio_codec')} "
                f"{info.get('width')}x{info.get('height')} "
                f"{self.input_duration:.2f}s"
            )
            if self.input_duration > 0:
                from .preview import format_timestamp

                self.end_edit.setText(
                    format_timestamp(int(self.input_duration * 1000))
                )
        except Exception as error:
            self.input_duration = 0.0
            self._append_log(f"Could not read input details: {error}")

        fmt = profiles.format_by_name(self._current_format_name())
        if fmt:
            directory = os.path.dirname(file_path)
            stem = os.path.splitext(os.path.basename(file_path))[0]
            self.output_edit.setText(
                os.path.join(directory, f"{stem}_converted.{fmt.extension}")
            )

    def select_output(self):
        fmt = profiles.format_by_name(self._current_format_name())
        file_filter = fmt.file_filter if fmt else "All files (*.*)"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Select output file",
            self.output_edit.text(),
            file_filter,
        )
        if not file_path:
            return

        if fmt:
            expected = f".{fmt.extension}"
            if not file_path.lower().endswith(expected):
                file_path += expected
        self.output_edit.setText(file_path)

    def _target_duration(self, job):
        if not job.has_range or self.input_duration <= 0:
            return self.input_duration

        start = time_to_seconds(job.start) if job.start else 0.0
        end = time_to_seconds(job.end) if job.end else self.input_duration
        return max(0.0, end - start)

    def start_conversion(self):
        input_file = self.input_edit.text().strip()
        output_file = self.output_edit.text().strip()
        ffmpeg_path = ffmpeg.tool_path("ffmpeg")

        if not os.path.isfile(ffmpeg_path):
            QMessageBox.critical(
                self, "Missing FFmpeg", "ffmpeg was not found in the bin folder."
            )
            return
        if not input_file or not os.path.isfile(input_file):
            QMessageBox.warning(self, "Invalid input", "Select a valid input video.")
            return
        if not output_file:
            QMessageBox.warning(self, "Invalid output", "Select an output file.")
            return
        if os.path.abspath(input_file) == os.path.abspath(output_file):
            QMessageBox.warning(
                self,
                "Invalid output",
                "The output file must be different from the input file.",
            )
            return

        output_directory = os.path.dirname(output_file)
        if output_directory and not os.path.isdir(output_directory):
            QMessageBox.warning(
                self, "Invalid directory", "The output directory does not exist."
            )
            return

        job = profiles.ConversionJob(
            input_file=input_file,
            output_file=output_file,
            profile_key=self._current_profile_key(),
            format_name=self._current_format_name(),
            start=self.start_edit.text().strip()
            if self.trim_check.isChecked()
            else None,
            end=self.end_edit.text().strip()
            if self.trim_check.isChecked()
            else None,
            scale_height=self.scale_combo.currentData(),
        )

        try:
            arguments = profiles.build_arguments(job)
        except ValueError as error:
            QMessageBox.critical(self, "Invalid settings", str(error))
            return

        self._pending_output = output_file
        self.log_edit.clear()
        self.progress_bar.setValue(0)
        self.output_preview.clear()
        self._append_log(f"Program: {ffmpeg_path}")
        self._append_log("Arguments: " + " ".join(arguments))
        self._append_log("")

        self.convert_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.status_label.setText("Converting…")

        self.controller.start(
            ffmpeg_path, arguments, self._target_duration(job)
        )

    # -- Controller callbacks ----------------------------------------------

    def _on_progress(self, percent):
        self.progress_bar.setValue(percent)
        self.status_label.setText(f"Converting: {percent}%")

    def _append_log(self, text):
        self.log_edit.appendPlainText(text)

    def _on_finished(self, success):
        self.convert_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

        if success:
            self.progress_bar.setValue(100)
            self.status_label.setText("Conversion completed")
            output = getattr(self, "_pending_output", "")
            if output and os.path.isfile(output):
                self.output_preview.load(output)
            QMessageBox.information(
                self, "Completed", "The video was converted successfully."
            )
        else:
            self.status_label.setText("Conversion failed")
            QMessageBox.critical(
                self,
                "Conversion failed",
                "FFmpeg could not complete the conversion.\n\n"
                "Check the FFmpeg log for details.",
            )
