"""SolidWorks' Mirror about a MAIN plane mirrors about the PART's plane,
whatever frame the mirrored node lives in (2026-11-13, the user's
Exercise 10: Boss-Extrude 3, sketched on the right face — inside a
translate + rotate frame and a reverse-direction mirror — mirrored about
the Right plane came out on top of itself).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import mesh, mirror_feature
from khervecad.mainwindow import MainWindow
from khervecad.mcp_tools import McpToolExecutor

# a block, and a boss on its right face (x = 60) extruded back into it,
# written the way a face sketch + Reverse direction writes it
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
    w = MainWindow()
    McpToolExecutor(w).execute("apply_code", {"code": PART})
    yield w
    w._dirty = False
    w.close()


@pytest.mark.parametrize("plane, check", [
    ("Right Plane (YZ)", "x"),
    ("Front Plane (XZ)", "y"),
])
def test_a_main_plane_is_the_parts_plane(win, plane, check):
    ext = next(n for n in win.model.root.walk()
               if n.type == "linear_extrude")
    win.mirror_plane_hook = lambda: plane
    node = mirror_feature._finish(win, [ext])
    assert node is not None and node.type == "symmetry"
    tris = mesh.tessellate(win.model.root)
    pts = [p for t in tris for p in t[:3]]
    if check == "x":
        # the original boss stands at x 40..60; its copy at -60..-40
        assert min(p[0] for p in pts) == pytest.approx(-60, abs=1e-6)
        assert any(-60 - 1e-6 <= p[0] <= -40 + 1e-6 and p[2] > 15 + 1e-6
                   for p in pts)
    else:
        # the boss spans y -10..10 already: about the Front plane its
        # mirror is itself, so nothing reaches past it
        assert max(abs(p[1]) for p in pts if p[2] > 15 + 1e-6) == \
            pytest.approx(10, abs=1e-6)


def test_the_copy_is_not_the_original(win):
    """Before the fix the plane was the boss's own centre plane."""
    ext = next(n for n in win.model.root.walk()
               if n.type == "linear_extrude")
    win.mirror_plane_hook = lambda: "Right Plane (YZ)"
    mirror_feature._finish(win, [ext])
    pts = [p for t in mesh.tessellate(win.model.root) for p in t[:3]
           if p[2] > 15 + 1e-6]
    assert min(p[0] for p in pts) < -39 and max(p[0] for p in pts) > 59
