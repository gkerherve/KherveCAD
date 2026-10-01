"""scatter.py: copies of a piece over a surface — the node, its code,
the importer and the scatter_on_surface MCP tool.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import mesh, scadparse, scatter
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def _doc(count=30):
    doc = DocumentModel()
    cone = doc.add_node("cylinder", dict(height=4.0, radius_bottom=1.0,
                                         radius_top=0.0, segments=8))
    ball = doc.add_node("sphere", dict(radius=20.0, segments=32))
    node = doc.wrap_nodes([cone, ball], "scatter")
    node.params["count"] = count
    return doc, node


def test_copies_stand_on_the_surface_along_its_normal(app):
    doc, node = _doc()
    assert node.id not in validate(doc.root)
    _ops, mats = scatter.compute(node, {})
    assert len(mats) == 30
    for m in mats:
        origin = (m[3], m[7], m[11])
        axis = (m[2], m[6], m[10])                # where +Z went
        r = math.sqrt(sum(c * c for c in origin))
        assert r == pytest.approx(20.0, abs=0.6)  # on the sphere
        size = math.sqrt(sum(c * c for c in axis))
        cos = sum(origin[k] * axis[k] for k in range(3)) / (r * size)
        assert cos > 0.95                         # pointing outwards
    tris = mesh.tessellate(doc.root)
    assert max(math.sqrt(sum(c * c for c in v)) for t in tris
               for v in t) > 22.5                 # the spikes stick out


def test_spacing_keeps_copies_apart_and_the_seed_repeats(app):
    doc, node = _doc(200)
    node.params["spacing"] = 6.0
    _ops, mats = scatter.compute(node, {})
    pts = [(m[3], m[7], m[11]) for m in mats]
    for i, a in enumerate(pts):
        for b in pts[i + 1:]:
            assert math.dist(a, b) >= 6.0 - 1e-6
    assert len(pts) < 200                         # the sphere is full
    _ops, again = scatter.compute(node, {})
    assert again == mats


def test_facing_and_within_keep_a_region(app):
    doc, node = _doc(40)
    node.params.update(facing="+z", max_angle=45.0)
    _ops, mats = scatter.compute(node, {})
    assert mats and all(m[11] > 20.0 * math.cos(math.radians(46))
                        for m in mats)
    node.params.update(facing="any", within=[[0, -30, -30], [30, 30, 30]])
    _ops, mats = scatter.compute(node, {})
    assert mats and all(m[3] > -0.5 for m in mats)


def test_a_path_puts_a_row_on_the_surface_tapering_to_its_ends(app):
    doc, node = _doc(9)
    node.params.update(mode="path", taper=0.5, scale_jitter=0.0,
                       path=[[-25, 0, 0], [0, 0, 30], [25, 0, 0]])
    assert node.id not in validate(doc.root)
    _ops, mats = scatter.compute(node, {})
    assert len(mats) == 9
    sizes = [math.sqrt(m[2] ** 2 + m[6] ** 2 + m[10] ** 2) for m in mats]
    assert sizes[4] == pytest.approx(1.0)
    assert sizes[0] == pytest.approx(0.5) and sizes[-1] == pytest.approx(0.5)
    for m in mats:
        assert abs(m[7]) < 0.6                    # on the y = 0 arc
        assert math.sqrt(m[3] ** 2 + m[7] ** 2 + m[11] ** 2) == \
            pytest.approx(20.0, abs=0.6)


def test_the_program_round_trips_and_keeps_the_piece(app):
    doc, node = _doc()
    node.params.update(scale=1.5, sink=0.5, facing="+z", max_angle=80.0)
    code = doc.to_scad()
    assert "module kcad_scatter(" in code and "multmatrix" in code
    assert "kcad_scatter(mode = \"surface\", count = 30" in code
    root, warnings = scadparse.parse_scad(code)
    assert not warnings
    back = next(n for n in root.walk() if n.type == "scatter")
    for key in ("count", "scale", "sink", "facing", "max_angle"):
        assert back.params[key] == node.params[key], key
    assert [c.type for c in back.children] == ["cylinder", "sphere"]


def test_validation_asks_for_a_piece_and_a_surface(app):
    doc = DocumentModel()
    cone = doc.add_node("cylinder")
    node = doc.wrap_nodes([cone], "scatter")
    assert "piece" in validate(doc.root)[node.id]
    ball = doc.add_node("sphere", parent=node)
    assert node.id not in validate(doc.root)
    node.params["mode"] = "path"
    assert "path" in validate(doc.root)[node.id]
    node.params.update(mode="surface", align="sideways")
    assert "align" in validate(doc.root)[node.id]
    node.params["align"] = "normal"
    loop = doc.wrap_nodes([node], "for_loop")
    assert "inside" in validate(doc.root)[node.id]
    assert ball is not None and loop is not None


@pytest.mark.skipif(shutil.which("openscad") is None
                    and not Path("/opt/homebrew/bin/openscad").exists(),
                    reason="OpenSCAD not installed")
def test_openscad_renders_every_copy(app, tmp_path):
    doc, node = _doc(12)
    node.params["show_target"] = False
    path = tmp_path / "scatter.scad"
    path.write_text(doc.to_scad())
    binary = shutil.which("openscad") or "/opt/homebrew/bin/openscad"
    out = tmp_path / "scatter.stl"
    subprocess.run([binary, "-o", str(out), str(path)], check=True,
                   capture_output=True, timeout=120)
    from khervecad import engine
    tris = engine.parse_mesh(str(out))
    # twelve separate cones, none lost
    assert len(tris) == pytest.approx(12 * 16, rel=0.25)


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(900, 700)
    return win


def test_scatter_on_surface_tool_wraps_and_maps_a_world_path(window):
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(window)
    doc = window.model
    cone = doc.add_node("cylinder", dict(height=4.0, radius_bottom=1.0,
                                         radius_top=0.0))
    obj = doc.add_node("translate", dict(x=100.0))
    ball = doc.add_node("sphere", dict(radius=20.0), parent=obj)
    out = ex.execute("scatter_on_surface", {
        "piece_id": cone.id, "surface_id": obj.id, "count": 25,
        "sink": 0.5})
    assert "error" not in out, out
    assert out["placed"] == 25
    node = next(n for n in doc.root.walk() if n.id == out["scatter"])
    assert [c.type for c in node.children] == ["cylinder", "translate"]
    out = ex.execute("scatter_on_surface", {
        "scatter_id": node.id, "count": 5,
        "path": [[80, 0, 0], [100, 0, 25], [120, 0, 0]]})
    assert out["placed"] == 5 and out["mode"] == "path"
    assert node.params["path"][1] == pytest.approx([100, 0, 25])
    assert "error" in ex.execute("scatter_on_surface", {"piece_id": cone.id})
    assert "error" in ex.execute("scatter_on_surface", {
        "scatter_id": node.id, "align": "sideways"})
    assert ball is not None
