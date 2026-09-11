"""3D preview — software-rendered shaded viewer.

Bottom-right frame of the main window. Renders a triangle mesh with a
painter's-algorithm rasteriser (no OpenGL dependency): orbit with the
left mouse button, pan with the right/middle button, zoom with the
wheel. The mesh comes from the OpenSCAD engine when available, or
from the built-in tessellator otherwise; a badge in the corner says
which one produced it.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import threading

from PyQt5.QtCore import (QPointF, QRectF, QSettings, Qt, QTimer,
                          pyqtSignal)
from PyQt5.QtGui import (QColor, QImage, QPainter, QPen, QPolygonF)
from PyQt5.QtWidgets import (QGridLayout, QLabel, QSlider, QToolButton,
                             QWidget)

from . import bsp as bsp_mod

_SETTINGS = ("Kherve", "KherveCAD")

#: 3D render styles: how each face's shade becomes a colour.
RENDER_STYLES = ["Shaded", "Matte", "Clay", "Toon", "Brushed metal",
                 "Gold", "Copper", "Wireframe", "X-ray"]

#: how the camera maps depth: perspective (things shrink with distance)
#: or orthographic (parallel rays, true proportions — the way Blender's
#: numpad-5 view lines a model up against a reference).
PROJECTIONS = ["Perspective", "Orthographic"]

#: a color node's material (model.MATERIALS) -> how its faces shade.
#: A material wins over the global render style, except Wireframe and
#: X-ray, which exist to see through everything.
MATERIAL_STYLES = {
    "Plastic": "Shaded", "Metal": "Brushed metal", "Matte": "Matte",
    "Clay": "Clay", "Glass": "Glass", "Rubber": "Rubber", "Skin": "Skin",
    "Gold": "Gold", "Copper": "Copper", "Emissive": "Emissive",
}

#: 3D viewport backgrounds. "Theme" tracks the app theme; the rest are
#: explicit (top, bottom) pairs painted as a vertical gradient.
BACKGROUNDS = {
    "Theme": None,
    "Studio": ("#f4f6f8", "#c9d2da"),
    "Light": ("#fbfbfb", "#ededed"),
    "Slate": ("#3a4048", "#22262b"),
    "Dark": ("#2b2f33", "#16181b"),
    "Blueprint": ("#123a6b", "#0a1f3d"),
}


#: how far the sliders can push the shading: the value offset at full
#: brightness, and the contrast gain at full contrast (2** the slider,
#: so -100 halves the spread and +100 doubles it, symmetrically).
LIGHT_RANGE = 0.45


def _clamp_light(value) -> float:
    """A slider setting as a float in [-1, 1] (QSettings hands back
    strings, and an absent key is None)."""
    try:
        return min(max(float(value), -1.0), 1.0)
    except (TypeError, ValueError):
        return 0.0


class LightingBar(QWidget):
    """Floating brightness / contrast sliders over the 3D view, with a
    Redraw button.

    Every face is shaded from one fixed light, so depending on the
    render style, the part's own colour and the background, a model can
    come out flatter or darker than you want to read it. These two
    sliders adjust the *finished* face colours — a value offset and a
    contrast gain about mid-grey — so nothing about the geometry, the
    theme or the exported program changes."""

    #: Redraw was clicked: rebuild both views from the tree.
    refresh_requested = pyqtSignal()

    ROWS = (("brightness", "Bright",
             "Lighten or darken every face (the model only — the "
             "background and the theme are untouched)."),
            ("contrast", "Contrast",
             "Spread or flatten the shading between the lit and "
             "unlit faces, about mid-grey."))

    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.setObjectName("lightingBar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "#lightingBar { background: rgba(24, 27, 31, 175);"
            " border: 1px solid rgba(255, 255, 255, 40);"
            " border-radius: 6px; }"
            "#lightingBar QLabel { color: #e6e9ec; font-size: 10px; }"
            "#lightingBar QToolButton { color: #e6e9ec;"
            " background: transparent; border: none; font-size: 13px; }"
            "#lightingBar QToolButton:hover { color: #ffffff; }")
        grid = QGridLayout(self)
        grid.setContentsMargins(8, 5, 6, 5)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(1)
        self.sliders = {}
        for row, (key, label, tip) in enumerate(self.ROWS):
            slider = QSlider(Qt.Horizontal, self)
            slider.setRange(-100, 100)
            slider.setValue(int(round(getattr(view, key) * 100)))
            slider.setFixedWidth(96)
            slider.setToolTip(tip)
            slider.valueChanged.connect(
                lambda value, k=key: self.view.set_light(k, value / 100.0))
            grid.addWidget(QLabel(label, self), row, 0)
            grid.addWidget(slider, row, 1)
            self.sliders[key] = slider
        grid.addWidget(
            self._button("mdi.backup-restore", "⟲",
                         "Back to the default lighting", self.reset),
            0, 2, 2, 1)
        grid.addWidget(
            self._button("mdi.refresh", "⟳",
                         "Redraw: rebuild both views from the object "
                         "tree, dropping the mesh caches",
                         self.refresh_requested.emit),
            0, 3, 2, 1)

    def _button(self, glyph, fallback, tip, slot):
        from . import icons
        button = QToolButton(self)
        art = icons.icon(glyph, "#e6e9ec")
        if art.isNull():                      # qtawesome missing
            button.setText(fallback)
        else:
            button.setIcon(art)
        button.setToolTip(tip)
        button.clicked.connect(slot)
        return button

    def reset(self):
        for slider in self.sliders.values():
            slider.setValue(0)


class View3D(QWidget):
    """Orbiting shaded view of a triangle mesh."""

    #: emitted from the BSP worker thread; queued to the GUI thread
    _bsp_ready = pyqtSignal()

    #: past this many triangles, orbiting/panning/zooming draws a
    #: decimated "draft" mesh for a snappy frame rate, then the full
    #: mesh snaps back the moment you stop — OpenSCAD's preview/render
    #: split, done on the CPU.
    DRAFT_ABOVE = 9000
    DRAFT_TARGET = 6000

    #: the selection tint imitates OpenSCAD's `#` debug modifier. It is
    #: multiplied over the finished render (see _tint_selection), so
    #: the red channel passes through and green/blue are crushed: the
    #: object turns red while keeping its own shading and its holes.
    HIGHLIGHT_COLOR = "#ff2d2d"

    #: the camera's near clipping distance (mm). Geometry closer than
    #: this is cut away at the plane, never dropped whole (paintEvent).
    NEAR_PLANE = 0.1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mesh = []                  # [(v0, v1, v2)] world space
        self.colors = None              # optional per-face colours
        self.highlight_mesh = []        # selected object, world space
        #: anchor markers [{pos, dir, name, kind}] in world space —
        #: the selected Object's attachment points
        self.anchor_markers = []
        #: pictures drawn on their planes behind the model (refimage.py)
        self.reference_images = []
        #: pick mode: a callable fed the picked face/edge description
        #: (see anchors.describe_pick); left click picks, right cancels
        self._pick_cb = None
        self._pick_groups = None        # [(key, tris)] for group picks
        self._pick_banner = ""          # instruction drawn at the top
        self._pick_labeler = None       # names the hover highlight
        self._pick_hover = None         # (desc, label) under the cursor
        self._pick_pinned = None        # (desc, label) first snap click
        self._hover_pos = None
        # hover pre-highlight is throttled: at most one pick per tick
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(40)
        self._hover_timer.timeout.connect(self._hover_pick)
        self._draft_mesh = None         # decimated mesh for interaction
        self._draft_colors = None
        self._draft_hi = None
        self._bsp = None                # bsp.Tree of self.mesh, or None
        self._bsp_pending = None        # (serial, tree) left by the worker
        self._bsp_thread = None
        self._bsp_lock = threading.Lock()
        self._mesh_serial = 0           # bumps per set_mesh: stale trees
        self._bsp_ready.connect(self._take_bsp)
        self._fast = False              # currently interacting
        self.source = "no model"
        self.yaw = 35.0                 # degrees around Z
        self.pitch = 22.0               # degrees above the XY plane
        self.distance = 160.0
        self.target = [0.0, 0.0, 10.0]
        self._last = None
        self._mode = None
        # clears fast mode a moment after the last wheel tick (no
        # release event) so the crisp full mesh returns
        self._idle = QTimer(self)
        self._idle.setSingleShot(True)
        self._idle.setInterval(140)
        self._idle.timeout.connect(self._end_fast)
        #: set once the user orbits/pans/zooms, so the app stops
        #: auto-refitting their view out from under them.
        self.user_moved = False
        settings = QSettings(*_SETTINGS)
        saved = settings.value("render_style", "Shaded")
        self.style = saved if saved in RENDER_STYLES else "Shaded"
        bg = settings.value("render_bg", "Slate")
        self.background = bg if bg in BACKGROUNDS else "Slate"
        proj = settings.value("render_projection", "Perspective")
        self.projection = proj if proj in PROJECTIONS else "Perspective"
        self.brightness = _clamp_light(settings.value("render_brightness"))
        self.contrast = _clamp_light(settings.value("render_contrast"))
        self.setMinimumHeight(160)
        self.setMouseTracking(False)
        self.lighting_bar = LightingBar(self)
        self.lighting_bar.show()

    # ------------------------------------------------------- lighting
    def set_light(self, key: str, value: float):
        """Move one of the floating lighting sliders (brightness /
        contrast), persist it and repaint."""
        if key not in ("brightness", "contrast"):
            return
        setattr(self, key, _clamp_light(value))
        QSettings(*_SETTINGS).setValue(f"render_{key}",
                                       float(getattr(self, key)))
        self.update()

    def _light(self):
        """(gain, offset) for the finished face colours, or None when
        the sliders are centred — the hot paint loop then skips the
        adjustment entirely."""
        if not self.brightness and not self.contrast:
            return None
        return 2.0 ** self.contrast, self.brightness * LIGHT_RANGE

    @staticmethod
    def _adjust(color, gain, offset):
        """Contrast about mid-grey, then the brightness offset — value
        only, so hue and saturation (a part's own colour) survive."""
        hue, sat, val, alpha = color.getHsvF()
        val = min(max((val - 0.5) * gain + 0.5 + offset, 0.0), 1.0)
        out = QColor.fromHsvF(max(hue, 0.0), sat, val)
        out.setAlphaF(alpha)
        return out

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place_lighting_bar()

    def _place_lighting_bar(self):
        """Top-left corner: the source badge sits bottom-left and the
        bar hides itself for a pick, so nothing collides."""
        bar = self.lighting_bar
        bar.adjustSize()
        bar.move(8, 8)

    def set_style(self, style: str):
        if style in RENDER_STYLES:
            self.style = style
            QSettings(*_SETTINGS).setValue("render_style", style)
            self.update()

    def set_background(self, name: str):
        if name in BACKGROUNDS:
            self.background = name
            QSettings(*_SETTINGS).setValue("render_bg", name)
            self.update()

    def set_projection(self, name: str):
        if name in PROJECTIONS:
            self.projection = name
            QSettings(*_SETTINGS).setValue("render_projection", name)
            self.update()

    def _fill_background(self, painter, tokens):
        pair = BACKGROUNDS.get(self.background)
        if pair is None:                       # "Theme": follow the app
            painter.fillRect(self.rect(), QColor(tokens["editor"]))
            return
        from PyQt5.QtGui import QLinearGradient
        top, bottom = pair
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0.0, QColor(top))
        grad.setColorAt(1.0, QColor(bottom))
        painter.fillRect(self.rect(), grad)

    #: standard camera orientations (yaw, pitch) in degrees.
    VIEWS = {
        "Isometric": (35.0, 25.0), "Top": (-90.0, 89.0),
        "Bottom": (-90.0, -89.0), "Front": (-90.0, 2.0),
        "Back": (90.0, 2.0), "Right": (0.0, 2.0), "Left": (180.0, 2.0),
    }

    def set_view(self, name: str):
        if name in self.VIEWS:
            self.yaw, self.pitch = self.VIEWS[name]
            self.fit()

    def camera_state(self) -> dict:
        """The camera as plain numbers — enough to reproduce a view."""
        return {"azimuth": round(self.yaw, 3),
                "elevation": round(self.pitch, 3),
                "distance": round(self.distance, 3),
                "target": [round(v, 3) for v in self.target],
                "projection": self.projection}

    def snapshot(self, width, height, *, yaw=None, pitch=None,
                 distance=None, target=None, projection=None,
                 frame=None, zoom=1.0):
        """Paint the scene from another camera into a QImage, leaving
        this view — the user's camera — exactly where it is.

        An offscreen twin gets the same mesh, colours, selection, style,
        background and lighting; only the camera differs. *frame* is a
        list of world points to fit the view to (``[]`` or ``True``
        means the whole mesh); *zoom* then moves in (>1) or out (<1).
        Returns ``(image, camera_state)``."""
        from PyQt5.QtCore import QSize
        from PyQt5.QtGui import QImage, QPainter
        twin = View3D()
        twin.lighting_bar.hide()
        twin.resize(max(int(width), 2), max(int(height), 2))
        twin.style, twin.background = self.style, self.background
        twin.brightness, twin.contrast = self.brightness, self.contrast
        twin.projection = projection if projection in PROJECTIONS \
            else self.projection
        # a snapshot must be exact: wait for a tree still being built
        twin.set_mesh(self.mesh, self.source, self.colors,
                      bsp=self.wait_for_bsp())
        twin.set_highlight_mesh(self.highlight_mesh)
        twin.set_anchor_markers(list(self.anchor_markers))
        twin.reference_images = list(self.reference_images)
        twin.yaw = self.yaw if yaw is None else float(yaw)
        twin.pitch = self.pitch if pitch is None else float(pitch)
        twin.distance, twin.target = self.distance, list(self.target)
        if frame is not None and frame is not False:
            twin.fit(None if frame is True or not frame else list(frame))
        if target is not None:
            twin.target = [float(v) for v in target]
        if distance is not None:
            twin.distance = max(float(distance), 1e-3)
        if zoom and float(zoom) != 1.0:
            twin.distance /= max(float(zoom), 1e-3)
        img = QImage(QSize(twin.width(), twin.height()),
                     QImage.Format_ARGB32)
        img.fill(0)
        painter = QPainter(img)
        twin.render(painter)
        painter.end()
        state = twin.camera_state()
        twin.deleteLater()
        return img, state

    # ------------------------------------------------------------- API
    def _decimate(self, mesh, colors=None):
        """A strided subset of *mesh* (and matching colours) targeting
        ~DRAFT_TARGET triangles, or None when the mesh is small enough to
        draw whole even during interaction."""
        n = len(mesh)
        if n <= self.DRAFT_ABOVE:
            return None, None
        stride = (n + self.DRAFT_TARGET - 1) // self.DRAFT_TARGET
        return mesh[::stride], (colors[::stride] if colors else None)

    def set_mesh(self, mesh, source: str, colors=None, bsp=None):
        """*colors* is an optional per-face list of (colorstring,
        alpha) — colours from color() nodes shown by the preview.
        *bsp* hands over a `bsp.Tree` already built for this very mesh
        (the snapshot twin), otherwise one is built here."""
        self.mesh = mesh or []
        self.colors = colors if colors and len(colors) == len(self.mesh) \
            else None
        self._draft_mesh, self._draft_colors = self._decimate(
            self.mesh, self.colors)
        # A BSP tree gives an exact back-to-front order (see bsp.py).
        # It is built on a worker thread so a parameter edit repaints at
        # once (centroid-sorted, as before) and snaps to the exact order
        # when the tree lands; None for a mesh too big to partition.
        with self._bsp_lock:
            self._mesh_serial += 1
            self._bsp_pending = None
        self._bsp = bsp
        if bsp is None and self.mesh:
            serial, tris, colors_ = self._mesh_serial, self.mesh, self.colors

            def stale():
                return serial != self._mesh_serial

            def work():
                # a superseded build stops at once rather than competing
                # with the current one (and the GUI) for the GIL
                tree = bsp_mod.build(tris, colors_, cancel=stale)
                with self._bsp_lock:
                    # only the current mesh's tree may be posted: a late
                    # stale one used to overwrite the fresh result before
                    # the GUI thread took it, and the view then kept the
                    # centroid sort until a manual Redraw
                    if stale():
                        return
                    self._bsp_pending = (serial, tree)
                self._bsp_ready.emit()

            self._bsp_thread = threading.Thread(target=work, daemon=True)
            self._bsp_thread.start()
        self.source = source
        self.update()

    def _take_bsp(self):
        """Adopt the tree the worker left, if it is for the current
        mesh (a newer set_mesh may have superseded it)."""
        with self._bsp_lock:
            pending, self._bsp_pending = self._bsp_pending, None
        if pending is None:
            return
        serial, tree = pending
        if serial == self._mesh_serial and tree is not None:
            self._bsp = tree
            self.update()

    def wait_for_bsp(self, timeout=None):
        """Block until the tree for the current mesh is built (or the
        build has given up) and adopt it — for snapshots and tests,
        which paint without an event loop to deliver the signal."""
        thread = self._bsp_thread
        if thread is not None and thread.is_alive():
            thread.join(bsp_mod.TIME_BUDGET + 1.0 if timeout is None
                        else timeout)
        self._take_bsp()
        return self._bsp

    def set_highlight_mesh(self, tris):
        """Triangles of the selected object, drawn glowing on top."""
        self.highlight_mesh = tris or []
        self._draft_hi, _ = self._decimate(self.highlight_mesh)
        self.update()

    def set_reference_images(self, refs):
        """Pictures to draw on their planes, behind the model."""
        self.reference_images = [dict(r) for r in refs or []]
        self.update()

    def set_anchor_markers(self, markers):
        """World-space anchor markers of the selected Object."""
        self.anchor_markers = markers or []
        self.update()

    # ------------------------------------------------------- anchor pick
    def start_pick(self, callback, groups=None, banner="",
                   labeler=None):
        """Enter pick mode: the next left click on the model picks a
        face or edge and *callback* receives its description (world
        coordinates); right click or Esc cancels. While armed, the
        face/edge under the cursor is pre-highlighted with its owner's
        name, and *banner* is drawn as an instruction across the top
        of the view.

        Without *groups* the pick runs on the displayed mesh and the
        callback gets ``desc``. With *groups* (``[(key, tris)]``) the
        pick runs across those meshes instead and the callback gets
        ``(desc, key)`` — how the two-click Snap tool knows which
        Object a face belongs to. *labeler(desc, key)*, when given,
        names the hover pre-highlight (e.g. resolving the anchor a
        click would reuse) instead of the default owner · Face/Edge."""
        self._pick_cb = callback
        self._pick_groups = groups
        self._pick_banner = banner
        self._pick_labeler = labeler
        self._pick_hover = None
        self.lighting_bar.hide()             # nothing between you and the pick
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)          # hover pre-highlight
        self.setFocus(Qt.OtherFocusReason)   # so Esc reaches us
        self.update()

    def _end_pick_mode(self):
        self._pick_groups = None
        self._pick_banner = ""
        self._pick_labeler = None
        self._pick_hover = None
        self._hover_pos = None
        self._hover_timer.stop()
        self.setMouseTracking(False)
        self.unsetCursor()
        self.lighting_bar.show()
        self.update()

    def cancel_pick(self):
        if self._pick_cb is not None:
            callback, self._pick_cb = self._pick_cb, None
            groups = self._pick_groups
            self._end_pick_mode()
            self.set_pick_pinned(None)
            if groups is None:
                callback(None)
            else:
                callback(None, None)

    def set_pick_pinned(self, desc, label=""):
        """Keep *desc* (the first click of a two-click snap) visibly
        highlighted while the second click is aimed; None clears it."""
        self._pick_pinned = (desc, label) if desc is not None else None
        self.update()

    #: hover pre-highlight skips the face growth on meshes bigger than
    #: this (describe_pick builds an edge map over the whole mesh) and
    #: shows just the hit facet, keeping the feedback fluid.
    HOVER_DESCRIBE_LIMIT = 24000

    def _pick_at(self, x, y, quick=False):
        """``(desc, key)`` for the face/edge under screen (x, y), or
        ``(None, None)`` — key is the owning group key (two-click
        Snap) or None when picking the displayed mesh."""
        from . import anchors
        eye, right, up, forward = self._camera()

        def projector(v):
            return self._project(eye, right, up, forward, v)

        groups = self._pick_groups
        if groups is None:
            owner, key, start = self.mesh, None, 0
            index, point = anchors.pick(self.mesh, projector, x, y)
        else:
            tris = [t for _key, ts in groups for t in ts]
            index, point = anchors.pick(tris, projector, x, y)
            owner, key, start = None, None, 0
            if index is not None:
                # describe within the owner's own mesh so the face
                # growth never bleeds into a coplanar neighbour part
                for k, ts in groups:
                    if index < start + len(ts):
                        owner, key = ts, k
                        break
                    start += len(ts)
        if index is None or owner is None:
            return None, None
        # snap tolerance: ~8 px as world units at the hit depth
        depth = projector(point)[2]
        tol = 8.0 * depth / self._focal()
        if quick and len(owner) > self.HOVER_DESCRIBE_LIMIT:
            tri = owner[index - start]
            return dict(kind="face", pos=list(point),
                        dir=anchors._tri_normal(tri), name="Face",
                        tris=[tri]), key
        return anchors.describe_pick(owner, index - start, point,
                                     tol), key

    def _run_pick(self, x, y):
        callback, self._pick_cb = self._pick_cb, None
        groups = self._pick_groups
        # resolve before tearing pick state down (_pick_at reads groups)
        desc, key = self._pick_at(x, y)
        self._end_pick_mode()
        if groups is None:
            callback(desc)
        else:
            callback(desc, key)

    def _queue_hover(self, pos):
        self._hover_pos = pos
        if not self._hover_timer.isActive():
            self._hover_timer.start()

    def _hover_pick(self):
        if self._pick_cb is None or self._hover_pos is None:
            return
        desc, key = self._pick_at(self._hover_pos.x(),
                                  self._hover_pos.y(), quick=True)
        if desc is None:
            changed = self._pick_hover is not None
            self._pick_hover = None
        else:
            if self._pick_labeler is not None:
                label = self._pick_labeler(desc, key)
            else:
                owner = getattr(key, "name", "") \
                    if key is not None else ""
                label = f"{owner} · {desc['name']}" if owner \
                    else desc["name"]
            self._pick_hover = (desc, label)
            changed = True
        if changed:
            self.update()

    def _begin_fast(self):
        if self._draft_mesh is not None or self._draft_hi is not None:
            self._fast = True

    def _end_fast(self):
        if self._fast:
            self._fast = False
            self.update()                 # repaint the full, crisp mesh

    def fit(self, verts=None):
        """Frame the whole mesh — or only the world points *verts* (one
        part, say): centre it in the pane and size it to fill most of
        the view. Projects the bounding box in the current camera
        orientation, then adjusts distance and recentres the target so
        the model sits squarely in the middle (not low)."""
        if verts is None:
            verts = [v for tri in self.mesh for v in tri]
        if not verts:
            return
        if len(verts) > 3000:                     # sample: fit is exact
            verts = verts[::len(verts) // 3000]   # enough at this scale
        xs = [v[0] for v in verts]
        ys = [v[1] for v in verts]
        zs = [v[2] for v in verts]
        mn = (min(xs), min(ys), min(zs))
        mx = (max(xs), max(ys), max(zs))
        self.target = [(mn[i] + mx[i]) / 2 for i in range(3)]
        right, up, forward = self._orientation()
        size = max(mx[0] - mn[0], mx[1] - mn[1], mx[2] - mn[2], 1.0)
        self.distance = size * 2.0
        f = self._focal()
        ortho = self.projection == "Orthographic"

        def depth(cf):          # what the on-screen scale divides by
            return self.distance if ortho else self.distance + cf
        halfw = self.width() / 2 or 1.0
        halfh = self.height() / 2 or 1.0
        margin = 0.9
        # a few passes converge the distance (depth changes the on-screen
        # scale) and the recentre — perspective skews the projected
        # outline, so we centre on the real vertices, not just the box.
        for _ in range(4):
            cam = []
            for v in verts:
                d = (v[0] - self.target[0], v[1] - self.target[1],
                     v[2] - self.target[2])
                cr = d[0] * right[0] + d[1] * right[1] + d[2] * right[2]
                cu = d[0] * up[0] + d[1] * up[1] + d[2] * up[2]
                cf = d[0] * forward[0] + d[1] * forward[1] \
                    + d[2] * forward[2]
                cam.append((cr, cu, cf))
            need = 0.0
            for cr, cu, cf in cam:
                z = depth(cf)
                if z < 0.1:
                    continue
                need = max(need, abs(f * cr / z) / (halfw * margin),
                           abs(f * cu / z) / (halfh * margin))
            if need > 0:
                self.distance *= need
            sx = [f * cr / depth(cf) for cr, _cu, cf in cam]
            sy = [f * cu / depth(cf) for _cr, cu, cf in cam]
            ox = (min(sx) + max(sx)) / 2          # projected outline mid
            oy = (min(sy) + max(sy)) / 2
            self.target = [self.target[i]
                           + right[i] * ox * self.distance / f
                           + up[i] * oy * self.distance / f
                           for i in range(3)]
        self.update()

    # -------------------------------------------------------- projection
    def _orientation(self):
        """Camera basis (right, up, forward) from yaw/pitch alone —
        independent of target/distance, so fit() can use it."""
        yaw = math.radians(self.yaw)
        pitch = math.radians(self.pitch)
        # camera basis: forward points at the target.
        fx = -math.cos(pitch) * math.cos(yaw)
        fy = -math.cos(pitch) * math.sin(yaw)
        fz = -math.sin(pitch)
        rx, ry, rz = -math.sin(yaw), math.cos(yaw), 0.0
        # up = right x forward (so world +Z maps to screen up — the
        # other order gives uz = -cos(pitch) and renders upside down)
        ux = ry * fz - rz * fy
        uy = rz * fx - rx * fz
        uz = rx * fy - ry * fx
        return (rx, ry, rz), (ux, uy, uz), (fx, fy, fz)

    def _focal(self):
        return 1.2 * min(self.width(), self.height())

    def _camera(self):
        right, up, forward = self._orientation()
        fx, fy, fz = forward
        ex = self.target[0] - fx * self.distance
        ey = self.target[1] - fy * self.distance
        ez = self.target[2] - fz * self.distance
        return (ex, ey, ez), right, up, forward

    def _project(self, eye, right, up, forward, v):
        dx, dy, dz = v[0] - eye[0], v[1] - eye[1], v[2] - eye[2]
        cx = dx * right[0] + dy * right[1] + dz * right[2]
        cy = dx * up[0] + dy * up[1] + dz * up[2]
        cz = dx * forward[0] + dy * forward[1] + dz * forward[2]
        if self.projection == "Orthographic":
            s = self._focal() / max(self.distance, 1e-6)
            return (self.width() / 2 + s * cx,
                    self.height() / 2 - s * cy, cz)
        if cz < self.NEAR_PLANE:
            return None
        f = self._focal()
        return (self.width() / 2 + f * cx / cz,
                self.height() / 2 - f * cy / cz, cz)

    # ---------------------------------------------------------- painting
    def paintEvent(self, event):
        from .style import tokens
        t = tokens()
        painter = QPainter(self)
        # antialiasing is the single biggest cost; skip it while the user
        # is orbiting/panning for snappy feedback, then repaint crisp on
        # release (see mouseReleaseEvent)
        painter.setRenderHint(QPainter.Antialiasing, self._mode is None)
        self._fill_background(painter, t)

        eye, right, up, forward = self._camera()
        self._draw_ground(painter, t, eye, right, up, forward)
        if self.reference_images:
            from . import refimage
            refimage.draw_3d(painter, self.reference_images,
                             lambda v: self._project(eye, right, up,
                                                     forward, v))

        base = QColor(t["select"])
        light = (0.35, -0.5, 0.75)
        norm = math.sqrt(sum(c * c for c in light))
        light = tuple(c / norm for c in light)
        to_eye = (-forward[0], -forward[1], -forward[2])
        half = (light[0] + to_eye[0], light[1] + to_eye[1],
                light[2] + to_eye[2])
        hlen = math.sqrt(sum(c * c for c in half)) or 1.0
        half = tuple(c / hlen for c in half)

        # For an opaque closed solid the back-facing triangles are hidden
        # behind the front ones, so skip them: this roughly halves the
        # polygons projected, sorted and painted. Translucent / wireframe
        # styles need every face, so culling is disabled for them.
        style = self.style
        cull = style not in ("Wireframe", "X-ray")
        tex, tey, tez = to_eye

        # while interacting with a big model, draw the decimated draft;
        # otherwise walk the BSP tree, whose order is exact, and paint
        # its (split) triangles — the centroid sort below is only the
        # fallback for a mesh too big to partition
        tree = self._bsp
        if self._fast and self._draft_mesh is not None:
            mesh, colors = self._draft_mesh, self._draft_colors
            tree = None
        elif tree is not None and self._fast \
                and len(tree.tris) > self.DRAFT_ABOVE:
            # splitting grew the tree past the draft threshold: orbit on
            # the lighter unsplit mesh, the exact order returns on release
            mesh, colors = self.mesh, self.colors
            tree = None
        elif tree is not None:
            mesh, colors = tree.tris, tree.colors
        else:
            mesh, colors = self.mesh, self.colors
        hmesh = self._draft_hi if (self._fast and self._draft_hi
                                   is not None) else self.highlight_mesh

        # hoist every projection constant out of the per-vertex hot path
        # (the old _project recomputed focal/width/height for each vertex)
        f = self._focal()
        hw = self.width() * 0.5
        hh = self.height() * 0.5
        ex, ey, ez = eye
        rx, ry, rz = right
        uxa, uya, uza = up
        fxa, fya, fza = forward
        lx, ly, lz = light
        hax, hay, haz = half

        near = self.NEAR_PLANE
        ortho = self.projection == "Orthographic"
        scale = f / max(self.distance, 1e-6)       # orthographic px/mm

        def clip_proj(tri):
            """Screen points of *tri*, clipped to the near plane.

            A triangle reaching behind the camera is cut at the plane,
            not dropped: OpenSCAD meshes are full of long slivers that
            run the length of an edge, and in a close-up one far vertex
            slips behind the eye first — dropping the whole sliver
            opened a strip of background across the surface (the
            "white seams"). Returns 3-4 (x, y, depth) points, or None
            when the triangle lies wholly behind the camera."""
            a, b, c = tri
            ax = a[0] - ex; ay = a[1] - ey; az = a[2] - ez
            bx = b[0] - ex; by = b[1] - ey; bz = b[2] - ez
            cx = c[0] - ex; cy = c[1] - ey; cz = c[2] - ez
            z0 = ax * fxa + ay * fya + az * fza
            z1 = bx * fxa + by * fya + bz * fza
            z2 = cx * fxa + cy * fya + cz * fza
            if ortho:                  # parallel rays: nothing to clip
                return ((hw + scale * (ax * rx + ay * ry + az * rz),
                         hh - scale * (ax * uxa + ay * uya + az * uza),
                         z0),
                        (hw + scale * (bx * rx + by * ry + bz * rz),
                         hh - scale * (bx * uxa + by * uya + bz * uza),
                         z1),
                        (hw + scale * (cx * rx + cy * ry + cz * rz),
                         hh - scale * (cx * uxa + cy * uya + cz * uza),
                         z2))
            if z0 >= near and z1 >= near and z2 >= near:
                return ((hw + f * (ax * rx + ay * ry + az * rz) / z0,
                         hh - f * (ax * uxa + ay * uya + az * uza) / z0,
                         z0),
                        (hw + f * (bx * rx + by * ry + bz * rz) / z1,
                         hh - f * (bx * uxa + by * uya + bz * uza) / z1,
                         z1),
                        (hw + f * (cx * rx + cy * ry + cz * rz) / z2,
                         hh - f * (cx * uxa + cy * uya + cz * uza) / z2,
                         z2))
            if z0 < near and z1 < near and z2 < near:
                return None
            ring = ((ax * rx + ay * ry + az * rz,
                     ax * uxa + ay * uya + az * uza, z0),
                    (bx * rx + by * ry + bz * rz,
                     bx * uxa + by * uya + bz * uza, z1),
                    (cx * rx + cy * ry + cz * rz,
                     cx * uxa + cy * uya + cz * uza, z2))
            out = []
            for i in range(3):              # Sutherland-Hodgman, 1 plane
                p = ring[i]
                q = ring[(i + 1) % 3]
                p_in = p[2] >= near
                if p_in:
                    out.append((hw + f * p[0] / p[2],
                                hh - f * p[1] / p[2], p[2]))
                if p_in != (q[2] >= near):
                    t = (near - p[2]) / (q[2] - p[2])
                    out.append((hw + f * (p[0] + (q[0] - p[0]) * t) / near,
                                hh - f * (p[1] + (q[1] - p[1]) * t) / near,
                                near))
            return out

        faces = []
        append = faces.append
        if tree is not None:
            order = tree.order(eye, forward, ortho)
            sequence = ((i, mesh[i]) for i in order)
        else:
            sequence = enumerate(mesh)
        for index, tri in sequence:
            a, b, c = tri
            ux = b[0] - a[0]; uy = b[1] - a[1]; uz = b[2] - a[2]
            vx = c[0] - a[0]; vy = c[1] - a[1]; vz = c[2] - a[2]
            nx = uy * vz - uz * vy
            ny = uz * vx - ux * vz
            nz = ux * vy - uy * vx
            # cull on the raw normal (its sign is scale-independent)
            # before paying for the sqrt normalisation
            if cull and nx * tex + ny * tey + nz * tez < 0.0:
                continue
            l2 = nx * nx + ny * ny + nz * nz
            if l2 < 1e-24:
                continue
            pts = clip_proj(tri)
            if pts is None:
                continue
            inv = 1.0 / math.sqrt(l2)
            nx *= inv
            ny *= inv
            nz *= inv
            depth = sum(p[2] for p in pts) / len(pts)
            shade = abs(nx * lx + ny * ly + nz * lz)
            spec = max(nx * hax + ny * hay + nz * haz, 0.0)
            face_color = colors[index] if colors else None
            append((depth, pts, shade, spec, face_color))

        # The selected object is NOT drawn into the depth sort: its
        # triangles come from the built-in tessellator while `mesh` may
        # be OpenSCAD's exact render, and no depth bias can reconcile
        # two different tessellations of one surface — sorting them
        # together interleaved the two meshes and striped the selection
        # (zebra). Instead its silhouette is collected here and used as
        # a flat tint mask once the model is painted.
        hi_polys = []
        for tri in hmesh:
            pts = clip_proj(tri)
            if pts is not None:
                hi_polys.append(QPolygonF([QPointF(p[0], p[1])
                                           for p in pts]))

        if tree is None:                        # BSP order is already exact
            faces.sort(key=lambda fc: -fc[0])
        lighting = self._light()                # sliders, None when centred
        edge = QColor(t["border"])
        edge.setAlpha(60)
        pen = QPen(edge)
        pen.setWidthF(0.4)
        wire = QColor(base.darker(115))
        wire.setAlpha(70)
        wire_pen = QPen(wire)
        wire_pen.setWidthF(0.3)
        for _depth, pts, shade, spec, face_color in faces:
            poly = QPolygonF([QPointF(p[0], p[1]) for p in pts])
            if face_color is not None and face_color[0]:
                own = QColor(face_color[0])
                hue = max(own.hueF(), 0.0)
                sat = own.saturationF()
                val = own.valueF()
                alpha = max(min(face_color[1], 1.0), 0.15)
            else:
                hue = base.hueF() if base.hueF() >= 0 else 0.58
                sat = base.saturationF() * 0.75
                val = 1.0
                alpha = 1.0
            face_style = style
            if face_color is not None and len(face_color) > 2 \
                    and style not in ("Wireframe", "X-ray"):
                face_style = MATERIAL_STYLES.get(face_color[2], style)
            color, use_pen = self._style_color(
                face_style, hue, sat, val, shade, spec, base)
            if color is not None and lighting is not None:
                color = self._adjust(color, *lighting)
            if color is None:                   # wireframe: edges only
                painter.setPen(wire_pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawPolygon(poly)
                continue
            if alpha < 1.0:
                color.setAlphaF(alpha)
            if use_pen is not None:
                face_pen = use_pen
            elif color.alphaF() >= 0.99:
                # opaque: outline each facet in its own fill colour, so
                # there are no facet lines and no anti-aliasing gaps
                # between neighbouring triangles — a smooth surface.
                # A full pixel: at 0.8 the seams of BSP-split facets
                # still let a contrasting face behind show through
                face_pen = QPen(color)
                face_pen.setWidthF(1.0)
            else:
                face_pen = pen              # translucent: faint edges help
            painter.setPen(face_pen)
            painter.setBrush(color)
            painter.drawPolygon(poly)

        if hi_polys:
            self._tint_selection(painter, hi_polys)
        self._draw_anchors(painter, eye, right, up, forward)
        self._draw_pick_overlays(painter, eye, right, up, forward)
        self._draw_axes(painter, t, eye, right, up, forward)
        pair = BACKGROUNDS.get(self.background)
        if pair is None:
            painter.setPen(QColor(t["text"]))
        else:                                  # readable over the chosen bg
            dark = QColor(pair[1]).lightnessF() < 0.5
            painter.setPen(QColor("#e8e8e8") if dark else QColor("#333333"))
        painter.drawText(8, self.height() - 8,
                         f"{self.source} — {len(self.mesh)} triangles "
                         f"· {self.style}")
        painter.end()

    def _tint_selection(self, painter, polys):
        """Tint the selected object's screen region red, the way
        OpenSCAD's `#` modifier reads.

        The silhouette is filled into an offscreen mask and composited
        with **Multiply**, which buys three things a plain overlay
        cannot: the shading, facet edges and *cut holes* of whatever is
        underneath all survive (multiply keeps dark pixels dark, so a
        bore stays a bore); overlapping faces cannot stack into a
        darker patch, because the mask is flat; and nothing is
        interleaved with the model's own depth sort, so a mismatch
        between OpenSCAD's tessellation and the built-in one can never
        stripe the selection again."""
        mask = QImage(self.size(), QImage.Format_ARGB32_Premultiplied)
        mask.fill(Qt.transparent)
        mp = QPainter(mask)
        mp.setRenderHint(QPainter.Antialiasing,
                         painter.testRenderHint(QPainter.Antialiasing))
        mp.setPen(Qt.NoPen)
        mp.setBrush(QColor(self.HIGHLIGHT_COLOR))
        for poly in polys:
            mp.drawPolygon(poly)
        mp.end()
        mode = painter.compositionMode()
        painter.setCompositionMode(QPainter.CompositionMode_Multiply)
        painter.drawImage(0, 0, mask)
        painter.setCompositionMode(mode)

    @staticmethod
    def _style_color(style, hue, sat, val, shade, spec, base):
        """Map a face's shade/specular to a fill colour for the chosen
        render style. Returns (QColor|None, pen|None); None colour means
        draw edges only (wireframe)."""
        if style == "Wireframe":
            return None, None
        if style == "X-ray":
            # translucent glass — the form reads through overlapping faces
            c = QColor.fromHsvF(hue, sat * 0.6,
                                min(0.6 + 0.4 * shade, 1.0) * val)
            c.setAlphaF(0.13)
            return c, None
        if style == "Matte":
            # flat chalky plastic: desaturated, lighter, no highlight,
            # low shade contrast — clearly distinct from glossy Shaded
            c = QColor.fromHsvF(hue, sat * 0.5,
                                min((0.62 + 0.3 * shade) * val, 1.0))
            return c, None
        if style == "Clay":
            # neutral warm modelling clay — good for reading pure form
            c = QColor.fromHsvF(0.07, 0.20,
                                min((0.5 + 0.45 * shade) * val, 1.0))
            return c, None
        if style == "Toon":
            # cel shading: quantise the light into a few flat bands
            band = round(shade * 3.0) / 3.0
            c = QColor.fromHsvF(hue, min(sat * 0.95, 1.0),
                                min((0.45 + 0.55 * band) * val, 1.0))
            return c, None
        if style == "Brushed metal":
            # near-grey steel with a bright, tight specular streak
            highlight = spec ** 16
            v = min((0.28 + 0.45 * shade) * val + 0.7 * highlight, 1.0)
            s = sat * 0.22 * (1.0 - highlight)
            return QColor.fromHsvF(hue, s, v), None
        if style == "Gold":
            highlight = spec ** 20
            v = min((0.32 + 0.5 * shade) + 0.65 * highlight, 1.0)
            return QColor.fromHsvF(0.125, 0.72 * (1.0 - highlight * 0.6),
                                   v), None
        if style == "Copper":
            highlight = spec ** 20
            v = min((0.30 + 0.5 * shade) + 0.65 * highlight, 1.0)
            return QColor.fromHsvF(0.045, 0.68 * (1.0 - highlight * 0.6),
                                   v), None
        if style == "Glass":
            # see-through, with a sharp glint where the light catches
            glint = spec ** 24
            c = QColor.fromHsvF(hue, sat * 0.55,
                                min((0.55 + 0.35 * shade) * val
                                    + 0.6 * glint, 1.0))
            c.setAlphaF(0.35 + 0.4 * glint)
            return c, None
        if style == "Rubber":
            # dark and dull: no highlight, deep shadows
            return QColor.fromHsvF(hue, min(sat * 0.85, 1.0),
                                   (0.12 + 0.38 * shade) * val), None
        if style == "Skin":
            # soft and warm: low contrast, a faint sheen
            v = min((0.58 + 0.32 * shade) * val + 0.08 * spec ** 4, 1.0)
            return QColor.fromHsvF(hue, min(sat * 0.9 + 0.04, 1.0), v), None
        if style == "Emissive":
            # lights itself: its own colour at full strength, unshaded
            return QColor.fromHsvF(hue, sat, max(val, 0.9)), None
        # Shaded (default): rich, glossy — the reference look
        gloss = spec ** 10
        v = min((0.30 + 0.70 * shade) * val + 0.45 * gloss, 1.0)
        return QColor.fromHsvF(hue, min(sat * 1.1, 1.0), v), None

    #: automatic (bounding-box) anchors: one uniform, subtle colour —
    #: only the origin and the user's picked anchors stand out.
    AUTO_ANCHOR_COLOR = "#7f9db8"
    PICKED_ANCHOR_COLOR = "#f0269e"
    ORIGIN_ANCHOR_COLOR = "#ffcf40"

    def _marker_label(self, painter, x, y, text, color):
        """Bold label with a dark halo so it reads on any background."""
        if not text:
            return
        halo = QPen(QColor(0, 0, 0, 190))
        painter.setPen(halo)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx or dy:
                    painter.drawText(QPointF(x + dx, y + dy), text)
        painter.setPen(QPen(QColor(color)))
        painter.drawText(QPointF(x, y), text)

    def _draw_anchors(self, painter, eye, right, up, forward):
        """The selected Object's attachment points. Automatic anchors
        are small uniform dots; the origin is an RGB triad; the user's
        picked anchors are big haloed markers with an arrow and their
        name — unmissable."""
        if not self.anchor_markers or self._fast:
            return
        font = painter.font()
        font.setBold(True)
        font.setPointSizeF(8.5)
        painter.setFont(font)
        tick = self.distance / 14.0

        def project(p):
            return self._project(eye, right, up, forward, p)

        # 1. automatic bbox anchors: quiet, identical dots
        auto = QColor(self.AUTO_ANCHOR_COLOR)
        auto.setAlpha(170)
        painter.setPen(QPen(auto, 1.0))
        painter.setBrush(auto)
        for marker in self.anchor_markers:
            if marker.get("kind") not in ("face", "edge", "corner"):
                continue
            head = project(marker["pos"])
            if head is not None:
                r = 2.6 if marker["kind"] == "face" else 1.8
                painter.drawEllipse(QPointF(head[0], head[1]), r, r)

        # 2. the origin: a small RGB triad + yellow hub
        for marker in self.anchor_markers:
            if marker.get("kind") != "origin":
                continue
            pos = marker["pos"]
            head = project(pos)
            if head is None:
                continue
            for axis, color in (((tick, 0, 0), "#d64545"),
                                ((0, tick, 0), "#3f9e4d"),
                                ((0, 0, tick), "#3a6fd8")):
                tip = project((pos[0] + axis[0] * 0.8,
                               pos[1] + axis[1] * 0.8,
                               pos[2] + axis[2] * 0.8))
                if tip is not None:
                    painter.setPen(QPen(QColor(color), 1.8))
                    painter.drawLine(QPointF(head[0], head[1]),
                                     QPointF(tip[0], tip[1]))
            hub = QColor(self.ORIGIN_ANCHOR_COLOR)
            painter.setPen(QPen(QColor(255, 255, 255, 230), 2.0))
            painter.setBrush(hub)
            painter.drawEllipse(QPointF(head[0], head[1]), 4.0, 4.0)
            self._marker_label(painter, head[0] + 8, head[1] - 6,
                               marker.get("name", "Origin"),
                               self.ORIGIN_ANCHOR_COLOR)

        # 3. picked anchors: white-haloed marker, arrow, bold name
        pink = QColor(self.PICKED_ANCHOR_COLOR)
        for marker in self.anchor_markers:
            if marker.get("kind") != "custom":
                continue
            pos = marker["pos"]
            d = marker["dir"]
            head = project(pos)
            tip = project((pos[0] + d[0] * tick * 1.3,
                           pos[1] + d[1] * tick * 1.3,
                           pos[2] + d[2] * tick * 1.3))
            if head is None:
                continue
            if tip is not None:
                # white halo under the arrow, then the arrow itself
                painter.setPen(QPen(QColor(255, 255, 255, 220), 4.5))
                painter.drawLine(QPointF(head[0], head[1]),
                                 QPointF(tip[0], tip[1]))
                painter.setPen(QPen(pink, 2.2))
                painter.drawLine(QPointF(head[0], head[1]),
                                 QPointF(tip[0], tip[1]))
                # arrowhead: two short barbs back from the tip
                vx, vy = tip[0] - head[0], tip[1] - head[1]
                length = (vx * vx + vy * vy) ** 0.5 or 1.0
                vx, vy = vx / length, vy / length
                for s in (1.0, -1.0):
                    bx = tip[0] - 8.0 * vx + 4.5 * s * -vy
                    by = tip[1] - 8.0 * vy + 4.5 * s * vx
                    painter.drawLine(QPointF(tip[0], tip[1]),
                                     QPointF(bx, by))
            painter.setPen(QPen(QColor(255, 255, 255, 235), 2.4))
            painter.setBrush(pink)
            painter.drawEllipse(QPointF(head[0], head[1]), 5.5, 5.5)
            self._marker_label(painter, head[0] + 9, head[1] - 7,
                               marker.get("name", ""),
                               self.PICKED_ANCHOR_COLOR)

    #: pick-mode pre-highlight (hover) and the pinned first snap click.
    HOVER_PICK_COLOR = "#2f9df0"
    PINNED_PICK_COLOR = "#ff9b2f"

    def _draw_pick_desc(self, painter, project, desc, label, color):
        """One picked/hovered face or edge: translucent face fill (or a
        thick edge run), a marker dot and a haloed name label."""
        col = QColor(color)
        if desc.get("tris"):
            fill = QColor(col)
            fill.setAlpha(80)
            painter.setPen(Qt.NoPen)
            painter.setBrush(fill)
            for a, b, c in desc["tris"]:
                pa, pb, pc = project(a), project(b), project(c)
                if pa is None or pb is None or pc is None:
                    continue
                painter.drawPolygon(QPolygonF([
                    QPointF(pa[0], pa[1]), QPointF(pb[0], pb[1]),
                    QPointF(pc[0], pc[1])]))
        if desc.get("seg"):
            a, b = desc["seg"]
            pa, pb = project(a), project(b)
            if pa is not None and pb is not None:
                painter.setPen(QPen(QColor(255, 255, 255, 200), 5.0))
                painter.drawLine(QPointF(pa[0], pa[1]),
                                 QPointF(pb[0], pb[1]))
                painter.setPen(QPen(col, 3.0))
                painter.drawLine(QPointF(pa[0], pa[1]),
                                 QPointF(pb[0], pb[1]))
        head = project(desc["pos"])
        if head is not None:
            painter.setPen(QPen(QColor(255, 255, 255, 230), 1.6))
            painter.setBrush(col)
            painter.drawEllipse(QPointF(head[0], head[1]), 4.0, 4.0)
            self._marker_label(painter, head[0] + 8, head[1] - 6,
                               label, color)

    def _draw_pick_overlays(self, painter, eye, right, up, forward):
        """Pick mode's visual state: what the cursor is over, what the
        first snap click grabbed, and what to do next."""
        if self._pick_pinned is None and self._pick_cb is None:
            return

        def project(p):
            return self._project(eye, right, up, forward, p)

        font = painter.font()
        font.setBold(True)
        font.setPointSizeF(8.5)
        painter.setFont(font)
        if self._pick_pinned is not None:
            desc, label = self._pick_pinned
            self._draw_pick_desc(painter, project, desc, label,
                                 self.PINNED_PICK_COLOR)
        if self._pick_cb is not None and self._pick_hover is not None:
            desc, label = self._pick_hover
            self._draw_pick_desc(painter, project, desc, label,
                                 self.HOVER_PICK_COLOR)
        if self._pick_cb is not None and self._pick_banner:
            font.setPointSizeF(9.5)
            painter.setFont(font)
            metrics = painter.fontMetrics()
            w = metrics.horizontalAdvance(self._pick_banner) + 24
            h = metrics.height() + 10
            rect = QRectF((self.width() - w) / 2.0, 8.0, w, h)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(20, 26, 32, 215))
            painter.drawRoundedRect(rect, 6.0, 6.0)
            painter.setPen(QColor("#f2f6fa"))
            painter.drawText(rect, Qt.AlignCenter, self._pick_banner)

    def _draw_ground(self, painter, t, eye, right, up, forward):
        pen = QPen(QColor(t["border"]))
        pen.setWidthF(0.7)
        painter.setPen(pen)
        span, step = 100, 10
        for i in range(-span, span + 1, step):
            for a, b in (((i, -span, 0), (i, span, 0)),
                         ((-span, i, 0), (span, i, 0))):
                pa = self._project(eye, right, up, forward, a)
                pb = self._project(eye, right, up, forward, b)
                if pa and pb:
                    painter.drawLine(QPointF(pa[0], pa[1]),
                                     QPointF(pb[0], pb[1]))

    def _draw_axes(self, painter, t, eye, right, up, forward):
        origin = self._project(eye, right, up, forward, (0, 0, 0))
        if origin is None:
            return
        scale = self.distance / 8.0
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        for axis, label, color in (((scale, 0, 0), "X", "#d64545"),
                                   ((0, scale, 0), "Y", "#3f9e4d"),
                                   ((0, 0, scale), "Z", "#3a6fd8")):
            tip = self._project(eye, right, up, forward, axis)
            if tip:
                pen = QPen(QColor(color))
                pen.setWidthF(1.6)
                painter.setPen(pen)
                painter.drawLine(QPointF(origin[0], origin[1]),
                                 QPointF(tip[0], tip[1]))
                painter.drawText(QPointF(tip[0] + 3, tip[1] - 3),
                                 label)

    # ------------------------------------------------------------- mouse
    def mousePressEvent(self, event):
        if self._pick_cb is not None:
            if event.button() == Qt.LeftButton:
                self._run_pick(event.pos().x(), event.pos().y())
            else:                            # right/middle click cancels
                self.cancel_pick()
            return
        self._last = event.pos()
        self._mode = "orbit" if event.button() == Qt.LeftButton else "pan"
        self._begin_fast()

    def mouseReleaseEvent(self, event):
        self._last = None
        self._mode = None
        self._fast = False
        self.update()                     # repaint the final frame crisp

    def mouseMoveEvent(self, event):
        if self._pick_cb is not None and self._last is None:
            self._queue_hover(event.pos())    # pre-highlight the target
            return
        if self._last is None:
            return
        delta = event.pos() - self._last
        self._last = event.pos()
        self.user_moved = True                # you own the view now
        if self._mode == "orbit":
            self.yaw = (self.yaw - delta.x() * 0.5) % 360.0
            # free vertical orbit — wrap instead of clamping at the poles
            # so you can tumble the model right over the top
            self.pitch = (self.pitch + delta.y() * 0.5 + 180.0) \
                % 360.0 - 180.0
        else:
            _eye, right, up, _fwd = self._camera()
            scale = self.distance / 600.0
            for i in range(3):
                self.target[i] -= right[i] * delta.x() * scale
                self.target[i] += up[i] * delta.y() * scale
        self.update()

    def wheelEvent(self, event):
        self.user_moved = True
        factor = 0.87 if event.angleDelta().y() > 0 else 1.15
        self.distance = max(2.0, min(5000.0, self.distance * factor))
        self._begin_fast()                # draft while zooming...
        self._idle.start()                # ...back to crisp when it stops
        self.update()

    def mouseDoubleClickEvent(self, event):
        self.fit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self._pick_cb is not None:
            self.cancel_pick()
            return
        super().keyPressEvent(event)
