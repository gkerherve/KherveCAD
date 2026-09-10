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
import sys
import tempfile
import weakref
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from PyQt5.QtCore import QObject, QProcess, QSettings, QTimer, pyqtSignal

_SETTINGS = ("Kherve", "KherveCAD")

#: name of the binary inside a bundled ``openscad/`` folder.
_OPENSCAD_EXE = "openscad.exe" if os.name == "nt" else "openscad"

#: places to look for the binary besides PATH.
_CANDIDATES = [
    r"C:\Program Files\OpenSCAD\openscad.exe",
    r"C:\Program Files (x86)\OpenSCAD\openscad.exe",
    "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD",
    "/usr/bin/openscad",
    "/usr/local/bin/openscad",
    "/snap/bin/openscad",
]


#: layouts of a bundled ``openscad/`` folder, relative to a root. Windows
#: and Linux get the portable tree (the binary sits at the top); macOS
#: ships the official ``OpenSCAD.app``, whose binary is buried inside it.
_BUNDLE_LAYOUTS = [
    ("openscad", _OPENSCAD_EXE),
    ("openscad", "OpenSCAD.app", "Contents", "MacOS", "OpenSCAD"),
]


#: OpenSCAD gimbal camera rotations, by the name the 3D view uses for
#: the same viewpoint.  Paired with ``--viewall --autocenter`` these are
#: all a still needs: the distance is computed from the model.
CAMERA_ROTATIONS = {
    "Isometric": (55, 0, 25),
    "Top": (0, 0, 0),
    "Bottom": (180, 0, 0),
    "Front": (90, 0, 0),
    "Back": (90, 0, 180),
    "Right": (90, 0, 90),
    "Left": (90, 0, 270),
}


def bundled_openscad() -> str:
    """Path of the OpenSCAD shipped beside the app, or '' if there is none.

    The Windows installer drops the official portable build into an
    ``openscad/`` subfolder of the application directory, so the engine
    is guaranteed present; the macOS DMG does the same with the official
    ``OpenSCAD.app`` inside the bundle's ``Contents/Resources/``. Looks
    next to the executable when frozen (PyInstaller one-folder:
    ``sys.executable``'s directory, and ``sys._MEIPASS`` for a one-file
    build) and next to the project root when running from a checkout, so
    a manually-dropped copy works there too.
    """
    roots = []
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        roots.append(exe_dir)
        # In a .app the executable lives in Contents/MacOS/; everything
        # that is not code belongs one level over in Contents/Resources/.
        if exe_dir.name == "MacOS" and exe_dir.parent.name == "Contents":
            roots.append(exe_dir.parent / "Resources")
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            roots.append(Path(meipass))
    roots.append(Path(__file__).resolve().parent.parent)
    for root in roots:
        for layout in _BUNDLE_LAYOUTS:
            exe = root.joinpath(*layout)
            if exe.exists():
                return str(exe)
    return ""


def find_openscad() -> str:
    """Path of the OpenSCAD binary, or '' when not installed.

    A custom location can be stored in QSettings key ``openscad_path``
    (Edit > Locate OpenSCAD in the GUI). Setting the environment
    variable ``KHERVECAD_DISABLE_ENGINE`` forces the built-in preview
    (used by the test suite so no background renders are spawned).

    Order: the user's explicit choice, then the copy bundled beside the
    app, then PATH and the usual install locations. The bundle beats
    discovery — it is the one copy we know is there and know works — but
    not a path the user deliberately pointed us at, or Locate OpenSCAD
    would silently do nothing in an installed build.
    """
    if os.environ.get("KHERVECAD_DISABLE_ENGINE"):
        return ""
    custom = QSettings(*_SETTINGS).value("openscad_path", "")
    if custom and Path(custom).exists():
        return str(custom)
    bundled = bundled_openscad()
    if bundled:
        return bundled
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
    part_ready = pyqtSignal(str, list)  # (content key, exact part mesh)
    render_failed = pyqtSignal(str)    # compiler message
    busy_changed = pyqtSignal(bool)

    DEBOUNCE_MS = 500

    def __init__(self, parent=None):
        super().__init__(parent)
        self.binary = find_openscad()
        self._dir = Path(tempfile.mkdtemp(prefix="khervecad_"))
        self._process = None
        self._pending_code = None
        #: bumped whenever what is on screen stops matching the render
        #: in flight; _finished then drops that render's result.
        self._generation = 0
        self._running_generation = 0
        #: {content key: program} for per-part exact renders, and the
        #: key of the one running (so it is never queued twice)
        self._part_queue = {}
        self._running_part = None
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
        """Schedule a render of *scad_code* (debounced). A render still
        running is disowned: its code is already superseded, so letting
        it land would paint the previous model over the current one."""
        if not self.available:
            return
        self._pending_code = scad_code
        self._generation += 1
        self._timer.start()

    def request_part_render(self, key: str, scad_code: str):
        """Queue an exact render of ONE part, identified by its content
        *key*. Parts are rendered one at a time in the background and
        the result is emitted as `part_ready(key, mesh)`.

        This is what makes an exact preview affordable: a whole-document
        render redoes the CSG of every part on every change (a minute on
        a real assembly), while a part is re-rendered only when its own
        contents change — never when it is moved, snapped or coloured.
        A stale result cannot mislead: the key IS the content."""
        if not self.available or not key:
            return
        if key in self._part_queue or key == self._running_part:
            return
        self._part_queue[key] = scad_code
        self._timer.start()

    def cancel_parts(self):
        """Drop queued part renders (the document changed wholesale)."""
        self._part_queue.clear()

    def cancel(self):
        """Drop the pending render and disown one in flight — the
        built-in preview is authoritative from here (the document is
        multi-coloured, say, which a single STL cannot carry). Without
        this, a render requested before the change lands afterwards and
        silently replaces what is on screen."""
        self._timer.stop()
        self._pending_code = None
        self._generation += 1
        if self._part_queue:            # per-part renders still stand
            self._timer.start()

    def _watch(self, process, done):
        """Call *done(engine)* when *process* finishes — without the
        signal holding the engine.

        A slot that captures ``self`` makes a cycle (engine -> process
        -> connection -> slot -> engine). When its window is dropped
        with a render still running, the garbage collector clears the
        slot's ``self`` and destroys the engine; Qt then kills the
        QProcess and fires ``finished`` into the cleared slot — a
        NameError inside a Qt slot, which PyQt5 answers with abort().
        A weak reference is cleared *before* the collector breaks the
        cycle, so the late signal finds no engine and does nothing."""
        ref = weakref.ref(self)

        def finished(_code, _status):
            engine = ref()
            if engine is not None:
                done(engine)
        process.finished.connect(finished)

    def shutdown(self):
        """Stop rendering for good: drop everything queued and kill the
        render in flight, so no OpenSCAD process outlives the window
        that asked for it."""
        self._timer.stop()
        self._pending_code = None
        self._part_queue.clear()
        self._generation += 1
        process, self._process = self._process, None
        self._running_part = None
        if process is not None:
            try:
                process.finished.disconnect()
            except TypeError:                 # nothing connected
                pass
            process.kill()
            process.waitForFinished(2000)

    def _start(self):
        if self._process is not None:
            # A render is running: keep the code pending; _finished
            # restarts the timer so the newest code wins.
            return
        if self._pending_code is None:
            self._start_part()
            return
        code = self._pending_code
        self._pending_code = None
        self._running_generation = self._generation
        scad_path = self._dir / "model.scad"
        stl_path = self._dir / "model.stl"
        scad_path.write_text(code, encoding="utf-8")
        self._process = QProcess(self)
        path = str(stl_path)
        self._watch(self._process, lambda eng: eng._finished(path))
        self._process.start(self.binary,
                            ["-o", str(stl_path), str(scad_path)])
        self.busy_changed.emit(True)

    def _start_part(self):
        """Run the next queued part render (only when no whole-document
        render is waiting — that one is what the user is looking at)."""
        if not self._part_queue:
            return
        key, code = next(iter(self._part_queue.items()))
        del self._part_queue[key]
        self._running_part = key
        scad_path = self._dir / "part.scad"
        stl_path = self._dir / "part.stl"
        scad_path.write_text(code, encoding="utf-8")
        self._process = QProcess(self)
        self._watch(self._process,
                    lambda eng, k=key, p=str(stl_path):
                    eng._part_finished(k, p))
        self._process.start(self.binary,
                            ["-o", str(stl_path), str(scad_path)])
        self.busy_changed.emit(True)

    def _part_finished(self, key: str, stl_path: str):
        process = self._process
        self._process = None
        self._running_part = None
        self.busy_changed.emit(False)
        exit_ok = (process.exitStatus() == QProcess.NormalExit
                   and process.exitCode() == 0)
        if exit_ok and Path(stl_path).exists():
            try:
                mesh = parse_stl(stl_path)
            except Exception:
                mesh = None
            if mesh:
                # keyed by content, so a late result is never wrong —
                # it just lands under a key nothing is asking for
                self.part_ready.emit(key, mesh)
        if self._pending_code is not None or self._part_queue:
            self._timer.start()

    def _finished(self, stl_path: str):
        process = self._process
        self._process = None
        self.busy_changed.emit(False)
        if self._running_generation != self._generation:
            # superseded or cancelled while it ran: its mesh is of the
            # old model, so it must not reach the view
            if self._pending_code is not None or self._part_queue:
                self._timer.start()
            return
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
        if self._pending_code is not None or self._part_queue:
            self._timer.start()

    # ---------------------------------------------------------- export
    def _run_export(self, scad_code: str, out_path: str,
                    extra=(), timeout_ms: int = 120000) -> str:
        """Run the binary once with ``-o out_path``. '' on success."""
        scad_path = self._dir / "export.scad"
        scad_path.write_text(scad_code, encoding="utf-8")
        process = QProcess()
        process.start(self.binary,
                      ["-o", out_path, *extra, str(scad_path)])
        process.waitForFinished(timeout_ms)
        if process.exitStatus() == QProcess.NormalExit and \
                process.exitCode() == 0:
            return ""
        stderr = bytes(process.readAllStandardError()) \
            .decode(errors="replace").strip()
        return stderr or "OpenSCAD export failed"

    def export_mesh(self, scad_code: str, out_path: str) -> str:
        """Export to whatever format the extension asks for.

        OpenSCAD picks the writer from the suffix, so .stl, .3mf, .off
        and .amf all go down this one path.
        """
        return self._run_export(scad_code, out_path)

    def export_stl(self, scad_code: str, out_path: str) -> str:
        """Export *scad_code* to *out_path* synchronously via the
        binary. Returns '' on success, an error message otherwise."""
        return self.export_mesh(scad_code, out_path)

    def export_png(self, scad_code: str, out_path: str,
                   rotation=CAMERA_ROTATIONS["Isometric"],
                   size=(1600, 1200),
                   colorscheme: str = "Tomorrow") -> str:
        """Render a still to *out_path*.

        The camera is given as a gimbal rotation; ``--viewall
        --autocenter`` then frames the model, so the same rotation
        works for a 2 mm part and a 2 m one.  ``--camera`` must carry
        all seven gimbal values — six is a different form entirely
        (eye + centre), and reading a rotation as a look-at point
        points the camera at nothing.
        """
        extra = [
            "--render",
            "--viewall", "--autocenter",
            "--imgsize=%d,%d" % (int(size[0]), int(size[1])),
            "--camera=0,0,0,%g,%g,%g,0" % tuple(rotation),
            "--colorscheme=%s" % colorscheme,
        ]
        return self._run_export(scad_code, out_path, extra)
