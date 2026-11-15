"""The surface tools' windows by mouse (surface_tool.py): select the
surfaces in the tree, press the tool, click pieces / edges in the 3D
view, OK.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad import cadexchange as cx, curve_surface as cs, \
    surface_edit as se, surface_tool as st
from khervecad.mainwindow import MainWindow

pytestmark = pytest.mark.skipif(not cx.occ_available(),
                                reason="OpenCascade not installed")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def circle(cx_, cy, cz, r, n=24):
    return [[cx_ + r * math.cos(2 * math.pi * i / n), cy,
             cz + r * math.sin(2 * math.pi * i / n)] for i in range(n)]


@pytest.fixture
def win(app):
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    QTest.qWaitForWindowExposed(w)
    m = w.model
    # two crossing tubes: one along Y (centre x=0), one along X
    a = m.add_node("curve_surface", dict(
        cs._DEFAULTS, kind="extrude", height=100.0, direction="+Y",
        sheet=True), parent=m.root, name="TubeA")
    m.add_node("curve", dict(points=circle(0, -50, 0, 20), closed=True),
               parent=a)
    b = m.add_node("curve_surface", dict(
        cs._DEFAULTS, kind="extrude", height=100.0, direction="+X",
        sheet=True), parent=m.root, name="TubeB")
    m.add_node("curve", dict(points=[
        [-50, 20 * math.cos(2 * math.pi * i / 24),
         20 * math.sin(2 * math.pi * i / 24)] for i in range(24)],
        closed=True), parent=b)
    w._tubes = (a, b)
    yield w
    w._dirty = False
    w.close()


def _select(win, nodes):
    win.builder.active_tree().select_nodes(nodes)


def test_nothing_selected_says_what_to_do(win):
    assert st.start(win, "trim") is None
    assert "select" in win.statusBar().currentMessage().lower()


def test_trim_window_wraps_and_a_click_removes_a_piece(win):
    a, b = win._tubes
    _select(win, [a, b])
    panel = st.start(win, "trim")
    assert panel is not None
    node = win._surface_state["node"]
    assert node.type == "surface_edit" and node.params["op"] == "trim"
    assert [c.name for c in node.children] == ["TubeA", "TubeB"]
    # a mutual trim, then a real click on the 3D view where TubeA's
    # surface crosses the screen
    panel.fields["mutual"].setCurrentIndex(1)
    assert node.params["mutual"] is True
    world, m = st._own_meshes(win, node)
    view = win.view3d
    view.repaint()
    hit = None
    cam = view._camera()
    for t in world[::7]:
        c = [sum(v[i] for v in t) / 3 for i in range(3)]
        q = view._project(*cam, tuple(c))
        if q is not None:
            hit = (c, QPoint(int(q[0]), int(q[1])))
            break
    assert hit is not None
    before = len(node.params["remove"])
    QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, hit[1])
    assert len(node.params["remove"]) == before + 1
    st.ok(win)
    assert win._surface_state is None
    assert node.parent is not None


def test_cancel_takes_the_node_apart(win):
    a, b = win._tubes
    _select(win, [a, b])
    st.start(win, "knit")
    st.cancel(win)
    assert not any(n.type == "surface_edit" for n in win.model.root.walk())
    assert a.parent is win.model.root


def test_thicken_window_sets_the_wall(win):
    a, _b = win._tubes
    _select(win, [a])
    panel = st.start(win, "thicken")
    node = win._surface_state["node"]
    panel.fields["thickness"].setValue(3.0)
    assert node.params["thickness"] == 3.0
    from khervecad.model import validate
    assert validate(win.model.root).get(node.id) is None
    st.ok(win)


def test_tools_menu_lists_the_surface_edit_tools(win):
    labels = []
    for act in win.menuBar().actions():
        if "Tools" in act.text():
            for sub in act.menu().actions():
                if sub.menu() is not None and "Surface E" in sub.text():
                    labels = [a.text().replace("&", "")
                              for a in sub.menu().actions()]
    assert "Trim Surface" in labels and "Thicken" in labels
