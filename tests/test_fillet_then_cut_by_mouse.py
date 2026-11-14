"""A cut after a Fillet still cuts (2026-11-14, Exercise 55, the control
bracket: Fillet R3 round the arm, then Cut-Extrude2 through the hub's back
— the bore never appeared). The fillet's preview welded the Manifold cut
at 0.05 mm, which opened the surface where the arm's edge runs tangent
into the hub; the next Difference then could not cut it.

The fillet is made by mouse (Fillet with nothing selected, a click on the
arm's edge in 3D, the radius typed in Properties), the cut by the tools.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest

from khervecad import analysis, mesh
from khervecad.mcp_tools import McpToolExecutor
from test_drawings_by_mouse import _tool_on_part, _type_property
from test_lever_by_mouse import win  # noqa: F401


def _tangent(c1, r1, c2, r2, side):
    dx, dy = c2[0] - c1[0], c2[1] - c1[1]
    d = math.hypot(dx, dy)
    ux, uy = dx / d, dy / d
    k = (r1 - r2) / d
    h = math.sqrt(1 - k * k)
    nx, ny = k * ux - side * h * uy, k * uy + side * h * ux
    return (c1[0] + r1 * nx, c1[1] + r1 * ny, c2[0] + r2 * nx,
            c2[1] + r2 * ny)


def _volume(w):
    return McpToolExecutor(w).execute("mass_properties", {})["volume"]


def test_a_cut_after_a_fillet_on_a_tangent_arm_still_cuts(win):
    ex = McpToolExecutor(win)
    s = ex.execute("reference_geometry", {
        "action": "sketch", "origin": [0, 0, 0], "normal": [0, -1, 0]})[
        "sketch_id"]
    hub, small = (-50.0, 0.0), (-100.0, 50.0)

    def add(t, **p):
        return ex.execute("add_node", {"type": t, "parent_id": s,
                                       "params": p})["created"]
    for c, r in ((small, 11), (small, 7), (hub, 20), (hub, 12.5)):
        add("circle", x=c[0], y=c[1], radius=r)
    for side in (1, -1):
        x1, y1, x2, y2 = _tangent(small, 11, hub, 20, side)
        add("line", x1=x1, y1=y1, x2=x2, y2=y2, width=0.2)
    # the slot (R10 / R4.5, centres 25 apart) and the connector to it
    for r in (10, 4.5):
        add("line", x1=0, y1=-12.5, x2=0, y2=12.5, width=2 * r, slot=True)
    xa = hub[0] + math.sqrt(20 ** 2 - 12.5 ** 2)
    for y in (-12.5, 12.5):
        add("line", x1=xa, y1=y, x2=-10, y2=y, width=0.2)
    feat = lambda pts, **kw: ex.execute("sketch_feature", dict(
        node_id=s, regions=pts, **kw))
    assert "error" not in feat([[-75, 25], [-20, 3]], depth=10,
                               mid_plane=True)
    f = feat([[-34, -5], [-50, -3]], depth=20)
    ex.execute("reference_geometry", {"action": "two_way",
                                      "node_id": f["extrude_id"],
                                      "depth": 25})
    assert "error" not in feat([[-91, 50]], depth=16, mid_plane=True)
    assert "error" not in feat([[7.25, 3]], depth=16, mid_plane=True)
    QTest.qWait(50)
    v_sharp = _volume(win)
    # Fillet by mouse: a click on the arm's lower edge (the face the view
    # sees, y = +5; a hair inside it — the pick snaps to the edge), R3
    QTest.mouseClick(win.view3d.nav_bar.buttons["fit"], Qt.LeftButton)
    x1, y1, x2, y2 = _tangent(small, 11, hub, 20, -1)
    mid = ((x1 + x2) / 2 - 0.3, 5.0, (y1 + y2) / 2 + 0.3)
    _tool_on_part(win, "fillet", mid)
    fil = next(n for n in win.model.root.walk() if n.type == "fillet")
    _type_property(win, "radius", 3)
    QTest.keyClick(win.view3d, Qt.Key_Escape)
    QTest.qWait(100)
    assert fil.params.get("edges"), "no edge picked"
    # and the same edge on the far face (y = -5), as a click there after
    # turning the part over stores it
    ex.execute("fillet_edges", {"node_id": fil.children[0].id, "radius": 3,
                                "edges": [[x1, -5.0, y1, x2, -5.0, y2]]})
    QTest.qWait(50)
    assert len(fil.params["edges"]) == 2
    v_fillet = _volume(win)
    assert v_fillet < v_sharp - 1
    tris = mesh.tessellate(fil)
    water = [c for c in analysis.print_check(tris)["checks"]
             if c["name"] == "Watertight"][0]
    assert water["message"].startswith("0 open edge") or \
        water["status"] == "pass", water["message"]
    # then a cut through the hub's back: it must cut
    r = feat([[-50, -3]], kind="extruded_cut", reverse=True)
    assert "error" not in r, r
    ex.execute("reference_geometry", {"action": "end_condition",
                                      "node_id": r["extrude_id"],
                                      "condition": "through_all_one"})
    QTest.qWait(50)
    bore = math.pi * 12.5 ** 2 * 25
    assert _volume(win) == pytest.approx(v_fillet - bore, rel=0.03)
