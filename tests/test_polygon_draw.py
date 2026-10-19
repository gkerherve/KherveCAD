"""Drawing a polygon in the 2D view: every way to finish it, and no
half-drawn line left behind when the tool changes.

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

from khervecad.model import DocumentModel
from khervecad.view2d import LINE, POLYGON, RECT, SketchScene, SketchView


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def view(app):
    scene = SketchScene(DocumentModel())
    v = SketchView(scene)
    v.resize(600, 500)
    v.show()
    v.centerOn(20, 20)
    v.set_tool(POLYGON)
    yield v
    v.close()


def _click(view, x, y, button=Qt.LeftButton):
    QTest.mouseClick(view.viewport(), button, Qt.NoModifier,
                     view.mapFromScene(QPointF(x, y)))


def _polygons(view):
    return [n for n in view.scene().model.root.walk()
            if n.type == "polygon"]


def _leftovers(view):
    return [i for i in view.scene().items() if i.zValue() >= 1e6]


def test_right_click_finishes(view):
    for x, y in ((0, 0), (40, 0), (40, 30)):
        _click(view, x, y)
    assert view.polygon_bar.isVisible()
    _click(view, 10, 30, Qt.RightButton)
    assert len(_polygons(view)) == 1
    assert len(_polygons(view)[0].params["points"]) == 3
    assert not view.polygon_bar.isVisible() and not _leftovers(view)


def test_clicking_the_first_point_closes_it(view):
    for x, y in ((0, 0), (40, 0), (40, 30), (0, 30)):
        _click(view, x, y)
    _click(view, 0.3, 0.2)                 # within a few pixels of it
    assert len(_polygons(view)[0].params["points"]) == 4
    assert not _leftovers(view)


def test_the_bar_finishes_undoes_and_cancels(view):
    bar = view.polygon_bar
    _click(view, 0, 0)
    _click(view, 40, 0)
    assert bar.isVisible() and not bar.finish.isEnabled()
    assert "2 points" in bar.label.text()
    _click(view, 40, 30)
    _click(view, 20, 45)
    assert bar.finish.isEnabled()
    bar.undo.click()                        # 3 points left
    QTest.keyClick(view.viewport(), Qt.Key_Backspace)
    assert len(view.scene()._poly_points) == 2
    _click(view, 40, 30)
    bar.finish.click()
    assert len(_polygons(view)[0].params["points"]) == 3
    _click(view, 0, 0)
    bar.cancel.click()
    assert not bar.isVisible() and not _leftovers(view)
    assert len(_polygons(view)) == 1


def test_changing_tool_leaves_no_dead_line(view):
    """The bug: two polygon points, then another tool — the rubber band
    stayed on the sketch as a line nothing could select or delete."""
    _click(view, 0, 0)
    _click(view, 40, 0)
    view.set_tool(RECT)
    assert not _leftovers(view) and not view.scene()._poly_points
    assert not view.polygon_bar.isVisible()
    # a line being dragged when the tool changes goes too
    view.set_tool(LINE)
    QTest.mousePress(view.viewport(), Qt.LeftButton, Qt.NoModifier,
                     view.mapFromScene(QPointF(0, 0)))
    assert view.scene()._draft is not None
    view.set_tool(POLYGON)
    assert view.scene()._draft is None
    from PyQt5.QtWidgets import QGraphicsLineItem
    assert not [i for i in view.scene().items()
                if isinstance(i, QGraphicsLineItem)]
    assert not _polygons(view)
