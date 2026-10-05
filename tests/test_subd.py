"""SubD (subd.py): Catmull-Clark over a cage, creases, Edit Mode on the
cage, conversion.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
from collections import Counter
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import analysis, mesh, meshedit, scadparse, subd
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def open_edges(tris):
    c = Counter()

    def k(v):
        return (round(v[0], 4), round(v[1], 4), round(v[2], 4))
    for t in tris:
        for i in range(3):
            c[(k(t[i]), k(t[(i + 1) % 3]))] += 1
    return sum(1 for (a, b), n in c.items() if c.get((b, a), 0) != n)


def test_one_step_of_a_cube_is_24_quads():
    cage = subd.box_cage()
    faces = [f[::-1] for f in cage["faces"]]
    pts, quads, _cr = subd.catmull_clark(cage["points"], faces)
    assert len(quads) == 24 and len(pts) == 8 + 12 + 6


def test_a_box_becomes_a_closed_rounded_solid(app):
    m = DocumentModel()
    subd.insert_box(m)
    assert validate(m.root) == {}
    tris = mesh.tessellate(m.root)
    assert open_edges(tris) == 0
    vol = analysis.mass_properties(tris)["volume"]
    assert 0.2 * 24000 < vol < 24000          # rounder, so smaller
    xs = [v[0] for t in tris for v in t]
    assert max(xs) < 20                       # pulled in from the cage


def test_creases_keep_the_base_flat(app):
    m = DocumentModel()
    s = subd.insert_box(m)
    s.params["creases"] = [[0, 1], [1, 2], [2, 3], [3, 0]]
    tris = mesh.tessellate(m.root)
    flat = [v for t in tris for v in t if abs(v[2]) < 1e-9]
    assert len(flat) > 20 and open_edges(tris) == 0
    s.params["creases"] = []
    s.params["sharp"] = 60.0                  # every cube edge
    tris = mesh.tessellate(m.root)
    vol = analysis.mass_properties(tris)["volume"]
    assert vol == pytest.approx(24000, rel=1e-6)


def test_edit_mode_opens_the_cage(app):
    m = DocumentModel()
    s = subd.insert_box(m)
    assert meshedit.find_editable(s) is s.children[0]


def test_moving_a_cage_point_moves_the_surface(app):
    m = DocumentModel()
    s = subd.insert_box(m)
    before = max(v[2] for t in mesh.tessellate(m.root) for v in t)
    cage = s.children[0]
    pts = [list(p) for p in cage.params["points"]]
    for i in (4, 5, 6, 7):
        pts[i][2] += 30
    m.set_param(cage, "points", pts)
    after = max(v[2] for t in mesh.tessellate(m.root) for v in t)
    assert after > before + 20


def test_convert_and_round_trip(app):
    m = DocumentModel()
    c = m.add_node("cylinder", dict(height=20, radius_bottom=10,
                                    radius_top=10, segments=8))
    s = subd.convert(m, c)
    assert validate(m.root).get(s.id) is None
    code = m.to_scad()
    root, _w = scadparse.parse_scad(code)
    got = [n for n in root.walk() if n.type == "subd"]
    assert got and got[0].children[0].type == "polyhedron"
