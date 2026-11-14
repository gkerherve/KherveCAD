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
