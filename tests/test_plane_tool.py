"""SolidWorks' Plane window (2026-11-13, the user: "click on a face or a
plane or somewhere on the things, and it creates the plane ... as easy as
Extruded Boss"): the plane from up to three references, shown, then OK.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QApplication

from khervecad import plane_tool as pt
from khervecad.mainwindow import MainWindow
from khervecad.mcp_tools import McpToolExecutor


def P(o, n, text="P"):
    return dict(kind="plane", point=list(o), dir=list(n), text=text)


def L(o, d, text="L"):
    return dict(kind="line", point=list(o), dir=list(d), text=text)


def Q(o, text="Q"):
    return dict(kind="point", point=list(o), text=text)


def _on(o, n, p):
    """Is point p on the plane (o, n)?"""
    return abs(sum((p[i] - o[i]) * n[i] for i in range(3))) < 1e-6


def test_one_face_is_an_offset():
    o, n, text = pt.compute([P((0, 0, 15), (0, 0, 1), "Top face")], 10)
    assert o == pytest.approx([0, 0, 25]) and n == pytest.approx([0, 0, 1])
    assert "Offset 10" in text
    o, _n, _t = pt.compute([P((0, 0, 15), (0, 0, 1))], 10, flip=True)
    assert o[2] == pytest.approx(5)


def test_two_parallel_faces_give_the_mid_plane():
    o, n, text = pt.compute([P((0, 0, 0), (0, 0, -1)),
                             P((5, 3, 20), (0, 0, 1))])
    assert o[2] == pytest.approx(10) and abs(n[2]) == pytest.approx(1)
    assert text.startswith("Mid-plane")


def test_two_faces_at_an_angle_are_bisected():
    # a block's top (+Z) and right (+X) faces meet along x = 10, z = 5:
    # the bisector is the 45° plane through that edge
    o, n, _t = pt.compute([P((5, 0, 5), (0, 0, 1)),
                           P((10, 0, 2), (1, 0, 0))])
    assert _on(o, n, (10, 0, 5)) and _on(o, n, (10, 7, 5))
    assert abs(n[0]) == pytest.approx(abs(n[2])) and n[1] == pytest.approx(0)


def test_a_face_and_an_edge_on_it_make_a_plane_at_the_angle():
    o, n, text = pt.compute([P((0, 0, 0), (0, 0, 1)),
                             L((0, 0, 0), (1, 0, 0), "Edge")], angle=90)
    assert _on(o, n, (0, 0, 0)) and _on(o, n, (7, 0, 0))
    assert abs(n[1]) == pytest.approx(1)             # standing up
    assert "90°" in text


def test_face_and_point_line_and_point_points():
    o, n, _t = pt.compute([P((0, 0, 0), (0, 0, 1)), Q((3, 4, 12))])
    assert o == pytest.approx([3, 4, 12]) and n == pytest.approx([0, 0, 1])
    o, n, _t = pt.compute([L((0, 0, 0), (0, 0, 1))])
    assert n == pytest.approx([0, 0, 1])             # square to the edge
    o, n, _t = pt.compute([L((0, 0, 0), (1, 0, 0)), Q((0, 5, 0))])
    assert abs(n[2]) == pytest.approx(1)
    o, n, _t = pt.compute([Q((0, 0, 0)), Q((10, 0, 0)), Q((0, 10, 0))])
    assert abs(n[2]) == pytest.approx(1)
    o, n, _t = pt.compute([Q((0, 0, 0)), Q((0, 0, 20))])
    assert o == pytest.approx([0, 0, 10]) and abs(n[2]) == pytest.approx(1)
    assert pt.compute([Q((0, 0, 0))])[0] is None     # a point alone


# ----------------------------------------------------------- the window
@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app):
    QSettings("Kherve", "KherveCAD").setValue("tree/planes", True)
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    McpToolExecutor(w).execute(
        "apply_code", {"code": "cube([40, 30, 20]); // Block\n"})
    for _ in range(5):
        app.processEvents()
    yield w
    QSettings("Kherve", "KherveCAD").setValue("tree/planes", False)
    w._dirty = False
    w.close()


def _planes(win):
    return [n for n in win.model.root.walk() if n.type == "ref_plane"]


def test_top_plane_row_then_ok_adds_an_offset_plane(win):
    from khervecad import tree_history
    tree = win.builder.active_tree()
    tree.clearSelection()
    panel = pt.start(win)
    assert panel.isVisible() and not panel.ok.isEnabled()
    assert win.view3d._pick_cb is not None           # clicks in 3D
    item = next(tree.topLevelItem(i) for i in range(tree.topLevelItemCount())
                if tree.topLevelItem(i).data(0, tree_history.ROLE_FIXED)
                == "plane:Top (XY)")
    tree_history.clicked(tree, item)
    st = win._plane_tool
    assert st["refs"][0]["text"] == "Top Plane"
    assert panel.ok.isEnabled() and st["active"] == "ref2"
    panel.fields["distance"].setValue(35.0)
    panel.ok.click()
    planes = _planes(win)
    assert len(planes) == 1
    p = planes[0].params
    assert (p["z"], p["nz"]) == (pytest.approx(35), pytest.approx(1))
    assert getattr(win, "_plane_tool", None) is None


def test_a_face_clicked_and_a_corner(win):
    panel = pt.start(win)
    # the block's top face, clicked
    win.view3d._pick_cb(dict(kind="face", pos=(20, 15, 20), dir=(0, 0, 1),
                             point=(12, 9, 20)), None)
    st = win._plane_tool
    assert st["refs"][0]["kind"] == "plane"
    # an edge clicked near its end: that corner, a point
    win.view3d._pick_cb(dict(kind="edge", seg=((0, 0, 0), (40, 0, 0)),
                             pos=(0.05, 0, 0), point=(0.05, 0, 0)), None)
    assert st["refs"][1]["kind"] == "point"
    assert st["refs"][1]["point"] == pytest.approx([0, 0, 0])
    # top face + the origin corner: parallel to the top through z = 0
    assert st["result"][0] == pytest.approx([0, 0, 0])
    panel.ok.click()
    assert _planes(win)[0].params["nz"] == pytest.approx(1)


def test_esc_adds_nothing(win):
    pt.start(win)
    win.view3d.cancel_pick()                         # what Esc does
    assert getattr(win, "_plane_tool", None) is None
    assert not _planes(win)


def test_the_round_face_of_a_cylinder_is_its_axis(win):
    from khervecad import mesh, scadparse
    tris = mesh.tessellate(scadparse.parse_scad(
        "translate([30, 5, 0]) cylinder(r = 8, h = 10, $fn = 48);")[0])
    side = [t for t in tris if abs(t[0][2] - t[1][2]) > 1e-6 or
            abs(t[1][2] - t[2][2]) > 1e-6]
    seed = tuple(sum(p[i] for p in side[0][:3]) / 3 for i in range(3))
    ref = pt._ref_of_pick(win, dict(kind="face", pos=seed, dir=(1, 0, 0)),
                          tris)
    assert ref["kind"] == "line" and abs(ref["dir"][2]) == \
        pytest.approx(1, abs=1e-3)
    assert math.hypot(ref["point"][0] - 30, ref["point"][1] - 5) < 0.05
