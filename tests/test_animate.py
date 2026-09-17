"""$t animation (animate.py): the time reaches expressions, OpenSCAD runs
and exact-mesh keys, and never the document."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import animate, engine, expr, mesh
from khervecad.model import DocumentModel
from khervecad.scadparse import parse_scad


@pytest.fixture(autouse=True)
def reset_time():
    yield
    expr.SPECIAL_DEFAULTS["$t"] = 0
    engine.DEFINES.pop("$t", None)


def test_time_moves_the_preview_not_the_document():
    root, _ = parse_scad("translate([100 * $t, 0, 0]) cube(1);")
    model = DocumentModel()
    model.root = root
    code = model.to_scad()
    assert animate.uses_time(root)
    animate.set_time(None, 0.25)
    xs = [v[0] for tri in mesh.tessellate(root) for v in tri]
    assert min(xs) == pytest.approx(25)
    assert engine.DEFINES == {"$t": "0.25"}
    assert "-D" in engine.openscad_args("openscad", "o.stl", "i.scad")
    assert model.to_scad() == code                 # not written in
    animate.set_time(None, 0)
    assert engine.DEFINES == {}


def test_animated_parts_key_by_time():
    model = DocumentModel()
    comp = model.new_component("Arm")
    model.add_node("rotate", dict(x=0.0, y=0.0, z="360 * $t"), parent=comp)
    still = model.new_component("Base")
    model.add_node("cube", parent=still)
    k0, s0 = mesh.exact_key(comp), mesh.exact_key(still)
    animate.set_time(None, 0.5)
    assert mesh.exact_key(comp) != k0
    assert mesh.exact_key(still) == s0


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_panel_and_mcp_set_the_time(app):
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    win = MainWindow()
    try:
        panel = animate.open_panel(win)
        panel.steps.setValue(4)
        panel.slider.setValue(2)
        assert animate.current_time() == 0.5
        panel.close()
        assert animate.current_time() == 0
        ex = McpToolExecutor(win)
        assert "error" not in ex.execute("set_render_options", {"time": 0.75})
        assert animate.current_time() == 0.75
    finally:
        win._dirty = False
        win.close()
