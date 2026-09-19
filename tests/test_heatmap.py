"""Heat maps (heatmap.py / heatmap_ui.py) and their MCP switch.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")

from khervecad import csg, heatmap, mesh, scadparse


def _tris(code):
    root, _w = scadparse.parse_scad(code)
    return mesh.tessellate(root, fn=32)


@pytest.fixture(params=[True, False], ids=["manifold", "grid"])
def backend(request):
    saved = csg.ENABLED
    if request.param and not saved:
        pytest.skip("manifold3d not installed")
    csg.ENABLED = request.param
    yield
    csg.ENABLED = saved


def test_a_thin_fin_is_red_and_the_block_is_not(backend):
    tris = _tris("cube([20, 20, 10]); translate([0, 25, 0]) "
                 "cube([20, 0.5, 10]);")
    cols, stats = heatmap.colours(tris, "thickness", min_wall=0.8)
    assert stats["thinnest"] == pytest.approx(0.5, abs=1e-6)
    fin = [c[0] for t, c in zip(tris, cols)
           if all(v[1] >= 25 for v in t) and abs(
               (t[1][0] - t[0][0]) * (t[2][2] - t[0][2])
               - (t[1][2] - t[0][2]) * (t[2][0] - t[0][0])) > 1e-9]
    assert fin and set(fin) == {heatmap.RED}
    block_top = [c[0] for t, c in zip(tris, cols)
                 if all(v[1] <= 20 and v[2] == 10 for v in t)]
    assert block_top and heatmap.RED not in block_top
    assert 0 < stats["thin_fraction"] < 1


def test_overhangs_are_red_and_the_plate_blue():
    tris = _tris("translate([0, 0, 10]) cube(10); cube([2, 2, 10]);")
    cols, stats = heatmap.colours(tris, "overhang", overhang=45)
    by_face = {}
    for t, c in zip(tris, cols):
        by_face.setdefault(round(min(v[2] for v in t), 3), set()).add(c[0])
    assert heatmap.BLUE in by_face[0.0]          # on the plate
    assert heatmap.RED in by_face[10.0]          # the ledge underside
    assert stats["overhang_fraction"] > 0


def test_the_mcp_switch_paints_the_view(window_ex):
    win, call = window_ex
    call("apply_code", code="cube([20, 20, 0.4]);")
    out = call("set_render_options", heatmap="thickness")
    assert out["heatmap"]["kind"] == "thickness"
    assert out["heatmap"]["thinnest"] == pytest.approx(0.4, abs=1e-3)
    colours = {c[0] for c in win.view3d.model_colors}
    assert heatmap.RED in colours
    assert "heat map" in win.view3d.source
    out = call("set_render_options", heatmap="off")
    assert out["heatmap"]["kind"] == "off"
    assert "heat map" not in win.view3d.source


@pytest.fixture(scope="module")
def app():
    from PyQt5.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window_ex(app):
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    win = MainWindow()
    ex = McpToolExecutor(win)

    def call(name, **params):
        out = ex.execute(name, params)
        assert "error" not in out, out
        return out
    return win, call
