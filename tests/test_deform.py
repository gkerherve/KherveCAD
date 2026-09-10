"""Tests for the deformers and subdivision (deform.py) and their baked
nodes (bake.py).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import deform, document, mesh, scadparse
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def _box(x0, y0, z0, x1, y1, z1):
    return mesh.cube_mesh(dict(x=x0, y=y0, z=z0, width=x1 - x0,
                               depth=y1 - y0, height=z1 - z0,
                               center=False))


def _bounds(tris):
    pts = [v for tri in tris for v in tri]
    return ([min(p[i] for p in pts) for i in range(3)],
            [max(p[i] for p in pts) for i in range(3)])


def _closed(tris) -> bool:
    count = Counter()
    for a, b, c in tris:
        for u, w in ((a, b), (b, c), (c, a)):
            count[(u, w)] += 1
    return all(n == 1 and count[(w, u)] == 1
               for (u, w), n in count.items())


def _volume(tris) -> float:
    total = 0.0
    for a, b, c in tris:
        total += (a[0] * (b[1] * c[2] - b[2] * c[1])
                  - a[1] * (b[0] * c[2] - b[2] * c[0])
                  + a[2] * (b[0] * c[1] - b[1] * c[0]))
    return total / 6.0


def _longest(tris):
    return max(math.dist(a, b) for tri in tris
               for a, b in ((tri[0], tri[1]), (tri[1], tri[2]),
                            (tri[2], tri[0])))


# ── edge splitting ─────────────────────────────────────────────────

def test_split_long_edges_stays_closed_and_keeps_volume():
    cube = _box(0, 0, 0, 10, 10, 10)
    fine = deform.split_long_edges(cube, 3.0)
    assert _longest(fine) <= 3.0 + 1e-9
    assert _closed(fine)                     # no T-junction cracks
    assert _volume(fine) == pytest.approx(1000.0)
    assert len(fine) > 12 * 8


# ── deformers ──────────────────────────────────────────────────────

def test_bend_curls_a_bar_into_a_quarter_circle():
    bar = deform.split_long_edges(_box(-2, -2, 0, 2, 2, 40), 1.0)
    bent = deform.bend(bar, "z", "x", 90.0)
    radius = 40 / (math.pi / 2)
    lo, hi = _bounds(bent)
    assert hi[0] == pytest.approx(radius, abs=0.2)     # the tip reaches R
    assert hi[2] == pytest.approx(radius + 2, abs=0.2)
    assert lo[2] == pytest.approx(0.0, abs=1e-9)       # the base stays
    assert _closed(bent)
    assert _volume(bent) == pytest.approx(640.0, rel=0.03)


def test_twist_turns_the_far_end_and_keeps_the_volume():
    bar = deform.split_long_edges(_box(-5, -1, 0, 5, 1, 30), 1.0)
    twisted = deform.twist(bar, "z", 90.0)
    top = [v for t in twisted for v in t if v[2] > 30 - 1e-9]
    xs = [v[0] for v in top]
    ys = [v[1] for v in top]
    assert max(xs) == pytest.approx(1.0, abs=1e-6)   # the slab turned 90°
    assert max(ys) == pytest.approx(5.0, abs=1e-6)
    assert _closed(twisted)
    assert _volume(twisted) == pytest.approx(600.0, rel=0.02)


def test_taper_narrows_the_far_end():
    bar = deform.split_long_edges(_box(-2, -2, 0, 2, 2, 20), 2.0)
    tapered = deform.taper(bar, "z", 0.5)
    top = [v for t in tapered for v in t if v[2] > 20 - 1e-9]
    assert max(v[0] for v in top) == pytest.approx(1.0)
    bottom = [v for t in tapered for v in t if v[2] < 1e-9]
    assert max(v[0] for v in bottom) == pytest.approx(2.0)
    assert _closed(tapered)


def test_lattice_drags_points_with_their_corner():
    cube = deform.split_long_edges(_box(0, 0, 0, 10, 10, 10), 2.0)
    shift_top = [[0, 0, 0]] * 4 + [[5, 0, 0]] * 4        # z = 1 corners
    sheared = deform.lattice(cube, shift_top)
    lo, hi = _bounds(sheared)
    assert hi[0] == pytest.approx(15.0) and lo[0] == pytest.approx(0.0)
    assert _volume(sheared) == pytest.approx(1000.0)    # a shear


def test_loop_subdivision_smooths_a_cube():
    cube = _box(0, 0, 0, 20, 20, 20)
    smooth = deform.loop_subdivide(cube, 2)
    assert len(smooth) == 12 * 16
    assert _closed(smooth) and _volume(smooth) > 0
    assert 0.3 * 8000 < _volume(smooth) < 8000           # pulled inward
    lo, hi = _bounds(smooth)
    assert all(0 <= v <= 20 for v in lo + hi)


# ── the nodes ──────────────────────────────────────────────────────

def _bent_bar(app, **params):
    doc = DocumentModel()
    bar = doc.add_node("cube", dict(x=-2.0, y=-2.0, width=4.0, depth=4.0,
                                    height=40.0))
    node = doc.wrap_nodes([bar], "bend")
    node.params.update(dict(dict(axis="z", toward="x", angle=90.0,
                                 detail=2.0), **params))
    return doc, node


def test_the_bend_node_previews_the_bent_bar(app):
    doc, _node = _bent_bar(app)
    tris = mesh.tessellate(doc.root)
    assert _closed(tris) and _volume(tris) > 0
    _lo, hi = _bounds(tris)
    assert hi[0] == pytest.approx(40 / (math.pi / 2), abs=0.3)


def test_deformer_codegen_and_lossless_round_trip(app, tmp_path):
    doc = DocumentModel()
    for kind, extra in (("bend", {}), ("twist", dict(angle=45.0)),
                        ("taper", dict(factor=0.7)),
                        ("lattice", dict(offsets=[[0.0, 0.0, 0.0]] * 4
                                         + [[3.0, 0.0, 0.0]] * 4)),
                        ("subdivide", dict(levels=1))):
        node = doc.wrap_nodes([doc.add_node("cube")], kind)
        node.params.update(extra)
    code1 = doc.to_scad()
    assert 'kcad_bend(axis = "z", toward = "x", angle = 45, detail = 2,' \
        in code1
    assert "module kcad_subdivide(levels = 1, points = [], faces = [])" \
        in code1
    path = tmp_path / "deform.scad"
    document.export_scad(doc, str(path))
    other = DocumentModel()
    assert not scadparse.import_scad(other, str(path))
    assert other.to_scad().splitlines()[3:] == code1.splitlines()[3:]


def test_deformer_validation(app):
    doc = DocumentModel()
    cut = doc.wrap_nodes([doc.add_node("cube"), doc.add_node("sphere")],
                         "difference")
    bent = doc.wrap_nodes([cut], "bend")
    same = doc.wrap_nodes([doc.add_node("cube")], "bend")
    same.params.update(toward="z")
    lat = doc.wrap_nodes([doc.add_node("cube")], "lattice")
    lat.params["offsets"] = [[0.0, 0.0, 0.0]] * 7
    loop = doc.add_node("for_loop")
    inner = doc.add_node("twist", parent=loop)
    doc.add_node("cube", parent=inner)
    errors = validate(doc.root)
    assert "difference" in errors[bent.id]
    assert "must differ" in errors[same.id]
    assert "8 corner" in errors[lat.id]
    assert "for" in errors[inner.id]


def _openscad_binary():
    for candidate in (shutil.which("openscad"), "/opt/homebrew/bin/openscad",
                      "/usr/local/bin/openscad",
                      "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"):
        if candidate and Path(candidate).exists():
            return candidate
    return None


@pytest.mark.parametrize("kind", ["bend", "twist", "subdivide"])
def test_openscad_renders_the_baked_deformation(app, tmp_path, kind):
    binary = _openscad_binary()
    if binary is None:
        pytest.skip("OpenSCAD is not installed")
    from khervecad import engine
    doc = DocumentModel()
    bar = doc.add_node("cube", dict(x=-3.0, y=-2.0, width=6.0, depth=4.0,
                                    height=30.0))
    node = doc.wrap_nodes([bar], kind)
    if kind == "bend":
        node.params.update(angle=60.0, detail=3.0)
    elif kind == "twist":
        node.params.update(angle=120.0, detail=3.0)
    scad, stl = tmp_path / f"{kind}.scad", tmp_path / f"{kind}.stl"
    scad.write_text(doc.to_scad())
    run = subprocess.run([binary, "-o", str(stl), str(scad)],
                         capture_output=True, text=True, timeout=180)
    assert run.returncode == 0, run.stderr[-1500:]
    exact = engine.parse_stl(str(stl))
    preview = mesh.tessellate(doc.root)
    for got, want in zip(_bounds(exact), _bounds(preview)):
        assert got == pytest.approx(want, abs=0.01)
    assert _volume(exact) == pytest.approx(_volume(preview), rel=0.005)
