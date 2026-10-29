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

from PyQt5.QtCore import Qt
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
