"""MCP sketch_feature (2026-11-14, Exercise 6's problem 3): an assistant
makes Extruded Boss / Cut from a sketch the ribbon's way — the AREA the
lines close, a circle inside it a hole.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest
from PyQt5.QtTest import QTest

from test_lever_by_mouse import win  # noqa: F401
from test_rib import _volume


def _sketch(win, z=0.0):
    from khervecad import refgeom_ui
    return refgeom_ui.sketch_on(win, origin=(0, 0, z), normal=(0, 0, 1),
                                label="Sketch", open_2d=False)


def _square_of_lines_round_a_hole(win, group):
    m = win.model
    pts = [(0, 0), (40, 0), (40, 40), (0, 40)]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        m.add_node("line", dict(x1=x1, y1=y1, x2=x2, y2=y2, width=0.2),
                   parent=group)
    m.add_node("circle", dict(x=20, y=20, radius=8), parent=group)


def test_a_boss_of_lines_round_a_circle_has_its_hole(win):
    from khervecad.mcp_tools import McpToolExecutor
    group = _sketch(win)
    _square_of_lines_round_a_hole(win, group)
    out = McpToolExecutor(win).execute(
        "sketch_feature", {"node_id": group.id, "depth": 5})
    assert "error" not in out, out
    QTest.qWait(50)
    assert _volume(win) == pytest.approx(
        (1600 - math.pi * 64) * 5, rel=0.02)


def test_a_cut_through_all_goes_through_the_part(win):
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(win)
    ex.execute("apply_code", {"code": "cube([40, 40, 20]); // Block\n"})
    QTest.qWait(50)
    part = next(n for n in win.model.root.walk() if n.type == "cube")
    group = _sketch(win, z=20)
    win.model.add_node("rect", dict(x=10, y=10, width=10, height=10),
                       parent=group)
    out = ex.execute("sketch_feature", {
        "node_id": group.id, "kind": "extruded_cut", "through_all": True,
        "part_id": part.id})
    assert "error" not in out, out
    QTest.qWait(50)
    assert _volume(win) == pytest.approx(40 * 40 * 20 - 100 * 20, rel=0.02)


def test_a_bad_kind_is_refused(win):
    from khervecad.mcp_tools import McpToolExecutor
    group = _sketch(win)
    out = McpToolExecutor(win).execute(
        "sketch_feature", {"node_id": group.id, "kind": "melt"})
    assert "error" in out


def test_mirror_feature_mirrors_a_rib_about_the_right_plane(win):
    """A rib made in a turned plane sketch, mirrored about the Right
    Plane by MCP, lands on the other side (a plain symmetry wrap
    mirrored it in the sketch's own frame)."""
    from khervecad.mcp_tools import McpToolExecutor
    from test_rib import CODE, _rib_sketch
    ex = McpToolExecutor(win)
    ex.execute("apply_code", {"code": CODE})
    QTest.qWait(50)
    rib = ex.execute("rib", {"node_id": _rib_sketch(win).id})
    out = ex.execute("mirror_feature", {"node_ids": [rib["rib_id"]],
                                        "plane": "Right"})
    assert "error" not in out, out
    QTest.qWait(50)
    from khervecad import mesh
    xs = [p[0] for t in mesh.tessellate(win.model.root) for p in t[:3]]
    assert min(xs) == pytest.approx(-40, abs=0.5)   # the copy, x -40..0
    assert max(xs) == pytest.approx(60, abs=0.5)    # the part as it was


def test_a_cut_into_an_extruded_boss_leaves_the_boss_alone(win):
    """Exercise 6's base: a 160 deep boss, then a groove Through All —
    the depth went onto the BOSS's extrude (22 mm) instead of the cut."""
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(win)
    s = _sketch(win)
    win.model.add_node("rect", dict(x=0, y=0, width=40, height=40),
                       parent=s)
    boss = ex.execute("sketch_feature", {"node_id": s.id, "depth": 30})
    s2 = _sketch(win, z=30)
    win.model.add_node("rect", dict(x=10, y=10, width=10, height=10),
                       parent=s2)
    out = ex.execute("sketch_feature", {
        "node_id": s2.id, "kind": "extruded_cut", "through_all": True,
        "part_id": boss["feature_id"]})
    assert "error" not in out, out
    QTest.qWait(50)
    assert _volume(win) == pytest.approx(40 * 40 * 30 - 100 * 30, rel=0.02)


def test_one_line_cuts_the_corner_it_closes_with_the_face_edges(win):
    """Exercise 51's Cut-Extrude2: ONE line from a face's side to its
    top edge closes a triangle with the face's edges (SolidWorks' "close
    with model edges"). By MCP the line was extruded as a 0.2 mm strip."""
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(win)
    s = _sketch(win)
    win.model.add_node("rect", dict(x=0, y=0, width=40, height=40),
                       parent=s)
    boss = ex.execute("sketch_feature", {"node_id": s.id, "depth": 30})
    s2 = _sketch(win, z=30)
    win.model.add_node("line", dict(x1=0, y1=20, x2=20, y2=40, width=0.2),
                       parent=s2)
    out = ex.execute("sketch_feature", {
        "node_id": s2.id, "kind": "extruded_cut", "depth": 10,
        "part_id": boss["feature_id"]})
    assert "error" not in out, out
    QTest.qWait(50)
    # the smaller of the two areas, as the ribbon takes it
    assert _volume(win) == pytest.approx(40 * 40 * 30 - 200 * 10, rel=0.01)


def test_region_picks_which_area_a_line_closes(win):
    """`region` (a point in the sketch) chooses the other area."""
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(win)
    s = _sketch(win)
    win.model.add_node("rect", dict(x=0, y=0, width=40, height=40),
                       parent=s)
    boss = ex.execute("sketch_feature", {"node_id": s.id, "depth": 30})
    s2 = _sketch(win, z=30)
    win.model.add_node("line", dict(x1=0, y1=20, x2=20, y2=40, width=0.2),
                       parent=s2)
    out = ex.execute("sketch_feature", {
        "node_id": s2.id, "kind": "extruded_cut", "depth": 10,
        "region": [30, 10], "part_id": boss["feature_id"]})
    assert "error" not in out, out
    QTest.qWait(50)
    assert _volume(win) == pytest.approx(40 * 40 * 30 - 1400 * 10, rel=0.01)
