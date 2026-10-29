"""Clicking a line a Difference cuts away in the tree, then another row:
Properties follows (2026-10-29, the user: "nothing changed in the
property"). The line has no fill, so dashing it raised half way through
the selection, and the guard stayed on — every later click was ignored.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication([])


def test_properties_follow_after_a_cut_line_is_clicked():
    from khervecad.mainwindow import MainWindow
    from khervecad import scadparse
    w = MainWindow()
    w.show()
    QTest.qWait(50)
    try:
        model = w.model
        ext = model.add_node("linear_extrude", {"height": 5})
        diff = model.add_node("difference", {}, parent=ext)
        model.add_node("rect", {"width": 40, "height": 20}, parent=diff)
        model.add_node("line", {"x1": 5, "y1": 10, "x2": 35, "y2": 10},
                       parent=diff)
        model.add_node("cube", {})
        QTest.qWait(50)
        nodes = list(model.root.walk())
        line = next(n for n in nodes if n.type == "line")
        cube = next(n for n in nodes if n.type == "cube")
        tree = w.builder.active_tree()
        tree.select_nodes([line])
        QTest.qWait(30)
        assert w.properties.node is line
        assert not w._syncing
        tree.select_nodes([cube])
        QTest.qWait(30)
        assert w.properties.node is cube
    finally:
        w._dirty = False
        w.close()


def test_a_polygon_with_paths_draws_separate_loops():
    """A part section kept in a sketch (outline + two holes) drew a
    stray slanted line from one loop to the next (the user, 2026-10-29)."""
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    w.show()
    QTest.qWait(50)
    try:
        pts = [[0, 0], [40, 0], [40, 40], [0, 40],
               [10, 10], [10, 15], [15, 15], [15, 10],
               [25, 25], [25, 30], [30, 30], [30, 25]]
        node = w.model.add_node("polygon", {
            "points": pts, "paths": [[0, 1, 2, 3], [4, 5, 6, 7],
                                     [8, 9, 10, 11]]})
        QTest.qWait(50)
        w.builder.active_tree().select_nodes([node])
        QTest.qWait(30)
        item = w.scene._items[node.id]
        path = item.shape()
        # three closed loops, no line from one to the next
        polys = path.toSubpathPolygons()
        assert len(polys) == 3
        assert not path.contains(QPointF(12.5, 12.5))   # a hole stays open
        assert path.contains(QPointF(5, 5))
        w.view2d.viewport().repaint()
    finally:
        w._dirty = False
        w.close()
