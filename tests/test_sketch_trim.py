"""Trim Entities with SolidWorks' options (2026-11-11, the user).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest
from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad import sketch_trim as tr
from khervecad.model import DocumentModel
from khervecad.view2d import SketchScene, SketchView


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
    v.centerOn(10, 5)
    yield v
    tr.set_mode(tr.CLOSEST)
    v.close()


def _line(m, a, b, name):
    return m.add_node("line", dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1],
                                   width=0.2), name=name)


def _ends(n):
    p = n.params
    return (round(p["x1"], 3), round(p["y1"], 3), round(p["x2"], 3),
            round(p["y2"], 3))


def _click(view, x, y):
    QTest.mouseClick(view.viewport(), Qt.LeftButton, Qt.NoModifier,
                     view.mapFromScene(QPointF(x, y)))
    QApplication.processEvents()


def test_corner_runs_two_lines_to_meet(app):
    m = DocumentModel()
    a = _line(m, (0, 0), (8, 0), "A")            # short of the corner
    b = _line(m, (12, -5), (12, 10), "B")         # past it
    tr.corner(m, a, (2, 0), b, (12, 8))
    assert _ends(a) == (0, 0, 12, 0)
    assert _ends(b) == (12, 0, 12, 10)            # the clicked side kept


def test_away_inside_and_outside(app):
    m = DocumentModel()
    l1 = _line(m, (0, 0), (30, 0), "L")
    b1 = _line(m, (10, -5), (10, 5), "B1")
    c = m.add_node("circle", dict(x=25, y=0, radius=2))   # crosses at 23, 27
    assert tr.away(m, l1, [b1, c], inside=True) == "split"
    pieces = sorted(_ends(n) for n in m.root.children
                    if n.type == "line" and n.name != "B1")
    assert pieces == [(0, 0, 10, 0), (27, 0, 30, 0)]
    l2 = _line(m, (0, 3), (30, 3), "L2")
    b2 = _line(m, (20, -5), (20, 5), "B2")
    tr.away(m, l2, [b1, b2], inside=False)
    assert _ends(l2) == (10, 3, 20, 3)


def test_options_by_mouse_in_the_window(view):
    from khervecad import sketch_modify
    m = view.scene().model
    a = _line(m, (0, 0), (20, 0), "A")
    b1 = _line(m, (5, -5), (5, 5), "B1")
    b2 = _line(m, (15, -5), (15, 5), "B2")
    QApplication.processEvents()
    view.set_tool(sketch_modify.TRIM)
    panel = tr.open_panel(view)
    panel.fields["mode"].setCurrentIndex(
        [k for k, _l in tr.MODES].index(tr.INSIDE))
    assert tr.mode() == tr.INSIDE
    assert "boundary" in panel.message.text()
    _click(view, 5, 3)                            # boundary 1
    _click(view, 15, 3)                           # boundary 2
    _click(view, 10, 0)                           # the line: middle goes
    pieces = sorted(_ends(n) for n in m.root.children
                    if n.type == "line" and n not in (b1, b2))
    assert pieces == [(0, 0, 5, 0), (15, 0, 20, 0)]


def test_power_trim_drags_across(view):
    from khervecad import sketch_modify
    m = view.scene().model
    _line(m, (0, 0), (20, 0), "A")
    _line(m, (0, 4), (20, 4), "C")
    b = _line(m, (10, -5), (10, 10), "B")
    QApplication.processEvents()
    tr.set_mode(tr.POWER)
    view.set_tool(sketch_modify.TRIM)
    vp = view.viewport()
    start = view.mapFromScene(QPointF(15, -2))
    end = view.mapFromScene(QPointF(15, 6))
    QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, start)
    from PyQt5.QtGui import QMouseEvent
    from PyQt5.QtCore import QEvent
    for k in range(1, 9):
        p = start + (end - start) * k / 8
        QApplication.sendEvent(vp, QMouseEvent(
            QEvent.MouseMove, p, Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
    QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, end)
    QApplication.processEvents()
    ends = sorted(_ends(n) for n in m.root.children
                  if n.type == "line" and n is not b)
    assert ends == [(0, 0, 10, 0), (0, 4, 10, 4)]  # both lost x > 10


def test_circles_trim_inside_each_other_like_the_flange(app):
    """SolidWorks' exercise: the Ø80 and the Ø30 overlap; trimming each
    inside the other leaves two open arcs that meet at the crossings —
    and their Ø dimensions and centres still drive them."""
    import math
    from khervecad import sketch_arc, sketch_constraints as sc
    m = DocumentModel()
    big = m.add_node("circle", dict(x=0, y=0, radius=40), name="Big")
    small = m.add_node("circle", dict(x=-46, y=0, radius=15), name="Small")
    sc.add(m, m.root, "diameter", [sc.ref_of(m.root, big, "o")], value=80)
    sc.add(m, m.root, "fix", [sc.ref_of(m.root, big, "c")])
    sc.add(m, m.root, "fix", [sc.ref_of(m.root, small, "c")])
    # the piece of the big circle inside the small one, near (-40, 0)
    assert tr.trim_piece(m, big, (-40, 0.5)) == "opened"
    assert big.type == "line" and sketch_arc.is_arc(big)
    assert tr.trim_piece(m, small, (-31, 0.2)) == "opened"
    # both end where the two circles cross
    d, r0, r1 = 46.0, 40.0, 15.0
    a = (r0 * r0 - r1 * r1 + d * d) / (2 * d)
    h = math.sqrt(r0 * r0 - a * a)
    cross = {(round(-a, 3), round(h, 3)), (round(-a, 3), round(-h, 3))}
    for n in (big, small):
        ends = {(round(n.params["x1"], 3), round(n.params["y1"], 3)),
                (round(n.params["x2"], 3), round(n.params["y2"], 3))}
        assert ends == cross
    # the big arc stays round the origin, the small round (-46, 0), and
    # the arcs left are the OUTER parts (a point far out lies on them)
    g = tr.curve_of(big)
    assert (round(g[1], 4), round(g[2], 4), round(g[3], 4)) == (0, 0, 40)
    assert tr._on(g, (40, 0)) is not None
    g2 = tr.curve_of(small)
    assert (round(g2[1], 4), round(g2[3], 4)) == (-46, 15)
    assert tr._on(g2, (-61, 0)) is not None
    # its Ø dimension still holds on the arc
    report = sc.solve(m.root)
    assert report["ok"]
    rows = [r for r in sc.rows(m.root) if r["kind"] == "diameter"]
    assert rows and sc._circle(big, "o", {})[1] == pytest.approx(40, abs=1e-4)


def test_a_line_through_a_circle_trims_to_its_crossings(app):
    m = DocumentModel()
    m.add_node("circle", dict(x=0, y=0, radius=10))
    line = _line(m, (-30, 0), (30, 0), "L")
    assert tr.trim_piece(m, line, (0, 0)) == "split"
    ends = sorted(_ends(n) for n in m.root.children if n.type == "line")
    assert ends == [(-30, 0, -10, 0), (10, 0, 30, 0)]


def test_the_piece_under_the_cursor_is_found_for_the_highlight(app):
    m = DocumentModel()
    big = m.add_node("circle", dict(x=0, y=0, radius=40))
    m.add_node("circle", dict(x=-46, y=0, radius=15))
    pts = tr.piece_points(big, (-40, 0))
    assert len(pts) > 2
    assert all(math.hypot(x + 46, y) <= 15.01 for x, y in pts)


def test_hover_shows_the_piece_and_a_click_removes_it(view):
    """The flange by mouse: the cursor over the big circle's piece
    inside the small one lights that piece; a click opens the circle."""
    from PyQt5.QtGui import QMouseEvent
    from PyQt5.QtCore import QEvent
    from khervecad import sketch_arc, sketch_modify
    tr.set_mode(tr.CLOSEST)
    m = view.scene().model
    big = m.add_node("circle", dict(x=0, y=0, radius=40))
    m.add_node("circle", dict(x=-46, y=0, radius=15))
    QApplication.processEvents()
    view.resetTransform()
    view.scale(4, -4)
    view.centerOn(-20, 0)
    view.set_tool(sketch_modify.TRIM)
    at = view.mapFromScene(QPointF(-40, 0))
    QApplication.sendEvent(view.viewport(), QMouseEvent(
        QEvent.MouseMove, at, Qt.NoButton, Qt.NoButton, Qt.NoModifier))
    hover = view.scene()._trim_hover
    assert len(hover) > 2
    assert all(math.hypot(p.x() + 46, p.y()) <= 15.05 for p in hover)
    view.viewport().repaint()                      # paints, never raises
    _click(view, -40, 0)
    assert big.type == "line" and sketch_arc.is_arc(big)
    assert view.scene()._trim_hover == []


def test_a_trim_shows_and_can_be_restored(app):
    """The user: "can't see where the trimming has happened … something
    so that we can remove it" — a trimmed shape remembers what it was;
    Restore Untrimmed brings it back, split pieces joined again."""
    m = DocumentModel()
    big = m.add_node("circle", dict(x=0, y=0, radius=40), name="Big")
    m.add_node("circle", dict(x=-46, y=0, radius=15), name="Small")
    line = _line(m, (-60, 30), (60, 30), "L")
    tr.trim_piece(m, big, (-40, 0.5))
    tr.trim_piece(m, line, (0, 30))                # splits the line
    assert tr.trimmed(big) and tr.trimmed(line)
    pieces = [n for n in m.root.children if tr.trimmed(n)
              and n.params[tr.KEY]["key"] == line.params[tr.KEY]["key"]]
    assert len(pieces) == 2
    tr.restore(m, big)
    assert big.type == "circle" and big.params["radius"] == 40
    assert not tr.trimmed(big)
    tr.restore(m, pieces[1])
    lines = [n for n in m.root.children if n.type == "line"]
    assert len(lines) == 1 and _ends(lines[0]) == (-60, 30, 60, 30)


def test_a_circle_trims_at_the_point_where_another_only_touches_it(app):
    """The user's picture: a small circle tangent INSIDE the big one —
    the trim must stop at that touching point, not run past it."""
    m = DocumentModel()
    big = m.add_node("circle", dict(x=0, y=0, radius=80), name="Big")
    # tangent inside at (0, -80), centre placed by a solver (a hair off)
    m.add_node("circle", dict(x=0, y=-64.99999, radius=15),
               name="Touching")
    cutter = _line(m, (-100, -40), (100, -40), "Chord")
    tr.trim_piece(m, big, (30, -74))           # the bottom-right piece
    g = tr.curve_of(big)
    ends = {(round(p[0], 3), round(p[1], 3))
            for p in (tr.point_at(g, 0), tr.point_at(g, 1))}
    assert any(abs(x) < 0.05 and abs(y + 80) < 0.001 for x, y in ends)
