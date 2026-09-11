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


def test_perspective_culling_keeps_the_rim_of_a_torus(app):
    """Faces were culled against one constant view direction; in
    perspective the near inner rim of a ring then vanished in a
    saw-tooth and the far wall showed through. Every visible face must
    be tested against the ray from that face to the eye."""
    import math
    from khervecad import sweep
    ring = [[20 * math.cos(math.radians(a)), 20 * math.sin(math.radians(a)),
             0.0] for a in range(0, 360, 45)]
    circ = [(3 * math.cos(2 * math.pi * k / 20),
             3 * math.sin(2 * math.pi * k / 20)) for k in range(20)]
    tris = sweep.sweep([circ], ring, smooth=3, closed=True)
    view = View3D()
    view.resize(800, 600)
    view.background = "Light"
    view.style = "Matte"                  # not set_style: that persists
    view.set_mesh(tris, "test")
    view.wait_for_bsp()
    view.yaw, view.pitch = 30.0, 22.0     # the near side is at 30°
    view.fit()
    view.distance *= 0.85                 # closer: stronger perspective
    img = view.grab().toImage()
    eye, right, up, forward = view._camera()
    # the top-inner quadrant of the cord on the near side of the ring:
    # visible surface, so every sample must be the model's colour —
    # the culled band let the pale background show through
    seen = []
    for angle in range(-30, 91, 10):
        for phi in range(96, 113, 2):
            t, p = math.radians(angle), math.radians(phi)
            r = 20 + 3 * math.cos(p)
            world = (r * math.cos(t), r * math.sin(t), 3 * math.sin(p))
            x, y, _ = view._project(eye, right, up, forward, world)
            assert 0 <= x < 800 and 0 <= y < 600
            seen.append(img.pixelColor(int(x), int(y)).lightnessF())
    assert max(seen) < 0.86, max(seen)


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


# ------------------------------------------------------- lighting bar

@pytest.fixture
def neutral_light():
    """The sliders persist in QSettings and every View3D reads them at
    construction, so a test that moves one would otherwise re-shade
    every later test (and the user's own app)."""
    from PyQt5.QtCore import QSettings

    from khervecad.view3d import _SETTINGS
    keys = ("render_brightness", "render_contrast")
    settings = QSettings(*_SETTINGS)
    saved = [settings.value(k) for k in keys]
    for key in keys:
        settings.setValue(key, 0.0)
    yield
    for key, value in zip(keys, saved):
        settings.setValue(key, 0.0 if value is None else value)


def test_brightness_slider_lightens_the_model(app, neutral_light):
    """The floating Bright slider changes the rendered faces, and
    centring it restores exactly the default look."""
    view = View3D()
    view.resize(300, 300)
    view.set_mesh(_cube(), "test")
    view.fit()
    default = _central_avg(view)

    view.lighting_bar.sliders["brightness"].setValue(80)
    assert view.brightness == pytest.approx(0.8)
    brighter = _central_avg(view)
    view.lighting_bar.sliders["brightness"].setValue(-80)
    darker = _central_avg(view)
    assert sum(brighter) > sum(default) + 30
    assert sum(darker) < sum(default) - 30

    view.lighting_bar.reset()
    assert view._light() is None                # hot path skipped again
    assert _central_avg(view) == default


def test_contrast_slider_spreads_the_shading(app, neutral_light):
    """Contrast pivots about mid-grey: the spread between the lit and
    the unlit faces widens, without simply brightening everything."""
    view = View3D()
    view.resize(300, 300)
    view.set_mesh(_cube(), "test")
    view.fit()

    def spread():
        shades = sorted(r for r, _g, _b in _selection_pixels(view))
        if not shades:
            return 0.0
        cut = max(len(shades) // 10, 1)
        return shades[-cut] - shades[cut]

    flat = spread()
    view.lighting_bar.sliders["contrast"].setValue(100)
    assert view.contrast == pytest.approx(1.0)
    assert spread() > flat


def test_lighting_settings_persist_and_survive_junk(app, neutral_light):
    from PyQt5.QtCore import QSettings

    from khervecad.view3d import _SETTINGS
    view = View3D()
    view.set_light("brightness", 0.5)
    assert View3D().brightness == pytest.approx(0.5)
    QSettings(*_SETTINGS).setValue("render_brightness", "nonsense")
    assert View3D().brightness == 0.0           # never crashes on junk
    view.set_light("brightness", 0.0)


def test_lighting_bar_steps_aside_for_a_pick(app, neutral_light):
    view = View3D()
    view.resize(300, 300)
    view.set_mesh(_cube(), "test")
    view.start_pick(lambda d: None, banner="Click a face")
    assert view.lighting_bar.isHidden()
    view.cancel_pick()
    assert not view.lighting_bar.isHidden()


def test_redraw_button_rebuilds_both_views(app):
    """The Redraw button on the bar drops the mesh caches and rebuilds
    the views — the escape hatch when the incremental 3D pipeline shows
    something stale."""
    from khervecad import mesh
    from khervecad.mainwindow import MainWindow
    window = MainWindow()
    m = window.model
    comp = m.new_component("Part")
    m.add_node("cube", dict(width=10.0, depth=10.0, height=10.0),
               parent=comp)
    m.structure_changed.emit()
    assert mesh._COMP_CACHE                      # populated by the preview

    window.view3d.lighting_bar.refresh_requested.emit()
    assert window.view3d.mesh                    # redrawn, not emptied
    assert comp.id in window.scene._part_items


def test_colouring_cancels_a_render_that_would_wipe_it(app):
    """Colours live only in the built-in preview (an STL carries none),
    so once a document is multi-coloured any render still in flight is
    disowned — otherwise it lands and repaints everything grey."""
    from khervecad.mainwindow import MainWindow
    window = MainWindow()
    window.engine.binary = "openscad"            # pretend one was found
    m = window.model
    a = m.add_node("cube", dict(width=10.0, depth=10.0, height=10.0))
    b = m.add_node("sphere", dict(radius=5.0, x=30.0))
    m.structure_changed.emit()
    assert window.engine._pending_code is not None   # plain: render it

    m.wrap_nodes([a], "color").params["color"] = "#ff0000"
    m.wrap_nodes([b], "color").params["color"] = "#00ff00"
    m.structure_changed.emit()
    assert window.engine._pending_code is None       # coloured: cancelled
    colors = window.view3d.colors
    assert colors and any(c is not None for c in colors)


def _render(view):
    """The view painted into a pixel-addressable image."""
    from PyQt5.QtCore import QSize
    from PyQt5.QtGui import QImage, QPainter
    img = QImage(QSize(view.width(), view.height()), QImage.Format_ARGB32)
    img.fill(0)
    painter = QPainter(img)
    view.render(painter)
    painter.end()
    return img


def _close_up(view):
    """Park the camera 5 mm above a point on the floor."""
    view.yaw, view.pitch = 35.0, 22.0
    view.target, view.distance = [0.0, 0.0, 0.0], 5.0


def test_close_up_clips_faces_instead_of_dropping_them(app):
    """A face reaching behind the camera is clipped at the near plane,
    not dropped whole. Dropping it opened strips of background across
    a close-up of an OpenSCAD mesh — the long edge slivers lose one
    vertex behind the eye first — which read as white seams."""
    floor = [((-500, -500, 0), (500, -500, 0), (500, 500, 0)),
             ((-500, -500, 0), (500, 500, 0), (-500, 500, 0))]
    view = View3D()
    view.resize(300, 300)
    view.set_style("Shaded")
    view.set_mesh([], "test")
    _close_up(view)
    empty = _render(view)
    view.set_mesh(floor, "test")
    _close_up(view)
    # the premise: every face has a corner behind the eye
    eye, _right, _up, forward = view._camera()
    for tri in floor:
        assert any(sum((v[i] - eye[i]) * forward[i] for i in range(3))
                   < view.NEAR_PLANE for v in tri)
    drawn = _render(view)
    probes = [(x, y) for x in range(40, 261, 20)
              for y in range(120, 261, 20)]
    covered = 0
    for x, y in probes:
        a, b = empty.pixelColor(x, y), drawn.pixelColor(x, y)
        if (abs(a.red() - b.red()) + abs(a.green() - b.green())
                + abs(a.blue() - b.blue())) > 20:
            covered += 1
    # a few probes may land on the axis gizmo, drawn over both images
    assert covered >= 0.9 * len(probes), \
        f"{len(probes) - covered}/{len(probes)} px show the background"


def test_near_clip_keeps_faces_in_front_untouched(app):
    """Clipping must not bend a face that is wholly in front: the
    ordinary path still paints a fitted cube solid."""
    view = View3D()
    view.resize(200, 200)
    view.set_mesh(_cube(), "test")
    view.fit()
    img = _render(view)
    view.set_mesh([], "test")
    bg = _render(view)
    a, b = img.pixelColor(100, 100), bg.pixelColor(100, 100)
    assert (abs(a.red() - b.red()) + abs(a.green() - b.green())
            + abs(a.blue() - b.blue())) > 20


def test_orthographic_projection_keeps_true_size(app):
    """Orthographic rays are parallel: an edge far away projects the
    same length as one near by. Perspective shrinks the far one."""
    view = View3D()
    view.resize(300, 300)
    view.yaw, view.pitch = 0.0, 0.0          # from +X, looking along -X
    view.target, view.distance = [0.0, 0.0, 0.0], 100.0
    near, far = (0.0, 10.0, 0.0), (-50.0, 10.0, 0.0)

    def offset(v):
        eye, right, up, forward = view._camera()
        return view._project(eye, right, up, forward, v)[0] - 150

    view.projection = "Perspective"
    assert abs(offset(near)) > abs(offset(far)) + 1
    view.projection = "Orthographic"
    assert offset(near) == pytest.approx(offset(far))


def test_fit_frames_the_model_in_orthographic_too(app):
    view = View3D()
    view.resize(400, 300)
    view.projection = "Orthographic"
    view.set_mesh(_cube(30.0), "test")
    view.fit()
    eye, right, up, forward = view._camera()
    ys = [view._project(eye, right, up, forward, v)[1]
          for tri in _cube(30.0) for v in tri]
    assert 0.7 < (max(ys) - min(ys)) / view.height() <= 1.0


def test_snapshot_leaves_the_users_camera_alone(app):
    """An assistant inspecting from another angle must not move the
    view the user is working in."""
    view = View3D()
    view.resize(300, 200)
    view.set_mesh(_cube(), "test")
    view.fit()
    before = view.camera_state()
    img, state = view.snapshot(240, 160, yaw=0.0, pitch=0.0,
                               projection="Orthographic", frame=True)
    assert view.camera_state() == before
    assert (img.width(), img.height()) == (240, 160)
    assert state["azimuth"] == 0.0 and state["elevation"] == 0.0
    assert state["projection"] == "Orthographic"


def test_snapshot_frames_just_the_points_it_is_given(app):
    """frame=<points> aims at one part: the camera targets its centre,
    not the middle of the whole scene."""
    far = [tuple((x + 200, y, z) for x, y, z in tri) for tri in _cube(10)]
    view = View3D()
    view.resize(300, 300)
    view.set_mesh(_cube(10) + far, "test")
    _img, state = view.snapshot(300, 300, frame=[v for t in far for v in t])
    assert state["target"][0] == pytest.approx(205.0, abs=2.0)
    _img, whole = view.snapshot(300, 300, frame=True)
    # perspective fit centres the projected outline, so the whole-scene
    # target sits somewhere between the two cubes — not on the far one
    assert 20.0 < whole["target"][0] < 190.0
    assert state["distance"] < whole["distance"]


def test_zoom_moves_the_snapshot_camera_in(app):
    view = View3D()
    view.resize(200, 200)
    view.set_mesh(_cube(), "test")
    _img, base = view.snapshot(200, 200, frame=True)
    _img, close = view.snapshot(200, 200, frame=True, zoom=2.0)
    # camera_state rounds to the micrometre
    assert close["distance"] == pytest.approx(base["distance"] / 2,
                                              abs=1e-2)


def test_projection_persists(app):
    from PyQt5.QtCore import QSettings
    settings = QSettings("Kherve", "KherveCAD")
    saved = settings.value("render_projection", "Perspective")
    try:
        View3D().set_projection("Orthographic")
        assert View3D().projection == "Orthographic"
        View3D().set_projection("Sideways")       # unknown: ignored
        assert View3D().projection == "Orthographic"
    finally:
        settings.setValue("render_projection", saved)
