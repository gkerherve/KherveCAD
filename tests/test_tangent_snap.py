"""A line's end snaps TANGENT to a circle / arc (2026-11-14, Exercise 6's
Rib2: from the base's corner, tangent to the R30 round).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest

from khervecad import tangent_snap as ts

C = {"centre": (30.0, 42.0), "r": 30.0, "closed": True}


def test_the_end_snaps_to_the_tangent_point_near_the_cursor():
    start = (160.0, 12.0)
    pts = ts.tangent_points(start, C["centre"], C["r"])
    upper = max(pts, key=lambda p: p[1])
    got = ts.snap(start, (upper[0] + 1.0, upper[1] - 0.5), [C], tol=2.0)
    assert got is not None
    p, _c = got
    assert p == pytest.approx(upper)
    # really tangent: radius square to the line
    rx, ry = p[0] - 30.0, p[1] - 42.0
    lx, ly = p[0] - start[0], p[1] - start[1]
    assert abs(rx * lx + ry * ly) < 1e-6
    assert ts.snap(start, (upper[0] + 5, upper[1]), [C], tol=2.0) is None


def test_only_where_an_arc_really_is():
    """The top half only (0..180°): the lower tangent point is refused."""
    arc = dict(C, closed=False, start=0.0, sweep=180.0)
    start = (160.0, 12.0)
    lower = min(ts.tangent_points(start, C["centre"], 30.0),
                key=lambda p: p[1])
    assert ts.snap(start, lower, [arc], tol=2.0) is None


class _N:
    def __init__(self, type_, **p):
        self.type, self.params = type_, p


def test_sketch_circles_arcs_and_the_parts_round_edges_count():
    seg = []
    for k in range(18):                    # an R30 half round, end-on
        a0, a1 = math.pi * k / 18, math.pi * (k + 1) / 18
        seg.append(((30 + 30 * math.cos(a0), 42 + 30 * math.sin(a0)),
                    (30 + 30 * math.cos(a1), 42 + 30 * math.sin(a1))))
    found = ts.circles_of([_N("circle", x=0, y=0, radius=5),
                           _N("line", x1=15, y1=0, x2=-15, y2=0, bulge=1)],
                          seg)
    assert len(found) == 3
    part = found[2]
    assert part["r"] == pytest.approx(30, rel=0.01)
    assert part["centre"] == pytest.approx((30, 42), abs=0.3)


def test_the_line_tool_snaps_tangent_and_adds_the_relation():
    """In the 2D sketch: a circle, then the Line tool from a point
    outside, the cursor near the tangent point -> the end lands there and
    a Tangent relation ties the line to the circle."""
    from PyQt5.QtCore import QPointF
    from PyQt5.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from khervecad.mainwindow import MainWindow
    from khervecad import sketch_line, sketch_constraints as sc
    w = MainWindow()
    w.show()
    sk = w.model.add_node("union", {}, name="Sketch")
    circ = w.model.add_node("circle", dict(x=30, y=42, radius=30),
                            parent=sk)
    w.model.structure_changed.emit()
    QApplication.processEvents()
    scene = w.view2d.scene()
    start = QPointF(160, 12)
    up = max(ts.tangent_points((160, 12), (30, 42), 30), key=lambda p: p[1])
    pt, info = sketch_line.snap(scene, QPointF(up[0] + 0.3, up[1] - 0.2),
                                start)
    assert (pt.x(), pt.y()) == pytest.approx(up, abs=1e-6)
    assert info.get("tangent", {}).get("node") is circ
    line = w.model.add_node("line", dict(x1=160, y1=12, x2=pt.x(),
                                         y2=pt.y(), width=0.2), parent=sk)
    sketch_line._relations(scene, line, info, {})
    assert any(r["kind"] == "tangent" for r in sc.rows(sk))
    w._dirty = False
    w.close()
