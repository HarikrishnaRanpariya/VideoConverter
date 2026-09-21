import os
import sys
import subprocess

from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QComboBox,
    QProgressBar,
    QPlainTextEdit,
    QMessageBox,
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
)


def application_directory():
    """
    Locate bundled files.

    When running from source, use the directory containing app.py.
    When running as a PyInstaller one-file executable, use _MEIPASS.
    """
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))

    return os.path.dirname(os.path.abspath(__file__))


def tool_path(tool_name):
    """
    Return the bundled FFmpeg or FFprobe path.
    """
    return os.path.join(
        application_directory(),
        "bin",
        f"{tool_name}.exe"
    )


def read_duration(input_file):
    """
    Use FFprobe to obtain the input duration in seconds.
    """
    ffprobe = tool_path("ffprobe")

    if not os.path.isfile(ffprobe):
        raise FileNotFoundError("ffprobe.exe was not found in the bin folder.")

    command = [
        ffprobe,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        input_file,
    ]

    startup_info = None

    if os.name == "nt":
        startup_info = subprocess.STARTUPINFO()
        startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
        startupinfo=startup_info,
    )

    return float(result.stdout.strip())


def time_to_seconds(value):
    """
    Convert HH:MM:SS.microseconds into seconds.
    """
    try:
        hours, minutes, seconds = value.split(":")
        return (
            float(hours) * 3600
            + float(minutes) * 60
            + float(seconds)
        )
    except (ValueError, AttributeError):
        return 0.0


class VideoConverter(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Video Converter")
        self.resize(850, 620)

        self.process = None
        self.input_duration = 0.0
        self.stdout_buffer = ""

        self.create_interface()
        self.check_ffmpeg()

    def create_interface(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Input
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Select an input video")

        input_button = QPushButton("Browse")
        input_button.clicked.connect(self.select_input)

        # Output format
        self.format_combo = QComboBox()
        self.format_combo.addItems(["MP4", "MOV"])
        self.format_combo.currentTextChanged.connect(
            self.update_output_extension
        )

        # Conversion profile
        self.profile_combo = QComboBox()
        self.profile_combo.addItem(
            "Remux – copy video and audio",
            "remux"
        )
        self.profile_combo.addItem(
            "Compatible – H.264 video and AAC audio",
            "compatible"
        )
        self.profile_combo.addItem(
            "Editing – ProRes 422 and PCM audio",
            "prores"
        )
        self.profile_combo.currentIndexChanged.connect(
            self.profile_changed
        )

        # Output
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Select the output file")

        output_button = QPushButton("Browse")
        output_button.clicked.connect(self.select_output)

        # Buttons
        self.convert_button = QPushButton("Convert")
        self.convert_button.clicked.connect(self.start_conversion)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_conversion)
        self.cancel_button.setEnabled(False)

        # Progress and status
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.status_label = QLabel("Ready")

        # FFmpeg log
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setPlaceholderText(
            "FFmpeg information and errors will appear here."
        )

        grid = QGridLayout()

        grid.addWidget(QLabel("Input video:"), 0, 0)
        grid.addWidget(self.input_edit, 0, 1)
        grid.addWidget(input_button, 0, 2)

        grid.addWidget(QLabel("Output format:"), 1, 0)
        grid.addWidget(self.format_combo, 1, 1)

        grid.addWidget(QLabel("Conversion mode:"), 2, 0)
        grid.addWidget(self.profile_combo, 2, 1, 1, 2)

        grid.addWidget(QLabel("Output file:"), 3, 0)
        grid.addWidget(self.output_edit, 3, 1)
        grid.addWidget(output_button, 3, 2)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.convert_button)
        button_layout.addWidget(self.cancel_button)

        layout = QVBoxLayout(central_widget)
        layout.addLayout(grid)
        layout.addSpacing(10)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        layout.addLayout(button_layout)
        layout.addWidget(QLabel("FFmpeg log:"))
        layout.addWidget(self.log_edit)

    def check_ffmpeg(self):
        missing = []

        for tool in ("ffmpeg", "ffprobe"):
            path = tool_path(tool)

            if not os.path.isfile(path):
                missing.append(f"{tool}.exe")

        if missing:
            QMessageBox.warning(
                self,
                "FFmpeg not found",
                "The following files were not found in the bin folder:\n\n"
                + "\n".join(missing)
            )

    def select_input(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select input video",
            "",
            (
                "Video files "
                "(*.mp4 *.mov *.mkv *.avi *.webm *.m4v);;"
                "All files (*.*)"
            ),
        )

        if not file_path:
            return

        self.input_edit.setText(file_path)

        extension = self.format_combo.currentText().lower()
        directory = os.path.dirname(file_path)
        filename = os.path.splitext(os.path.basename(file_path))[0]

        output_path = os.path.join(
            directory,
            f"{filename}_converted.{extension}"
        )

        self.output_edit.setText(output_path)

    def select_output(self):
        output_format = self.format_combo.currentText().lower()

        if output_format == "mp4":
            file_filter = "MP4 video (*.mp4)"
        else:
            file_filter = "MOV video (*.mov)"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Select output file",
            self.output_edit.text(),
            file_filter,
        )

        if file_path:
            expected_extension = f".{output_format}"

            if not file_path.lower().endswith(expected_extension):
                file_path += expected_extension

            self.output_edit.setText(file_path)

    def update_output_extension(self):
        output_path = self.output_edit.text().strip()

        if output_path:
            root, _ = os.path.splitext(output_path)
            extension = self.format_combo.currentText().lower()
            self.output_edit.setText(f"{root}.{extension}")

        self.profile_changed()

    def profile_changed(self):
        profile = self.profile_combo.currentData()

        # ProRes should normally be stored in MOV.
        if profile == "prores":
            self.format_combo.blockSignals(True)
            self.format_combo.setCurrentText("MOV")
            self.format_combo.setEnabled(False)
            self.format_combo.blockSignals(False)
            self.update_output_extension()
        else:
            self.format_combo.setEnabled(True)

    def create_ffmpeg_arguments(self, input_file, output_file):
        profile = self.profile_combo.currentData()
        output_format = self.format_combo.currentText().lower()

        arguments = [
            "-y",
            "-nostdin",
            "-i", input_file,
        ]

        if profile == "remux":
            arguments += [
                "-map", "0",
                "-c", "copy",
            ]

        elif profile == "compatible":
            arguments += [
                "-map", "0:v:0",
                "-map", "0:a?",
                "-c:v", "libx264",
                "-crf", "20",
                "-preset", "medium",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
            ]

            if output_format == "mp4":
                arguments += ["-movflags", "+faststart"]

        elif profile == "prores":
            arguments += [
                "-map", "0:v:0",
                "-map", "0:a?",
                "-c:v", "prores_ks",
                "-profile:v", "2",
                "-pix_fmt", "yuv422p10le",
                "-c:a", "pcm_s16le",
            ]

        # Machine-readable progress is written to standard output.
        arguments += [
            "-progress", "pipe:1",
            "-nostats",
            output_file,
        ]

        return arguments

    def start_conversion(self):
        input_file = self.input_edit.text().strip()
        output_file = self.output_edit.text().strip()
        ffmpeg = tool_path("ffmpeg")

        if not os.path.isfile(ffmpeg):
            QMessageBox.critical(
                self,
                "Missing FFmpeg",
                "ffmpeg.exe was not found in the bin folder."
            )
            return

        if not input_file or not os.path.isfile(input_file):
            QMessageBox.warning(
                self,
                "Invalid input",
                "Select a valid input video."
            )
            return

        if not output_file:
            QMessageBox.warning(
                self,
                "Invalid output",
                "Select an output file."
            )
            return

        if os.path.abspath(input_file) == os.path.abspath(output_file):
            QMessageBox.warning(
                self,
                "Invalid output",
                "The output file must be different from the input file."
            )
            return

        output_directory = os.path.dirname(output_file)

        if output_directory and not os.path.isdir(output_directory):
            QMessageBox.warning(
                self,
                "Invalid directory",
                "The selected output directory does not exist."
            )
            return

        profile = self.profile_combo.currentData()

        if profile == "remux":
            answer = QMessageBox.information(
                self,
                "Remux mode",
                "Remuxing works only when the destination container "
                "supports the existing video, audio, subtitle, and data "
                "streams.\n\n"
                "For example, AV1 cannot be copied into a normal MOV file."
            )

        try:
            self.input_duration = read_duration(input_file)
        except Exception as error:
            self.input_duration = 0.0
            self.append_log(f"Could not read duration: {error}")

        arguments = self.create_ffmpeg_arguments(
            input_file,
            output_file
        )

        self.log_edit.clear()
        self.progress_bar.setValue(0)
        self.stdout_buffer = ""

        self.append_log(f"Program: {ffmpeg}")
        self.append_log("Arguments:")
        self.append_log(" ".join(arguments))
        self.append_log("")

        self.process = QProcess(self)
        self.process.setProgram(ffmpeg)
        self.process.setArguments(arguments)
        self.process.setProcessChannelMode(
            QProcess.ProcessChannelMode.SeparateChannels
        )

        self.process.readyReadStandardOutput.connect(
            self.read_progress
        )
        self.process.readyReadStandardError.connect(
            self.read_error_output
        )
        self.process.finished.connect(
            self.conversion_finished
        )
        self.process.errorOccurred.connect(
            self.process_error
        )

        self.convert_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.status_label.setText("Converting...")

        self.process.start()

    def read_progress(self):
        if not self.process:
            return

        text = bytes(
            self.process.readAllStandardOutput()
        ).decode("utf-8", errors="replace")

        self.stdout_buffer += text

        while "\n" in self.stdout_buffer:
            line, self.stdout_buffer = self.stdout_buffer.split(
                "\n", 1
            )

            line = line.strip()

            if not line:
                continue

            if "=" not in line:
                continue

            key, value = line.split("=", 1)

            if key == "out_time":
                current_seconds = time_to_seconds(value)

                if self.input_duration > 0:
                    percentage = int(
                        current_seconds
                        / self.input_duration
                        * 100
                    )

                    percentage = max(0, min(100, percentage))
                    self.progress_bar.setValue(percentage)

                    self.status_label.setText(
                        f"Converting: {percentage}%"
                    )

            elif key == "progress" and value == "end":
                self.progress_bar.setValue(100)

    def read_error_output(self):
        if not self.process:
            return

        text = bytes(
            self.process.readAllStandardError()
        ).decode("utf-8", errors="replace")

        if text:
            self.append_log(text.rstrip())

    def conversion_finished(self, exit_code, exit_status):
        self.convert_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

        if exit_code == 0:
            self.progress_bar.setValue(100)
            self.status_label.setText("Conversion completed")

            QMessageBox.information(
                self,
                "Completed",
                "The video was converted successfully."
            )
        else:
            self.status_label.setText(
                f"Conversion failed: FFmpeg exit code {exit_code}"
            )

            QMessageBox.critical(
                self,
                "Conversion failed",
                "FFmpeg could not complete the conversion.\n\n"
                "Check the FFmpeg log for details."
            )

        self.process = None

    def process_error(self, error):
        self.append_log(f"QProcess error: {error}")

    def cancel_conversion(self):
        if not self.process:
            return

        if self.process.state() == QProcess.ProcessState.NotRunning:
            return

        self.status_label.setText("Cancelling...")
        self.process.terminate()

        process = self.process

        def force_stop():
            if (
                process
                and process.state()
                != QProcess.ProcessState.NotRunning
            ):
                process.kill()

        QTimer.singleShot(3000, force_stop)

    def append_log(self, text):
        self.log_edit.appendPlainText(text)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = VideoConverter()
    window.show()

    sys.exit(app.exec())
