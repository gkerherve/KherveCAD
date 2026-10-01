"""displace.py and bakedkit.py: surface patterns along the normals, the
baked node's code, importer, validation and cache.

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

from khervecad import bake, displace, mesh, scadparse
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def _doc(pattern="scales", strength=0.6, scale=6.0):
    doc = DocumentModel()
    ball = doc.add_node("sphere", dict(radius=20.0, segments=48))
    node = doc.wrap_nodes([ball], "displace")
    node.params.update(pattern=pattern, strength=strength, scale=scale)
    return doc, node


def _radii(tris):
    return np.linalg.norm(np.asarray(tris).reshape(-1, 3), axis=1)


def _closed(tris):
    points, faces = bake.to_polyhedron(tris)
    return bake._check_polyhedron(dict(points=points, faces=faces)) is None


@pytest.mark.parametrize("pattern", ["scales", "shingles", "warts",
                                     "chitin", "ridges", "noise"])
def test_every_pattern_raises_a_closed_skin(app, pattern):
    doc, node = _doc(pattern)
    assert node.id not in validate(doc.root)
    tris = mesh.tessellate(doc.root)
    r = _radii(tris)
    assert r.max() > 20.3                  # it stands out
    assert r.min() > 19.5                  # midlevel 0: nothing sinks
    assert _closed(tris)


def test_cracks_carve_in_with_a_negative_strength(app):
    doc, _node = _doc("cracks", -0.8)
    r = _radii(mesh.tessellate(doc.root))
    assert r.min() < 19.5 and r.max() < 20.1


def test_midlevel_half_moves_both_ways(app):
    doc, node = _doc("noise", 1.0)
    node.params["midlevel"] = 0.5
    r = _radii(mesh.tessellate(doc.root))
    assert r.min() < 19.8 and r.max() > 20.2


def test_within_keeps_the_pattern_to_a_region(app):
    doc, node = _doc("scales", 1.0)
    node.params["within"] = [[0, -30, -30], [30, 30, 30]]
    a = np.asarray(mesh.tessellate(doc.root)).reshape(-1, 3)
    r = np.linalg.norm(a, axis=1)
    far = a[:, 0] < -6.0                   # a cell past the region
    assert r[far].max() < 20.05
    assert r[a[:, 0] > 3.0].max() > 20.5


def test_the_refinement_is_capped(app):
    from khervecad.model import CadNode
    cube = CadNode("cube", "", dict(width=400.0, depth=400.0, height=400.0))
    tris = [t for t, _c, _s in mesh._tess(cube, {}, None, frozenset(),
                                          False)]
    edge = displace.refine_edge(tris, 1.0, 0.0)
    area = 6 * 400.0 ** 2
    assert area / (0.433 * edge * edge) <= displace.MAX_TRIS * 1.01


def test_voronoi_distances_are_ordered():
    pts = np.random.default_rng(3).random((500, 3)) * 30
    f1, f2, centre, cid = displace.voronoi(pts, 5.0, 1)
    assert np.all(f1 <= f2 + 1e-12)
    assert np.all((cid >= 0) & (cid < 1))
    assert np.allclose(np.linalg.norm(pts / 5.0 - centre / 5.0, axis=1), f1)


def test_the_program_round_trips_and_the_kit_caches(app):
    doc, node = _doc("shingles", 0.5, 6.0)
    node.params.update(axis="+y", seed=4, detail=2.0, within=[[-30, -30, 0],
                                                  [30, 30, 30]])
    code = doc.to_scad()
    assert "module kcad_displace(" in code
    assert 'kcad_displace(pattern = "shingles", strength = 0.5' in code
    root, warnings = scadparse.parse_scad(code)
    assert not warnings
    back = next(n for n in root.walk() if n.type == "displace")
    for key in ("pattern", "strength", "scale", "axis", "seed", "within"):
        assert back.params[key] == node.params[key], key
    assert [c.type for c in back.children] == ["sphere"]
    # one bake, served from the cache the second time
    hit = displace.KIT.triangles(node, {})
    assert hit is displace.KIT.triangles(node, {})


def test_validation(app):
    doc, node = _doc()
    node.params["pattern"] = "fur"
    assert "pattern" in validate(doc.root)[node.id]
    node.params.update(pattern="image", image="")
    assert "picture" in validate(doc.root)[node.id]
    node.params.update(pattern="scales", scale=0)
    assert "size" in validate(doc.root)[node.id]
    node.params["scale"] = 4.0
    node.params["within"] = [[0, 0, 0]]
    assert "within" in validate(doc.root)[node.id]
    node.params["within"] = []
    empty = doc.add_node("displace")
    assert "inside" in validate(doc.root)[empty.id]
    loop = doc.wrap_nodes([node], "for_loop")
    assert "inside" in validate(doc.root)[node.id] and loop


def test_an_image_pattern_reads_a_picture(app, tmp_path):
    from PyQt5.QtGui import QColor, QImage
    img = QImage(20, 20, QImage.Format_RGB888)
    img.fill(QColor("black"))
    for y in range(20):
        for x in range(10, 20):
            img.setPixelColor(x, y, QColor("white"))
    path = tmp_path / "half.png"
    img.save(str(path))
    doc, node = _doc("image", 1.0)
    node.params.update(image=str(path), plane="Front (XZ)", image_x=-20.0,
                       image_y=-20.0, image_width=40.0, scale=2.0,
                       detail=1.0)
    assert node.id not in validate(doc.root)
    a = np.asarray(mesh.tessellate(doc.root)).reshape(-1, 3)
    r = np.linalg.norm(a, axis=1)
    assert r[a[:, 0] > 3].max() > 20.5     # white: out
    assert r[a[:, 0] < -3].max() < 20.1    # black: stays


def test_wrap_nodes_offers_displace(app):
    from khervecad import mcp_schema, toolbars, tooltips
    assert "displace" in mcp_schema.WRAP_TYPES
    assert "displace" in dict(toolbars.OPERATION_GROUPS)["deform"]
    assert "Displace" in tooltips.TIPS["displace"][0]
