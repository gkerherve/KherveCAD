"""Voxel remesh (remesh.py): winding fill, closed output, the node.

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

from khervecad import analysis, document, mesh, remesh, scadparse
from khervecad.decimate import weld
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _tris(code):
    root, _w = scadparse.parse_scad(code)
    return mesh.tessellate(root, fn=48)


def _closed(tris):
    _p, faces = weld(tris)
    count = Counter()
    for a, b, c in faces:
        for u, w in ((a, b), (b, c), (c, a)):
            count[(u, w)] += 1
    return all(n == 1 and count[(w, u)] == 1 for (u, w), n in count.items())


def _volume(tris):
    return analysis.mass_properties(tris)["volume"]


def test_overlapping_pieces_become_one_closed_solid():
    soup = _tris("cube(20); translate([10, 10, 10]) sphere(12);")
    out = remesh.remesh(soup, 1.0)
    assert _closed(out) and analysis.watertight(out)["ok"]
    assert _volume(out) == pytest.approx(8829, rel=0.02)   # the union


def test_an_open_mesh_is_closed_and_keeps_its_size():
    cube = _tris("cube(10);")
    out = remesh.remesh(cube[:-2], 0.5)                    # top missing
    assert _closed(out)
    assert _volume(out) == pytest.approx(1000, rel=0.02)


def test_the_occupancy_counts_winding_not_parity():
    import numpy as np
    two = _tris("cube(10); translate([0, 0, 5]) cube(10);")  # overlap
    occ = remesh.occupancy(two, np.array([-1.0, -1.0, -1.0]), 1.0,
                           (12, 12, 17))
    assert occ[5, 5, 1:16].all()     # the overlap z 5..10 is not a gap


def test_the_node_bakes_and_round_trips(app, tmp_path):
    doc = DocumentModel()
    a = doc.add_node("cube", dict(width=10.0, depth=10.0, height=10.0))
    b = doc.add_node("sphere", dict(x=10.0, y=5.0, z=5.0, radius=6.0))
    node = doc.wrap_nodes([a, b], "remesh")
    node.params["voxel"] = 0.8
    assert validate(doc.root) == {}
    tris = mesh.tessellate(doc.root)
    assert _closed(tris)
    code = doc.to_scad()
    assert "kcad_remesh(voxel = 0.8, snap = true," in code
    path = tmp_path / "r.scad"
    document.export_scad(doc, str(path))
    other = DocumentModel()
    assert not scadparse.import_scad(other, str(path))
    assert other.to_scad().splitlines()[3:] == code.splitlines()[3:]
