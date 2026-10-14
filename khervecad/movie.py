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
that stands still; "both" does the two at once; "sequence" is an advert
in three acts — the light sweeps round the still model, the
camera turns round it, the light sweeps again (`light_seconds` each
swing, the turn the rest; a third each by default) — each a whole turn,
so every act ends where the next begins and the movie loops.

`motion` "still" keeps the camera where the user has it, and "tumble"
turns the camera round the model AND over it at the same time — yaw and
pitch both advance, `tumble_turns` times over the top while it goes
`turns` times round — so the model is seen from every side, top and
underneath. The fitted distance is measured from every pitch the
tumble passes through.

**Moving parts** (`animate`): a model that moves through Customizer
sliders (motion_play.sliders — a robot arm's joints, a gear train's
angle, an orrery's days) can MOVE while it is filmed. `Animator` sweeps
each named slider from its minimum to its maximum and back
(`ping_pong`, so the movie loops), `animate_cycles` times, all together
— or only between the `from` / `to` a request gives — or along KEYS,
[[time 0..1, value], ...], eased between them (`key_value`), so a
mechanism can act out a sequence: a robot arm turns to an object,
reaches down with the gripper open, closes on it, lifts it and lets go. With no names it
takes the motion sliders: those in a Motion / Time group, else
motion_play.pick's one. Each frame writes the values into the
variables, re-solves the mates and repaints the preview before the
snapshot; the values the user had are put back afterwards and the
document is not marked changed (nothing reaches the undo stack). The
fitted distance looks at the model in several of those poses.

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
MOTIONS = ("turntable", "light", "both", "sequence", "still", "tumble")
#: poses of a moving model the fitted distance looks at
ANIMATION_FIT_POSES = (1.0, 0.75, 0.5, 0.25, 0.0)
#: movie times the fitted distance looks at (keyed tracks peak anywhere)
FIT_TIMES = (0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 0.0)
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


def _model_points(view3d):
    # the model's own points: the on-screen fit takes the platform in
    # as well, and the model came out small in the middle of a big disc
    verts = [v for tri in view3d.mesh for v in tri]
    if len(verts) > 3000:
        verts = verts[::len(verts) // 3000]
    return verts


def turntable_frame(view3d, width, height, pitch, pitches=None,
                    points=None):
    """(distance, target) that frame the whole model from every side at
    this *pitch* (or at every one of *pitches*) — the largest fitted
    distance, the model's centre. *points* replaces the mesh's own
    (a moving model's points in several poses)."""
    best, target = 0.0, None
    verts = points if points is not None else _model_points(view3d)
    for p in (pitches or [pitch]):
        for i in range(FIT_SAMPLES):
            yaw = 360.0 * i / FIT_SAMPLES
            _img, cam = view3d.snapshot(max(width // 8, 16),
                                        max(height // 8, 16), yaw=yaw,
                                        pitch=p, frame=verts or True,
                                        clean=True)
            if cam["distance"] > best:
                best = cam["distance"]
            if target is None:
                target = cam["target"]
    return best, target


def tumble_pitches(count, turns=1.0, start=22.0):
    """The camera pitch of every tumble frame: *turns* whole turns over
    the top, wrapped into (-180, 180] like the view's own orbit."""
    out = []
    for i in range(int(count)):
        p = start + 360.0 * float(turns) * i / max(int(count), 1)
        out.append((p + 180.0) % 360.0 - 180.0)
    return out


def ping_pong(count, cycles=1.0):
    """0 -> 1 -> 0 for every frame, *cycles* times over the movie — the
    last frame one step short of the first, so the movie loops."""
    out = []
    for i in range(int(count)):
        u = (float(cycles) * i / max(int(count), 1)) % 1.0
        out.append(1.0 - abs(2.0 * u - 1.0))
    return out


class Animator:
    """Moves a model's slider variables for a movie, and puts them back.

    *window* is the main window (its model and preview); *requests* a
    list of names or {"variable", "from", "to"} dicts, or None / "auto"
    for the model's motion sliders."""

    def __init__(self, window, requests=None):
        from . import customizer, motion_play
        self.window, self.model = window, window.model
        try:
            found = motion_play.sliders(self.model)
        except Exception:                   # no Customizer annotations
            found = []
        if not found:
            raise MovieError(
                "Nothing moves: the document has no slider variable. "
                "Moving parts are driven by an annotated variable such "
                "as `angle = 0;  // [0:5:360]` used in their placement.")
        if requests in (None, "auto", True) or requests == []:
            grouped = [n for n in found if any(
                g in str(customizer.group_of(n) or "").lower()
                for g in motion_play.MOTION_GROUPS)]
            requests = [str(n.params.get("variable")) for n in
                        (grouped or [motion_play.pick(self.model)])]
        if isinstance(requests, (str, dict)):
            requests = [requests]
        self.tracks = []                    # (node, lo, hi, original)
        for req in requests:
            name = req.get("variable") if isinstance(req, dict) else req
            try:
                node = motion_play.pick(self.model, str(name))
            except motion_play.MotionError as exc:
                raise MovieError(str(exc))
            spec = customizer.widget(node) or {}
            keys = req.get("keys") if isinstance(req, dict) else None
            if keys is not None:
                keys = check_keys(name, keys)
                lo = hi = None
            else:
                lo, hi = spec.get("min"), spec.get("max")
                if isinstance(req, dict):
                    lo, hi = req.get("from", lo), req.get("to", hi)
                try:
                    lo, hi = float(lo), float(hi)
                except (TypeError, ValueError):
                    raise MovieError(
                        f"{name}: give its range as from / to (or keys) — "
                        "it is not a slider with a minimum and maximum.")
            self.tracks.append((node, lo, hi, node.params.get("value"),
                                keys))
        if not self.tracks:
            raise MovieError("animate named no slider.")

    @property
    def names(self):
        return [str(n.params.get("variable")) for n, *_r in self.tracks]

    def _refresh(self):
        from . import mates
        mates.refresh(self.model)
        self.window._refresh_preview()

    def pose(self, u):
        """Every from/to track at fraction *u* (0..1) of its range, every
        keyed track at time *u* of its cycle."""
        for node, lo, hi, _orig, keys in self.tracks:
            value = key_value(keys, u) if keys else lo + (hi - lo) * float(u)
            node.params["value"] = round(value, 6)
        self._refresh()

    def at(self, t, cycles=1.0):
        """Every track at movie time *t* (0..1): a from/to track goes
        there and back (`ping_pong`), a keyed track follows its keys."""
        u = (float(cycles) * float(t)) % 1.0
        swing = 1.0 - abs(2.0 * u - 1.0)
        for node, lo, hi, _orig, keys in self.tracks:
            value = key_value(keys, u) if keys else lo + (hi - lo) * swing
            node.params["value"] = round(value, 6)
        self._refresh()

    def restore(self):
        for node, _lo, _hi, orig, _keys in self.tracks:
            node.params["value"] = orig
        self._refresh()

    def points(self, view3d):
        """The model's points in several poses (for the fitted
        distance), leaving it at the first frame's."""
        pts = []
        for t in FIT_TIMES:                 # ends at 0, the first frame
            self.at(t)
            pts.extend(_model_points(view3d))
        return pts


def check_keys(name, keys):
    """[[time 0..1, value], ...] sorted by time, or MovieError."""
    try:
        rows = sorted((float(t), float(v)) for t, v in keys)
    except (TypeError, ValueError):
        raise MovieError(f"{name}: keys are [time 0-1, value] pairs.")
    if not rows or any(not 0.0 <= t <= 1.0 for t, _v in rows):
        raise MovieError(f"{name}: key times run from 0 to 1.")
    return rows


def key_value(keys, u):
    """The keyed value at cycle time *u*, eased (smoothstep) between
    keys so every move starts and stops gently; held before the first
    key and after the last."""
    if u <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if u <= t1:
            if t1 <= t0:
                return v1
            s = (u - t0) / (t1 - t0)
            return v0 + (v1 - v0) * s * s * (3.0 - 2.0 * s)
    return keys[-1][1]


def light_turns(count, turns=1.0, start=0.0):
    """The lighting bar's light_turn (-1..1 = half a turn either way)
    for every frame of *turns* sweeps, wrapped into that range."""
    out = []
    for i in range(int(count)):
        t = start + 2.0 * float(turns) * i / max(int(count), 1)
        out.append(((t + 1.0) % 2.0) - 1.0)
    return out


def motion_path(motion, count, turns, yaw, light, clockwise=True,
                light_frames=None):
    """(yaws, light_turns) for every frame of *motion*. In a sequence
    each light swing lasts *light_frames* (default a third each)."""
    sweep = turns if clockwise else -turns
    if motion == "sequence":
        act = max(count // 3, 1) if not light_frames else \
            max(min(int(light_frames), (count - 1) // 2), 1)
        mid = count - 2 * act
        sweep_y, sweep_l = [yaw] * act, light_turns(act, sweep, light)
        yaws = sweep_y + frame_yaws(mid, turns, yaw, clockwise) + sweep_y
        lights = sweep_l + [light] * mid + sweep_l
        return yaws, lights
    yaws = frame_yaws(count, 0 if motion in ("light", "still") else turns,
                      yaw, clockwise)
    if motion in ("turntable", "still", "tumble"):
        return yaws, [light] * count
    return yaws, light_turns(count, sweep, light)


def render_frames(view3d, folder, *, seconds, fps, turns, width, height,
                  pitch=None, clockwise=True, progress=None,
                  motion="turntable", light_seconds=None, animator=None,
                  animate_cycles=1.0, tumble_turns=1.0):
    """Write ``frame_00000.png`` … into *folder*; returns the count.
    *progress(i, n)* may return False to cancel (MovieError).
    *animator* (an Animator) moves the model's parts while it films."""
    from . import pngexport
    if not view3d.mesh:
        raise MovieError("There is nothing in the 3D view to film.")
    if motion not in MOTIONS:
        raise MovieError(f"motion is one of {', '.join(MOTIONS)}.")
    count = int(round(float(seconds) * int(fps)))
    pitch = view3d.pitch if pitch is None else float(pitch)
    if motion == "tumble":
        pitches = tumble_pitches(count, tumble_turns, pitch)
    else:
        pitches = [pitch] * count
    try:
        points = animator.points(view3d) if animator else None
        fit_pitches = (sorted(set(round(p) for p in pitches[::max(
            count // 12, 1)])) if motion == "tumble" else None)
        if motion == "still":
            distance, target = view3d.distance, list(view3d.target)
        else:
            distance, target = turntable_frame(
                view3d, width, height, pitch, fit_pitches, points)
        ratio = pngexport.pixel_ratio(view3d, width, height)
        light_frames = None if not light_seconds else \
            int(round(float(light_seconds) * int(fps)))
        yaws, lights = motion_path(motion, count, turns, view3d.yaw,
                                   view3d.light_turn, clockwise,
                                   light_frames)

        saved = view3d.light_turn
        try:
            for i, (yaw, light) in enumerate(zip(yaws, lights)):
                if progress is not None and progress(i, count) is False:
                    raise MovieError("Cancelled.")
                if animator is not None:
                    animator.at(i / count, animate_cycles)
                view3d.light_turn = light  # copied by the snapshot twin
                image, _cam = view3d.snapshot(
                    width, height, yaw=yaw, pitch=pitches[i],
                    distance=distance, target=target, clean=True,
                    pixel_ratio=ratio)
                if not image.save(str(Path(folder) / f"frame_{i:05d}.png"),
                                  "PNG"):
                    raise OSError(
                        f"Could not write frame {i} into {folder}.")
        finally:
            view3d.light_turn = saved
    finally:
        if animator is not None:
            animator.restore()
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
           progress=None, motion="turntable", light_seconds=None,
           animator=None, animate_cycles=1.0, tumble_turns=1.0) -> dict:
    """Film the turntable into *path*. Returns what was written."""
    path, seconds, fps, turns, width, height = check(
        path, seconds, fps, turns, width, height)
    if motion == "sequence" and light_seconds:
        light_seconds = float(light_seconds)
        if light_seconds <= 0 or 2 * light_seconds >= seconds:
            raise MovieError(
                f"Each light swing must be shorter than half the movie "
                f"({seconds / 2:g} s), so the turn has time between them.")
    try:
        animate_cycles, tumble_turns = float(animate_cycles), \
            float(tumble_turns)
    except (TypeError, ValueError):
        raise MovieError("animate_cycles and tumble_turns are numbers.")
    if not (0 < animate_cycles <= 20 and 0 < abs(tumble_turns) <= 10):
        raise MovieError("animate_cycles must be 0-20 and tumble_turns "
                         "non-zero, at most 10.")
    exe = ffmpeg_exe()
    if not exe:
        raise MovieError(MISSING)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kcad_movie_") as folder:
        count = render_frames(view3d, folder, seconds=seconds, fps=fps,
                              turns=turns, width=width, height=height,
                              pitch=pitch, clockwise=clockwise,
                              progress=progress, motion=motion,
                              light_seconds=light_seconds,
                              animator=animator,
                              animate_cycles=animate_cycles,
                              tumble_turns=tumble_turns)
        encode(folder, path, fps, exe)
    out = {"exported": str(path), "format": path.suffix[1:],
           "frames": count, "seconds": seconds, "fps": fps,
           "turns": turns, "motion": motion, "width": width,
           "height": height,
           "bytes": path.stat().st_size}
    if motion == "tumble":
        out["tumble_turns"] = tumble_turns
    if animator is not None:
        out["animated"] = animator.names
        out["animate_cycles"] = animate_cycles
    return out


def export_request(window, params) -> dict:
    """The export_movie MCP tool."""
    direction = str(params.get("direction", "clockwise")).lower()
    if direction not in ("clockwise", "anticlockwise", "counterclockwise"):
        raise MovieError("direction is clockwise or anticlockwise.")
    animate = params.get("animate")
    animator = None
    if animate not in (None, False, [], ""):
        animator = Animator(window, None if animate is True else animate)
    return export(window.view3d, params.get("path", ""),
                  seconds=params.get("seconds", DEFAULT["seconds"]),
                  fps=params.get("fps", DEFAULT["fps"]),
                  turns=params.get("turns", DEFAULT["turns"]),
                  width=params.get("width", DEFAULT["width"]),
                  height=params.get("height", DEFAULT["height"]),
                  pitch=params.get("elevation"),
                  clockwise=direction == "clockwise",
                  motion=str(params.get("motion", "turntable")),
                  light_seconds=params.get("light_seconds"),
                  animator=animator,
                  animate_cycles=params.get("animate_cycles", 1.0),
                  tumble_turns=params.get("tumble_turns", 1.0))


# ── dialog ─────────────────────────────────────────────────────────

def open_dialog(window):
    """File ▸ Export Turntable Movie…"""
    from PyQt5.QtCore import QSettings, Qt
    from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox,
                                 QDialog,
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
    motion.addItem(window.tr("Light, then turn, then light"), "sequence")
    motion.addItem(window.tr("Tumble: round and over the top at once"),
                   "tumble")
    motion.addItem(window.tr("Camera still (my current view)"), "still")
    motion.setCurrentIndex(max(motion.findData(
        settings.value("movie/motion", "turntable")), 0))
    light_secs = QDoubleSpinBox()
    light_secs.setRange(0.5, 60)
    light_secs.setSuffix(" s")
    light_secs.setValue(float(settings.value("movie/light_seconds", 4.0)))
    light_secs.setToolTip(window.tr(
        "Sequence only: how long each light swing lasts. The camera "
        "turn gets the rest of the movie."))

    tumble = QDoubleSpinBox()
    tumble.setRange(0.25, 10)
    tumble.setSingleStep(0.25)
    tumble.setValue(float(settings.value("movie/tumble_turns", 1.0)))
    tumble.setToolTip(window.tr(
        "Tumble only: how many times the camera goes over the top while "
        "it goes round."))
    from . import motion_play
    try:
        has_motion = bool(motion_play.sliders(window.model))
    except Exception:
        has_motion = False
    animate = QCheckBox(window.tr("Move the moving parts while filming"))
    animate.setToolTip(window.tr(
        "Sweeps the model's Motion sliders (its joints, gears, crank...) "
        "from one end to the other and back, so the mechanism works in "
        "the movie. Your slider values come back afterwards."))
    animate.setEnabled(has_motion)
    animate.setChecked(has_motion and settings.value(
        "movie/animate", "false") == "true")
    cycles = QDoubleSpinBox()
    cycles.setRange(0.5, 20)
    cycles.setSingleStep(0.5)
    cycles.setValue(float(settings.value("movie/animate_cycles", 1.0)))
    cycles.setSuffix(window.tr(" × there and back"))

    def _sequence_only():
        light_secs.setEnabled(motion.currentData() == "sequence")
        tumble.setEnabled(motion.currentData() == "tumble")
        cycles.setEnabled(animate.isChecked())
    motion.currentIndexChanged.connect(_sequence_only)
    animate.toggled.connect(_sequence_only)
    _sequence_only()
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
    form.addRow(window.tr("Each light swing"), light_secs)
    form.addRow(window.tr("Turns over the top"), tumble)
    form.addRow(window.tr("Moving parts"), animate)
    form.addRow(window.tr("Movements"), cycles)
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
    settings.setValue("movie/light_seconds", light_secs.value())
    settings.setValue("movie/tumble_turns", tumble.value())
    settings.setValue("movie/animate",
                      "true" if animate.isChecked() else "false")
    settings.setValue("movie/animate_cycles", cycles.value())
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
        animator = Animator(window) if animate.isChecked() else None
        result = export(view, path.text(), seconds=seconds.value(),
                        fps=fps.value(), turns=turns.value(), width=w,
                        height=h, pitch=pitch.value(),
                        clockwise=bool(direction.currentData()),
                        progress=_tick, motion=motion.currentData(),
                        light_seconds=light_secs.value(),
                        animator=animator,
                        animate_cycles=cycles.value(),
                        tumble_turns=tumble.value())
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
