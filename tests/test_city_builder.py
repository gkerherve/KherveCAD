"""City Builder window, driven with real mouse events: select a piece
with any tool, drag it, turn it with its handle through the whole 360°,
rubber-band several, place library pieces (a park, a traffic light) and
build them, and pick up pieces moved in the main window.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QPoint, QPointF, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad import city, city_items as CI


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def panel(app):
    from khervecad import city_dialog
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(900, 700)
    p = city_dialog.open_builder(win)
    p.resize(1300, 820)
    p.show()
    QApplication.processEvents()
    yield p
    p.close()          # not the main window: it would ask to save


def _view_point(panel, x, y):
    view = panel.canvas
    return view.mapFromScene(QPointF(x, y))


def _click(panel, x, y, modifier=Qt.NoModifier):
    QTest.mouseClick(panel.canvas.viewport(), Qt.LeftButton, modifier,
                     _view_point(panel, x, y))
    QApplication.processEvents()


def _drag(panel, start, end, modifier=Qt.NoModifier, steps=6):
    """Press, move with the button HELD (QTest.mouseMove sends none, so
    Qt never starts a drag) and release."""
    from PyQt5.QtCore import QEvent
    from PyQt5.QtGui import QMouseEvent
    vp = panel.canvas.viewport()
    QTest.mousePress(vp, Qt.LeftButton, modifier, start)
    for k in range(1, steps + 1):
        pos = start + (end - start) * k / steps
        ev = QMouseEvent(QEvent.MouseMove, QPointF(pos), Qt.NoButton,
                         Qt.LeftButton, modifier)
        QApplication.sendEvent(vp, ev)
    QTest.mouseRelease(vp, Qt.LeftButton, modifier, end)
    QApplication.processEvents()


def _house(panel, x=0.0, y=0.0):
    panel.style_combo.setCurrentText("house")
    panel._place("building", QPointF(x, y))
    panel.canvas.fit()
    QApplication.processEvents()
    return panel.spec["buildings"][-1]


def test_a_click_selects_a_piece_even_with_a_placing_tool(panel):
    house = _house(panel)
    panel.canvas.scene().clearSelection()
    panel.set_tool("building")
    _click(panel, 0, 0)
    assert len(panel.spec["buildings"]) == 1          # nothing placed
    assert panel.selected is house
    _click(panel, 0, 0, Qt.ShiftModifier)             # Shift places anyway
    assert len(panel.spec["buildings"]) == 2


def test_drag_moves_and_handle_turns_through_360(panel):
    house = _house(panel)
    panel.set_tool("select")
    item = panel.canvas.items_by_id[id(house)]
    item.setSelected(True)
    QApplication.processEvents()
    start = _view_point(panel, 0, 0)
    end = _view_point(panel, 12000, 3000)
    _drag(panel, start, end)
    assert abs(house["x"] - 12000) < 600 and abs(house["y"] - 3000) < 600
    handle = item._handle
    assert handle is not None
    # drag the handle a quarter turn round the house: its front turns
    # to face +X (rz 90)
    item_pos = item.scenePos()
    grip = _view_point(panel, item_pos.x() + 0, item_pos.y() - 9000)
    _drag(panel, panel.canvas.mapFromScene(handle.scenePos()),
          _view_point(panel, item_pos.x() + 9000, item_pos.y()))
    assert house["rz"] == 90.0, house["rz"]
    handle.owner.turn_to(CI.wrap(-90))
    assert house["rz"] == 270.0
    handle.owner.turn_to(CI.wrap(360))
    assert house["rz"] == 0.0
    panel._rotate_selected(350)
    assert house["rz"] == 350.0
    panel._rotate_selected(20)
    assert house["rz"] == 10.0
    assert panel.b_rz.maximum() == 360.0 and panel.b_rz.wrapping()


def test_rubber_band_selects_several_and_delete_removes_them(panel):
    _house(panel, 0, 0)
    _house(panel, 20000, 0)
    panel._place("tree", QPointF(40000, 20000))
    panel.canvas.fit()
    panel.set_tool("select")
    QApplication.processEvents()
    a = _view_point(panel, -12000, -12000)
    b = _view_point(panel, 32000, 12000)
    _drag(panel, a, b, Qt.ShiftModifier)
    selected = panel._selected_specs()
    assert len([s for s in selected if s in panel.spec["buildings"]]) == 2
    panel._remove_selected()
    assert not panel.spec["buildings"] and len(panel.spec["trees"]) == 1


def test_library_pieces_place_turn_and_build(panel):
    panel._add_road([[-40000, 0], [40000, 0]])
    idx = panel.prop_combo.findData("signal_traffic")
    panel.prop_combo.setCurrentIndex(idx)
    panel._place("prop", QPointF(5000, 6000))
    light = panel.spec["props"][-1]
    assert light["part_id"] == "signal_traffic" and light["dims"]
    panel._rotate_selected(90)
    idx = panel.prop_combo.findData("park_bench")
    panel.prop_combo.setCurrentIndex(idx)
    panel._place("prop", QPointF(-5000, 6000))
    panel._build()
    model = panel.window.model
    names = [c.name for c in model.root.children]
    assert "City props" in names
    assert [p["part_id"] for p in model.city["props"]] == ["signal_traffic",
                                                          "park_bench"]


def test_pieces_moved_in_the_main_window_come_back(panel):
    _house(panel, 0, 0)
    panel._build()
    model = panel.window.model
    comp = next(c for c in model.root.children if c.name == "City buildings")
    placed = next(n for n in comp.walk() if n.type == "translate"
                  and n.name == model.city["buildings"][0]["name"])
    placed.params["x"] = 7777.0
    placed.children[0].params["z"] = 45.0
    assert city.sync_from_document(model) == 1
    assert model.city["buildings"][0]["x"] == 7777.0
    assert model.city["buildings"][0]["rz"] == 45.0
    panel.load_from_document(force=True)
    assert panel.spec["buildings"][0]["x"] == 7777.0
