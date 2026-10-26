"""Main application window: wiring, layout, previews, and trim controls."""

import os
import sys

from PySide6.QtCore import Qt, QThread
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
from .conversion import ConversionController, LoudnessAnalysisWorker, time_to_seconds
from .downloader import DownloadWorker, UpdateWorker
from .preview import VideoPreview, format_loudness


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Amrut Audio Video Converter")
        self.resize(1080, 760)

        self.input_duration = 0.0
        self.input_video_codec = None
        self.input_audio_codec = None
        self.input_sample_rate = None
        self.controller = ConversionController(self)
        self.controller.progress.connect(self._on_progress)
        self.controller.log.connect(self._append_log)
        self.controller.finished.connect(self._on_finished)

        self._download_thread = None
        self._download_worker = None
        self._update_thread = None
        self._update_worker = None
        self._analysis_thread = None
        self._analysis_worker = None
        self._pending_job = None
        self._last_output_dir = None
        self._last_download_dir = None

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
        self.output_edit.setPlaceholderText("Choose an output folder (filename auto-filled)")
        output_button = QPushButton("Browse")
        output_button.clicked.connect(self.select_output)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("or paste a video URL to download")
        self.download_button = QPushButton("Download")
        self.download_button.clicked.connect(self.start_download)
        self.update_button = QPushButton("Update downloader")
        self.update_button.setToolTip(
            "Fetch the latest yt-dlp so downloads keep working as sites change."
        )
        self.update_button.clicked.connect(self.start_update_downloader)

        url_row = QHBoxLayout()
        url_row.addWidget(self.download_button)
        url_row.addWidget(self.update_button)
        url_buttons = QWidget()
        url_buttons.setLayout(url_row)
        url_buttons.setContentsMargins(0, 0, 0, 0)

        disclaimer = QLabel(
            "Downloading may violate a site's Terms of Service or copyright. "
            "Only download content you have the right to use."
        )
        disclaimer.setWordWrap(True)
        disclaimer.setStyleSheet("color: gray; font-size: 11px;")

        grid.addWidget(QLabel("Input video:"), 0, 0)
        grid.addWidget(self.input_edit, 0, 1)
        grid.addWidget(input_button, 0, 2)
        grid.addWidget(QLabel("Video URL:"), 1, 0)
        grid.addWidget(self.url_edit, 1, 1)
        grid.addWidget(url_buttons, 1, 2)
        grid.addWidget(disclaimer, 2, 1, 1, 2)
        grid.addWidget(QLabel("Output folder:"), 3, 0)
        grid.addWidget(self.output_edit, 3, 1)
        grid.addWidget(output_button, 3, 2)
        return grid

    def _build_previews(self):
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)

        self.input_preview = VideoPreview("Input preview")
        self.output_preview = VideoPreview("Output preview")
        self.input_preview.waveform.loudness_changed.connect(
            lambda value: self._log_loudness("Input", value)
        )
        self.output_preview.waveform.loudness_changed.connect(
            lambda value: self._log_loudness("Output", value)
        )
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

        self.loudness_combo = QComboBox()
        self.loudness_combo.addItem("Keep original level", None)
        for preset in profiles.LOUDNESS_PRESETS:
            self.loudness_combo.addItem(preset.label, preset.key)

        grid.addWidget(QLabel("Mode:"), 0, 0)
        grid.addWidget(self.profile_combo, 0, 1)
        grid.addWidget(QLabel("Format:"), 1, 0)
        grid.addWidget(self.format_combo, 1, 1)
        grid.addWidget(QLabel("Resolution:"), 2, 0)
        grid.addWidget(self.scale_combo, 2, 1)
        grid.addWidget(QLabel("Audio loudness:"), 3, 0)
        grid.addWidget(self.loudness_combo, 3, 1)
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
        self.cancel_button.clicked.connect(self.cancel_work)
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

    def _select_profile(self, key):
        index = self.profile_combo.findData(key)
        if index >= 0:
            self.profile_combo.setCurrentIndex(index)

    def _select_format(self, name):
        index = self.format_combo.findData(name)
        if index >= 0:
            self.format_combo.setCurrentIndex(index)

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
        self._update_loudness_enabled()

    def _update_loudness_enabled(self):
        profile = profiles.profile_by_key(self._current_profile_key())
        allowed = profile is not None and not profile.copy
        if not allowed:
            self.loudness_combo.setCurrentIndex(0)
        self.loudness_combo.setEnabled(allowed)
        self.loudness_combo.setToolTip(
            "Two-pass EBU R128 loudness normalization of the first audio "
            "track: measures the input, then applies a clean gain (true-peak "
            "limited only if needed) to hit the target."
            if allowed
            else "Remux copies audio untouched. Choose an encoding mode to "
            "normalize loudness."
        )

    def _log_loudness(self, label, measurement):
        if measurement:
            self._append_log(f"{label} loudness: {format_loudness(measurement)}")

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

    def _default_output_dir(self):
        """A sensible default output folder for the current OS."""
        home = os.path.expanduser("~")
        if os.name == "nt":
            candidates = [os.path.join(home, "Videos"), os.path.join(home, "Downloads")]
        elif sys.platform == "darwin":
            candidates = [os.path.join(home, "Movies"), os.path.join(home, "Downloads")]
        else:
            candidates = [os.path.join(home, "Videos"), os.path.join(home, "Downloads")]
        for candidate in candidates:
            if os.path.isdir(candidate):
                return candidate
        return home

    def select_input(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select input video",
            "",
            "Video files (*.mp4 *.mov *.mkv *.avi *.webm *.m4v);;All files (*.*)",
        )
        if file_path:
            self._load_input_file(file_path)

    def _load_input_file(self, file_path):
        """Set a file as the conversion input: preview, probe, default output."""
        self.input_edit.setText(file_path)
        self.input_preview.load(file_path)

        try:
            info = ffmpeg.probe_media(file_path)
            self.input_duration = info["duration"]
            self.input_video_codec = info.get("video_codec")
            self.input_audio_codec = info.get("audio_codec")
            self.input_sample_rate = info.get("sample_rate")
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
            self.input_video_codec = None
            self.input_audio_codec = None
            self.input_sample_rate = None
            self._append_log(f"Could not read input details: {error}")

        fmt = profiles.format_by_name(self._current_format_name())
        if fmt:
            if self._last_output_dir and os.path.isdir(self._last_output_dir):
                directory = self._last_output_dir
            else:
                directory = os.path.dirname(file_path)
            stem = os.path.splitext(os.path.basename(file_path))[0]
            self.output_edit.setText(
                os.path.join(directory, f"{stem}_converted.{fmt.extension}")
            )

    def start_download(self):
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "No URL", "Paste a video URL to download.")
            return
        if self._download_thread is not None:
            return

        start_dir = self._last_download_dir or self._default_output_dir()
        dest_dir = QFileDialog.getExistingDirectory(
            self, "Choose download folder", start_dir
        )
        if not dest_dir:
            return
        self._last_download_dir = dest_dir

        self.download_button.setEnabled(False)
        self.convert_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("Downloading…")

        self._download_thread = QThread(self)
        self._download_worker = DownloadWorker(url, dest_dir)
        self._download_worker.moveToThread(self._download_thread)
        self._download_thread.started.connect(self._download_worker.run)
        self._download_worker.progress.connect(self._on_progress)
        self._download_worker.log.connect(self._append_log)
        self._download_worker.finished.connect(self._on_download_finished)
        self._download_thread.start()

    def _on_download_finished(self, success, result):
        if self._download_thread is not None:
            self._download_thread.quit()
            self._download_thread.wait()
            self._download_thread = None
            self._download_worker = None

        self.download_button.setEnabled(True)
        self.convert_button.setEnabled(not self._busy())

        if success:
            self.status_label.setText("Download complete")
            self._load_input_file(result)
        else:
            self.status_label.setText("Download failed")
            self._append_log(f"Download error: {result}")
            QMessageBox.critical(
                self,
                "Download failed",
                f"Could not download the video.\n\n{result}",
            )

    def start_update_downloader(self):
        if self._update_thread is not None:
            return
        self.update_button.setEnabled(False)
        self.status_label.setText("Updating downloader…")

        self._update_thread = QThread(self)
        self._update_worker = UpdateWorker()
        self._update_worker.moveToThread(self._update_thread)
        self._update_thread.started.connect(self._update_worker.run)
        self._update_worker.log.connect(self._append_log)
        self._update_worker.finished.connect(self._on_update_finished)
        self._update_thread.start()

    def _on_update_finished(self, success, result):
        if self._update_thread is not None:
            self._update_thread.quit()
            self._update_thread.wait()
            self._update_thread = None
            self._update_worker = None

        self.update_button.setEnabled(True)
        if success:
            self.status_label.setText(f"Downloader updated (yt-dlp {result})")
            self._append_log(f"yt-dlp updated to {result}")
        else:
            self.status_label.setText("Downloader update failed")
            self._append_log(f"Update error: {result}")
            QMessageBox.critical(
                self,
                "Update failed",
                f"Could not update yt-dlp.\n\n{result}",
            )

    def select_output(self):
        start = (
            self._last_output_dir
            or os.path.dirname(self.output_edit.text().strip())
            or self._default_output_dir()
        )
        directory = QFileDialog.getExistingDirectory(
            self, "Choose output folder", start
        )
        if not directory:
            return

        self._last_output_dir = directory
        fmt = profiles.format_by_name(self._current_format_name())
        extension = fmt.extension if fmt else "mp4"

        current = self.output_edit.text().strip()
        if current:
            stem = os.path.splitext(os.path.basename(current))[0]
        else:
            input_path = self.input_edit.text().strip()
            base = os.path.splitext(os.path.basename(input_path))[0]
            stem = f"{base}_converted" if base else "output"

        self.output_edit.setText(
            os.path.join(directory, f"{stem}.{extension}")
        )

    def _target_duration(self, job):
        if not job.has_range or self.input_duration <= 0:
            return self.input_duration

        start = time_to_seconds(job.start) if job.start else 0.0
        end = time_to_seconds(job.end) if job.end else self.input_duration
        return max(0.0, end - start)

    def start_conversion(self):
        if self._busy():
            return

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

        profile = profiles.profile_by_key(self._current_profile_key())
        format_name = self._current_format_name()
        if profile is not None and profile.copy:
            problems = profiles.remux_incompatibilities(
                format_name, self.input_video_codec, self.input_audio_codec
            )
            if problems:
                box = QMessageBox(self)
                box.setIcon(QMessageBox.Icon.Warning)
                box.setWindowTitle("Remux not possible")
                box.setText(
                    f"The {', '.join(problems)} cannot be copied into a "
                    f"{format_name} file."
                )
                box.setInformativeText(
                    "Convert to a compatible MP4 (H.264 / AAC) instead, or "
                    "cancel and choose settings yourself."
                )
                convert_button = box.addButton(
                    "Convert to MP4 (H.264/AAC)",
                    QMessageBox.ButtonRole.AcceptRole,
                )
                box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
                box.exec()
                if box.clickedButton() is not convert_button:
                    return
                self._select_profile("h264")
                self._select_format("MP4")

        output_file = self.output_edit.text().strip()
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
            loudness_key=self.loudness_combo.currentData()
            if self.loudness_combo.isEnabled()
            else None,
            input_sample_rate=self.input_sample_rate,
        )

        try:
            profiles.build_arguments(job)
        except ValueError as error:
            QMessageBox.critical(self, "Invalid settings", str(error))
            return

        self.log_edit.clear()
        self.output_preview.clear()

        if job.loudness_key and not self.input_audio_codec:
            self._append_log("Input has no audio track; skipping loudness normalization.")
            job.loudness_key = None

        if job.loudness_key:
            self._start_loudness_analysis(job)
        else:
            self._launch_conversion(job)

    def _start_loudness_analysis(self, job):
        """Pass 1/2: measure loudness of exactly the range that will be encoded."""
        preset = profiles.loudness_preset_by_key(job.loudness_key)
        self._pending_job = job

        self.convert_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Pass 1/2: measuring loudness…")
        self._append_log(
            f"Pass 1/2: measuring loudness (target {preset.integrated:g} LUFS, "
            f"true peak ≤ {preset.true_peak:g} dBTP)…"
        )

        self._analysis_thread = QThread(self)
        self._analysis_worker = LoudnessAnalysisWorker(
            job.input_file,
            profiles.loudnorm_filter(preset),
            job.start,
            job.end,
            self._target_duration(job),
        )
        self._analysis_worker.moveToThread(self._analysis_thread)
        self._analysis_thread.started.connect(self._analysis_worker.run)
        self._analysis_worker.progress.connect(self._on_analysis_progress)
        self._analysis_worker.finished.connect(self._on_analysis_finished)
        self._analysis_thread.start()

    def _on_analysis_progress(self, percent):
        self.progress_bar.setValue(percent)
        self.status_label.setText(f"Pass 1/2: measuring loudness… {percent}%")

    def _on_analysis_finished(self, success, result):
        if self._analysis_thread is not None:
            self._analysis_thread.quit()
            self._analysis_thread.wait()
            self._analysis_thread = None
            self._analysis_worker = None

        job, self._pending_job = self._pending_job, None

        if not success:
            self.convert_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            self.progress_bar.setValue(0)
            if result is None:
                self.status_label.setText("Cancelled")
                self._append_log("Loudness measurement cancelled.")
                return
            self.status_label.setText("Loudness measurement failed")
            self._append_log(f"Loudness measurement failed: {result}")
            QMessageBox.critical(
                self,
                "Loudness measurement failed",
                f"Could not measure the input loudness.\n\n{result}",
            )
            return

        self._append_log(f"Measured input: {format_loudness(result)}")
        if result["input_i"] <= profiles.LOUDNESS_SILENCE_LUFS:
            self._append_log(
                "Input audio is silent; converting without loudness normalization."
            )
            job.loudness_key = None
        else:
            job.loudness_measured = result
        self._launch_conversion(job)

    def _launch_conversion(self, job):
        ffmpeg_path = ffmpeg.tool_path("ffmpeg")
        try:
            arguments = profiles.build_arguments(job)
        except ValueError as error:
            self.convert_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            QMessageBox.critical(self, "Invalid settings", str(error))
            return

        self._pending_output = job.output_file
        self.progress_bar.setValue(0)
        self._append_log(f"Program: {ffmpeg_path}")
        self._append_log("Arguments: " + " ".join(arguments))
        self._append_log("")

        self.convert_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.status_label.setText(
            "Pass 2/2: converting…" if job.loudness_measured else "Converting…"
        )

        self.controller.start(
            ffmpeg_path, arguments, self._target_duration(job)
        )

    def cancel_work(self):
        if self._analysis_worker is not None:
            self._analysis_worker.cancel()
        self.controller.cancel()

    def _busy(self):
        """True while loudness pass 1 or an FFmpeg conversion is running."""
        return self._analysis_thread is not None or self.controller.running

    def closeEvent(self, event):
        self.input_preview.waveform.clear()
        self.output_preview.waveform.clear()
        if self._analysis_thread is not None:
            self._analysis_worker.cancel()
            self._analysis_thread.quit()
            self._analysis_thread.wait(5000)
        super().closeEvent(event)

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
