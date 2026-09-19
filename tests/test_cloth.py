"""Cloth (cloth.py): the sheet, the solver, the node.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")

from PyQt5.QtWidgets import QApplication

from khervecad import analysis, cloth, csg, document, mesh, scadparse
from khervecad.model import DocumentModel, validate

SQUARE = [[(-80, -80), (80, -80), (80, 80), (-80, 80)]]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _table():
    root, _w = scadparse.parse_scad(
        "translate([-40, -40, 0]) cube([80, 80, 100]);")
    return mesh.tessellate(root)


def _edges(faces):
    f = np.array(faces)
    return np.unique(np.sort(np.concatenate(
        [f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1), axis=0)


def test_a_round_sheet_is_round():
    circle = [[(50 * math.cos(a * math.pi / 24),
                50 * math.sin(a * math.pi / 24)) for a in range(48)]]
    pts, faces = cloth.sheet(circle, 4, 10)
    r = [math.hypot(p[0], p[1]) for p in pts]
    assert max(r) == pytest.approx(50, abs=0.2) and len(faces) > 200


def test_a_pinned_flag_hangs_its_own_length():
    pts, faces = cloth.sheet(SQUARE, 5, 120)
    x = np.array(cloth.simulate(pts, faces, [], 150, 1.0, 16,
                                pins=[[[-100, 70, 0], [100, 100, 200]]],
                                floor=False))
    e = _edges(faces)
    p = np.array(pts)
    rest = np.linalg.norm(p[e[:, 1]] - p[e[:, 0]], axis=1)
    now = np.linalg.norm(x[e[:, 1]] - x[e[:, 0]], axis=1)
    assert (now / rest).mean() == pytest.approx(1.0, abs=0.03)
    assert x[:, 2].min() == pytest.approx(120 - 150, abs=8)


@pytest.mark.skipif(not csg.available(), reason="manifold3d needed")
def test_a_tablecloth_stays_on_the_table_and_hangs():
    out = cloth.drape(SQUARE, _table(), detail=5, steps=120)
    assert analysis.watertight(out)["ok"]
    top = [v for t in out for v in t if abs(v[0]) < 5 and abs(v[1]) < 5]
    assert top and min(v[2] for v in top) == pytest.approx(100.5, abs=0.2)
    xs = [abs(v[0]) for t in out for v in t]
    assert max(xs) < 70                     # the sides hang, not stick out
    assert min(v[2] for t in out for v in t) > 20   # nor reach the floor


def test_the_node_bakes_and_round_trips(app, tmp_path):
    doc = DocumentModel()
    square = doc.add_node("rect", dict(x=-30.0, y=-30.0, width=60.0,
                                       height=60.0))
    box = doc.add_node("cube", dict(x=-15.0, y=-15.0, width=30.0,
                                    depth=30.0, height=30.0))
    node = doc.wrap_nodes([square, box], "cloth")
    node.params.update(steps=40, detail=6.0)
    assert validate(doc.root) == {}
    tris = mesh.tessellate(doc.root)
    assert len(tris) > len(mesh.tessellate(box))
    code = doc.to_scad()
    assert "kcad_cloth(lift = 20, detail = 6, thickness = 1, steps = 40" \
        in code and "children([1 : $children - 1])" in code
    path = tmp_path / "c.scad"
    document.export_scad(doc, str(path))
    other = DocumentModel()
    assert not scadparse.import_scad(other, str(path))
    assert other.to_scad().splitlines()[3:] == code.splitlines()[3:]


def test_a_3d_first_child_is_refused(app):
    doc = DocumentModel()
    node = doc.wrap_nodes([doc.add_node("cube"), doc.add_node("sphere")],
                          "cloth")
    assert "2D shape" in validate(doc.root)[node.id]
