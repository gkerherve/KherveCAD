"""Extrude end conditions: through all and up to an object.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import extent
from khervecad.model import DocumentModel


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_through_all_cuts_the_whole_body(app):
    m = DocumentModel()
    d = m.add_node("difference", {})
    m.add_node("cube", dict(width=40, depth=40, height=30), parent=d)
    t = m.add_node("translate", dict(x=20, y=20, z=10), parent=d)
    ex = m.add_node("linear_extrude", dict(height=1), parent=t)
    m.add_node("circle", dict(radius=4), parent=ex)
    extent.set_extent(m, ex, "through_all")
    # the body spans z -10..20 in the extrude's frame -> 2 * (20 + 1)
    assert ex.params["height"] == pytest.approx(42)
    assert ex.params["center"] is True
    d.children[0].params["height"] = 60       # the body grows
    extent.refresh(m)
    assert ex.params["height"] == pytest.approx(2 * 51)


def test_up_to_an_object(app):
    m = DocumentModel()
    roof = m.add_node("cube", dict(z=50, width=10, depth=10, height=5))
    roof.name = "Roof"
    ex = m.add_node("linear_extrude", dict(height=1))
    m.add_node("rect", dict(width=5, height=5), parent=ex)
    assert extent.set_extent(m, ex, "up_to", "Roof", "near") == \
        pytest.approx(50)
    assert extent.set_extent(m, ex, "up_to", "Roof", "far", 2) == \
        pytest.approx(57)
    with pytest.raises(ValueError):
        extent.set_extent(m, ex, "up_to", "Nobody")


def test_window_keeps_the_depth_live(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    try:
        m = win.model
        roof = m.add_node("cube", dict(z=50))
        roof.name = "Roof"
        ex = m.add_node("linear_extrude", dict(height=1))
        m.add_node("rect", {}, parent=ex)
        m.set_param(ex, "up_to", "Roof")
        m.set_param(ex, "extent", "up_to")
        assert ex.params["height"] == pytest.approx(70)
        m.set_param(roof, "z", 80)
        assert ex.params["height"] == pytest.approx(100)
    finally:
        win._dirty = False
        win.close()
