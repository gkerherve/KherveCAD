"""A new circle's centre lands ON a line, its radius snaps tangent
(2026-11-11, the user).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad import sketch_constraints as sc, sketch_touch
from khervecad.model import DocumentModel
from khervecad.view2d import CIRCLE, SketchScene, SketchView


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def view(app):
    scene = SketchScene(DocumentModel())
    scene.snap_enabled = False
    v = SketchView(scene)
    v.resize(800, 600)
    v.show()
    v.resetTransform()
    v.scale(8, -8)
    v.centerOn(15, 0)
    yield v
    v.close()


def _drag(view, a, b):
    vp = view.viewport()
    pa, pb = view.mapFromScene(QPointF(*a)), view.mapFromScene(QPointF(*b))
    QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, pa)
    from PyQt5.QtCore import QEvent
    from PyQt5.QtGui import QMouseEvent
    for k in range(1, 9):
        p = pa + (pb - pa) * k / 8
        QApplication.sendEvent(vp, QMouseEvent(
            QEvent.MouseMove, p, Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
    QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, pb)
    QApplication.processEvents()


def test_centre_on_the_centerline_radius_tangent_to_a_circle(view):
    m = view.scene().model
    axis = m.add_node("line", dict(x1=-40, y1=0, x2=60, y2=0, width=0.2,
                                   modifier="%"), name="Axis")
    other = m.add_node("circle", dict(x=30, y=0, radius=10), name="Other")
    QApplication.processEvents()
    view.set_tool(CIRCLE)
    # the centre dropped a little off the line, the rim pulled out to
    # nearly touch the other circle (centre 25 away: tangent at r 15)
    _drag(view, (5, 0.4), (5, 15.3))
    new = [n for n in m.root.children if n.type == "circle"
           and n is not other][0]
    assert new.params["y"] == pytest.approx(0, abs=1e-6)     # on the line
    assert new.params["radius"] == pytest.approx(15, abs=1e-6)
    sketch_touch.relate(m, new)                # (the window does it too)
    rows = sc.rows(m.root)
    me_c = sc.ref_of(m.root, new, "c")
    me_o = sc.ref_of(m.root, new, "o")
    assert any(r["kind"] == "point_on" and me_c in r["refs"]
               and sc.ref_of(m.root, axis, "l") in r["refs"] for r in rows)
    assert any(r["kind"] == "tangent" and me_o in r["refs"]
               and sc.ref_of(m.root, other, "o") in r["refs"]
               for r in rows)
    # the other circle grows: the new one stays tangent, on the line
    i = None
    sc.add(m, m.root, "diameter", [sc.ref_of(m.root, other, "o")],
           value=20)
    i = len(sc.rows(m.root)) - 1
    sc.set_value(m, m.root, i, 30)
    import math
    d = math.hypot(new.params["x"] - other.params["x"],
                   new.params["y"] - other.params["y"])
    assert d == pytest.approx(new.params["radius"] + 15, abs=1e-3)
    assert new.params["y"] == pytest.approx(0, abs=1e-4)


def test_a_radius_far_from_any_tangent_stays_as_drawn(view):
    m = view.scene().model
    m.add_node("circle", dict(x=30, y=0, radius=10))
    QApplication.processEvents()
    view.set_tool(CIRCLE)
    _drag(view, (-20, 20), (-20, 26))
    new = [n for n in m.root.children if n.type == "circle"
           and n.params["x"] != 30][0]
    assert new.params["radius"] == pytest.approx(6, abs=0.2)


def test_the_3d_sketch_circle_snaps_tangent_too(app, monkeypatch):
    from khervecad import cut_feature
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    monkeypatch.setattr(cut_feature, "IN_3D", True)
    win = MainWindow()
    try:
        McpToolExecutor(win).execute(
            "apply_code", {"code": "cube([80, 60, 20]); // Block\n"})
        QApplication.processEvents()
        part = next(c for c in win.model.root.children
                    if c.visible and c.type != "assign")
        cut_feature.start(win, "extruded_cut")
        win.view3d._pick_cb(dict(kind="face", pos=(40, 30, 20),
                                 dir=(0, 0, 1)), part)
        tool = win.view3d.edit_tool
        win.view3d.resize(800, 600)
        win.view3d.fit()
        g = tool.group
        other = win.model.add_node("circle", dict(x=50, y=30, radius=8),
                                   parent=g)
        r, target = tool._tangent3d((30, 30), 12.1)
        assert r == pytest.approx(12) and target == (other, "o")
        r, target = tool._tangent3d((30, 30), 5)
        assert r == 5 and target is None
        tool.finish()
    finally:
        win._dirty = False
        win.close()
