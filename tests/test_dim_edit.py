"""Clicking a dimension label in 2D types the size.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import dim_edit
from khervecad.model import DocumentModel

_APP = QApplication.instance() or QApplication([])


def test_apply_each_kind():
    m = DocumentModel()
    r = m.add_node("rect", dict(width=10, height=5))
    dim_edit.apply(m, r, "width", None, 30)
    assert r.params["width"] == 30
    c = m.add_node("circle", dict(radius=2))
    dim_edit.apply(m, c, "diameter", None, 12)
    assert c.params["radius"] == 6
    ln = m.add_node("line", dict(x1=0, y1=0, x2=3, y2=4))
    dim_edit.apply(m, ln, "length", None, 10)
    assert (ln.params["x2"], ln.params["y2"]) == pytest.approx((6, 8))
    poly = m.add_node("polygon", dict(points=[[0, 0], [10, 0], [10, 10],
                                              [0, 10]]))
    dim_edit.apply(m, poly, "edge", 0, 25)
    assert dim_edit.current(poly, "edge", 0) == pytest.approx(25, abs=1e-3)
    dim_edit.apply(m, poly, "edge", 0, 20)       # the same dimension, set
    assert dim_edit.current(poly, "edge", 0) == pytest.approx(20, abs=1e-3)
    with pytest.raises(ValueError):
        dim_edit.apply(m, r, "height", None, 0)


def test_click_the_label_and_type(monkeypatch):
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    try:
        r = w.model.add_node("rect", dict(width=20, height=10))
        v2 = w.view2d
        v2.scene().show_dims = True
        v2.frame_rect(v2.scene().itemsBoundingRect())
        for _ in range(3):
            _APP.processEvents()
        v2.viewport().grab()                       # paints the labels
        width_chips = [rect for rect, ctx in v2._dim_hits
                       if ctx[0] is r and ctx[1] == "width"]
        assert width_chips
        c = width_chips[0].center()
        from PyQt5.QtCore import QPoint
        assert dim_edit.press(v2, QPoint(int(c.x()), int(c.y())))
        box = v2._dim_editor
        assert box.text() == "20"
        box.setText("35")
        box.returnPressed.emit()
        assert r.params["width"] == 35
    finally:
        w._dirty = False
        w.close()
