"""Mass properties of overlapping parts count the shared volume ONCE
(2026-11-14, a SolidWorks exercise: a tube standing on an arm read
30 000 mm³ heavy — the two solids were summed).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtTest import QTest

from test_lever_by_mouse import win  # noqa: F401


def test_two_overlapping_cubes_weigh_their_union(win):
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(win)
    ex.execute("apply_code", {"code": "cube(10);\n"
                              "translate([5, 0, 0]) cube(10);\n"})
    QTest.qWait(50)
    m = ex.execute("mass_properties", {})
    assert m["volume"] == pytest.approx(1500, rel=1e-3)
    assert m["centre_of_mass"][0] == pytest.approx(7.5, abs=0.01)


def test_list_edges_finds_where_two_overlapping_parts_meet(win):
    """The fillet unites its parts before rounding, so list_edges must
    too: the inside corner where a rib meets a boss is an edge to pick."""
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(win)
    ex.execute("apply_code", {"code": "union() { cube([40, 40, 10]);\n"
                              "translate([10, 10, 5]) cube([20, 20, 20]); }\n"})
    QTest.qWait(50)
    u = next(n for n in win.model.root.walk() if n.type == "union")
    r = ex.execute("list_edges", {"node_id": u.id})
    inside = [e for e in r["edges"] if not e["convex"]
              and abs(e["centre"][2] - 10) < 0.01]
    assert inside, "no concave edge where the block stands on the plate"
