# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for KherveCAD — one-folder (onedir) build.

Produces ``dist/KherveCAD/KherveCAD.exe`` alongside a folder of the
decompressed runtime (Python + Qt), so it launches instantly with
nothing to unpack — and so the bundled OpenSCAD can sit next to it in
``dist/KherveCAD/openscad/`` (see packaging/build_installer.py, which
puts it there). Build with:

    pyinstaller packaging/KherveCAD.spec --noconfirm

On macOS the same spec additionally wraps the collected folder into
``dist/KherveCAD.app`` — Finder will not treat a bare folder as an
application — and packaging/build_macos.py drops OpenSCAD into that
bundle's ``Contents/Resources/openscad/``.

The window/taskbar icon is baked in from ``packaging/khervecad.ico``
(regenerate with ``python packaging/make_icon.py``); macOS needs an
``.icns`` instead, generated on demand by ``packaging/make_icns.py``.
"""

import os
import subprocess
import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules

_HERE = os.path.abspath(SPECPATH)                 # packaging/
_ROOT = os.path.dirname(_HERE)                    # project root

_IS_MAC = sys.platform == "darwin"

# The icon format is per-platform and .icns is built from the same PNG on
# demand, so a Mac checkout needs no committed binary the Windows build
# would never read.
if _IS_MAC:
    _ICON = os.path.join(_ROOT, "build", "KherveCAD.icns")
    if not os.path.isfile(_ICON):
        subprocess.run([sys.executable,
                        os.path.join(_HERE, "make_icns.py"), _ICON],
                       check=True)
else:
    _ICON = os.path.join(_HERE, "khervecad.ico")

datas, binaries, hiddenimports = [], [], []

# Bake the resolved version into the frozen build — a PyInstaller bundle
# never ships .git, so without this khervecad/_version.py would fall back
# to the placeholder "0.1.0". build_installer.py writes this file with the
# real git-derived version just before invoking PyInstaller.
_version_file = os.path.join(_ROOT, "khervecad", "VERSION")
if os.path.isfile(_version_file):
    datas.append((_version_file, "khervecad"))

# The whole app package. Several modules are imported lazily inside
# functions or purely for their import side effects (examples_flowers /
# examples_trees extend examples.EXAMPLES on import, the library_* modules
# register parts into PARTS), so nothing static would pull them in.
hiddenimports += collect_submodules("khervecad")

# Dependencies that ship data files or dynamically-imported submodules.
for _pkg in ("qtawesome",):
    try:
        d, b, h = collect_all(_pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass   # optional dependency not installed — skip it

a = Analysis(
    [os.path.join(_ROOT, "KherveCAD.py")],
    pathex=[_ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # Trim libraries the app never uses, to keep the folder smaller.
    # KherveCAD's geometry is pure Python (mesh.py) — no numpy/scipy.
    excludes=["tkinter", "PyQt6", "PySide2", "PySide6", "PyQt5.QtQml",
              "PyQt5.QtQuick", "PyQt5.QtWebEngine", "numpy", "scipy",
              "matplotlib", "pandas", "PIL"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,                 # onedir: binaries live in COLLECT
    name="KherveCAD",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,                         # GUI app: no console window
    icon=_ICON,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="KherveCAD",                      # -> dist/KherveCAD/
)

# --------------------------------------------------------- macOS bundle

if _IS_MAC:
    # CFBundleShortVersionString has to be dot-separated digits, and the
    # git-derived string carries a "+sha" suffix Finder rejects.
    _short_version = "0.1.0"
    if os.path.isfile(_version_file):
        with open(_version_file, encoding="utf-8") as _fh:
            _short_version = _fh.read().strip().split("+")[0] or _short_version

    app = BUNDLE(
        coll,
        name="KherveCAD.app",
        icon=_ICON,
        bundle_identifier="com.kerherve.khervecad",
        version=_short_version,
        info_plist={
            "CFBundleName": "KherveCAD",
            "CFBundleDisplayName": "KherveCAD",
            "CFBundleShortVersionString": _short_version,
            "CFBundleVersion": _short_version,
            "LSMinimumSystemVersion": "11.0",
            # Without this the 2D sketch view and the software-rendered 3D
            # preview draw at 1x and get scaled up — every line reads soft
            # on a Retina display.
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
            "CFBundleDocumentTypes": [
                {
                    "CFBundleTypeName": "KherveCAD Model",
                    "CFBundleTypeExtensions": ["kcad"],
                    "CFBundleTypeRole": "Editor",
                    "LSHandlerRank": "Owner",
                },
                {
                    "CFBundleTypeName": "OpenSCAD Program",
                    "CFBundleTypeExtensions": ["scad"],
                    "CFBundleTypeRole": "Editor",
                    "LSHandlerRank": "Alternate",
                },
                {
                    "CFBundleTypeName": "3D Mesh",
                    "CFBundleTypeExtensions": ["stl", "obj", "off", "3mf"],
                    "CFBundleTypeRole": "Viewer",
                    "LSHandlerRank": "Alternate",
                },
            ],
            "NSHumanReadableCopyright":
                "Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0.",
        },
    )
