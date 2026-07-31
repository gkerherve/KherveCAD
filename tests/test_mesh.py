"""Tests for the built-in tessellator used by the 3D preview.

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
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import mesh
from khervecad.model import DocumentModel


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def model(app):
    return DocumentModel()


def _bounds(tris):
    xs = [v[0] for t in tris for v in t]
    ys = [v[1] for t in tris for v in t]
    zs = [v[2] for t in tris for v in t]
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


def test_triangulate_square():
    tris = mesh.triangulate([(0, 0), (10, 0), (10, 10), (0, 10)])
    assert len(tris) == 2
    area = sum(abs(mesh.polygon_area(t)) for t in tris)
    assert area == pytest.approx(100.0)


def test_triangulate_concave():
    # L-shape: 6 vertices -> 4 triangles, area 75.
    poly = [(0, 0), (10, 0), (10, 5), (5, 5), (5, 10), (0, 10)]
    tris = mesh.triangulate(poly)
    area = sum(abs(mesh.polygon_area(t)) for t in tris)
    assert area == pytest.approx(75.0)


def test_cube_mesh_bounds(model):
    node = model.add_node("cube", dict(x=1.0, y=2.0, z=3.0,
                                       width=10.0, depth=20.0,
                                       height=30.0, center=False))
    tris = mesh.tessellate(node)
    assert len(tris) == 12
    (x0, x1), (y0, y1), (z0, z1) = _bounds(tris)
    assert (x0, x1) == (1.0, 11.0)
    assert (y0, y1) == (2.0, 22.0)
    assert (z0, z1) == (3.0, 33.0)


def test_sphere_mesh_radius(model):
    node = model.add_node("sphere", dict(radius=5.0, segments=24))
    tris = mesh.tessellate(node)
    for tri in tris:
        for x, y, z in tri:
            assert math.sqrt(x * x + y * y + z * z) == \
                pytest.approx(5.0, abs=1e-6)


def test_linear_extrude_height(model):
    circle = model.add_node("circle", dict(radius=5.0, segments=16))
    ext = model.wrap_nodes([circle], "linear_extrude")
    ext.params["height"] = 12.0
    tris = mesh.tessellate(model.root)
    _xs, _ys, (z0, z1) = _bounds(tris)
    assert z0 == pytest.approx(0.0)
    assert z1 == pytest.approx(12.0)


def test_rotate_extrude_torus(model):
    # Circle at x=20 revolved -> torus spanning radius 15..25.
    circle = model.add_node("circle", dict(x=20.0, y=0.0, radius=5.0,
                                           segments=16))
    model.wrap_nodes([circle], "rotate_extrude")
    tris = mesh.tessellate(model.root)
    radii = [math.hypot(v[0], v[1]) for t in tris for v in t]
    assert min(radii) == pytest.approx(15.0, abs=0.3)
    assert max(radii) == pytest.approx(25.0, abs=0.3)
    _xs, _ys, (z0, z1) = _bounds(tris)
    assert z0 == pytest.approx(-5.0, abs=0.3)
    assert z1 == pytest.approx(5.0, abs=0.3)


def test_translate_moves_mesh(model):
    cube = model.add_node("cube", dict(width=2.0, depth=2.0, height=2.0))
    wrapper = model.wrap_nodes([cube], "translate")
    wrapper.params.update(x=100.0, y=0.0, z=0.0)
    (x0, x1), _, _ = _bounds(mesh.tessellate(model.root))
    assert x0 == pytest.approx(100.0)
    assert x1 == pytest.approx(102.0)


def test_hidden_node_not_tessellated(model):
    node = model.add_node("cube")
    model.set_visible(node, False)
    assert mesh.tessellate(model.root) == []


def test_difference_shows_first_operand(model):
    cube = model.add_node("cube", dict(width=4.0, depth=4.0, height=4.0))
    model.add_node("sphere", dict(radius=100.0))
    diff = model.wrap_nodes(list(model.root.children), "difference")
    tris = mesh.tessellate(diff)
    assert len(tris) == 12                 # just the cube
    assert mesh.uses_booleans(model.root)


def test_mirror_flips_and_keeps_winding(model):
    cube = model.add_node("cube", dict(x=5.0, width=2.0, depth=2.0,
                                       height=2.0))
    wrapper = model.wrap_nodes([cube], "mirror")
    wrapper.params.update(x=1.0, y=0.0, z=0.0)
    (x0, x1), _, _ = _bounds(mesh.tessellate(model.root))
    assert x1 == pytest.approx(-5.0)
    assert x0 == pytest.approx(-7.0)


def test_line_capsule_outline():
    outline = mesh.node_outlines(
        __import__("khervecad.model", fromlist=["CadNode"]).CadNode(
            "line", params=dict(x1=0.0, y1=0.0, x2=10.0, y2=0.0,
                                width=2.0)))[0]
    xs = [x for x, _ in outline]
    assert min(xs) == pytest.approx(-1.0, abs=0.05)
    assert max(xs) == pytest.approx(11.0, abs=0.05)


def test_rp_survives_a_list_param_that_is_not_points():
    """`rp` resolves every param, and a list one is normally polygon
    points — but an Object's "anchors" is a list of dicts. Unpacking
    one of those raised ValueError through a Qt slot, and PyQt turns an
    exception in a slot into abort(): the app died on the spot."""
    from khervecad.model import CadNode
    node = CadNode("component", "Part",
                   dict(x=1.0, y=2.0, z=3.0,
                        anchors=[{"name": "Port", "pos": [0, 0, 1],
                                  "dir": [0, 0, 1], "kind": "user"}]))
    out = mesh.rp(node)
    assert out["x"] == 1.0
    assert out["anchors"] == node.params["anchors"]   # passed through

    # real point lists still resolve, expressions included
    poly = CadNode("polygon", "P", dict(points=[[0, 0], [10, 0], ["5*2", 8]]))
    assert mesh.rp(poly)["points"] == [[0.0, 0.0], [10.0, 0.0],
                                       [10.0, 8.0]]
