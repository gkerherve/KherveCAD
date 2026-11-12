# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""Set Origin Here (origin_tool): a clicked sketch point becomes the
Object's 0, 0, 0 and nothing moves (2026-11-12, the user)."""

import pytest
from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app):
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    QApplication.processEvents()
    return w


def _world_box(win, node):
    from khervecad import mesh
    tris = mesh.transform_mesh(mesh.ancestor_matrix(node, {}),
                               mesh.tessellate(node, {}))
    return [round(f(v[i] for t in tris for v in t), 4)
            for i in range(3) for f in (min, max)]


def test_a_clicked_corner_becomes_the_origin(win):
    from khervecad import sketch_constraints as sc
    m = win.model
    obj = m.add_node("component", {}, name="Part")
    obj.visible = True
    rect = m.add_node("rect", dict(x=12.0, y=7.0, width=30, height=20),
                      parent=obj, name="Base")
    sc.add(m, obj, "length", [sc.ref_of(obj, rect, "e0")], 30.0)
    win.builder.open_component(obj)
    QApplication.processEvents()
    before = _world_box(win, obj)
    view = win.view2d
    scene = view.scene()
    scene.set_tool("sk_origin") if hasattr(scene, "set_tool") else \
        setattr(scene, "tool", "sk_origin")
    corner = view.mapFromScene(QPointF(12.0, 7.0))
    QTest.mouseClick(view.viewport(), Qt.LeftButton, Qt.NoModifier, corner)
    QApplication.processEvents()
    shift = obj.children[0]
    assert shift.name == "Origin shift"
    assert (shift.params["x"], shift.params["y"]) == (-12.0, -7.0)
    assert (obj.params["x"], obj.params["y"]) == (12.0, 7.0)
    assert _world_box(win, obj) == before          # nothing moved
    assert sc.rows(shift) and not sc.rows(obj)     # dimension kept
