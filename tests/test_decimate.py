"""Decimate (decimate.py): quadric edge collapse, the node, its program.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
from collections import Counter

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")

from PyQt5.QtWidgets import QApplication

from khervecad import analysis, csg, decimate, document, mesh, scadparse
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _closed(tris) -> bool:
    points, faces = decimate.weld(tris)
    count = Counter()
    for a, b, c in faces:
        for u, w in ((a, b), (b, c), (c, a)):
            count[(u, w)] += 1
    return all(n == 1 and count[(w, u)] == 1 for (u, w), n in count.items())


def _volume(tris):
    return analysis.mass_properties(tris)["volume"]


def _sphere(fn=90):
    root, _w = scadparse.parse_scad(f"sphere(20, $fn = {fn});")
    return mesh.tessellate(root)


@pytest.fixture(params=[True, False], ids=["manifold", "python"])
def backend(request):
    saved = csg.ENABLED
    csg.ENABLED = request.param and saved
    if request.param and not saved:
        pytest.skip("manifold3d not installed")
    yield request.param
    csg.ENABLED = saved


def test_a_ratio_keeps_that_share_and_the_shape(backend):
    tris = _sphere()
    for ratio in (0.5, 0.1):
        out = decimate.decimate(tris, ratio)
        assert len(out) == pytest.approx(len(tris) * ratio, abs=2)
        assert _closed(out)
        assert _volume(out) == pytest.approx(_volume(tris), rel=0.03)


def test_a_tolerance_moves_the_surface_less_than_it(backend):
    tris = _sphere()
    out = decimate.decimate(tris, tolerance=0.2)
    assert len(out) < len(tris) / 2 and _closed(out)
    for tri in out:
        for x, y, z in tri:
            assert abs((x * x + y * y + z * z) ** 0.5 - 20) <= 0.2 + 0.02


def test_a_sliced_box_goes_down_to_its_twelve_triangles(backend):
    root, _w = scadparse.parse_scad(
        "linear_extrude(height = 10, slices = 10) square(10);")
    tris = mesh.tessellate(root)
    assert len(tris) > 12
    box = decimate.decimate(tris, tolerance=0.001)   # flat: free
    assert len(box) == 12 and _closed(box)
    assert _volume(box) == pytest.approx(1000)


def test_an_open_border_is_kept(backend):
    grid = []
    for i in range(6):
        for j in range(6):
            a, b = (i, j, 0.0), (i + 1, j, 0.0)
            c, d = (i + 1, j + 1, 0.0), (i, j + 1, 0.0)
            grid += [(a, b, c), (a, c, d)]
    out = decimate.decimate(grid, 0.1)
    xs = {round(v[0], 6) for t in out for v in t}
    assert {0.0, 6.0} <= xs and len(out) < len(grid)


def test_the_node_previews_compiles_and_round_trips(app, tmp_path):
    doc = DocumentModel()
    ball = doc.add_node("sphere", dict(radius=20.0, segments=60))
    node = doc.wrap_nodes([ball], "decimate")
    node.params.update(ratio=0.25)
    assert validate(doc.root) == {}
    full = len(mesh.tessellate(ball))
    tris = mesh.tessellate(doc.root)
    assert len(tris) == pytest.approx(full / 4, abs=2) and _closed(tris)
    code = doc.to_scad()
    assert "module kcad_decimate(ratio = 0.5, tolerance = 0" in code
    assert "kcad_decimate(ratio = 0.25, tolerance = 0," in code
    path = tmp_path / "dec.scad"
    document.export_scad(doc, str(path))
    other = DocumentModel()
    assert not scadparse.import_scad(other, str(path))
    assert other.to_scad().splitlines()[3:] == code.splitlines()[3:]


def test_a_cut_part_can_be_decimated(app):
    if not csg.available():
        pytest.skip("manifold3d not installed")
    doc = DocumentModel()
    root, _w = scadparse.parse_scad(
        "difference() { sphere(20, $fn = 80); "
        "cylinder(r = 5, h = 50, center = true); }")
    part = root.children[0]
    doc.root.add(part)
    node = doc.wrap_nodes([part], "decimate")
    assert validate(doc.root) == {}
    tris = mesh.tessellate(doc.root)
    assert _closed(tris) and _volume(tris) < _volume(_sphere(80)) * 0.95
