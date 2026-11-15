# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""SolidWorks' Deform > Curve to curve BY MOUSE (2026-11-15): the ribbon
button opens a window; the initial curve, the target curve and the body
are clicked in the tree; OK bends the body."""

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QToolButton


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app):
    from khervecad.mainwindow import MainWindow
    from khervecad import toolbar_style
    w = MainWindow()
    w.resize(1500, 950)
    toolbar_style.apply(w, "SolidWorks", remember=False)
    w.show()
    QTest.qWaitForWindowExposed(w)
    w.ribbon.show_tab("features")
    QTest.qWait(50)
    yield w
    toolbar_style.apply(w, "KherveCAD", remember=False)
    w._dirty = False
    w.close()


def _find_button(win, key):
    for b in win.findChildren(QToolButton):
        a = b.defaultAction()
        if a is not None and a.data() == key and b.isVisible():
            return b
    return None


def _scene(win):
    """A rod with its centre line (revolved), and an S-ish target sketch."""
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(win)

    def sk(label):
        n = ex.execute("reference_geometry", dict(
            action="sketch", origin=[0, 0, 0],
            normal=[0, -1, 0]))["sketch_id"]
        ex.execute("set_params", dict(changes=[{"id": n, "name": label}]))
        return n

    def ln(parent, x1, y1, x2, y2):
        return ex.execute("add_node", dict(
            type="line", parent_id=parent,
            params=dict(x1=x1, y1=y1, x2=x2, y2=y2, width=0.2)))["created"]
    s1 = sk("Sketch1")
    for seg in ((0, 0, 0, 5), (0, 5, 60, 5), (60, 5, 60, 0), (0, 0, 60, 0)):
        ln(s1, *seg)
    axis = ln(s1, 0, 0, 60, 0)
    ex.execute("sketch_modify", dict(action="construction", node_id=axis))
    ex.execute("sketch_feature", dict(node_id=s1, kind="revolved_boss"))
    s6 = sk("Sketch6")
    ln(s6, 0, 0, 20, 0)
    ln(s6, 20, 0, 20, 20)
    ln(s6, 20, 20, 60, 20)
    return s1, s6


def test_deform_by_mouse_ribbon_button_tree_clicks_ok(win):
    from khervecad import analysis, mesh
    s1, s6 = _scene(win)
    node = lambda i: next(n for n in win.model.root.walk()   # noqa: E731
                          if n.id == i)
    tree = win.builder.active_tree()
    tree.clearSelection()
    button = _find_button(win, "curve_deform")
    assert button is not None, "the Deform button is on the ribbon"
    QTest.mouseClick(button, Qt.LeftButton)
    panel = win._deform_panel
    assert panel is not None and panel.isVisible()
    assert not panel.ok.isEnabled()
    tree.select_nodes([node(s1)])                   # box 1: initial curve
    assert win._deform_state["initial"] == [node(s1)]
    assert win._deform_state["active"] == "target"
    tree.select_nodes([node(s6)])                   # box 2: target curve
    assert win._deform_state["target"] == [node(s6)]
    assert win._deform_state["active"] == "bodies"
    assert not panel.ok.isEnabled()
    tree.select_nodes([node(s1)])                   # box 3: the rod
    assert panel.ok.isEnabled()
    QTest.mouseClick(panel.ok, Qt.LeftButton)
    assert getattr(win, "_deform_state", None) is None
    d = next(n for n in win.model.root.walk() if n.type == "curve_deform")
    assert d.params["target"][0][0] == pytest.approx(0, abs=1e-3)
    tris = [tuple(t[:3]) for t in mesh.tessellate(win.model.root)]
    zs = [p[2] for t in tris for p in t]
    assert max(zs) == pytest.approx(20 + 5, abs=1.0)   # the rod rose 20
    assert analysis.mass_properties(tris)["volume"] > 3000


def test_the_assistant_tool_makes_the_same_deform(win):
    from khervecad.mcp_tools import McpToolExecutor
    s1, s6 = _scene(win)
    out = McpToolExecutor(win).execute("deform_curve", dict(
        initial_id=s1, target_id=s6, body_ids=[s1]))
    d = next(n for n in win.model.root.walk() if n.id == out["deform_id"])
    assert d.type == "curve_deform" and len(d.params["target"]) == 4


def test_cancel_leaves_the_part_as_it_was(win):
    s1, s6 = _scene(win)
    before = sum(1 for _ in win.model.root.walk())
    tree = win.builder.active_tree()
    tree.clearSelection()
    QTest.mouseClick(_find_button(win, "curve_deform"), Qt.LeftButton)
    panel = win._deform_panel
    QTest.mouseClick(panel.cancel, Qt.LeftButton)
    assert getattr(win, "_deform_state", None) is None
    assert sum(1 for _ in win.model.root.walk()) == before
