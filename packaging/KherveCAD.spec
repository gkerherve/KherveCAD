# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for KherveCAD — one-folder (onedir) build.

Produces ``dist/KherveCAD/KherveCAD.exe`` alongside a folder of the
decompressed runtime (Python + Qt), so it launches instantly with
nothing to unpack — and so the bundled OpenSCAD can sit next to it in
``dist/KherveCAD/openscad/`` (see packaging/build_installer.py, which
puts it there). Build with:

    pyinstaller packaging/KherveCAD.spec --noconfirm

The window/taskbar icon is baked in from ``packaging/khervecad.ico``
(regenerate with ``python packaging/make_icon.py``).
"""

import os

from PyInstaller.utils.hooks import collect_all, collect_submodules

_HERE = os.path.abspath(SPECPATH)                 # packaging/
_ROOT = os.path.dirname(_HERE)                    # project root

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
    icon=os.path.join(_HERE, "khervecad.ico"),
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
