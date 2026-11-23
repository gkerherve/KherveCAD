# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""Fillet a CURVED face's edges (2026-11-22, Exercise 010: SolidWorks'
Fillet takes Face<1>, the dome, and rounds where every arm meets it; kCAD
found only flat faces, so the click on the dome rounded nothing)."""

import math

from khervecad import fillet, mesh
from khervecad.model import DocumentModel


def _part():
    m = DocumentModel()
    u = m.add_node("union", {}, name="Body")
    m.add_node("cylinder", dict(height=20.0, radius_bottom=10.0,
                                radius_top=10.0, segments=48), parent=u)
    m.add_node("sphere", dict(z=20.0, radius=10.0, segments=48), parent=u)
    arm = m.add_node("translate", dict(x=0.0, y=-3.0, z=14.0), parent=u)
    m.add_node("cube", dict(width=25.0, depth=6.0, height=12.0), parent=arm)
    rows = [(t, None, False) for t in mesh.tessellate(m.root)]
    return fillet._merged(rows)


def test_a_click_on_a_dome_takes_the_creases_round_the_dome_only():
    tris = _part()
    edges = fillet.crease_edges(tris)
    p = (0.0, -7.0, 20.0 + math.sqrt(100 - 49))
    n = fillet._unit(fillet._sub(p, (0.0, 0.0, 20.0)))
    got = fillet.face_edges(tris, edges, list(p) + list(n), 1e-3)
    assert got, "the dome's edges"
    zs = [e.mid[2] for e in got]
    xs = [e.mid[0] for e in got]
    # where the arm meets the dome (x > 0 side, high), never the base
    # rim (z = 0) or the cylinder's far side
    assert min(zs) > 13.0, zs
    assert min(xs) > -1.0, xs
