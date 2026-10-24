"""The tree's History view and fixed rows: another drawing of the same
nodes, never a change to the document.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from khervecad import tree_history
from khervecad.model import DocumentModel
from khervecad.treepanel import ObjectTree


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def _texts(item):
    return [item.child(i).text(0) for i in range(item.childCount())]


def _part(m):
    d = m.add_node("difference", {})
    e = m.add_node("linear_extrude", {}, parent=d)
    m.add_node("rect", {}, parent=e)
    m.add_node("cylinder", {}, parent=d)
    g = m.add_node("union", {})
    m.rename(g, "Bolts")
    m.add_node("sphere", {}, parent=g)
    return d, e, g


def test_fixed_rows_in_history_only(app):
    m = DocumentModel()
    _part(m)
    assert ObjectTree(m).topLevelItem(0).text(0) != "Origin"
    tree_history.set_enabled(True)
    try:
        tree = ObjectTree(m)
    finally:
        tree_history.set_enabled(False)
    top = _texts(tree.invisibleRootItem())
    assert top[0] == "Origin" and top[1].startswith("Material")
    origin = tree.topLevelItem(0)
    assert _texts(origin) == ["Front Plane", "Top Plane", "Right Plane"]
    picked = []
    tree.plane_picked.connect(picked.append)
    tree._double_clicked(origin.child(1), 0)
    assert picked == ["Top (XY)"]


def test_history_lists_features_in_order_and_keeps_groups(app):
    tree_history.set_enabled(True)
    try:
        m = DocumentModel()
        d, e, g = _part(m)
        before = m.to_scad()
        tree = ObjectTree(m)
        top = _texts(tree.invisibleRootItem())[2:]
        assert top[:3] == ["Extrude 1", "Cylinder 1", "Cut 1"]
        assert top[3] == "Bolts"                     # the group, a folder
        assert _texts(tree.topLevelItem(5)) == ["Sphere 1"]
        assert _texts(tree.topLevelItem(2)) == ["Rectangle"] or \
            len(_texts(tree.topLevelItem(2))) == 1   # the sketch, tucked
        assert m.to_scad() == before                 # nothing changed
        # a row selects its node
        tree.topLevelItem(4).setSelected(True)
        assert tree.selected_nodes() == [d]
    finally:
        tree_history.set_enabled(False)


def test_material_row_sets_every_part(app):
    m = DocumentModel()
    _part(m)
    tree_history.set_enabled(True)
    tree = ObjectTree(m)
    try:
        tree_history.set_material(tree, "Metal")
    finally:
        tree_history.set_enabled(False)
    assert all(n.type == "color" and n.params["material"] == "Metal"
               for n in m.root.children)
    tree_history.set_enabled(True)
    try:
        tree.rebuild()
        assert "Metal" in tree.topLevelItem(1).text(0)
    finally:
        tree_history.set_enabled(False)


def test_origin_and_plane_rows_act_in_the_window():
    from khervecad.mainwindow import MainWindow
    QApplication.instance() or QApplication([])
    w = MainWindow()
    w.show()
    tree_history.set_enabled(True)
    try:
        w.model.add_node("cube", {})
        tree = w.builder.tree
        tree.rebuild()
        origin = tree.topLevelItem(0)
        view = w.view3d
        before = view.axes
        tree_history.clicked(tree, origin)
        assert view.axes != before                   # axes toggled
        tree_history.double_clicked(tree, origin.child(0))
        assert w.scene.plane == "Front (XZ)"
        assert (view.yaw, view.pitch) == pytest.approx((-90.0, 0.0))
    finally:
        tree_history.set_enabled(False)
        w._dirty = False
        w.close()
