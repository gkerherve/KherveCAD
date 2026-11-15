"""Selected Contours: ONE sketch, several bosses at several depths, each
from the regions picked (Exercise 53, wLhqYhJMTXw: Sketch1 on the Top
Plane closes a plate, a wall and a ring; Boss-Extrude1 takes the plate
10 high, Boss-Extrude2 the wall 35, Boss-Extrude3 the ring 45).

MCP `sketch_feature` took the WHOLE closed area of a sketch that closes
its own areas (its `region` only served a single line closed by the
part's edges) and could not reuse a sketch already extruded. By mouse:
the sketch selected, Extruded Boss asks for the regions in 3D; with
nothing selected, the toggle bar's region click reuses the sketch.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from test_lever_by_mouse import win  # noqa: F401
from test_rib import _volume


def _sketch(win):
    """A 60 x 40 frame of lines with a line across at y = 20: two
    regions, 60 x 20 each."""
    from khervecad import refgeom_ui
    group = refgeom_ui.sketch_on(win, origin=(0, 0, 0), normal=(0, 0, 1),
                                 label="Sketch", open_2d=False)
    m = win.model
    pts = [(0, 0), (60, 0), (60, 40), (0, 40)]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        m.add_node("line", dict(x1=x1, y1=y1, x2=x2, y2=y2, width=0.2),
                   parent=group)
    m.add_node("line", dict(x1=0, y1=20, x2=60, y2=20, width=0.2),
               parent=group)
    QApplication.processEvents()
    return group


def _bounds(win):
    from khervecad import mesh
    tris = mesh.tessellate(win.model.root)
    zs = [p[2] for t in tris for p in t]
    ys = [p[1] for t in tris for p in t]
    return min(ys), max(ys), min(zs), max(zs)


def test_mcp_picks_one_region_then_reuses_the_sketch_for_the_other(win):
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(win)
    group = _sketch(win)
    out = ex.execute("sketch_feature", {"node_id": group.id, "depth": 10,
                                        "region": [30, 10]})
    assert "error" not in out, out
    QTest.qWait(50)
    assert _volume(win) == pytest.approx(60 * 20 * 10, rel=0.02)
    # the same sketch again, the other region, another depth
    out = ex.execute("sketch_feature", {"node_id": group.id, "depth": 35,
                                        "regions": [[30, 30]]})
    assert "error" not in out, out
    QTest.qWait(50)
    assert _volume(win) == pytest.approx(60 * 20 * (10 + 35), rel=0.02)
    assert _bounds(win) == pytest.approx((0, 40, 0, 35), abs=0.1)


def _click_world(win, p):
    view = win.view3d
    eye, r, u, f = view._camera()
    x, y, _z = view._project(eye, r, u, f, p)
    pos = QPoint(int(round(x)), int(round(y)))
    QTest.mouseMove(view, pos)
    QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, pos)
    QApplication.processEvents()


def _ok(win):
    from khervecad import region_panel
    QApplication.processEvents()
    panel = region_panel._panel(win) if hasattr(region_panel, "_panel") \
        else None
    win.view3d.cancel_pick()               # what the window's OK does
    for _ in range(5):
        QApplication.processEvents()
    return panel


def test_by_mouse_two_bosses_from_one_sketch(win):
    from khervecad import drag_feature
    group = _sketch(win)
    win.view3d.set_view("Top") if hasattr(win.view3d, "set_view") else None
    win.view3d.fit()
    QApplication.processEvents()
    # Boss-Extrude1: the sketch just drawn, nothing selected, Extruded
    # Boss -> click the front region in 3D -> OK
    win.builder.active_tree().select_nodes([])
    win._apply_operation("linear_extrude")
    QApplication.processEvents()
    assert win.view3d._pick_cb is not None, "no region pick started"
    _click_world(win, (30, 10, 0))
    _ok(win)
    exts = [n for n in win.model.root.walk() if n.type == "linear_extrude"]
    assert len(exts) == 1
    win.model.set_param(exts[0], "height", 10)
    drag_feature.stop(win) if hasattr(drag_feature, "stop") else None
    QTest.qWait(50)
    assert _volume(win) == pytest.approx(60 * 20 * 10, rel=0.02)
    # Boss-Extrude2: nothing selected, Extruded Boss -> the toggle bar ->
    # click the back region of the extruded sketch -> it is picked -> OK
    win.builder.active_tree().select_nodes([])
    win.view3d.cancel_pick()
    QApplication.processEvents()
    win._apply_operation("linear_extrude")
    QApplication.processEvents()
    assert win.view3d._pick_cb is not None, "no toggle bar pick"
    _click_world(win, (30, 30, 0))
    for _ in range(5):
        QApplication.processEvents()
    _ok(win)
    exts = [n for n in win.model.root.walk() if n.type == "linear_extrude"]
    assert len(exts) == 2
    new = next(e for e in exts if e is not exts[0] or True
               if any(r.type == "regions" and r.params.get("sketch_of")
                      for r in e.walk()))
    win.model.set_param(new, "height", 35)
    QTest.qWait(50)
    assert _volume(win) == pytest.approx(60 * 20 * 45, rel=0.02)
    assert _bounds(win) == pytest.approx((0, 40, 0, 35), abs=0.1)


def _block_and_leg(win):
    """Exercise 53's plate, arm and wall, and on the plate's side face
    (x = 45) its leg: a closed profile of lines hanging below, its top
    line ON the plate's bottom edge, the right side flaring into it with
    a sketch fillet R25 (an arc) under the arm and the wall."""
    import math
    from khervecad import refgeom_ui, sketch_corner
    from khervecad.mcp_tools import McpToolExecutor
    McpToolExecutor(win).execute("apply_code", {"code": (
        "union() { translate([-45, -28, 0]) cube([90, 40, 10]); "
        "translate([45, 12, 0]) cube([24, 38, 10]); "
        "translate([25, 25, 0]) cube([20, 25, 35]); }\n")})
    QApplication.processEvents()
    group = refgeom_ui.sketch_on(win, origin=(45, 0, 0), normal=(1, 0, 0),
                                 label="Sketch", open_2d=False)
    m = win.model

    def tangent(E, side):
        c, r = (0, -56), 19
        dx, dy = E[0] - c[0], E[1] - c[1]
        a, b = math.atan2(dy, dx), math.acos(r / math.hypot(dx, dy))
        pts = [(c[0] + r * math.cos(a + s * b),
                c[1] + r * math.sin(a + s * b)) for s in (-1, 1)]
        return min(pts, key=lambda p: -side * p[0])

    def line(a, b):
        return m.add_node("line", dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1],
                                       width=0.2), parent=group)
    m.add_node("circle", dict(x=0, y=-56, radius=19), parent=group)
    line((-28, 0), (52.7034, 0))
    line((-28, 0), tangent((-28, 0), -1))
    slant = line((33, 0), tangent((33, 0), 1))
    rest = line((33, 0), (60, 0))
    sketch_corner.corner(m, slant, rest, 25)
    rest.parent.remove(rest)
    m.structure_changed.emit()
    QApplication.processEvents()
    return group


def _leg_edges(win):
    """The block's bottom near the leg: True when some edge lies a hair
    below it (the leg's top 0.05 mm under the block — a gap)."""
    from khervecad import mesh
    zs = {round(p[2], 4) for t in mesh.tessellate(win.model.root)
          for p in t}
    return sorted(z for z in zs if abs(z + 0.05) < 0.004)


def test_by_mouse_a_profile_closed_by_its_own_lines_meets_the_part(win):
    """Picked in 3D with the part beside it, the leg came out with its
    top 0.05 mm below the block where the part's grown outline split the
    area — a gap no fillet could cross (Exercise 53's Fillet2)."""
    from khervecad import sketch_regions
    group = _block_and_leg(win)
    win.builder.active_tree().select_nodes([])
    win.view3d.fit()
    QApplication.processEvents()
    assert sketch_regions.start_3d(win, group)
    _click_world(win, (45, 0, -20))
    _ok(win)
    ext = next(n for n in win.model.root.walk()
               if n.type == "linear_extrude")
    win.model.set_param(ext, "height", 10)
    win.model.set_param(ext, "reverse", True)
    QTest.qWait(50)
    assert _leg_edges(win) == []
    from khervecad import mesh
    ys = [p[1] for t in mesh.tessellate(win.model.root) for p in t]
    assert min(ys) == pytest.approx(-28, abs=1e-6)


def test_mcp_a_profile_closed_by_its_own_lines_meets_the_part(win):
    from khervecad.mcp_tools import McpToolExecutor
    group = _block_and_leg(win)
    out = McpToolExecutor(win).execute("sketch_feature", {
        "node_id": group.id, "depth": 10, "reverse": True,
        "regions": [[0, -20]]})
    assert "error" not in out, out
    QTest.qWait(50)
    assert _leg_edges(win) == []
    from khervecad import mesh
    ys = [p[1] for t in mesh.tessellate(win.model.root) for p in t]
    assert min(ys) == pytest.approx(-28, abs=1e-6)
