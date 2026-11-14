"""A concave fillet larger than the face it rolls onto stops at the
part's edge, as SolidWorks' does (2026-11-14, Exercise 52: the rib's
R32 foot on a base only 28 mm wider than the rib stood 4 mm out past
the base, the part 88 wide instead of 84).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtTest import QTest

from test_lever_by_mouse import win  # noqa: F401

CODE = ("cube([40, 20, 10]); // Base\n"
        "translate([0, 0, 10]) cube([30, 20, 30]); // Wall\n")


def test_a_concave_fillet_stays_on_the_part(win):
    from khervecad import mesh
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(win)
    ex.execute("apply_code", {"code": CODE})
    QTest.qWait(50)
    top = [c for c in win.model.root.children if c.visible]
    body = top[0] if len(top) == 1 else win.model.wrap_nodes(top, "union")
    edges = ex.execute("list_edges", {"node_id": body.id})["edges"]
    foot = [e["index"] for e in edges if not e["convex"]
            and abs(e["centre"][0] - 30) < 0.5
            and abs(e["centre"][2] - 10) < 0.5]
    assert foot
    out = ex.execute("fillet_edges", {"node_id": body.id, "chains": foot,
                                      "radius": 15})
    assert "error" not in out, out
    QTest.qWait(50)
    xs = [p[0] for t in mesh.tessellate(win.model.root) for p in t[:3]]
    assert max(xs) == pytest.approx(40, abs=0.05)


def test_the_cut_back_fillet_is_still_a_solid(win):
    """A Difference after it must still cut (Exercise 52's side hole)."""
    from khervecad import csg, mesh
    test_a_concave_fillet_stays_on_the_part(win)
    fil = next(n for n in win.model.root.walk() if n.type == "fillet")
    rows = mesh._tess(fil, {}, None, set(), False)
    assert csg.to_manifold(rows, {}) is not None
