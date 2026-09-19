"""Push / pull faces and the knife (faceedit.py), nodes and MCP.

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

from PyQt5.QtWidgets import QApplication

from khervecad import analysis, csg, document, faceedit, mesh, scadparse
from khervecad.model import DocumentModel, validate

pytestmark = pytest.mark.skipif(not csg.available(),
                                reason="manifold3d not installed")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _tris(code):
    root, _w = scadparse.parse_scad(code)
    return mesh.tessellate(root, fn=32)


def _vol(tris):
    return analysis.mass_properties(tris)["volume"]


BOX = "cube([40, 30, 10]);"


@pytest.mark.parametrize("row, volume", [
    ([20, 15, 10, 5, 0], 40 * 30 * 15),            # top out
    ([20, 15, 10, -4, 5], 12000 - 30 * 20 * 4),    # pocket with a rim
    ([0, 15, 5, 10, 0], 50 * 30 * 10),             # side out
])
def test_push_pull_volumes(row, volume):
    out, missing = faceedit.push_pull(_tris(BOX), [row])
    assert not missing and _vol(out) == pytest.approx(volume)
    assert analysis.watertight(out)["ok"]


def test_rows_apply_in_order_so_a_new_top_can_be_raised_again():
    out, missing = faceedit.push_pull(
        _tris(BOX), [[20, 15, 10, -4, 5], [20, 15, 6, 2, 0]])
    assert not missing
    assert _vol(out) == pytest.approx(12000 - 600 * 4 + 600 * 2)


def test_a_face_with_a_hole_keeps_it():
    holey = _tris("difference() { cube([40, 30, 10]); "
                  "translate([20, 15, -1]) cylinder(r = 5, h = 20); }")
    out, _m = faceedit.push_pull(holey, [[5, 5, 10, 6, 0]])
    assert _vol(out) == pytest.approx(_vol(holey) * 1.6, rel=1e-6)


def test_a_point_off_the_part_is_reported():
    assert faceedit.push_pull(_tris(BOX), [[99, 99, 99, 5, 0]])[1] == [0]


@pytest.mark.parametrize("keep, volume, span", [
    ("above", 7200, (4, 10)), ("below", 4800, (0, 4)),
    ("both", 12000, (-1.5, 11.5))])
def test_bisect(keep, volume, span):
    out = faceedit.bisect(_tris(BOX), [0, 0, 4], [0, 0, 1], keep, gap=3)
    zs = [v[2] for t in out for v in t]
    assert _vol(out) == pytest.approx(volume)
    assert (min(zs), max(zs)) == pytest.approx(span)


def test_the_nodes_round_trip(app, tmp_path):
    doc = DocumentModel()
    a = doc.add_node("cube", dict(width=40.0, depth=30.0, height=10.0))
    pp = doc.wrap_nodes([a], "push_pull")
    pp.params["pushes"] = [[20.0, 15.0, 10.0, 5.0, 2.0]]
    b = doc.add_node("sphere", dict(x=80.0, radius=10.0))
    bi = doc.wrap_nodes([b], "bisect")
    bi.params.update(pz=0.0, keep="below")
    assert validate(doc.root) == {}
    code = doc.to_scad()
    assert "kcad_push_pull(pushes = [[20, 15, 10, 5, 2]]," in code
    assert 'kcad_bisect(px = 0, py = 0, pz = 0, nx = 0, ny = 0, nz = 1, ' \
        'keep = "below", gap = 0,' in code
    path = tmp_path / "f.scad"
    document.export_scad(doc, str(path))
    other = DocumentModel()
    assert not scadparse.import_scad(other, str(path))
    assert other.to_scad().splitlines()[3:] == code.splitlines()[3:]
    pp.params["pushes"] = [[99.0, 99.0, 99.0, 5.0, 0.0]]
    assert "no flat face" in validate(doc.root)[pp.id]


def test_the_mcp_tool(app):
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    win = MainWindow()
    ex = McpToolExecutor(win)
    ex.execute("apply_code", {"code": "translate([100, 0, 0]) "
                              "cube([40, 30, 10]);"})
    part = [n for n in win.model.root.walk() if n.type == "cube"][0]
    out = ex.execute("push_pull_face", {"node_id": part.id,
                                        "point": [120, 15, 10],
                                        "distance": -4, "inset": 5})
    assert "error" not in out, out
    pp = next(n for n in win.model.root.walk() if n.type == "push_pull")
    assert _vol(mesh.tessellate(pp)) == pytest.approx(12000 - 2400)
    bad = ex.execute("push_pull_face", {"node_id": pp.id,
                                        "point": [0, 0, 500],
                                        "distance": 3})
    assert "error" in bad


def test_every_choice_param_survives_import(app, tmp_path):
    """The importer's generic choice branch only knows x / y / z: the
    node-specific choices must be read before it."""
    doc = DocumentModel()
    cases = [("bisect", dict(keep="both")),
             ("bevel", dict(which="both")),
             ("shrinkwrap", dict(mode="project", axis="-z", keep="all"))]
    made = []
    for kind, params in cases:
        a = doc.add_node("cube")
        extra = [doc.add_node("sphere")] if kind == "shrinkwrap" else []
        node = doc.wrap_nodes([a] + extra, kind)
        node.params.update(params)
        made.append((kind, params))
    path = tmp_path / "choices.scad"
    document.export_scad(doc, str(path))
    other = DocumentModel()
    scadparse.import_scad(other, str(path))
    for kind, params in made:
        node = next(n for n in other.root.walk() if n.type == kind)
        for key, value in params.items():
            assert node.params[key] == value, (kind, key)
