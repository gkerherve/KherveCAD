# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""Unused sketch shapes are drawn as lines in 3D (2026-11-12, the user
could not see their trimmed rectangle)."""

import pytest
from PyQt5.QtWidgets import QApplication


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def test_loose_sketch_lines_are_drawn_in_3d(app):
    from khervecad.mainwindow import MainWindow
    from khervecad import free_sketch3d
    w = MainWindow()
    w.show()
    QApplication.processEvents()
    m = w.model
    obj = m.add_node("component", {}, name="Ex")
    obj.visible = True
    ext = m.add_node("linear_extrude", {"height": 10}, parent=obj)
    m.add_node("circle", dict(x=0, y=0, radius=10), parent=ext)
    m.add_node("line", dict(x1=-5, y1=-30, x2=5, y2=-30, width=0.2),
               parent=obj)
    m.add_node("line", dict(x1=0, y1=0, x2=0, y2=-40, width=0.5,
                            modifier="%"), parent=obj)    # construction
    w.builder.open_component(obj)
    QApplication.processEvents()
    loops = free_sketch3d._loops(w)
    assert len(loops) == 1                       # the line, not the rest
    ys = {round(p[1], 3) for p in loops[0]}
    assert ys and all(abs(y + 30) < 0.2 for y in ys)
    # Main: none drawn
    w.builder.setCurrentWidget(w.builder.widget(0))
    QApplication.processEvents()
    w._free_sketch_loops = None
    assert free_sketch3d._loops(w) == []
