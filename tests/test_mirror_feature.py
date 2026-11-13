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
    key = mirror_feature._BY_NAME[plane]
    made = mirror_feature.mirror(win, [ext], ("main", key))
    assert len(made) == 1
    node = made[0]
    assert node.type == "symmetry"
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
    mirror_feature.mirror(win, [ext], ("main", "Side (YZ)"))
    pts = [p for t in mesh.tessellate(win.model.root) for p in t[:3]
           if p[2] > 15 + 1e-6]
    assert min(p[0] for p in pts) < -39 and max(p[0] for p in pts) > 59


# ------------------------------------------------ the Mirror window
@pytest.fixture
def shown(app):
    from PyQt5.QtCore import QSettings
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


def _plane_item(tree, plane):
    from khervecad import tree_history
    for i in range(tree.topLevelItemCount()):
        item = tree.topLevelItem(i)
        if item.data(0, tree_history.ROLE_FIXED) == "plane:" + plane:
            return item
    return None


def test_nothing_selected_opens_the_window_and_the_tree_fills_it(shown):
    """No menu at the cursor: the window, box 1 from a tree row, box 2
    from the Right Plane row at the top of the tree, then OK."""
    from khervecad import tree_history
    win = shown
    tree = win.builder.active_tree()
    tree.clearSelection()
    panel = mirror_feature.start(win)
    assert panel is not None and panel.isVisible()
    st = win._mirror_state
    assert st["active"] == "nodes" and not panel.ok.isEnabled()
    assert win.view3d._pick_cb is not None          # parts clickable
    ext = next(n for n in win.model.root.walk()
               if n.type == "linear_extrude")
    tree.select_nodes([ext])
    assert st["nodes"] == [ext]
    assert st["active"] == "plane"                  # on to the plane
    assert win._plane_pick and win._plane_pick.get("mirror")
    item = _plane_item(tree, "Side (YZ)")
    assert item is not None
    tree_history.clicked(tree, item)
    assert st["plane"] == ("main", "Side (YZ)")
    assert "Right Plane" in panel.boxes["plane"].body.text()
    assert panel.ok.isEnabled()
    panel.ok.click()
    assert getattr(win, "_mirror_state", None) is None
    assert win.view3d._pick_cb is None and not win._plane_pick
    sym = next(n for n in win.model.root.walk() if n.type == "symmetry")
    assert ext.parent is sym
    pts = [p for t in mesh.tessellate(win.model.root) for p in t[:3]
           if p[2] > 15 + 1e-6]
    assert min(p[0] for p in pts) == pytest.approx(-60, abs=1e-6)


def test_a_plane_clicked_in_3d_is_the_mirror_plane(shown):
    win = shown
    ext = next(n for n in win.model.root.walk()
               if n.type == "linear_extrude")
    win.builder.active_tree().select_nodes([ext])
    panel = mirror_feature.start(win)
    st = win._mirror_state
    assert st["nodes"] == [ext] and st["active"] == "plane"
    # where the Top plane shows on screen, off the part: the pick callback
    # is told of empty space at a point inside the Top plane's square
    from khervecad import plane_pick
    view = win.view3d
    view.repaint()
    polys = win._plane_pick.get("polys") or []
    pos = None
    for plane, _n, poly in polys:
        if plane == "Top (XY)":
            r = poly.boundingRect()
            from PyQt5.QtCore import QPoint
            for fx in (0.08, 0.92, 0.5):
                for fy in (0.08, 0.92, 0.5):
                    q = QPoint(int(r.x() + r.width() * fx),
                               int(r.y() + r.height() * fy))
                    if plane_pick.hit(win, q) == "Top (XY)":
                        pos = q
                        break
                if pos is not None:
                    break
    assert pos is not None
    st["pos"] = pos
    view._pick_cb(None, None)
    assert st["plane"] == ("main", "Top (XY)")
    assert win._plane_pick.get("chosen") == "Top (XY)"
    mirror_feature.cancel(win)
    assert not any(n.type == "symmetry" for n in win.model.root.walk())


def test_esc_cancels_and_leaves_nothing(shown):
    win = shown
    win.builder.active_tree().clearSelection()
    mirror_feature.start(win)
    win.view3d.cancel_pick()                         # what Esc does
    assert getattr(win, "_mirror_state", None) is None
    assert getattr(win, "_mirror_panel", None) is None
    assert not any(n.type == "symmetry" for n in win.model.root.walk())
