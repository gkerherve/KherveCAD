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

import os
import shutil
import struct
import tempfile
import xml.etree.ElementTree as ET
import zipfile
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
    (Edit > Locate OpenSCAD in the GUI). Setting the environment
    variable ``KHERVECAD_DISABLE_ENGINE`` forces the built-in preview
    (used by the test suite so no background renders are spawned).
    """
    if os.environ.get("KHERVECAD_DISABLE_ENGINE"):
        return ""
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


def _parse_obj(text):
    """Wavefront OBJ -> triangle list (v vertices + f faces, triangulated
    by fan; vt/vn slashes and negative indices handled)."""
    verts, mesh = [], []
    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "v" and len(parts) >= 4:
            verts.append((float(parts[1]), float(parts[2]),
                          float(parts[3])))
        elif parts[0] == "f" and len(parts) >= 4:
            idx = []
            for tok in parts[1:]:
                n = int(tok.split("/")[0])
                idx.append(n - 1 if n > 0 else len(verts) + n)
            for j in range(1, len(idx) - 1):
                try:
                    mesh.append((verts[idx[0]], verts[idx[j]],
                                 verts[idx[j + 1]]))
                except IndexError:
                    pass
    return mesh


def _parse_off(text):
    """Object File Format (OFF) -> triangle list. Faces of any vertex
    count are fan-triangulated; a leading OFF/COFF/NOFF header and #
    comments are tolerated."""
    tokens = []
    for line in text.splitlines():
        tokens.extend(line.split("#", 1)[0].split())
    if not tokens:
        return []
    i = 1 if tokens[0].upper().endswith("OFF") else 0
    mesh = []
    try:
        nv, nf = int(tokens[i]), int(tokens[i + 1])
        i += 3                                    # skip the edge count
        verts = []
        for _ in range(nv):
            verts.append((float(tokens[i]), float(tokens[i + 1]),
                          float(tokens[i + 2])))
            i += 3
        for _ in range(nf):
            cnt = int(tokens[i])
            i += 1
            face = [int(tokens[i + j]) for j in range(cnt)]
            i += cnt
            for j in range(1, cnt - 1):
                mesh.append((verts[face[0]], verts[face[j]],
                             verts[face[j + 1]]))
    except (IndexError, ValueError):
        pass
    return mesh


def _parse_3mf(path: str):
    """3MF (a zip of XML) -> triangle list. Reads every mesh's vertices
    and triangles; build-item transforms are ignored (the OpenSCAD engine
    applies them for the exact render)."""
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        model = "3D/3dmodel.model"
        if model not in names:
            model = next((n for n in names
                          if n.lower().endswith(".model")), None)
            if model is None:
                return []
        root = ET.fromstring(archive.read(model))
    for element in root.iter():                   # drop XML namespaces
        element.tag = element.tag.split("}")[-1]
    mesh = []
    for block in root.iter("mesh"):
        verts = [(float(v.get("x")), float(v.get("y")), float(v.get("z")))
                 for v in block.iter("vertex")]
        for tri in block.iter("triangle"):
            try:
                mesh.append((verts[int(tri.get("v1"))],
                             verts[int(tri.get("v2"))],
                             verts[int(tri.get("v3"))]))
            except (IndexError, TypeError, ValueError):
                pass
    return mesh


#: Mesh formats KherveCAD can preview in the built-in viewer (the
#: OpenSCAD engine's import() renders them all for the exact mesh).
MESH_EXTS = (".stl", ".obj", ".off", ".3mf")


def parse_mesh(path: str):
    """Parse any supported mesh file into a triangle list, by extension."""
    ext = Path(path).suffix.lower()
    if ext == ".obj":
        return _parse_obj(Path(path).read_text(errors="replace"))
    if ext == ".off":
        return _parse_off(Path(path).read_text(errors="replace"))
    if ext == ".3mf":
        return _parse_3mf(path)
    return parse_stl(path)


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
            self.render_failed.emit(stderr or "render failed")
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
