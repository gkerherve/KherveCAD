"""MCP pattern_feature and a mid-plane between two faces (2026-11-14,
the pattern exercise ogsBu7TcfDI): the video makes three lugs with a
Circular Pattern about the cylinder's axis, a plane halfway between the
top and bottom faces, a row of slots with a Linear Pattern — an
assistant had no tool for any of the three.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtTest import QTest

from test_lever_by_mouse import win  # noqa: F401
from test_rib import _volume


def _boss(ex):
    ex.execute("apply_code", {
        "code": "translate([40, 0, 0]) cube([10, 10, 10]); // Lug\n"})
    QTest.qWait(50)


def _lug(win):
    return next(n for n in win.model.root.walk() if n.type == "cube")


def test_a_circular_pattern_makes_three_lugs(win):
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(win)
    _boss(ex)
    out = ex.execute("pattern_feature", {
        "kind": "circular", "node_ids": [_lug(win).id], "count": 3,
        "axis": [0, 0, 1], "centre": [0, 0, 0]})
    assert "error" not in out, out
    QTest.qWait(50)
    assert _volume(win) == pytest.approx(3000, rel=0.01)
    node = next(n for n in win.model.root.walk()
                if n.id == out["pattern_ids"][0])
    assert node.params["kind"] == "polar" and node.params["count"] == 3


def test_a_linear_pattern_makes_a_row(win):
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(win)
    _boss(ex)
    out = ex.execute("pattern_feature", {
        "kind": "linear", "node_ids": [_lug(win).id], "count": 7,
        "direction": [1, 0, 0], "spacing": 20})
    assert "error" not in out, out
    QTest.qWait(50)
    assert _volume(win) == pytest.approx(7000, rel=0.01)


def test_a_circular_pattern_of_a_cut_copies_the_hole(win):
    """The cut feature sketch_feature returns (its Difference) patterns
    as its HOLE, not as three copies of the holed part."""
    from khervecad import refgeom_ui
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(win)
    ex.execute("apply_code", {"code": "cube([100, 100, 10], center = true);"
                                      " // Plate\n"})
    QTest.qWait(50)
    plate = next(n for n in win.model.root.walk() if n.type == "cube")
    g = refgeom_ui.sketch_on(win, origin=(0, 0, 5), normal=(0, 0, 1),
                             label="Sketch", open_2d=False)
    win.model.add_node("circle", dict(x=30, y=0, radius=5), parent=g)
    cut = ex.execute("sketch_feature", {
        "node_id": g.id, "kind": "extruded_cut", "through_all": True,
        "part_id": plate.id})
    assert "error" not in cut, cut
    out = ex.execute("pattern_feature", {
        "kind": "circular", "node_ids": [cut["feature_id"]], "count": 3})
    assert "error" not in out, out
    QTest.qWait(50)
    hole = 3.14159 * 25 * 10
    assert _volume(win) == pytest.approx(100000 - 3 * hole, rel=0.01)


def test_a_plane_halfway_between_two_faces(win):
    from khervecad.mcp_tools import McpToolExecutor
    out = McpToolExecutor(win).execute("reference_geometry", {
        "action": "plane", "faces": [[0, 0, 225, 0, 0, 1],
                                     [5, 3, 0, 0, 0, -1]]})
    assert "error" not in out, out
    assert out["origin"][2] == pytest.approx(112.5)
    assert abs(out["direction"][2]) == pytest.approx(1.0)
