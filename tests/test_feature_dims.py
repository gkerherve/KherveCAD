# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""Feature dimensions (an extrude's depth, a revolve's angle) on the 3D
view, typed in place, and dimensions LINKED by clicking another while
one is typed (2026-11-10, the user)."""
import pytest
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtTest import QTest

from khervecad import dim_link, feature_dims
from khervecad import sketch_constraints as sc


@pytest.fixture
def win():
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    QTest.qWait(50)
    yield w
    w._dirty = False
    w.close()


def _plate(win):
    m = win.model
    ext = m.add_node("linear_extrude", dict(height=10))
    rect = m.add_node("rect", dict(x=0, y=0, width=40, height=20),
                      parent=ext)
    rev = m.add_node("rotate_extrude", dict(angle=270))
    m.add_node("rect", dict(x=50, y=0, width=5, height=10), parent=rev)
    QTest.qWait(50)
    return ext, rect, rev


def _paint(win):
    win.view3d.repaint()
    QTest.qWait(10)


def test_selected_features_show_their_dimensions(win):
    ext, rect, rev = _plate(win)
    win.builder.active_tree().select_nodes([ext])
    QTest.qWait(50)
    dims = feature_dims.dimensions(win)
    assert [(d[1], d[2]) for d in dims] == [("height", "10")]
    a0, a1, _d0, _d1 = dims[0][4]
    assert a0[2] == pytest.approx(0) and a1[2] == pytest.approx(10)
    win.builder.active_tree().select_nodes([rev])
    QTest.qWait(50)
    assert [(d[1], d[2]) for d in feature_dims.dimensions(win)] == \
        [("angle", "270°")]
    _paint(win)
    assert win._feature_dim_hits and win._feature_dim_hits[0][2] == "angle"


def test_two_directions_show_both_depths(win):
    ext, rect, rev = _plate(win)
    win.model.set_param(ext, "height2", 4)
    win.builder.active_tree().select_nodes([ext])
    QTest.qWait(50)
    assert [d[1] for d in feature_dims.dimensions(win)] == \
        ["height", "height2"]


def test_typing_a_new_depth(win):
    ext, rect, rev = _plate(win)
    win.builder.active_tree().select_nodes([ext])
    QTest.qWait(50)
    _paint(win)
    rect_, node, key = win._feature_dim_hits[0]
    box = feature_dims.edit(win, rect_, node, key)
    box.setText("12 + 3")
    QTest.keyClick(box, Qt.Key_Return)
    QTest.qWait(30)
    assert ext.params["height"] == pytest.approx(15)
    assert win.view3d._dim3d_editor is None


def test_clicking_another_dimension_links_to_it(win):
    ext, rect, rev = _plate(win)
    m = win.model
    # the rectangle's width as a Smart Dimension of its sketch
    sc.add(m, ext, "length", [sc.ref_of(ext, rect, "e0")], 40)
    win.builder.active_tree().select_nodes([rev])
    QTest.qWait(50)
    _paint(win)
    rect_, node, key = win._feature_dim_hits[0]
    assert key == "angle"
    box = feature_dims.edit(win, rect_, node, key)
    QTest.qWait(10)
    _paint(win)                     # typing: every feature's dims show
    target = next(h for h in win._feature_dim_hits if h[2] == "height")
    pos = target[0].center()
    assert dim_link.press(win, QPoint(int(pos.x()), int(pos.y())))
    assert dim_link.release(win, QPoint(int(pos.x()), int(pos.y())))
    name = box.text()
    assert ext.params["height"] == name                  # now a variable
    assert any(n.params.get("variable") == name
               for n in m.global_assigns())
    box.setText(name + " * 20")
    QTest.keyClick(box, Qt.Key_Return)
    QTest.qWait(30)
    assert rev.params["angle"] == name + " * 20"
    # change the depth's variable: the angle follows
    var = next(n for n in m.global_assigns()
               if n.params.get("variable") == name)
    m.set_param(var, "value", 12)
    assert feature_dims._num(rev, "angle", feature_dims._env(win), 0) == \
        pytest.approx(240)


def test_link_to_a_sketch_dimension(win):
    ext, rect, rev = _plate(win)
    m = win.model
    sc.add(m, ext, "length", [sc.ref_of(ext, rect, "e0")], 40)
    index = len(sc.rows(ext)) - 1
    name = dim_link.link(win, ("feature", ext, "height"),
                         ("sketch", ext, index))
    assert sc.rows(ext)[index]["value"] == name
    assert ext.params["height"] == name
    assert feature_dims._num(ext, "height", feature_dims._env(win), 0) == \
        pytest.approx(40)


def test_mcp_links_a_revolve_angle_to_an_extrude_depth(win):
    from khervecad.mcp_tools import McpToolExecutor
    ext, rect, rev = _plate(win)
    got = McpToolExecutor(win).execute("sketch_constraint", {
        "action": "link", "node_id": ext.id, "feature_id": rev.id,
        "key": "angle", "source_feature_id": ext.id,
        "source_key": "height"})
    name = got["variable"]
    assert rev.params["angle"] == name and ext.params["height"] == name
