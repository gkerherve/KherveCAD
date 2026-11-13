"""Undo / redo while a region pick or the Boss / Cut toggle bar is up
(2026-11-13, the user: numbered regions stayed on an empty 3D view after
an undo). Both held the OLD tree: the pick ends, the bar comes back on
the new one.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import feature_pick, region_show, sketch_regions
from khervecad.mainwindow import MainWindow
from khervecad.mcp_tools import McpToolExecutor


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _pump(app, n=10):
    for _ in range(n):
        app.processEvents()


def _fresh(win):
    win.model.undo_stack.clear()
    win.model._last_state = win.model._serialize()


@pytest.fixture
def win(app):
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    _pump(app)
    yield w
    w._dirty = False
    w.close()


def test_undo_ends_a_region_pick_without_extruding(app, win):
    ex = McpToolExecutor(win)
    ex.execute("apply_code", {"code": "union() { square([40, 20]); "
                              "translate([20, 20]) circle(r=15); }\n"})
    _pump(app)
    _fresh(win)
    ex.execute("apply_code", {"code": "translate([0, 60]) "
                              "square([10, 10]);\n"})
    _pump(app)
    cont = next(n for n in win.model.root.walk() if n.type == "union")
    assert sketch_regions.start_3d(win, cont, window_at_once=True)
    _pump(app)
    view = win.view3d
    assert win._region_show and view._pick_cb is not None
    win.model.undo_stack.undo()
    _pump(app)
    assert getattr(win, "_region_show", None) is None
    assert view._pick_cb is None
    assert getattr(win, "_region_panel", None) is None
    assert not view.pick_lines
    # nothing was extruded into the gone sketch, and redo is clean too
    assert not any(n.type in ("linear_extrude", "regions")
                   for n in win.model.root.walk())
    win.model.undo_stack.redo()
    _pump(app)
    assert getattr(win, "_region_show", None) is None
    assert view._pick_cb is None


def test_stale_regions_are_never_painted(app, win):
    """Even if a path forgot to stop it: regions of another tree."""
    region_show.start(win, [([[(0, 0, 0), (1, 0, 0), (0, 1, 0)]],
                              (0.3, 0.3, 0), 1)])
    win.model.root = win.model.root.__class__("union", name="Root")
    painted = []
    region_show.paint(win, None, lambda p: painted.append(p) or (0, 0))
    assert not painted and win._region_show is None


def test_undo_brings_the_toggle_bar_back_on_the_new_tree(app, win):
    ex = McpToolExecutor(win)
    ex.execute("apply_code", {"code": "cube([30, 20, 10]); // Block\n"})
    _pump(app)
    _fresh(win)
    ex.execute("apply_code", {"code": "translate([50, 0, 0]) cube(5); "
                              "// Small\n"})
    _pump(app)
    feature_pick.start(win, "extruded_boss")
    _pump(app)
    before = win._feature_pick
    count = len(before["parts"])
    try:
        win.model.undo_stack.undo()
        _pump(app, 20)
        after = win._feature_pick
        assert after is not None and after is not before
        assert len(after["parts"]) == count - 1
        assert win.view3d._pick_cb is not None
    finally:
        feature_pick.stop(win)
