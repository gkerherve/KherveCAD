"""Cut Through: the clipped and capped model, the 3D view's cut, and
everything that must keep seeing the whole part.

Run with: python -m pytest tests/  (offscreen Qt).

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
from PyQt5.QtWidgets import QApplication

from khervecad import analysis, cutaway, mesh, pngexport, scadparse
from khervecad.model import CadNode


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(900, 650)
    win._confirm_discard = lambda: True
    root, _w = scadparse.parse_scad(
        "cube([40, 30, 20]); translate([20, 15, 20]) cylinder(h=10, r=5);")
    win.model.root = root
    win.model.structure_changed.emit()
    win._refresh_preview()
    yield win
    win._dirty = False
    win.close()


def _ring():
    return mesh.tessellate(scadparse.parse_scad(
        "rotate_extrude($fn=64) translate([6, 0]) square([4, 30]);")[0])


def test_half_a_box_is_a_closed_solid_of_half_the_volume(app):
    box = mesh.tessellate(CadNode("cube", "b", dict(width=40, depth=30,
                                                    height=20)))
    for axis in "xyz":
        for flip in (False, True):
            tris, colors, offset = cutaway.apply(box, None, axis, 0.5, flip)
            assert analysis.mass_properties(tris)["volume"] == \
                pytest.approx(12000.0), (axis, flip)
            assert colors[-1] == cutaway.CAP_COLOR
            assert offset == {"x": 20.0, "y": 15.0, "z": 10.0}[axis]


def test_a_tube_caps_as_a_ring_with_the_bore_left_open(app):
    ring = _ring()
    cap = cutaway.caps(ring, "z", 15.0)
    area = sum(((b[0] - a[0]) * (c[1] - a[1])
                - (b[1] - a[1]) * (c[0] - a[0])) / 2.0 for a, b, c in cap)
    assert area == pytest.approx(math.pi * (10 ** 2 - 6 ** 2), rel=0.01)
    # facing up, towards the half taken away
    assert all(((b[0] - a[0]) * (c[1] - a[1])
                - (b[1] - a[1]) * (c[0] - a[0])) > 0 for a, b, c in cap)
    tris, _c, _o = cutaway.apply(ring, None, "y", 0.5)
    assert analysis.mass_properties(tris)["volume"] == pytest.approx(
        math.pi * (10 ** 2 - 6 ** 2) * 30 / 2.0, rel=0.01)


def test_fill_leaves_holes_open(app):
    square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    hole = [(3.0, 3.0), (3.0, 7.0), (7.0, 7.0), (7.0, 3.0)]
    tris = cutaway.fill([square, hole])
    area = sum(((b[0] - a[0]) * (c[1] - a[1])
                - (b[1] - a[1]) * (c[0] - a[0])) / 2.0 for a, b, c in tris)
    assert area == pytest.approx(100.0 - 16.0)


def test_the_3d_view_cuts_and_puts_it_back(window):
    view = window.view3d
    whole = len(view.model_mesh)
    window.set_cut(True, axis="z")
    assert view.cut_state()["axis"] == "z"
    assert len(view.model_mesh) == whole                    # untouched
    assert view.mesh != view.model_mesh
    top = max(p[2] for t in view.mesh for p in t)
    assert top == pytest.approx(view.cut_state()["offset"])
    assert not view.cut_bar.isHidden()
    assert window._cut_act.isChecked() and window._cut_tool_act.isChecked()
    view.cut_bar.slider.setValue(250)                       # the bar moves it
    assert view.cut_state()["position"] == pytest.approx(0.25)
    window.set_cut(False)
    assert view.cut_state() is None and view.mesh == view.model_mesh
    assert view.cut_bar.isHidden()
    assert not window._cut_act.isChecked()
    assert not window._cut_tool_act.isChecked()


def test_the_toolbar_button_switches_it(window):
    window._cut_tool_act.trigger()
    assert window.view3d.cut_state() is not None
    window._cut_tool_act.trigger()
    assert window.view3d.cut_state() is None


def test_a_new_model_is_cut_too(window):
    window.set_cut(True, axis="x", position=0.5)
    window.model.add_node("cube", dict(x=100, width=10, depth=10, height=10))
    view = window.view3d
    assert max(p[0] for t in view.model_mesh for p in t) == \
        pytest.approx(110.0)
    # the cut follows the new extent (0..110, middle 55): nothing shown
    # beyond it, so the new cube at 100..110 is on the hidden side
    assert view.cut_state()["offset"] == pytest.approx(55.0)
    assert max(p[0] for t in view.mesh for p in t) <= 55.0 + 1e-6


def test_printables_stills_and_drawings_see_the_whole_part(window):
    view = window.view3d
    plain = pngexport.render(view, 240, 180, "Isometric")
    window.set_cut(True, axis="y")
    cut = pngexport.render(view, 240, 180, "Isometric")
    whole = pngexport.render(view, 240, 180, "Isometric", uncut=True)
    assert whole == plain and cut != plain
    from khervecad import blueprint
    win = blueprint.open_blueprint(window)
    try:
        assert len(win.scene.geometry.tris) == len(view.model_mesh)
    finally:
        win.close()


def test_mcp_switches_the_cut(window):
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(window)
    out = ex.execute("set_render_options", {"cut": "z",
                                            "cut_position": 0.3})
    assert out["cut"]["axis"] == "z"
    assert out["cut"]["position"] == pytest.approx(0.3)
    assert "error" in ex.execute("set_render_options", {"cut": "w"})
    assert "error" in ex.execute("set_render_options",
                                 {"cut": "z", "cut_position": 4})
    assert ex.execute("set_render_options", {"cut": "none"})["cut"] is None


def test_an_error_in_a_callback_is_logged_not_fatal(tmp_path, app):
    from khervecad import app as app_mod
    log = tmp_path / "crash.log"
    saved = sys.excepthook
    try:
        hook = app_mod.install_excepthook(log, notify=False)
        try:
            raise ValueError("a tool broke")
        except ValueError:
            hook(*sys.exc_info())
        assert "a tool broke" in log.read_text()
    finally:
        sys.excepthook = saved
