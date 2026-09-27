# -*- mode: python ; coding: utf-8 -*-
#
# Cross-platform PyInstaller spec.
#   Windows  -> dist/VideoConverter/VideoConverter.exe   (unchanged behavior)
#   macOS    -> dist/VideoConverter.app                  (new)
#   Linux    -> dist/VideoConverter/VideoConverter
#
# Build with:  pyinstaller VideoConverter.spec

import os
import sys

is_windows = sys.platform.startswith("win")
is_macos = sys.platform == "darwin"

# Per-platform FFmpeg binary names (Windows uses .exe; macOS/Linux do not).
if is_windows:
    _binary_pairs = [("bin/ffmpeg.exe", "bin"), ("bin/ffprobe.exe", "bin")]
else:
    _binary_pairs = [("bin/ffmpeg", "bin"), ("bin/ffprobe", "bin")]


def _existing(pairs):
    """Keep only binaries that exist so a build never hard-fails on a missing tool."""
    kept = []
    for src, dest in pairs:
        if os.path.isfile(src):
            kept.append((src, dest))
        else:
            print(f"WARNING: bundled binary not found, skipping: {src}")
    return kept


binaries = _existing(_binary_pairs)

# UPX is reliable on Windows but frequently corrupts macOS binaries; disable off-Windows.
use_upx = is_windows


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=binaries,
    datas=[],
    hiddenimports=[
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VideoConverter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=use_upx,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=use_upx,
    upx_exclude=[],
    name='VideoConverter',
)

# On macOS, wrap the collected app into a proper .app bundle.
if is_macos:
    app = BUNDLE(
        coll,
        name='VideoConverter.app',
        icon=None,
        bundle_identifier='com.videoconverter.app',
        info_plist={
            'CFBundleName': 'Video Converter',
            'CFBundleDisplayName': 'Video Converter',
            'CFBundleShortVersionString': '2.0.0',
            'CFBundleVersion': '2.0.0',
            'NSHighResolutionCapable': True,
        },
    )
