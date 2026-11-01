"""Round an edge / push a face from the 3D view with nothing selected,
and the 3D view's right-click menu.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QMenu

from khervecad import round_ui


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    yield win
    win._dirty = False
    win.close()


def test_click_an_edge_with_nothing_selected(window):
    m = window.model
    m.set_global_fn(False)
    cube = m.add_node("cube", dict(width=40.0, depth=30.0, height=20.0))
    window.builder.active_tree().select_nodes([])
    window._apply_operation("fillet")            # the toolbar button
    view = window.view3d
    assert view._pick_cb is not None             # asks for a click
    seg = [[0.0, 0.0, 20.0], [40.0, 0.0, 20.0]]
    view._pick_cb(dict(kind="edge", seg=seg), cube)
    fillet = cube.parent
    assert fillet.type == "fillet"               # an item in the tree
    assert fillet.params["edges"] == [[0.0, 0.0, 20.0, 40.0, 0.0, 20.0]]
    assert view._pick_cb is not None             # more edges welcome
    view.cancel_pick()


def test_chamfer_from_the_menu_sets_the_kind(window):
    m = window.model
    cube = m.add_node("cube")
    window.builder.active_tree().select_nodes([])
    round_ui.start(window, "fillet", "chamfer")
    window.view3d._pick_cb(dict(kind="face", tris=[]), cube)
    assert cube.parent.type == "fillet"
    assert cube.parent.params["kind"] == "chamfer"
    window.view3d.cancel_pick()


def test_right_click_offers_the_menu(window, monkeypatch):
    shown = []
    monkeypatch.setattr(QMenu, "exec_", lambda self, *a: shown.append(
        [a.text() for a in self.actions() if a.text()]))
    from PyQt5.QtCore import QPoint
    window.view3d.context_requested.emit(QPoint(10, 10))
    assert shown and any("fillet" in t for t in shown[0])


def test_a_selected_2d_shape_rounds_its_part(window):
    """The user had Polygon 2 (inside the extrude) selected: Fillet
    wrapped the flat polygon and nothing could be rounded."""
    m = window.model
    obj = m.add_node("component", {})
    obj.visible = True
    d = m.add_node("difference", {}, parent=obj)
    e = m.add_node("linear_extrude", dict(height=10), parent=d)
    p = m.add_node("polygon", dict(points=[[0, 0], [20, 0], [20, 5],
                                           [0, 5]]), parent=e)
    QApplication.processEvents()
    window.builder.open_component(obj)
    QApplication.processEvents()
    window.builder.active_tree().select_nodes([p])
    window._apply_operation("fillet")
    assert d.parent.type == "fillet"           # the part, not the polygon
    assert p.parent is e
    assert window.view3d._pick_cb is not None
    window.view3d.cancel_pick()


def test_an_optional_table_can_be_emptied(app):
    from khervecad.rowsedit import RowsEditor
    got = []
    ed = RowsEditor([[0, 1, 2]], None, got.append, allow_empty=True)
    ed.table.setCurrentCell(0, 0)
    ed._remove_row()
    assert got[-1] == []
    keep = RowsEditor([[0, 1, 2]], None, got.append)
    keep._remove_row()
    assert keep.table.rowCount() == 1        # a required list keeps one


def test_clear_and_pick_again(window, monkeypatch):
    from PyQt5.QtWidgets import QMenu
    m = window.model
    cube = m.add_node("cube")
    f = m.wrap_nodes([cube], "fillet")
    f.params["edges"] = [[0, 0, 20, 20, 0, 20]]
    tree = window.builder.active_tree()
    tree.select_nodes([f])
    QApplication.processEvents()
    shown = []
    monkeypatch.setattr(QMenu, "exec_", lambda self, *a: shown.append(
        [x for x in self.actions() if x.text()]))
    tree._context_menu(tree.visualItemRect(tree.currentItem()).center())
    act = next(a for a in shown[0] if a.text().startswith("Clear and pick"))
    act.trigger()
    assert f.params["edges"] == [] and window.view3d._pick_cb is not None
    window.view3d.cancel_pick()


def _l_object(window):
    m = window.model
    obj = m.add_node("component", {})
    obj.visible = True
    e = m.add_node("linear_extrude", dict(height=5), parent=obj)
    m.add_node("polygon", dict(points=[[0, 0], [40, 0], [40, 10], [10, 10],
                                       [10, 40], [0, 40]]), parent=e)
    QApplication.processEvents()
    window.builder.open_component(obj)
    QApplication.processEvents()
    return m, e


def test_pick_again_after_a_face_is_rounded(window):
    """The second Pick edges refused: the shown (cut) mesh no longer
    matched the fillet's uncut one triangle for triangle."""
    from khervecad import fillet_pick
    m, e = _l_object(window)
    f = m.wrap_nodes([e], "fillet")
    for n in (1, 2):
        assert fillet_pick.start(window, f)
        world, _local = fillet_pick.meshes(window, f)
        top = [t for t in world if all(abs(v[2] - 5) < 1e-9 for v in t)]
        side = [t for t in world if all(abs(v[1]) < 1e-9 for v in t)]
        window.view3d._pick_cb(dict(kind="face",
                                    tris=top if n == 1 else side), f)
        window.view3d.cancel_pick()
    assert len(f.params["faces"]) == 2


def test_a_drag_turns_the_view_and_done_stops(window):
    from PyQt5.QtCore import QPoint
    from khervecad import fillet_pick
    m, e = _l_object(window)
    f = m.wrap_nodes([e], "fillet")
    view = window.view3d
    view.resize(600, 400)
    assert fillet_pick.start(window, f)
    assert view._pick_done.isVisibleTo(view)
    yaw = view.yaw
    QTest.mousePress(view, Qt.LeftButton, Qt.NoModifier, QPoint(300, 200))
    from PyQt5.QtCore import QEvent, QPointF
    from PyQt5.QtGui import QMouseEvent
    # offscreen, QTest.mouseMove carries no held button: send the drag
    QApplication.sendEvent(view, QMouseEvent(
        QEvent.MouseMove, QPointF(360, 210), Qt.NoButton, Qt.LeftButton,
        Qt.NoModifier))
    QTest.mouseRelease(view, Qt.LeftButton, Qt.NoModifier, QPoint(360, 210))
    assert view.yaw != yaw                     # turned, not picked
    assert view._pick_cb is not None           # still picking
    view._pick_done.click()
    assert view._pick_cb is None and not view._pick_done.isVisibleTo(view)


def test_plus_in_the_fillet_table_picks_on_the_model(window):
    from khervecad.rowsedit import RowsEditor
    m, e = _l_object(window)
    f = m.wrap_nodes([e], "fillet")
    window.builder.active_tree().select_nodes([f])
    QApplication.processEvents()
    eds = [w for w in window.findChildren(RowsEditor)
           if w.isVisibleTo(window) and w._on_add is not None]
    assert eds
    eds[0]._add_row()
    assert window.view3d._pick_cb is not None
    window.view3d.cancel_pick()


def _menus(monkeypatch):
    shown = []
    monkeypatch.setattr(QMenu, "exec_", lambda self, *a: shown.append(
        [a.text() for a in self.actions() if a.text()]))
    return shown


def test_a_right_click_opens_the_menu_and_a_right_drag_pans(window,
                                                            monkeypatch):
    """SolidWorks: the middle drag pans, a right CLICK is the menu."""
    shown = _menus(monkeypatch)
    view = window.view3d
    view.resize(400, 300)
    p = view.rect().center()
    QTest.mousePress(view, Qt.RightButton, Qt.NoModifier, p)
    QTest.mouseRelease(view, Qt.RightButton, Qt.NoModifier, p)
    assert len(shown) == 1
    assert "Zoom to Fit" in shown[0]
    target = list(view.target)
    QTest.mousePress(view, Qt.RightButton, Qt.NoModifier, p)
    from PyQt5.QtGui import QMouseEvent
    from PyQt5.QtCore import QEvent, QPoint
    q = p + QPoint(40, 0)
    view.mouseMoveEvent(QMouseEvent(QEvent.MouseMove, q, Qt.RightButton,
                                    Qt.RightButton, Qt.NoModifier))
    QTest.mouseRelease(view, Qt.RightButton, Qt.NoModifier, q)
    assert len(shown) == 1                       # a drag: no menu
    assert list(view.target) != target           # it panned


def test_a_smart_dimension_is_deleted_from_the_3d_menu(window,
                                                       monkeypatch):
    from PyQt5.QtCore import QPoint, QRectF
    from khervecad import sketch_constraints as sc, view3d_menu
    m = window.model
    g = m.add_node("union", {})
    m.add_node("line", dict(x1=0, y1=0, x2=10, y2=0), parent=g)
    sc.add(m, g, "length", ["0.l"], 12)
    assert len(sc.rows(g)) == 1
    window._dims3d_hits = [(QRectF(5, 5, 30, 14), g, 0)]
    menus = []
    monkeypatch.setattr(QMenu, "exec_", lambda self, *a: menus.append(self))
    view3d_menu.context_menu(window, QPoint(10, 10))
    acts = {a.text(): a for a in menus[0].actions()}
    assert "Edit value…" in acts
    acts["Delete dimension"].trigger()
    assert sc.rows(g) == []


def test_model_edges_explain_themselves_and_light_up(window):
    """The user found "Model edges" with no properties and nothing drawn."""
    from khervecad import sketch_section
    m = window.model
    g = m.add_node("union", {})
    poly = m.add_node("polygon", dict(points=[[0, 0], [30, 0], [30, 20]],
                                      modifier="%"), parent=g)
    poly.name = sketch_section.NAME
    QApplication.processEvents()
    window.builder.active_tree().select_nodes([poly])
    window._tree_selected([poly])
    QApplication.processEvents()
    texts = [w.text() for w in window.properties.findChildren(
        __import__("PyQt5.QtWidgets", fromlist=["QLabel"]).QLabel)]
    assert any("construction" in t for t in texts)
    window._highlight_tris_now({poly.id})
    assert window.view3d.selection_lines            # drawn on the model
    assert window.view3d.selection_labels
    assert poly.params["modifier"] == "%"           # mark put back
