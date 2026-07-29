"""Tests for 3D render styles and selection glow.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad.view3d import RENDER_STYLES, View3D


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def test_every_style_paints_without_error(app):
    view = View3D()
    view.resize(200, 200)
    view.set_mesh([((0, 0, 0), (10, 0, 0), (0, 10, 0)),
                   ((0, 0, 0), (0, 10, 0), (0, 0, 10))], "test")
    view.set_highlight_mesh([((0, 0, 0), (10, 0, 0), (0, 10, 0))])
    for style in RENDER_STYLES:
        view.set_style(style)
        assert view.style == style
        view.grab()                    # exercises the paint path


def _grid_mesh(n):
    """A throwaway mesh of *n* triangles."""
    return [((i, 0, 0), (i + 1, 0, 0), (i, 1, 0)) for i in range(n)]


def test_small_mesh_has_no_draft(app):
    view = View3D()
    view.set_mesh(_grid_mesh(100), "test")
    assert view._draft_mesh is None          # drawn whole even while dragging


def test_big_mesh_decimates_for_interaction(app):
    view = View3D()
    view.set_mesh(_grid_mesh(60000), "test")
    assert view._draft_mesh is not None
    # the draft targets ~DRAFT_TARGET triangles, well under the full count
    assert len(view._draft_mesh) <= view.DRAFT_TARGET * 1.2
    assert len(view._draft_mesh) < 60000


def test_fast_mode_draws_the_draft(app):
    view = View3D()
    view.resize(200, 200)
    view.set_mesh(_grid_mesh(60000), "test")
    view._begin_fast()
    assert view._fast is True
    view.grab()                              # paints the draft path
    view._end_fast()
    assert view._fast is False


def test_style_persists(app):
    view = View3D()
    view.set_style("Brushed metal")
    other = View3D()
    assert other.style == "Brushed metal"
    view.set_style("Shaded")           # restore default for other tests


def test_unknown_style_ignored(app):
    view = View3D()
    view.set_style("Shaded")
    view.set_style("Nonsense")
    assert view.style == "Shaded"


def _cube(s=20.0):
    pts = [(0, 0, 0), (s, 0, 0), (s, s, 0), (0, s, 0),
           (0, 0, s), (s, 0, s), (s, s, s), (0, s, s)]
    faces = [(0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6),
             (0, 4, 5), (0, 5, 1), (1, 5, 6), (1, 6, 2),
             (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0)]
    return [tuple(pts[i] for i in f) for f in faces]


def _central_avg(view):
    from PyQt5.QtCore import QSize
    from PyQt5.QtGui import QImage, QPainter
    w, h = view.width(), view.height()
    img = QImage(QSize(w, h), QImage.Format_ARGB32)
    img.fill(0)
    painter = QPainter(img)
    view.render(painter)
    painter.end()
    r = g = b = n = 0
    for x in range(w // 3, 2 * w // 3, 4):
        for y in range(h // 3, 2 * h // 3, 4):
            c = img.pixelColor(x, y)
            r += c.red(); g += c.green(); b += c.blue(); n += 1
    return (r / n, g / n, b / n)


def test_styles_render_distinctly(app):
    """Each render style must produce a visibly different image — a
    regression guard against styles collapsing into look-alikes."""
    view = View3D()
    view.resize(300, 300)
    view.set_mesh(_cube(), "test")
    view.fit()
    avgs = {}
    for style in RENDER_STYLES:
        view.set_style(style)
        avgs[style] = _central_avg(view)

    def dist(a, b):
        return sum(abs(x - y) for x, y in zip(a, b))

    # every pair of styles differs by a clear margin
    styles = list(RENDER_STYLES)
    for i in range(len(styles)):
        for j in range(i + 1, len(styles)):
            d = dist(avgs[styles[i]], avgs[styles[j]])
            assert d > 20, (styles[i], styles[j], d)
    # Matte used to be nearly identical to Shaded — keep them apart
    assert dist(avgs["Matte"], avgs["Shaded"]) > 60


def _selection_pixels(view):
    """Every pixel over the model, as (r, g, b)."""
    from PyQt5.QtCore import QSize
    from PyQt5.QtGui import QImage, QPainter
    w, h = view.width(), view.height()
    img = QImage(QSize(w, h), QImage.Format_ARGB32)
    img.fill(0)
    painter = QPainter(img)
    view.render(painter)
    painter.end()
    out = []
    for x in range(w // 3, 2 * w // 3, 2):
        for y in range(h // 3, 2 * h // 3, 2):
            c = img.pixelColor(x, y)
            if c.alpha() > 0:
                out.append((c.red(), c.green(), c.blue()))
    return out


def test_selection_paints_openscad_red(app):
    """Selecting an object shows it in OpenSCAD `#` style: red, not
    the base shading."""
    view = View3D()
    view.resize(300, 300)
    view.set_mesh(_cube(), "test")
    view.fit()
    plain = _central_avg(view)
    view.set_highlight_mesh(_cube())
    picked = _central_avg(view)
    # red channel dominates, and it clearly changed from unselected
    assert picked[0] > picked[1] + 40
    assert picked[0] > picked[2] + 40
    assert abs(picked[0] - plain[0]) + abs(picked[2] - plain[2]) > 40


def test_selection_keeps_the_form_readable(app):
    """The `#` tint must not flatten the object into one solid blob:
    the faces keep distinct shading (the old opaque amber fill plus a
    per-triangle pen destroyed this)."""
    view = View3D()
    view.resize(300, 300)
    view.set_mesh(_cube(), "test")
    view.fit()
    view.set_highlight_mesh(_cube())
    shades = {r // 16 for r, _g, _b in _selection_pixels(view)}
    assert len(shades) >= 2, "selection collapsed to a flat colour"


def test_selection_does_not_stripe_on_a_mismatched_mesh(app):
    """The displayed mesh is OpenSCAD's exact render while the
    highlight comes from the built-in tessellator, so the two are
    different triangulations of one surface. They must not be sorted
    together: that interleaved them and striped the selection with
    untinted bands (the "zebra" bug)."""
    import math

    def disc(segments, phase):
        """A closed disc; *phase* rotates the tessellation without
        changing the shape."""
        tris, r, h = [], 20.0, 5.0
        for i in range(segments):
            a0 = 2 * math.pi * (i + phase) / segments
            a1 = 2 * math.pi * (i + 1 + phase) / segments
            p0 = (r * math.cos(a0), r * math.sin(a0))
            p1 = (r * math.cos(a1), r * math.sin(a1))
            tris.append(((0.0, 0.0, h), (p0[0], p0[1], h),
                         (p1[0], p1[1], h)))
            tris.append(((0.0, 0.0, 0.0), (p1[0], p1[1], 0.0),
                         (p0[0], p0[1], 0.0)))
            # both triangles of the side quad, or the wall has holes
            tris.append(((p0[0], p0[1], 0.0), (p1[0], p1[1], 0.0),
                         (p1[0], p1[1], h)))
            tris.append(((p0[0], p0[1], 0.0), (p1[0], p1[1], h),
                         (p0[0], p0[1], h)))
        return tris

    view = View3D()
    view.resize(300, 300)
    view.set_style("Matte")
    # the same disc tessellated two different ways, as OpenSCAD's
    # exact render and the built-in tessellator really do differ
    view.set_mesh(disc(40, 0.37), "OpenSCAD")
    view.set_highlight_mesh(disc(40, 0.0))
    view.fit()
    # Count only pixels still wearing the untinted base colour — a
    # warm r > g > b in the shaded range. That excludes the pale
    # background (too bright) and the axis gizmo drawn over the tint
    # (blue/green, so not warm), leaving exactly the striping signal.
    pixels = _selection_pixels(view)
    untinted = [p for p in pixels
                if 90 < p[1] < 215 and p[0] > p[1] > p[2]]
    # striping loses ~97% of the part; a handful of antialiased edge
    # blends is not it, so 1% keeps a wide margin either way
    assert len(untinted) * 100 < len(pixels), \
        (f"{len(untinted)}/{len(pixels)} px escaped the tint — "
         f"the selection striped")


def test_backface_culling_keeps_the_solid_opaque(app):
    """Culling back faces must not make a closed solid see-through:
    the centre of a shaded cube stays a solid surface colour."""
    from PyQt5.QtCore import QSize
    from PyQt5.QtGui import QColor, QImage, QPainter
    from khervecad.style import tokens
    view = View3D()
    view.resize(300, 300)
    view.set_mesh(_cube(), "test")
    view.fit()
    view.set_style("Shaded")
    img = QImage(QSize(300, 300), QImage.Format_ARGB32)
    img.fill(0)
    painter = QPainter(img)
    view.render(painter)
    painter.end()
    bg = QColor(tokens()["editor"])
    c = img.pixelColor(150, 150)
    diff = (abs(c.red() - bg.red()) + abs(c.green() - bg.green())
            + abs(c.blue() - bg.blue()))
    assert diff > 20                          # a face is drawn, not the bg


def test_fit_centers_the_model(app):
    """fit() frames the mesh centred in the pane and filling most of
    the height, so it never sits low with dead space above."""
    view = View3D()
    view.resize(400, 300)
    mesh = _cube(30.0)
    # offset the cube well away from the origin/target start
    mesh = [tuple((x + 70, y - 40, z + 25) for x, y, z in tri)
            for tri in mesh]
    view.set_mesh(mesh, "test")
    view.fit()
    eye, right, up, forward = view._camera()
    xs, ys = [], []
    for tri in mesh:
        for v in tri:
            p = view._project(eye, right, up, forward, v)
            if p:
                xs.append(p[0]); ys.append(p[1])
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    assert abs(cx - view.width() / 2) < 12
    assert abs(cy - view.height() / 2) < 12       # centred, not low
    fill_h = (max(ys) - min(ys)) / view.height()
    assert fill_h > 0.7                            # fills the pane


def test_orbit_pitch_is_not_clamped(app):
    from PyQt5.QtCore import QPoint
    view = View3D()
    view.pitch = 88.0
    view._mode = "orbit"
    view._last = QPoint(0, 0)

    class _Evt:
        def __init__(self, x, y):
            self._p = QPoint(x, y)

        def pos(self):
            return self._p

    view.mouseMoveEvent(_Evt(0, 20))               # drag down past the top
    assert view.pitch > 90.0                        # not clamped at 89


def test_orbiting_marks_user_moved(app):
    from PyQt5.QtCore import QPoint
    view = View3D()
    assert view.user_moved is False
    view._mode = "orbit"
    view._last = QPoint(0, 0)

    class _Evt:
        def __init__(self, x, y):
            self._p = QPoint(x, y)

        def pos(self):
            return self._p

    view.mouseMoveEvent(_Evt(10, 0))
    assert view.user_moved is True             # app stops auto-refitting


def test_backgrounds_paint_without_error(app):
    from PyQt5.QtCore import QSize
    from PyQt5.QtGui import QImage, QPainter
    from khervecad.view3d import BACKGROUNDS
    view = View3D()
    view.resize(120, 120)
    view.set_mesh([((0, 0, 0), (10, 0, 0), (0, 10, 0))], "test")
    view.fit()
    for name in BACKGROUNDS:
        view.set_background(name)
        assert view.background == name
        view.grab()
    # a gradient background differs top vs bottom
    view.set_background("Dark")
    img = QImage(QSize(120, 120), QImage.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    view.render(p)
    p.end()
    assert img.pixelColor(60, 3) != img.pixelColor(60, 117)
    view.set_background("Theme")               # restore default


def test_escape_cancels_pick_mode(app):
    """Esc leaves pick mode and the callback hears the cancel."""
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QKeyEvent
    from PyQt5.QtCore import QEvent
    view = View3D()
    got = []
    view.start_pick(got.append, banner="pick something")
    assert view._pick_banner == "pick something"
    assert view.hasMouseTracking()
    view.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Escape,
                                 Qt.NoModifier))
    assert got == [None]
    assert view._pick_cb is None and view._pick_banner == ""
    assert not view.hasMouseTracking()


def test_pick_overlays_paint_without_error(app):
    """Hover + pinned pick highlights and the banner all paint."""
    view = View3D()
    view.resize(200, 200)
    view.set_mesh([((0, 0, 0), (10, 0, 0), (0, 10, 0))], "test")
    face = dict(kind="face", name="Face", pos=[3.0, 3.0, 0.0],
                dir=[0.0, 0.0, 1.0],
                tris=[((0, 0, 0), (10, 0, 0), (0, 10, 0))])
    edge = dict(kind="edge", name="Edge", pos=[5.0, 0.0, 0.0],
                dir=[0.0, -1.0, 0.0],
                seg=[[0.0, 0.0, 0.0], [10.0, 0.0, 0.0]])
    view.start_pick(lambda d: None, banner="Snap 1/2 — click a face")
    view._pick_hover = (face, "Cube · Face")
    view.set_pick_pinned(edge, "Lid · Edge")
    view.grab()
    view.cancel_pick()
    assert view._pick_pinned is None


def test_describe_pick_reports_highlight_geometry(app):
    """describe_pick returns the grown face (tris) or the edge run
    (seg) so the view can pre-highlight the exact pick target."""
    from khervecad import anchors
    # a 10x10 square in the XY plane, two coplanar triangles
    tris = [((0, 0, 0), (10, 0, 0), (10, 10, 0)),
            ((0, 0, 0), (10, 10, 0), (0, 10, 0))]
    desc = anchors.describe_pick(tris, 0, [5.0, 5.0, 0.0], tol=0.1)
    assert desc["kind"] == "face" and len(desc["tris"]) == 2
    desc = anchors.describe_pick(tris, 0, [5.0, 0.05, 0.0], tol=0.5)
    assert desc["kind"] == "edge"
    a, b = desc["seg"]
    assert sorted([a[0], b[0]]) == [0.0, 10.0]
