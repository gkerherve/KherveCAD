"""strands.py: hair strands grown from a surface — the paths, the tubes,
the node's code and the grow_hair MCP tool.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import bake, bakedkit, mesh, scadparse, strands
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def _doc(**params):
    doc = DocumentModel()
    ball = doc.add_node("sphere", dict(radius=20.0))
    node = doc.wrap_nodes([ball], "hair_strands")
    node.params.update(count=200, **params)
    return doc, node


def test_strands_are_closed_tubes_out_of_the_surface(app):
    doc, node = _doc(gravity=0.0, clumps=0)
    assert node.id not in validate(doc.root)
    tris = strands.KIT.triangles(node, {})[0]
    points, faces = bake.to_polyhedron(tris)
    assert bake._check_polyhedron(dict(points=points, faces=faces)) is None
    r = np.linalg.norm(np.asarray(tris).reshape(-1, 3), axis=1)
    assert r.max() > 20 + 30 * 0.6               # straight out, ~length
    assert r.min() > 18.0                        # roots just under the skin


def test_the_face_stays_clear_and_within_holds(app):
    doc, node = _doc(clumps=0)
    paths = strands.strand_paths(strands._roots(
        bakedkit.source_tris(node, {}), 200, [], "-y", 60.0, 1),
        strands._resolved(node, {}))
    roots = paths[:, 0]
    assert (roots[:, 1] / np.linalg.norm(roots, axis=1)).min() > -0.55
    node.params["within"] = [[-30, -30, 10], [30, 30, 30]]
    a = np.asarray(strands.KIT.triangles(node, {})[0]).reshape(-1, 3)
    assert a[:, 2].min() > 8.0


def test_gravity_droops_and_clumps_gather(app):
    doc, node = _doc(gravity=1.0, clumps=0, clear="none")
    res = strands._resolved(node, {})
    roots = strands._roots(bakedkit.source_tris(node, {}), 200, [], "none",
                           60.0, 1)
    straight = strands.strand_paths(roots, dict(res, gravity=0.0))
    droop = strands.strand_paths(roots, res)
    assert (droop[:, -1, 2] < straight[:, -1, 2] - 1).mean() > 0.9
    loose = strands.strand_paths(roots, dict(res, gravity=0.0))
    locks = strands.strand_paths(roots, dict(res, gravity=0.0, clumps=10,
                                             clump_strength=1.0))
    tips = len({tuple(np.round(p, 3)) for p in locks[:, -1]})
    assert tips <= 10 < len({tuple(np.round(p, 3)) for p in loose[:, -1]})


def test_the_strands_carry_their_colour_and_round_trip(app):
    doc, node = _doc(color="#aa5500", material="Fur")
    colours = {c for _t, c in mesh.tessellate_colored(doc.root)}
    assert ("#aa5500", 1.0, "Fur") in colours
    root, warnings = scadparse.parse_scad(doc.to_scad())
    assert not warnings
    back = next(n for n in root.walk() if n.type == "hair_strands")
    for key in ("count", "color", "material", "clear", "gravity"):
        assert back.params[key] == node.params[key], key
    node.params["material"] = "Velour"
    assert "material" in validate(doc.root)[node.id]


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(900, 700)
    return win


def test_grow_hair_tool(window):
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(window)
    ball = window.model.add_node("sphere", dict(radius=20.0))
    out = ex.execute("grow_hair", {"node_id": ball.id, "count": 100,
                                   "length": 20, "within": {
                                       "min": [-30, -30, 0],
                                       "max": [30, 30, 30]}})
    assert "error" not in out, out
    assert out["strands"] == 100 and out["triangles"] > 0
    assert "error" in ex.execute("grow_hair", {"node_id": out["hair"],
                                               "fuzz": 1})
