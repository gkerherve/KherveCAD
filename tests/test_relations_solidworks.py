# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""Sketch relations the SolidWorks way (2026-11-10, the user): one drawn
tile per relation in both views, none where two points were simply
joined, a switch to hide them, lines coloured by how defined they are,
and Display/Delete Relations."""
import pytest
from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtWidgets import QApplication

from khervecad import relation_marks, sketch_state
from khervecad import sketch_constraints as sc
from khervecad.model import DocumentModel


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _sketch():
    m = DocumentModel()
    a = m.add_node("line", dict(x1=0, y1=0, x2=40, y2=3))
    b = m.add_node("line", dict(x1=41, y1=1, x2=45, y2=30))
    c = m.add_node("circle", dict(x=10, y=20, radius=4))
    return m, a, b, c


def _ref(m, node, name):
    return sc.ref_of(m.root, node, name)


def test_two_points_made_one_draw_no_mark(app):
    m, a, b, c = _sketch()
    r = m.root
    sc.add(m, r, "coincident", [_ref(m, a, "p2"), _ref(m, b, "p1")])
    sc.add(m, r, "horizontal", [_ref(m, a, "l")])
    rows = sc.rows(r)
    assert relation_marks.hidden(r, rows[0])
    assert not relation_marks.hidden(r, rows[1])


def test_every_kind_paints_a_tile(app):
    img = QImage(40, 40, QImage.Format_ARGB32)
    for kind in list(sc.KINDS) + ["something new"]:
        img.fill(0)
        p = QPainter(img)
        relation_marks.paint(p, QRectF(2, 2, relation_marks.SIZE,
                                       relation_marks.SIZE), kind)
        p.end()
        assert img.pixelColor(10, 10).alpha() > 0, kind


def test_the_switch_is_remembered(app):
    was = relation_marks.shown()
    try:
        relation_marks.set_shown(False)
        assert not relation_marks.shown()
        relation_marks.set_shown(True)
        assert relation_marks.shown()
    finally:
        relation_marks.set_shown(was)


def test_lines_blue_until_held_then_black(app):
    m, a, b, c = _sketch()
    r = m.root
    st = sketch_state.states(m, r)
    assert st[a.id] == st[b.id] == st[c.id] == "free"
    sc.add(m, r, "fix", [_ref(m, a, "p1")])
    sc.add(m, r, "fix", [_ref(m, a, "p2")])
    st = sketch_state.states(m, r)
    assert st[a.id] == "defined"
    assert st[b.id] == "free" and st[c.id] == "free"
    assert sketch_state.ink(m, a, True) == sketch_state.INK["defined"]
    assert sketch_state.ink(m, b, True) == sketch_state.INK["free"]


def test_an_unconstrained_overview_keeps_its_ink(app):
    m, a, b, c = _sketch()
    assert sketch_state.ink(m, a, editing=False) is None
    assert sketch_state.ink(m, a, editing=True) == sketch_state.INK["free"]


def test_display_delete_relations_lists_and_deletes(app):
    from khervecad import relations_window
    m, a, b, c = _sketch()
    r = m.root
    sc.add(m, r, "horizontal", [_ref(m, a, "l")])
    sc.add(m, r, "coincident", [_ref(m, a, "p2"), _ref(m, b, "p1")])
    label, ents, _v = relations_window.describe(r, sc.rows(r)[1])
    assert label == "Coincident"
    assert ents == "%s (end), %s (start)" % (a.name, b.name)

    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    try:
        win.model.root.children[:] = []
        wm = win.model
        a2 = wm.add_node("line", dict(x1=0, y1=0, x2=40, y2=3))
        sc.add(wm, wm.root, "horizontal", [sc.ref_of(wm.root, a2, "l")])
        sc.add(wm, wm.root, "length", [sc.ref_of(wm.root, a2, "l")], 30)
        dlg = relations_window.open_window(win)
        assert dlg.list.topLevelItemCount() == 2
        dlg.filter.setCurrentIndex(1)            # relations only
        assert dlg.list.topLevelItemCount() == 1
        dlg.filter.setCurrentIndex(0)
        dlg.list.topLevelItem(0).setSelected(True)
        dlg.buttons["delete"].click()
        assert [x["kind"] for x in sc.rows(wm.root)] == ["length"]
        dlg.close()
    finally:
        win._dirty = False
        win.close()


def test_a_circle_drawn_on_a_side_middle_stays_in_the_middle(app):
    """2026-11-10, the user: lock a circle onto the middle of one of a
    rectangle's lines — it only got Point on curve and slid along."""
    from khervecad import sketch_touch
    m = DocumentModel()
    rect = m.add_node("rect", dict(x=0, y=0, width=40, height=20))
    hole = m.add_node("circle", dict(x=20, y=0, radius=3))
    assert sketch_touch.relate(m, hole) == 1
    assert [r["kind"] for r in sc.rows(m.root)] == ["midpoint"]
    m.set_param(rect, "width", 60)
    sc.refresh(m, edited=[rect.id])
    assert hole.params["x"] == pytest.approx(
        rect.params["x"] + rect.params["width"] / 2, abs=1e-4)
    assert hole.params["y"] == pytest.approx(rect.params["y"], abs=1e-4)


def test_a_polygon_side_middle_locks_a_rectangle_centre_does_not(app):
    from khervecad import sketch_touch
    m = DocumentModel()
    m.add_node("rect", dict(x=0, y=0, width=40, height=20))
    tri = m.add_node("polygon", dict(x=0, y=0, points=[[50, 0], [80, 0],
                                                         [65, 20]]))
    c1 = m.add_node("circle", dict(x=20, y=10, radius=2))
    c2 = m.add_node("circle", dict(x=65, y=0, radius=2))
    sketch_touch.relate(m, c1)
    sketch_touch.relate(m, c2)
    kinds = sorted(r["kind"] for r in sc.rows(m.root))
    assert kinds == ["midpoint"]         # a corner rectangle: no centre
    assert any(r["kind"] == "midpoint" and
               r["refs"][1] == sc.ref_of(m.root, tri, "e0")
               for r in sc.rows(m.root))
