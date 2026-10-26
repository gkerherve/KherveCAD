# Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later
"""Picking SolidWorks' Front / Top / Right Plane to sketch on."""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import normal_to, plane_pick
from khervecad.tree_history import ROLE_FIXED


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from PyQt5.QtCore import QSettings
    QSettings("Kherve", "KherveCAD").setValue("tree/planes", True)
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(1200, 800)
    win.show()
    app.processEvents()
    yield win
    win._dirty = False
    win.close()


def _turned(monkeypatch):
    got = []
    monkeypatch.setattr(normal_to, "turn_to",
                        lambda w, plane, *a, **k: got.append(plane))
    return got


def test_the_tree_lists_the_three_planes_by_their_solidworks_names(window):
    tree = window.builder.tree
    names = []
    for i in range(tree.topLevelItemCount()):
        top = tree.topLevelItem(i)
        for j in range(top.childCount()):
            role = top.child(j).data(0, ROLE_FIXED) or ""
            if role.startswith("plane:"):
                names.append(top.child(j).text(0))
    assert names == ["Front Plane", "Top Plane", "Right Plane"]


def test_a_selected_plane_row_is_where_the_sketch_starts(window,
                                                          monkeypatch):
    got = _turned(monkeypatch)
    tree = window.builder.tree
    origin = tree.topLevelItem(0)
    origin.child(2).setSelected(True)          # Right Plane
    normal_to.create(window)
    assert got == ["Side (YZ)"]


def test_with_nothing_selected_the_planes_are_clicked_in_3d(window,
                                                             monkeypatch):
    got = _turned(monkeypatch)
    window.builder.tree.clearSelection()
    normal_to.create(window)
    assert plane_pick.active(window)
    window.view3d.repaint()                     # lays the planes out
    polys = window._plane_pick["polys"]
    assert {p for p, _n, _poly in polys} == {
        "Front (XZ)", "Top (XY)", "Side (YZ)"}
    plane, _n, poly = max(polys, key=lambda t: plane_pick._area(t[2]))
    centre = poly.boundingRect().center()
    # a point inside it, nearer one corner than the shared middle
    pt = (centre + poly.at(2)) / 2
    assert plane_pick.press(window, pt.toPoint())
    assert got and not plane_pick.active(window)


def test_esc_or_select_cancels_the_plane_pick(window):
    from khervecad import stop_tool
    plane_pick.start(window)
    assert stop_tool.stop(window)
    assert not plane_pick.active(window)
