"""A Center Rectangle drawn from the origin in a new sketch stays centred
when its sides are dimensioned (found filming Exercise 7, 2026-11-15:
92 x 68 came out with its centre at y = 3.3). The relation holding the
centre was written on the document root, then the rectangle was wrapped
into its new Object and the relation stayed behind.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest

from khervecad import sketch_constraints as sc
from test_lever_by_mouse import _at, _move, _open_top_sketch, win  # noqa


def _click(win, x, y):
    v2 = win.view2d
    p = _at(win, x, y)
    _move(v2.viewport(), p)
    QTest.mouseClick(v2.viewport(), Qt.LeftButton, Qt.NoModifier, p)
    QTest.qWait(30)


def test_center_rectangle_from_the_origin_stays_centred(win):
    _open_top_sketch(win)
    v2 = win.view2d
    v2.scene().snap_enabled = True
    v2.set_tool("rect_center")
    _click(win, 0, 0)
    _click(win, 20, 15)
    rect = next(n for n in win.model.root.walk() if n.type == "rect")
    kinds = [r["kind"] for r in sc.rows(rect.parent)]
    assert "fix" in kinds, kinds
    values = iter(["50", "34"])
    v2.scene().ask_value = lambda kind, measured: next(values)
    v2.set_tool("con_dimension")
    for edge, place in (((-5, 15), (-5, 22)), ((25, -5), (33, -5))):
        _click(win, *edge)
        _click(win, *place)
    p = rect.params
    assert float(p["width"]) == pytest.approx(50, abs=1e-4)
    assert float(p["height"]) == pytest.approx(34, abs=1e-4)
    assert float(p["x"]) == pytest.approx(-25, abs=1e-4)
    assert float(p["y"]) == pytest.approx(-17, abs=1e-4)
