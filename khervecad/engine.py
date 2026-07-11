"""OpenSCAD engine integration.

OpenSCAD is the engine behind KherveCAD: the GUI generates an OpenSCAD
program and, when the ``openscad`` binary is installed, this module
runs it headless to produce the exact mesh (booleans included) shown
in the 3D view and exported to STL. Rendering runs in a background
QProcess with debouncing so dragging in the 2D view stays smooth.
Without the binary the app still works — the built-in tessellator
(mesh.py) supplies the preview.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import shutil
import struct
import tempfile
from pathlib import Path

from PyQt5.QtCore import QObject, QProcess, QSettings, QTimer, pyqtSignal

_SETTINGS = ("Kherve", "KherveCAD")

#: places to look for the binary besides PATH.
_CANDIDATES = [
    r"C:\Program Files\OpenSCAD\openscad.exe",
    r"C:\Program Files (x86)\OpenSCAD\openscad.exe",
    "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD",
    "/usr/bin/openscad",
    "/usr/local/bin/openscad",
    "/snap/bin/openscad",
]


def find_openscad() -> str:
    """Path of the OpenSCAD binary, or '' when not installed.

    A custom location can be stored in QSettings key ``openscad_path``
    (Edit > Locate OpenSCAD in the GUI).
    """
    custom = QSettings(*_SETTINGS).value("openscad_path", "")
    if custom and Path(custom).exists():
        return str(custom)
    path = shutil.which("openscad")
    if path:
        return path
    for candidate in _CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return ""


def set_openscad_path(path: str):
    QSettings(*_SETTINGS).setValue("openscad_path", path)


# ----------------------------------------------------------------- STL

def parse_stl(path: str):
    """Parse a binary or ASCII STL file into a triangle list."""
    data = Path(path).read_bytes()
    if len(data) >= 84:
        count = struct.unpack_from("<I", data, 80)[0]
        if len(data) == 84 + count * 50:
            return _parse_binary(data, count)
    return _parse_ascii(data.decode("ascii", errors="replace"))


def _parse_binary(data: bytes, count: int):
    mesh = []
    offset = 84
    for _ in range(count):
        values = struct.unpack_from("<12f", data, offset)
        mesh.append(((values[3], values[4], values[5]),
                     (values[6], values[7], values[8]),
                     (values[9], values[10], values[11])))
        offset += 50
    return mesh


def _parse_ascii(text: str):
    mesh = []
    vertices = []
    for line in text.splitlines():
        parts = line.split()
        if parts[:1] == ["vertex"]:
            vertices.append(tuple(float(v) for v in parts[1:4]))
            if len(vertices) == 3:
                mesh.append(tuple(vertices))
                vertices = []
    return mesh


def write_stl(mesh, path: str, name: str = "khervecad"):
    """Write a binary STL (used for export when OpenSCAD is absent)."""
    with open(path, "wb") as fh:
        header = f"{name} (KherveCAD)".encode()[:80]
        fh.write(header.ljust(80, b"\0"))
        fh.write(struct.pack("<I", len(mesh)))
        for a, b, c in mesh:
            ux, uy, uz = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
            vx, vy, vz = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
            nx, ny, nz = (uy * vz - uz * vy, uz * vx - ux * vz,
                          ux * vy - uy * vx)
            length = (nx * nx + ny * ny + nz * nz) ** 0.5 or 1.0
            fh.write(struct.pack("<3f", nx / length, ny / length,
                                 nz / length))
            for v in (a, b, c):
                fh.write(struct.pack("<3f", *v))
            fh.write(b"\0\0")


# --------------------------------------------------------------- engine

class ScadEngine(QObject):
    """Debounced background renders through the OpenSCAD binary."""

    mesh_ready = pyqtSignal(list)      # exact mesh from OpenSCAD
    render_failed = pyqtSignal(str)    # compiler message
    busy_changed = pyqtSignal(bool)

    DEBOUNCE_MS = 500

    def __init__(self, parent=None):
        super().__init__(parent)
        self.binary = find_openscad()
        self._dir = Path(tempfile.mkdtemp(prefix="khervecad_"))
        self._process = None
        self._pending_code = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self.DEBOUNCE_MS)
        self._timer.timeout.connect(self._start)

    @property
    def available(self) -> bool:
        return bool(self.binary)

    def refresh_binary(self):
        self.binary = find_openscad()
        return self.binary

    # ------------------------------------------------------- rendering
    def request_render(self, scad_code: str):
        """Schedule a render of *scad_code* (debounced)."""
        if not self.available:
            return
        self._pending_code = scad_code
        self._timer.start()

    def _start(self):
        if self._pending_code is None:
            return
        if self._process is not None:
            # A render is running: keep the code pending; _finished
            # restarts the timer so the newest code wins.
            return
        code = self._pending_code
        self._pending_code = None
        scad_path = self._dir / "model.scad"
        stl_path = self._dir / "model.stl"
        scad_path.write_text(code, encoding="utf-8")
        self._process = QProcess(self)
        self._process.finished.connect(
            lambda _code, _status: self._finished(str(stl_path)))
        self._process.start(self.binary,
                            ["-o", str(stl_path), str(scad_path)])
        self.busy_changed.emit(True)

    def _finished(self, stl_path: str):
        process = self._process
        self._process = None
        self.busy_changed.emit(False)
        exit_ok = (process.exitStatus() == QProcess.NormalExit
                   and process.exitCode() == 0)
        if exit_ok and Path(stl_path).exists():
            try:
                mesh = parse_stl(stl_path)
            except Exception as exc:
                self.render_failed.emit(f"STL parse error: {exc}")
            else:
                self.mesh_ready.emit(mesh)
        else:
            stderr = bytes(process.readAllStandardError()) \
                .decode(errors="replace").strip()
            self.render_failed.emit(stderr.splitlines()[-1]
                                    if stderr else "render failed")
        if self._pending_code is not None:
            self._timer.start()

    # ---------------------------------------------------------- export
    def export_stl(self, scad_code: str, out_path: str) -> str:
        """Export *scad_code* to *out_path* synchronously via the
        binary. Returns '' on success, an error message otherwise."""
        scad_path = self._dir / "export.scad"
        scad_path.write_text(scad_code, encoding="utf-8")
        process = QProcess()
        process.start(self.binary, ["-o", out_path, str(scad_path)])
        process.waitForFinished(120000)
        if process.exitStatus() == QProcess.NormalExit and \
                process.exitCode() == 0:
            return ""
        stderr = bytes(process.readAllStandardError()) \
            .decode(errors="replace").strip()
        return stderr or "OpenSCAD export failed"
