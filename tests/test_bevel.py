"""Bevel (bevel.py): every sharp edge, profiles, rolling-ball corners.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import os
from collections import Counter

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")

from PyQt5.QtWidgets import QApplication

from khervecad import analysis, bevel, csg, document, mesh, scadparse
from khervecad.decimate import weld
from khervecad.model import DocumentModel, validate

pytestmark = pytest.mark.skipif(not csg.available(),
                                reason="manifold3d not installed")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _tris(code, fn=48):
    root, _w = scadparse.parse_scad(code)
    return mesh.tessellate(root, fn=fn)


def _volume(tris):
    return analysis.mass_properties(tris)["volume"]


def _closed(tris):
    _p, faces = weld(tris)
    count = Counter()
    for a, b, c in faces:
        for u, w in ((a, b), (b, c), (c, a)):
            count[(u, w)] += 1
    return all(n == 1 and count[(w, u)] == 1 for (u, w), n in count.items())


def test_profile_exponents_follow_blender():
    assert bevel.exponent(0.5) == pytest.approx(2)
    assert bevel.exponent(0.25) == pytest.approx(1)
    assert bevel.exponent(0.75) == pytest.approx(4)


def test_a_round_bevel_is_the_rolling_ball_box():
    r = 2.0
    out = bevel.bevel(_tris("cube(20);"), r, 24, 0.5)
    exact = (20 ** 3 - 12 * (r * r - math.pi * r * r / 4) * (20 - 2 * r)
             - 8 * (r ** 3 - math.pi * r ** 3 / 6))
    assert _closed(out)
    assert _volume(out) == pytest.approx(exact, rel=5e-4)
    xs = [v[0] for t in out for v in t]
    assert min(xs) == pytest.approx(0) and max(xs) == pytest.approx(20)


def test_a_chamfer_leaves_blenders_corner_triangles():
    r = 2.0
    out = bevel.bevel(_tris("cube(20);"), r, 1, 0.25)
    # Blender's corner triangle x + y + z = 2r takes 5/6 of the corner
    # cube (the chamfers inside it included)
    exact = 20 ** 3 - 12 * (r * r / 2) * (20 - 2 * r) - 8 * r ** 3 * 5 / 6
    assert _volume(out) == pytest.approx(exact, rel=5e-4)
    planes = set()
    for a, b, c in out:
        n = [(b[1] - a[1]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[1] - a[1]),
             (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2]),
             (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])]
        k = math.sqrt(sum(x * x for x in n))
        n = [x / k for x in n]
        planes.add(tuple(round(x, 3) for x in n + [sum(
            x * y for x, y in zip(n, a)) / 5]))
    assert len(planes) == 6 + 12 + 8          # faces, chamfers, corners


def test_a_squarer_profile_takes_less_and_a_cove_more():
    box = _tris("cube(20);")
    round_ = _volume(bevel.bevel(box, 2, 8, 0.5))
    assert _volume(bevel.bevel(box, 2, 8, 0.9)) > round_
    assert _volume(bevel.bevel(box, 2, 8, 0.1)) < round_


def test_concave_edges_are_filled():
    part = _tris("linear_extrude(20) polygon([[0, 0], [20, 0], [20, 5], "
                 "[5, 5], [5, 20], [0, 20]]);")
    added = _volume(bevel.bevel(part, 2, 16, 0.5, which="concave")) - \
        _volume(part)
    assert added == pytest.approx(20 * (4 - math.pi), rel=0.05)


def test_gentle_facets_are_left_alone():
    cyl = _tris("cylinder(r = 10, h = 10);", fn=48)
    out = bevel.bevel(cyl, 1, 4, 0.5)
    # only the two rims are rounded, not 48 facet edges
    assert _volume(out) == pytest.approx(
        _volume(cyl) - 2 * (1 - math.pi / 4) * 2 * math.pi * 9.6, rel=0.02)


def test_the_node_bakes_compiles_and_round_trips(app, tmp_path):
    doc = DocumentModel()
    cube = doc.add_node("cube", dict(width=20.0, depth=20.0, height=20.0))
    node = doc.wrap_nodes([cube], "bevel")
    node.params.update(width=2.0, segments=6)
    assert validate(doc.root) == {}
    tris = mesh.tessellate(doc.root)
    assert _volume(tris) < 8000 - 100 and _closed(tris)
    code = doc.to_scad()
    assert 'kcad_bevel(width = 2, segments = 6, profile = 0.5, angle = ' \
        '30, which = "convex",' in code
    path = tmp_path / "bevel.scad"
    document.export_scad(doc, str(path))
    other = DocumentModel()
    assert not scadparse.import_scad(other, str(path))
    assert other.to_scad().splitlines()[3:] == code.splitlines()[3:]


_POCKET = ("difference() { cube([40, 30, 15]); "
           "translate([10, 8, 5]) cube([20, 14, 20]); }")


def test_a_pocket_rim_is_one_mitred_loop():
    _edges, runs = bevel.select(_tris(_POCKET), 30, "convex")
    rims = [r for r in runs if r["closed"]]
    assert len(rims) == 1 and len(rims[0]["edges"]) == 4
    zs = {round(p[2], 6) for p in rims[0]["points"]}
    assert zs == {15.0}


def test_inside_fillers_stop_under_a_bevelled_rim():
    out = bevel.bevel(_tris(_POCKET), 2, 6, 0.5, which="both")
    assert _closed(out)
    # nothing inside the pocket's footprint may stand above the rim's
    # bevel: 2 mm down from the top, within the pocket walls
    for tri in out:
        for x, y, z in tri:
            if 10.01 < x < 29.99 and 8.01 < y < 21.99:
                assert z <= 15 - 2 + 1e-6
