"""Entry point for the Video Converter desktop application.

A PySide6 GUI front end for bundled FFmpeg/FFprobe. All application logic lives
in the ``videoconverter`` package; this module only starts the Qt event loop.
"""

import sys

from PySide6.QtWidgets import QApplication

from videoconverter.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
