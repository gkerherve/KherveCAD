"""Sketch Fillet / Chamfer where arcs meet (2026-11-11, the user, with
SolidWorks' flange: 8 mm fillets where the two trimmed circles join).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest

from khervecad import sketch_corner as sk, sketch_trim as tr
from khervecad.model import DocumentModel


def _flange():
    m = DocumentModel()
    big = m.add_node("circle", dict(x=0, y=0, radius=40), name="Big")
    small = m.add_node("circle", dict(x=-46, y=0, radius=15), name="Small")
    tr.trim_piece(m, big, (-40, 0.5))
    tr.trim_piece(m, small, (-31, 0.2))
    return m, big, small


def test_a_fillet_between_the_two_arcs_is_tangent_to_both():
    m, big, small = _flange()
    fil = sk.corner(m, big, small, 8, round_=True)
    g = tr.curve_of(fil)
    assert g[0] == "arc" and g[3] == pytest.approx(8, abs=1e-6)
    q = (g[1], g[2])
    # outside both circles, touching each: |q - c| = r + 8
    assert math.hypot(q[0], q[1]) == pytest.approx(48, abs=1e-4)
    assert math.hypot(q[0] + 46, q[1]) == pytest.approx(23, abs=1e-4)
    # the arcs now end where the fillet does
    ends = {(round(x, 4), round(y, 4)) for x, y in sk._ends(g)}
    for node in (big, small):
        e = {(round(x, 4), round(y, 4))
             for x, y in sk._ends(tr.curve_of(node))}
        assert ends & e
    assert big.params["bulge"] and small.params["bulge"]


def test_a_chamfer_between_the_two_arcs():
    m, big, small = _flange()
    ch = sk.corner(m, big, small, 5, round_=False)
    g = tr.curve_of(ch)
    assert g[0] == "seg"
    # each end 5 mm along its arc from the old corner
    d, r0, r1 = 46.0, 40.0, 15.0
    a = (r0 * r0 - r1 * r1 + d * d) / (2 * d)
    h = math.sqrt(r0 * r0 - a * a)
    corners = [(-a, h), (-a, -h)]
    p = min(corners, key=lambda c: math.dist(c, g[1]))
    assert math.dist(p, g[1]) == pytest.approx(2 * 40 * math.sin(5 / 80),
                                               abs=1e-3)


def test_lines_meeting_at_a_corner_and_a_click_on_the_corner_point():
    m = DocumentModel()
    a = m.add_node("line", dict(x1=0, y1=0, x2=20, y2=0, width=0.2))
    b = m.add_node("line", dict(x1=20, y1=0, x2=20, y2=20, width=0.2))
    assert sk.partner(a, "p2") is b
    fil = sk.corner(m, a, b, 4)
    g = tr.curve_of(fil)
    assert (round(g[1], 4), round(g[2], 4), round(g[3], 4)) == (16, 4, 4)
    assert (a.params["x2"], b.params["y1"]) == (16, 4)


def test_curves_that_do_not_meet_are_refused():
    m = DocumentModel()
    a = m.add_node("line", dict(x1=0, y1=0, x2=20, y2=0, width=0.2))
    b = m.add_node("line", dict(x1=30, y1=5, x2=30, y2=20, width=0.2))
    with pytest.raises(ValueError):
        sk.corner(m, a, b, 4)


def test_a_chamfer_longer_than_a_side_is_refused():
    m = DocumentModel()
    a = m.add_node("line", dict(x1=0, y1=0, x2=3, y2=0, width=0.2))
    b = m.add_node("line", dict(x1=3, y1=0, x2=3, y2=20, width=0.2))
    with pytest.raises(ValueError):
        sk.corner(m, a, b, 5, round_=False)


def test_by_mouse_a_click_on_the_corner_point_fillets_it():
    from PyQt5.QtCore import QPointF, Qt
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import QApplication
    from khervecad import sketch_modify
    from khervecad.view2d import SketchScene, SketchView
    app = QApplication.instance() or QApplication([])
    scene = SketchScene(DocumentModel())
    scene.snap_enabled = False
    view = SketchView(scene)
    view.resize(700, 500)
    view.show()
    view.resetTransform()
    view.scale(5, -5)
    view.centerOn(-30, 0)
    m = scene.model
    big = m.add_node("circle", dict(x=0, y=0, radius=40))
    small = m.add_node("circle", dict(x=-46, y=0, radius=15))
    tr.trim_piece(m, big, (-40, 0.5))
    tr.trim_piece(m, small, (-31, 0.2))
    QApplication.processEvents()
    scene.ask_value = lambda tool, default: "8"
    view.set_tool(sketch_modify.FILLET)
    d, r0, r1 = 46.0, 40.0, 15.0
    a = (r0 * r0 - r1 * r1 + d * d) / (2 * d)
    h = math.sqrt(r0 * r0 - a * a)
    QTest.mouseClick(view.viewport(), Qt.LeftButton, Qt.NoModifier,
                     view.mapFromScene(QPointF(-a, h)))
    QApplication.processEvents()
    fillets = [n for n in m.root.children if n.name.startswith("Sketch fillet")]
    assert len(fillets) == 1
    g = tr.curve_of(fillets[0])
    assert g[3] == pytest.approx(8, abs=1e-6) and g[2] > 0
    view.close()


def test_a_fillets_radius_can_be_changed_later():
    """It carries a radius dimension and tangents: typed 12 later, the
    fillet grows and stays tangent to both arcs (the user)."""
    from khervecad import sketch_constraints as sc
    m, big, small = _flange()
    sc.add(m, m.root, "fix", [sc.ref_of(m.root, big, "c")])
    sc.add(m, m.root, "fix", [sc.ref_of(m.root, small, "c")])
    sc.add(m, m.root, "radius", [sc.ref_of(m.root, big, "o")], value=40)
    sc.add(m, m.root, "radius", [sc.ref_of(m.root, small, "o")], value=15)
    fil = sk.corner(m, big, small, 8)
    assert sk.label(fil) == "(fillet R8)"
    rows = sc.rows(m.root)
    me = sc.ref_of(m.root, fil, "o")
    i = next(k for k, r in enumerate(rows)
             if r["kind"] == "radius" and r["refs"] == [me])
    sc.set_value(m, m.root, i, 12)
    g = tr.curve_of(fil)
    assert g[3] == pytest.approx(12, abs=1e-3)
    q = (g[1], g[2])
    assert math.hypot(*q) == pytest.approx(52, abs=1e-3)
    assert math.hypot(q[0] + 46, q[1]) == pytest.approx(27, abs=1e-3)
    assert sk.label(fil) == "(fillet R12)"
    for node, r in ((big, 40), (small, 15)):        # the arcs stayed round
        assert tr.curve_of(node)[3] == pytest.approx(r, abs=1e-3)


def test_the_hovered_curves_and_the_first_pick_light_up():
    from PyQt5.QtCore import QEvent, QPointF, Qt
    from PyQt5.QtGui import QMouseEvent
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import QApplication
    from khervecad import sketch_modify
    from khervecad.view2d import SketchScene, SketchView
    app = QApplication.instance() or QApplication([])
    scene = SketchScene(DocumentModel())
    scene.snap_enabled = False
    view = SketchView(scene)
    view.resize(600, 500)
    view.show()
    view.resetTransform()
    view.scale(10, -10)
    view.centerOn(10, 10)
    m = scene.model
    a = m.add_node("line", dict(x1=0, y1=0, x2=20, y2=0, width=0.2))
    b = m.add_node("line", dict(x1=20, y1=0, x2=20, y2=20, width=0.2))
    QApplication.processEvents()
    view.set_tool(sketch_modify.FILLET)

    def move(x, y):
        QApplication.sendEvent(view.viewport(), QMouseEvent(
            QEvent.MouseMove, view.mapFromScene(QPointF(x, y)),
            Qt.NoButton, Qt.NoButton, Qt.NoModifier))
    move(20, 0)                                    # the corner point
    assert set(scene._corner_hover) == {a, b}
    move(10, 0.05)                                 # one line
    assert scene._corner_hover == [a]
    QTest.mouseClick(view.viewport(), Qt.LeftButton, Qt.NoModifier,
                     view.mapFromScene(QPointF(10, 0.05)))
    assert scene._sk_first is a                    # stays lit (blue)
    view.viewport().repaint()                      # paints, never raises
    view.close()
