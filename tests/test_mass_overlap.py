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


def _plate_block(win):
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(win)
    ex.execute("apply_code", {"code": "union() { cube([40, 40, 10]);\n"
                              "translate([10, 10, 5]) cube([20, 20, 20]); }\n"})
    QTest.qWait(50)
    return ex, next(n for n in win.model.root.walk() if n.type == "union")


def test_fillet_edges_takes_the_edge_list_edges_numbered(win):
    """list_edges numbers the UNITED part's edges; fillet_edges must
    read its chains the same way (it rounded other edges)."""
    ex, u = _plate_block(win)
    edges = ex.execute("list_edges", {"node_id": u.id})["edges"]
    i = next(e["index"] for e in edges if not e["convex"]
             and abs(e["centre"][2] - 10) < 0.01)
    want = edges[i]["seed"]
    out = ex.execute("fillet_edges", {"node_id": u.id, "chains": [i],
                                      "radius": 2})
    f = win.model.find(out["fillet"])
    got = f.params["edges"][0]
    assert got == pytest.approx(want, abs=1e-3)


def test_a_second_radius_is_a_second_fillet(win):
    """SolidWorks' Fillet2 R42 then Fillet3 R12: two features, each with
    its own radius (the second used to overwrite the first's radius)."""
    ex, u = _plate_block(win)
    edges = ex.execute("list_edges", {"node_id": u.id})["edges"]
    top = [e["index"] for e in edges if e["convex"]
           and abs(e["centre"][2] - 25) < 0.01][:1]
    foot = [e["index"] for e in edges if not e["convex"]
            and abs(e["centre"][2] - 10) < 0.01][:1]
    a = ex.execute("fillet_edges", {"node_id": u.id, "chains": top,
                                    "radius": 4})
    b = ex.execute("fillet_edges", {"node_id": u.id, "chains": foot,
                                    "radius": 2})
    fa, fb = win.model.find(a["fillet"]), win.model.find(b["fillet"])
    assert fa is not fb
    assert fa.params["radius"] == 4 and fb.params["radius"] == 2


def test_a_fillet_never_runs_metres_past_its_edge():
    """Faces meeting almost flat give a fillet profile reaching to
    infinity: the strip is left out (the edge stays sharp), it never
    becomes a slab metres long (Exercise 7's rib on its tube)."""
    from khervecad import fillet, mesh, scadparse
    # two faces at 179°: a block with a very slightly bent top
    code = ("rotate([90, 0, 0]) linear_extrude(height = 10) "
            "polygon([[0, 0], [40, 0], [40, 10], [20, 10.17], [0, 10]]);")
    root = scadparse.parse_scad(code)[0]
    tris = [tuple(t[:3]) for t in mesh.tessellate(root)]
    ch = [c for c in fillet.chains(tris, 0.5) if abs(c["centre"][0] - 20) < 0.5]
    assert ch
    res = fillet.compute(tris, [ch[0]["seed"]], 12, "round", 6)
    for piece in res["cuts"] + res["adds"]:
        for t in piece:
            for p in t[:3]:
                assert abs(p[0] - 20) < 60
