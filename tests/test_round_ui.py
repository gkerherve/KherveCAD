"""Round an edge / push a face from the 3D view with nothing selected,
and the 3D view's right-click menu.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
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
