"""Shrinkwrap (shrinkwrap.py): closest points, rays, the node.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import os
import random

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")

from PyQt5.QtWidgets import QApplication

from khervecad import csg, document, mesh, scadparse, shrinkwrap
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(params=[True, False], ids=["manifold", "numpy"])
def backend(request):
    saved = csg.ENABLED
    if request.param and not saved:
        pytest.skip("manifold3d not installed")
    csg.ENABLED = request.param
    yield request.param
    csg.ENABLED = saved


def _tris(code):
    root, _w = scadparse.parse_scad(code)
    return mesh.tessellate(root)


def _radii(tris):
    return [math.sqrt(x * x + y * y + z * z) for t in tris for x, y, z in t]


def test_closest_points_match_brute_force():
    body = _tris("rotate([10, 20, 30]) cube([30, 20, 10], center = true);")
    target = shrinkwrap.Target(body)
    rng = random.Random(3)
    pts = np.array([[rng.uniform(-40, 40) for _ in range(3)]
                    for _ in range(200)])
    q, _t = target.nearest(pts)
    brute = shrinkwrap.closest_on_triangles(pts, target.a, target.b,
                                            target.c)
    want = np.linalg.norm(brute - pts[:, None], axis=2).min(axis=1)
    got = np.linalg.norm(q - pts, axis=1)
    assert got == pytest.approx(want, abs=1e-9)


def test_nearest_with_an_offset_sits_that_far_out(backend):
    body = _tris("sphere(20, $fn = 60);")
    out = shrinkwrap.shrinkwrap(_tris("sphere(30, $fn = 40);"), body,
                                "nearest", 2.0, keep="all")
    radii = _radii(out)
    assert min(radii) > 21.9 and max(radii) < 22.01


def test_outside_moves_only_what_sinks_in(backend):
    body = _tris("sphere(20, $fn = 60);")
    far = _tris("translate([40, 0, 0]) cube(4, center = true);")
    out = shrinkwrap.shrinkwrap(far, body, "nearest", 1.0, keep="outside")
    assert sorted(map(tuple, out)) == sorted(map(tuple, far))
    ball = shrinkwrap.shrinkwrap(_tris("sphere(12, $fn = 30);"), body,
                                 "nearest", 1.0, keep="outside")
    assert min(_radii(ball)) > 20.9


def test_project_along_an_axis_drops_onto_the_top(backend):
    body = _tris("sphere(20, $fn = 60);")
    plate = _tris("translate([-5, -5, 30]) cube([10, 10, 1]);")
    out = shrinkwrap.shrinkwrap(plate, body, "project", 0.0, keep="all",
                                axis="-z")
    for t in out:
        for x, y, z in t:
            assert z == pytest.approx(math.sqrt(400 - x * x - y * y),
                                      abs=0.15)


def test_inside_by_ray_parity(backend):
    target = shrinkwrap.Target(_tris("sphere(20, $fn = 40);"))
    assert target.inside([[0, 0, 0], [19, 0, 0], [0, 0, 25],
                          [21, 0, 0]]).tolist() == [True, True, False,
                                                    False]


def test_the_node_previews_compiles_and_round_trips(app, tmp_path):
    doc = DocumentModel()
    cap = doc.add_node("sphere", dict(radius=12.0, segments=24))
    body = doc.add_node("sphere", dict(radius=20.0, segments=48))
    node = doc.wrap_nodes([cap, body], "shrinkwrap")
    node.params.update(offset=1.5)
    assert validate(doc.root) == {}
    tris = mesh.tessellate(doc.root)
    wrap = len(mesh.tessellate(cap))
    assert len(tris) == wrap + len(mesh.tessellate(body))   # target drawn
    code = doc.to_scad()
    assert 'kcad_shrinkwrap(mode = "nearest", axis = "normal", keep = ' \
        '"outside", offset = 1.5' in code
    assert "children([1 : $children - 1])" in code
    path = tmp_path / "wrap.scad"
    document.export_scad(doc, str(path))
    other = DocumentModel()
    assert not scadparse.import_scad(other, str(path))
    assert other.to_scad().splitlines()[3:] == code.splitlines()[3:]
    node.params["show_target"] = False
    assert len(mesh.tessellate(doc.root)) == wrap


def test_one_child_is_refused(app):
    doc = DocumentModel()
    node = doc.wrap_nodes([doc.add_node("cube")], "shrinkwrap")
    assert "FIRST child" in validate(doc.root)[node.id]
