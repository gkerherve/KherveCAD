"""Drop & settle (physics.py): tipping, stacking, placements, MCP.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")

from PyQt5.QtWidgets import QApplication

from khervecad import csg, mesh, physics, scadparse


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _tris(code):
    root, _w = scadparse.parse_scad(code)
    return mesh.tessellate(root, fn=32)


def _rest(tris):
    res = physics.drop([("a", tris)])["a"]
    rot = res["rotation"]
    moved = [[[a + b for a, b in zip(
        physics._rotate_about(v, rot, res["centre"]), res["move"])]
        for v in t] for t in tris]
    tilt = math.degrees(math.acos(max(-1.0, min(1.0, rot[2][2]))))
    zs = [v[2] for t in moved for v in t]
    return tilt, min(zs), max(zs)


def test_a_box_just_falls():
    tilt, lo, hi = _rest(_tris("translate([0, 0, 30]) cube(10);"))
    assert tilt == pytest.approx(0) and lo == pytest.approx(0)
    assert hi == pytest.approx(10)


def test_a_leaning_post_falls_flat():
    tilt, lo, hi = _rest(_tris(
        "translate([0, 0, 30]) rotate([0, 30, 0]) cube([4, 4, 30]);"))
    assert lo == pytest.approx(0, abs=1e-6)
    assert hi == pytest.approx(4, abs=1e-3)          # lying on a side


def test_a_cone_on_its_point_rolls_onto_its_flank():
    tilt, lo, _hi = _rest(_tris(
        "translate([0, 0, 20]) rotate([180, 0, 0]) "
        "cylinder(r1 = 10, r2 = 0, h = 30);"))
    half = math.degrees(math.atan(10 / 30))
    assert tilt == pytest.approx(90 - half, abs=1.0)
    assert lo == pytest.approx(0, abs=1e-6)


@pytest.mark.skipif(not csg.available(), reason="manifold3d needed")
def test_parts_stack():
    base = _tris("translate([0, 0, 5]) cube([20, 20, 4]);")
    top = _tris("translate([5, 5, 40]) cube(6);")
    moves = physics.drop([("base", base), ("top", top)])
    assert moves["base"]["move"][2] == pytest.approx(-5)
    assert 40 + moves["top"]["move"][2] == pytest.approx(4)


def test_the_mcp_tool_writes_placements(app):
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    win = MainWindow()
    ex = McpToolExecutor(win)
    ex.execute("apply_code", {"code": "translate([0, 0, 50]) "
                              "rotate([0, 40, 0]) cube([4, 4, 40]);"})
    part = [n for n in win.model.root.children if n.visible][0]
    out = ex.execute("drop_parts", {"node_ids": [part.id]})
    assert "error" not in out, out
    row = out["dropped"][0]
    assert row["tipped_deg"] > 30 and row["fell"] > 0
    world = physics.world_tris(win.model.root)
    zs = [v[2] for t in world for v in t]
    assert min(zs) == pytest.approx(0, abs=1e-3)
    assert max(zs) == pytest.approx(4, abs=0.01)
