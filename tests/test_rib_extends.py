"""A rib line that stops short of the part is EXTENDED to it, as
SolidWorks' Rib does (2026-11-14, Exercise 52: the bracket's rib line
ends 2 mm under the bearing; SolidWorks runs it on to the bearing, here
it was refused — "the line closes no area").

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

#: a base, a wall at its left end and a shelf over the base
CODE = ("cube([60, 40, 10]); // Base\n"
        "translate([0, 0, 10]) cube([10, 40, 40]); // Wall\n"
        "translate([0, 0, 50]) cube([40, 40, 10]); // Shelf\n")


def test_a_rib_line_short_of_the_part_runs_on_to_it(win):
    from khervecad import face_sketch, refgeom_ui
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(win)
    ex.execute("apply_code", {"code": CODE})
    QTest.qWait(50)
    before = _volume(win)
    group = refgeom_ui.sketch_on(win, origin=(0, 20, 0), normal=(0, 1, 0),
                                 label="Rib plane", open_2d=False)
    a = face_sketch.to_local(group, (30, 20, 48))     # 2 under the shelf
    b = face_sketch.to_local(group, (30, 20, 10))     # on the base
    win.model.add_node("line", dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1],
                                    width=0.2), parent=group)
    out = ex.execute("rib", {"node_id": group.id, "thickness": 10})
    assert "error" not in out, out
    QTest.qWait(50)
    # x 10..30 between the wall and the line, z 10..50 base to shelf
    assert _volume(win) - before == pytest.approx(20 * 40 * 10, rel=0.03)
