"""Convert Entities: the part's edges brought into the sketch
(2026-11-11, the user).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import cut_feature, sketch_convert as cv
from khervecad.mainwindow import MainWindow
from khervecad.mcp_tools import McpToolExecutor


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _square(n=4):
    pts = [(0, 0), (20, 0), (20, 10), (0, 10)]
    out = []
    for a, b in zip(pts, pts[1:] + pts[:1]):
        for k in range(n):             # tessellated: several pieces a side
            p = (a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n)
            q = (a[0] + (b[0] - a[0]) * (k + 1) / n,
                 a[1] + (b[1] - a[1]) * (k + 1) / n)
            out.append((p, q))
    return out


def _circle(cx, cy, r, n=48):
    pts = [(cx + r * math.cos(2 * math.pi * i / n),
            cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    return list(zip(pts, pts[1:] + pts[:1]))


def test_a_face_outline_becomes_four_lines_and_a_circle(app):
    segs = _square() + _circle(10, 5, 3)
    shapes = cv.convert(segs)
    kinds = sorted(t for t, _p in shapes)
    assert kinds == ["circle", "line", "line", "line", "line"]
    circle = next(p for t, p in shapes if t == "circle")
    assert circle["radius"] == pytest.approx(3, abs=0.01)
    edge = cv.whole_edge(segs, *segs[1])          # one piece of the bottom
    assert cv.convert(edge, segs) == [("line", dict(
        x1=0.0, y1=0.0, x2=20.0, y2=0.0, width=cv.LINE_W))]


def test_a_partial_arc_is_one_bulged_line(app):
    arc = [(10 + 5 * math.cos(math.radians(a)),
            5 * math.sin(math.radians(a))) for a in range(0, 91, 10)]
    segs = list(zip(arc, arc[1:])) + [((5, 0), (15, 0)), ((10, 5), (5, 0))]
    # (closed: the arc from (15, 0) to (10, 5), then two straight sides)
    shapes = cv.convert(segs)
    bulged = [p for t, p in shapes if t == "line" and "bulge" in p]
    assert len(bulged) == 1
    assert (bulged[0]["x1"], bulged[0]["y1"]) in ((15.0, 0.0), (10.0, 5.0))


def _sketch_on_top(win, monkeypatch, code):
    monkeypatch.setattr(cut_feature, "IN_3D", True)
    McpToolExecutor(win).execute("apply_code", {"code": code})
    QApplication.processEvents()
    part = next(c for c in win.model.root.children
                if c.visible and c.type not in ("assign", "variables"))
    cut_feature.start(win, "extruded_cut")
    win.view3d._pick_cb(dict(kind="face", pos=(0, 0, 10),
                             dir=(0, 0, 1)), part)
    win.view3d.resize(800, 600)
    win.view3d.fit()
    return win.view3d.edit_tool


def test_convert_in_the_3d_sketch(app, monkeypatch):
    from khervecad import sketch3d_tools
    win = MainWindow()
    try:
        sk = _sketch_on_top(win, monkeypatch,
                            "translate([-20, -10, 0]) cube([40, 20, 10]);"
                            " // Block\n")
        segs = sk.info.get("segments")
        assert segs
        g = sk.holder or sk.group
        sk.tool_icon("sk_convert")
        tool = win.view3d.edit_tool
        assert isinstance(tool, sketch3d_tools.Modify3D)
        # the whole face: a click in its middle
        v = win.view3d
        cam = v._camera()
        from khervecad.face_sketch import to_world
        s = v._project(*cam, to_world(g, 0.0, 0.0))
        made = tool._convert(s[0], s[1])
        assert sorted(n.type for n in made) == ["line"] * 4
        lengths = sorted(round(math.hypot(n.params["x2"] - n.params["x1"],
                                          n.params["y2"] - n.params["y1"]),
                               3) for n in made)
        assert lengths == [20, 20, 40, 40]
        assert all(n.parent is g for n in made)
        # a second click: the face is still the part's face, not the
        # part's face plus the lines just converted (Exercise 49)
        sk._load_face()
        again = tool._convert(s[0], s[1])
        assert len(again) == 4
    finally:
        win._dirty = False
        win.close()


def _tangent_arcs_outline():
    """Exercise 50's plate end: a bottom line, an R25 end and an R100
    sweeping back tangent to it, closed by straight lines."""
    pts = [(0.0, -25.0), (85.0, -25.0)]
    for i in range(1, 25):                   # R25 from -90° to +86.4°
        a = math.radians(-90 + 176.4 * i / 24)
        pts.append((85 + 25 * math.cos(a), 25 * math.sin(a)))
    c = (85 + 125 * math.cos(math.radians(86.4)),
         125 * math.sin(math.radians(86.4)))
    for i in range(1, 16):                   # R100, concave, to the left
        a = math.radians(266.4 - 40 * i / 15)
        pts.append((c[0] + 100 * math.cos(a), c[1] + 100 * math.sin(a)))
    pts.append((0.0, pts[-1][1]))
    return list(zip(pts, pts[1:] + pts[:1]))


def test_tangent_arcs_of_different_radii_are_two_arcs():
    from khervecad import face_outline
    got = sorted(r for _c, r in face_outline.arcs(_tangent_arcs_outline()))
    assert len(got) == 2, got
    assert got[0] == pytest.approx(25, rel=0.02)
    assert got[1] == pytest.approx(100, rel=0.02)


def test_convert_the_r25_brings_only_the_r25():
    segs = _tangent_arcs_outline()
    shapes = cv.convert(cv.whole_edge(segs, *cv.edge_at(segs, (110, 0), 1)),
                        segs)
    assert len(shapes) == 1, shapes
    t, p = shapes[0]
    assert p.get("bulge"), p
    assert (p["x1"], p["y1"]) == pytest.approx((85, -25), abs=0.01)


def test_convert_the_r100_stops_where_the_r25_starts():
    segs = _tangent_arcs_outline()
    c = (85 + 125 * math.cos(math.radians(86.4)),
         125 * math.sin(math.radians(86.4)))
    p = (c[0] + 100 * math.cos(math.radians(246)),
         c[1] + 100 * math.sin(math.radians(246)))
    shapes = cv.convert(cv.whole_edge(segs, *cv.edge_at(segs, p, 1)), segs)
    assert len(shapes) == 1, shapes
    q = shapes[0][1]
    assert (q["x2"], q["y2"]) == pytest.approx(
        (85 + 25 * math.cos(math.radians(86.4)),
         25 * math.sin(math.radians(86.4))), abs=0.01)


def test_a_straight_side_between_two_tangent_arcs_stays_straight():
    """The plate's bottom runs tangent out of one arc into another: its
    two ends turn a little, and were fitted as a circle of r ~ 1000 that
    swallowed the whole straight side."""
    pts = []
    for i in range(10):                      # R20 corner, 180° -> 270°
        a = math.radians(180 + 90 * i / 9)
        pts.append((20 * math.cos(a), -5 + 20 * math.sin(a)))
    for i in range(25):                      # R25 end from -90° to +90°
        a = math.radians(-90 + 180 * i / 24)
        pts.append((85 + 25 * math.cos(a), 25 * math.sin(a)))
    pts.append((-20.0, 25.0))
    segs = list(zip(pts, pts[1:] + pts[:1]))
    from khervecad import face_outline
    assert all(r < 30 for _c, r in face_outline.arcs(segs))
    shapes = cv.convert(cv.whole_edge(segs, *cv.edge_at(segs, (40, -25), 1)),
                        segs)
    assert len(shapes) == 1, shapes
    t, p = shapes[0]
    assert t == "line" and not p.get("bulge"), p
    assert sorted((p["x1"], p["x2"])) == pytest.approx([0, 85], abs=0.01)


def test_a_tangent_arc_between_lines_converts_whole(app):
    """Exercise 49: the plate's R89 arc runs tangent out of a long
    straight side; the junction turned only a little, so the side's far
    end was fitted into the arc (R118, wrong place) and Convert brought
    in a short wrong piece."""
    k = 8
    arc = [(89 * math.sin(t), 89 - 89 * math.cos(t))
           for t in (i / k for i in range(k + 1))]          # 0..1 rad
    pts = [(-80, 0)] + arc + [(arc[-1][0], -30), (-80, -30)]
    segs = list(zip(pts, pts[1:] + pts[:1]))
    from khervecad import face_outline
    found = face_outline.arcs(segs)
    assert len(found) == 1
    (cx, cy), r = found[0]
    assert r == pytest.approx(89, abs=0.5)
    assert (cx, cy) == pytest.approx((0, 89), abs=0.5)
    piece = cv.whole_edge(segs, arc[3], arc[4])
    shapes = cv.convert(piece, segs)
    assert len(shapes) == 1
    p = shapes[0][1]
    assert {(round(p["x1"], 2), round(p["y1"], 2)),
            (round(p["x2"], 2), round(p["y2"], 2))} == \
        {(0.0, 0.0), (round(arc[-1][0], 2), round(arc[-1][1], 2))}
