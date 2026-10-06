"""File ▸ Export Turntable Movie: the model turning round, for a product
page or an advert.

Every frame is painted by the 3D view (`View3D.snapshot`, an offscreen
twin — the user's camera never moves), so the movie shows exactly what
the screen shows: colours, materials, the reflective metal, lighting,
platform and shadow, a Cut Through. The camera swings round the model
at a fixed height, distance and target: `turntable_frame` measures the
distance that fits the model from EVERY side first, so the model does
not breathe in and out as it turns.

Frames go to a temporary folder as PNG and ffmpeg encodes them: MP4
(H.264, yuv420p, so every player and website takes it) or an animated
GIF (two-pass palette, for chats and slides). ffmpeg is found on
$KHERVECAD_FFMPEG, PATH, or the `imageio-ffmpeg` package's own binary;
without one the frames are kept and the error says how to get it.

`motion` "light" keeps the model and camera still and swings the key
light round instead (the lighting bar's Light turn, frame by frame), so
the shading and the metal's reflected soft boxes sweep across a part
that stands still; "both" does the two at once.

`export_request` is the `export_movie` MCP tool's body.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

FORMATS = (".mp4", ".gif")
#: what moves: the camera round the model, the light round a still
#: model (its reflections and shading sweep across it), or both
MOTIONS = ("turntable", "light", "both")
#: (key, label, (width, height))
SIZES = (
    ("1280x720", "1280 × 720 (HD)", (1280, 720)),
    ("1920x1080", "1920 × 1080 (Full HD)", (1920, 1080)),
    ("1080x1080", "1080 × 1080 (square, social)", (1080, 1080)),
    ("1080x1920", "1080 × 1920 (vertical, stories)", (1080, 1920)),
    ("640x480", "640 × 480 (small GIF)", (640, 480)),
)
DEFAULT = {"seconds": 8.0, "fps": 30, "turns": 1.0, "width": 1280,
           "height": 720, "direction": "clockwise", "pitch": None}
#: Limits a request is checked against: a 4K, 2-minute movie is ~3600
#: snapshots, which is a long wait, not a crash; past it, refuse.
MAX_FRAMES, MAX_SIDE, MIN_SIDE = 3600, 3840, 32
#: Angles the fitted distance is measured from.
FIT_SAMPLES = 8


class MovieError(ValueError):
    """A request the user or client should change."""


def ffmpeg_exe():
    """Path of an ffmpeg binary, or None."""
    env = os.environ.get("KHERVECAD_FFMPEG")
    if env and Path(env).is_file():
        return env
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:                       # not installed / no binary
        return None


MISSING = ("No video encoder found. Install one with "
           "`pip install imageio-ffmpeg` (or put ffmpeg on the PATH).")


def frame_yaws(count, turns=1.0, start=0.0, clockwise=True):
    """The camera yaw of every frame: *turns* full turns spread so the
    last frame is one step short of the first — the loop has no
    stutter where it joins."""
    step = 360.0 * float(turns) / max(int(count), 1)
    sign = -1.0 if clockwise else 1.0
    return [start + sign * step * i for i in range(int(count))]


def turntable_frame(view3d, width, height, pitch):
    """(distance, target) that frame the whole model from every side at
    this *pitch* — the largest fitted distance, the model's centre."""
    best, target = 0.0, None
    # the model's own points: the on-screen fit takes the platform in
    # as well, and the model came out small in the middle of a big disc
    verts = [v for tri in view3d.mesh for v in tri]
    if len(verts) > 3000:
        verts = verts[::len(verts) // 3000]
    for i in range(FIT_SAMPLES):
        yaw = 360.0 * i / FIT_SAMPLES
        _img, cam = view3d.snapshot(max(width // 8, 16),
                                    max(height // 8, 16), yaw=yaw,
                                    pitch=pitch, frame=verts or True,
                                    clean=True)
        if cam["distance"] > best:
            best = cam["distance"]
        if target is None:
            target = cam["target"]
    return best, target


def light_turns(count, turns=1.0, start=0.0):
    """The lighting bar's light_turn (-1..1 = half a turn either way)
    for every frame of *turns* sweeps, wrapped into that range."""
    out = []
    for i in range(int(count)):
        t = start + 2.0 * float(turns) * i / max(int(count), 1)
        out.append(((t + 1.0) % 2.0) - 1.0)
    return out


def render_frames(view3d, folder, *, seconds, fps, turns, width, height,
                  pitch=None, clockwise=True, progress=None,
                  motion="turntable"):
    """Write ``frame_00000.png`` … into *folder*; returns the count.
    *progress(i, n)* may return False to cancel (MovieError)."""
    from . import pngexport
    if not view3d.mesh:
        raise MovieError("There is nothing in the 3D view to film.")
    count = int(round(float(seconds) * int(fps)))
    pitch = view3d.pitch if pitch is None else float(pitch)
    distance, target = turntable_frame(view3d, width, height, pitch)
    ratio = pngexport.pixel_ratio(view3d, width, height)
    if motion not in MOTIONS:
        raise MovieError(f"motion is one of {', '.join(MOTIONS)}.")
    yaws = frame_yaws(count, turns if motion != "light" else 0,
                      view3d.yaw, clockwise)
    if motion == "turntable":
        lights = [view3d.light_turn] * count
    else:
        lights = light_turns(count, turns if clockwise else -turns,
                             view3d.light_turn)
    saved = view3d.light_turn
    try:
        for i, (yaw, light) in enumerate(zip(yaws, lights)):
            if progress is not None and progress(i, count) is False:
                raise MovieError("Cancelled.")
            view3d.light_turn = light      # copied by the snapshot twin
            image, _cam = view3d.snapshot(
                width, height, yaw=yaw, pitch=pitch, distance=distance,
                target=target, clean=True, pixel_ratio=ratio)
            if not image.save(str(Path(folder) / f"frame_{i:05d}.png"),
                              "PNG"):
                raise OSError(f"Could not write frame {i} into {folder}.")
    finally:
        view3d.light_turn = saved
    return count


def encode(folder, out, fps, ffmpeg=None):
    """ffmpeg the frames in *folder* into *out* (.mp4 or .gif)."""
    exe = ffmpeg or ffmpeg_exe()
    if not exe:
        raise MovieError(MISSING)
    pattern = str(Path(folder) / "frame_%05d.png")
    out = str(out)
    if out.lower().endswith(".gif"):
        # one palette for the whole loop, then dithered against it
        filt = ("split[a][b];[a]palettegen=stats_mode=diff[p];"
                "[b][p]paletteuse=dither=sierra2_4a")
        args = [exe, "-y", "-framerate", str(fps), "-i", pattern,
                "-filter_complex", filt, "-loop", "0", out]
    else:
        # H.264 wants even sides; yuv420p is what browsers can play
        args = [exe, "-y", "-framerate", str(fps), "-i", pattern,
                "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
                "-preset", "medium", "-movflags", "+faststart", out]
    done = subprocess.run(args, capture_output=True, text=True)
    if done.returncode != 0 or not Path(out).is_file():
        tail = (done.stderr or "").strip().splitlines()[-3:]
        raise MovieError("ffmpeg could not write the movie: "
                         + " / ".join(tail))
    return Path(out)


def check(path, seconds, fps, turns, width, height):
    """Normalised (path, seconds, fps, turns, width, height) or
    MovieError."""
    path = Path(str(path)).expanduser()
    if path.suffix.lower() not in FORMATS:
        raise MovieError("A movie path must end in .mp4 or .gif.")
    try:
        seconds, fps = float(seconds), int(fps)
        turns, width, height = float(turns), int(width), int(height)
    except (TypeError, ValueError):
        raise MovieError("seconds, fps, turns, width and height are "
                         "numbers.")
    if not (0.5 <= seconds <= 120 and 5 <= fps <= 60):
        raise MovieError("seconds must be 0.5-120 and fps 5-60.")
    if not (MIN_SIDE <= width <= MAX_SIDE and MIN_SIDE <= height <= MAX_SIDE):
        raise MovieError(f"width and height must be {MIN_SIDE}-{MAX_SIDE}"
                         " pixels.")
    if turns == 0 or abs(turns) > 10:
        raise MovieError("turns must be non-zero and at most 10.")
    if seconds * fps > MAX_FRAMES:
        raise MovieError(f"That is {int(seconds * fps)} frames; keep it "
                         f"under {MAX_FRAMES}.")
    return path, seconds, fps, turns, width, height


def export(view3d, path, *, seconds=DEFAULT["seconds"], fps=DEFAULT["fps"],
           turns=DEFAULT["turns"], width=DEFAULT["width"],
           height=DEFAULT["height"], pitch=None, clockwise=True,
           progress=None, motion="turntable") -> dict:
    """Film the turntable into *path*. Returns what was written."""
    path, seconds, fps, turns, width, height = check(
        path, seconds, fps, turns, width, height)
    exe = ffmpeg_exe()
    if not exe:
        raise MovieError(MISSING)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kcad_movie_") as folder:
        count = render_frames(view3d, folder, seconds=seconds, fps=fps,
                              turns=turns, width=width, height=height,
                              pitch=pitch, clockwise=clockwise,
                              progress=progress, motion=motion)
        encode(folder, path, fps, exe)
    return {"exported": str(path), "format": path.suffix[1:],
            "frames": count, "seconds": seconds, "fps": fps,
            "turns": turns, "motion": motion, "width": width,
            "height": height,
            "bytes": path.stat().st_size}


def export_request(window, params) -> dict:
    """The export_movie MCP tool."""
    direction = str(params.get("direction", "clockwise")).lower()
    if direction not in ("clockwise", "anticlockwise", "counterclockwise"):
        raise MovieError("direction is clockwise or anticlockwise.")
    return export(window.view3d, params.get("path", ""),
                  seconds=params.get("seconds", DEFAULT["seconds"]),
                  fps=params.get("fps", DEFAULT["fps"]),
                  turns=params.get("turns", DEFAULT["turns"]),
                  width=params.get("width", DEFAULT["width"]),
                  height=params.get("height", DEFAULT["height"]),
                  pitch=params.get("elevation"),
                  clockwise=direction == "clockwise",
                  motion=str(params.get("motion", "turntable")))


# ── dialog ─────────────────────────────────────────────────────────

def open_dialog(window):
    """File ▸ Export Turntable Movie…"""
    from PyQt5.QtCore import QSettings, Qt
    from PyQt5.QtWidgets import (QApplication, QComboBox, QDialog,
                                 QDialogButtonBox, QDoubleSpinBox,
                                 QFileDialog, QFormLayout, QHBoxLayout,
                                 QLineEdit, QMessageBox, QProgressDialog,
                                 QPushButton, QSpinBox, QWidget)
    view = window.view3d
    settings = QSettings("Kherve", "KherveCAD")
    dlg = QDialog(window)
    dlg.setWindowTitle(window.tr("Export Turntable Movie"))
    form = QFormLayout(dlg)
    size = QComboBox()
    for key, label, _s in SIZES:
        size.addItem(window.tr(label), key)
    size.setCurrentIndex(max(size.findData(
        settings.value("movie/size", "1280x720")), 0))
    seconds = QDoubleSpinBox()
    seconds.setRange(0.5, 120)
    seconds.setValue(float(settings.value("movie/seconds", 8.0)))
    seconds.setSuffix(" s")
    fps = QSpinBox()
    fps.setRange(5, 60)
    fps.setValue(int(settings.value("movie/fps", 30)))
    turns = QDoubleSpinBox()
    turns.setRange(0.25, 10)
    turns.setSingleStep(0.25)
    turns.setValue(float(settings.value("movie/turns", 1.0)))
    pitch = QDoubleSpinBox()
    pitch.setRange(-89, 89)
    pitch.setSuffix("°")
    pitch.setValue(round(view.pitch, 1))
    motion = QComboBox()
    motion.addItem(window.tr("Camera turns round the model"), "turntable")
    motion.addItem(window.tr("Model still, light turns round it"),
                   "light")
    motion.addItem(window.tr("Both turn"), "both")
    motion.setCurrentIndex(max(motion.findData(
        settings.value("movie/motion", "turntable")), 0))
    direction = QComboBox()
    direction.addItem(window.tr("Clockwise (seen from above)"), True)
    direction.addItem(window.tr("Anticlockwise"), False)
    stem = Path(getattr(window, "_path", "") or "model").stem
    folder = settings.value("movie/folder", str(Path.home() / "Movies"))
    path = QLineEdit(str(Path(folder) / f"{stem}-turntable.mp4"))
    browse = QPushButton(window.tr("Browse…"))
    row = QWidget()
    box = QHBoxLayout(row)
    box.setContentsMargins(0, 0, 0, 0)
    box.addWidget(path)
    box.addWidget(browse)

    def _browse():
        name, _f = QFileDialog.getSaveFileName(
            dlg, window.tr("Save Movie"), path.text(),
            window.tr("MP4 movie (*.mp4);;Animated GIF (*.gif)"))
        if name:
            path.setText(name)
    browse.clicked.connect(_browse)
    form.addRow(window.tr("Size"), size)
    form.addRow(window.tr("What moves"), motion)
    form.addRow(window.tr("Length"), seconds)
    form.addRow(window.tr("Frames per second"), fps)
    form.addRow(window.tr("Turns"), turns)
    form.addRow(window.tr("Camera height"), pitch)
    form.addRow(window.tr("Direction"), direction)
    form.addRow(window.tr("Save to"), row)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.button(QDialogButtonBox.Ok).setText(window.tr("Export"))
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    form.addRow(buttons)
    if dlg.exec_() != QDialog.Accepted:
        return None
    w, h = dict((k, s) for k, _l, s in SIZES)[size.currentData()]
    settings.setValue("movie/size", size.currentData())
    settings.setValue("movie/seconds", seconds.value())
    settings.setValue("movie/fps", fps.value())
    settings.setValue("movie/turns", turns.value())
    settings.setValue("movie/motion", motion.currentData())
    settings.setValue("movie/folder", str(Path(path.text()).parent))
    total = int(round(seconds.value() * fps.value()))
    bar = QProgressDialog(window.tr("Filming the turntable…"),
                          window.tr("Cancel"), 0, total, window)
    bar.setWindowModality(Qt.WindowModal)
    bar.setMinimumDuration(0)

    def _tick(i, n):
        bar.setValue(i)
        QApplication.processEvents()
        return not bar.wasCanceled()
    try:
        result = export(view, path.text(), seconds=seconds.value(),
                        fps=fps.value(), turns=turns.value(), width=w,
                        height=h, pitch=pitch.value(),
                        clockwise=bool(direction.currentData()),
                        progress=_tick, motion=motion.currentData())
    except (MovieError, OSError) as exc:
        bar.close()
        if str(exc) != "Cancelled.":
            QMessageBox.warning(window, window.tr("Export Turntable Movie"),
                                str(exc))
        return None
    bar.close()
    window.statusBar().showMessage(
        window.tr("Movie written: {0} ({1} frames)").format(
            result["exported"], result["frames"]), 8000)
    return result
