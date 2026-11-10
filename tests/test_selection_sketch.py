# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""A selected sketch outlines its shapes in 3D, even when the solid it
made is buried in the part and the depth-tested tint has nothing to
paint."""
import pytest
from PyQt5.QtTest import QTest

from khervecad import selection_sketch


_APP = None


@pytest.fixture
def win():
    global _APP
    from PyQt5.QtWidgets import QApplication
    _APP = QApplication.instance() or QApplication([])
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    QTest.qWait(50)
    yield w
    w._dirty = False
    w.close()


def test_selected_sketch_outlines_its_shapes(win):
    m = win.model
    block = m.add_node("cube")
    m.set_param(block, "width", 40)
    m.set_param(block, "depth", 40)
    m.set_param(block, "height", 20)
    sketch = m.add_node("union")
    sketch.params["face_sketch"] = True
    ext = m.add_node("linear_extrude", parent=sketch)
    circle = m.add_node("circle", parent=ext)
    m.set_param(circle, "x", 20)
    m.set_param(circle, "y", 20)
    m.set_param(ext, "height", 5)          # wholly inside the block
    QTest.qWait(50)
    assert selection_sketch.shape_ids(m, {sketch.id}) == [circle.id]
    assert selection_sketch.shape_ids(m, {ext.id}) == []   # its solid
    win.builder.active_tree().select_nodes([sketch])
    QTest.qWait(50)
    win._highlight_tris()
    assert win.view3d.selection_lines, "the sketch is not outlined"
    # a plain solid outlines nothing
    win.builder.active_tree().select_nodes([block])
    QTest.qWait(50)
    win._highlight_tris()
    assert not win.view3d.selection_lines
