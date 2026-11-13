"""SolidWorks' Circular / Linear Pattern windows (2026-11-13, the user:
"as nice as the circular sketch pattern ... select in the tree the part,
the Extruded Boss or the Extruded Cut, and make it circular through a
point").

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

from khervecad import mesh, pattern_feature as pf, scadparse
from khervecad.mainwindow import MainWindow
from khervecad.mcp_tools import McpToolExecutor

# a plate, and a boss on its right side (x = 60) sketched in a turned
# frame, the way a face sketch writes it
PART = """
translate([-60, -40, 0]) cube([120, 80, 15]); // Block
translate([60, 0, 0]) rotate([90, 0, 90]) union() {
    mirror([0, 0, 1]) {
        linear_extrude(height = 20) translate([-10, 0]) square([20, 30]);
    }
}
"""


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app):
    QSettings("Kherve", "KherveCAD").setValue("tree/planes", True)
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    McpToolExecutor(w).execute("apply_code", {"code": PART})
    for _ in range(5):
        app.processEvents()
    yield w
    QSettings("Kherve", "KherveCAD").setValue("tree/planes", False)
    w._dirty = False
    w.close()


def _boss(win):
    return next(n for n in win.model.root.walk()
                if n.type == "linear_extrude")


def _bounds(win, z_above=15.0):
    pts = [p for t in mesh.tessellate(win.model.root) for p in t[:3]
           if p[2] > z_above + 1e-6]
    return [(min(p[i] for p in pts), max(p[i] for p in pts))
            for i in range(3)]


def test_circular_about_z_through_the_origin(win):
    ext = _boss(win)
    win.builder.active_tree().select_nodes([ext])
    panel = pf.start(win, pf.CIRCULAR)
    st = win._pattern_state
    assert panel.isVisible() and st["nodes"] == [ext]
    assert st["active"] == "axis"                   # on to the axis
    assert st["made"] and panel.ok.isEnabled()      # copies show at once
    panel.ok.click()
    assert getattr(win, "_pattern_state", None) is None
    pat = next(n for n in win.model.root.walk() if n.type == "pattern")
    assert pat.params["kind"] == "polar" and pat.params["count"] == 4
    (x0, x1), (y0, y1), _z = _bounds(win)
    # the boss (x 40..60) at 0, 90, 180, 270° about Z through the origin
    assert x0 == pytest.approx(-60, abs=1e-6) and x1 == pytest.approx(60)
    assert y0 == pytest.approx(-60, abs=1e-6) and y1 == pytest.approx(60)
    # OpenSCAD reads it back as the same pattern
    root, _w = scadparse.parse_scad(win.model.to_scad())
    again = next(n for n in root.walk() if n.type == "pattern")
    assert again.params["axis"] == "custom"


def test_axis_from_the_right_plane_row_and_a_typed_centre(win):
    from khervecad import tree_history
    ext = _boss(win)
    win.builder.active_tree().select_nodes([ext])
    panel = pf.start(win, pf.CIRCULAR)
    st = win._pattern_state
    pf.plane_row(win, "Top (XY)")                 # Top Plane: about Z
    assert st["axis"] == pytest.approx((0, 0, 1))
    panel.fields["cX"].setValue(50.0)             # through (50, 0, 0)
    panel.fields["count"].setValue(2)
    panel.ok.click()
    (x0, x1), _y, _z = _bounds(win)
    # 180° about the line x = 50: the boss (40..60) stays on 40..60
    assert x0 == pytest.approx(40, abs=1e-6) and x1 == pytest.approx(60)
    assert tree_history  # (imported for the row hook)


def test_cancel_leaves_nothing(win):
    ext = _boss(win)
    parent = ext.parent
    win.builder.active_tree().select_nodes([ext])
    panel = pf.start(win, pf.CIRCULAR)
    assert win._pattern_state["made"]
    panel.cancel.click()
    assert not any(n.type == "pattern" for n in win.model.root.walk())
    assert ext.parent is parent


def test_linear_with_a_second_direction_is_a_grid(win):
    ext = _boss(win)
    win.builder.active_tree().select_nodes([ext])
    panel = pf.start(win, pf.LINEAR)
    st = win._pattern_state
    assert st["active"] == "dir"
    pf.plane_row(win, "Front (XZ)")               # Front: along Y
    panel.fields["spacing"].setValue(25.0)
    panel.fields["count"].setValue(3)
    pf._activate(win, "dir2")
    pf.plane_row(win, "Top (XY)")                 # Top: up Z
    assert st["use2"]
    panel.fields["spacing2"].setValue(40.0)
    panel.fields["count2"].setValue(2)
    panel.ok.click()
    pats = [n for n in win.model.root.walk() if n.type == "pattern"]
    assert len(pats) == 2
    _x, (y0, y1), (z0, z1) = _bounds(win, z_above=-1.0)
    # rows along Y: -10 .. 10 + 2 * 25; levels up Z: 0 .. 30 + 40
    assert y1 == pytest.approx(60, abs=1e-6)
    assert z1 == pytest.approx(70, abs=1e-6)


def test_a_pattern_selected_opens_again_to_change_it(win):
    ext = _boss(win)
    win.builder.active_tree().select_nodes([ext])
    pf.start(win, pf.CIRCULAR).ok.click()
    pat = next(n for n in win.model.root.walk() if n.type == "pattern")
    win.builder.active_tree().select_nodes([pat])
    panel = pf.start(win, pf.CIRCULAR)
    st = win._pattern_state
    assert st.get("editing") and st["made"] == [pat]
    assert st["nodes"] == [ext]
    panel.fields["count"].setValue(6)
    panel.ok.click()
    assert pat.params["count"] == 6
    assert len([n for n in win.model.root.walk()
                if n.type == "pattern"]) == 1


def test_a_round_face_gives_its_axis(win):
    st = pf._defaults(pf.CIRCULAR)
    tris = mesh.tessellate(scadparse.parse_scad(
        "translate([30, 5, 0]) cylinder(r = 8, h = 10, $fn = 48);")[0])
    side = [t for t in tris if abs(t[0][2] - t[1][2]) > 1e-6 or
            abs(t[1][2] - t[2][2]) > 1e-6]
    a = side[0]
    seed = tuple(sum(p[i] for p in a[:3]) / 3 for i in range(3))
    pf._from_pick(win, st, dict(kind="face", pos=seed, dir=(1, 0, 0)),
                  tris)
    assert st["axis_text"] == "Round face's axis"
    assert abs(st["axis"][2]) == pytest.approx(1, abs=1e-3)
    assert st["centre"][0] == pytest.approx(30, abs=0.05)
    assert st["centre"][1] == pytest.approx(5, abs=0.05)
    assert math.isfinite(st["centre"][2])
