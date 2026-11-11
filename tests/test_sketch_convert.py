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
    finally:
        win._dirty = False
        win.close()
