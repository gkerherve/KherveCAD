"""Sweep along a path: geometry (sweep.py), the node, its program and
the real OpenSCAD engine.

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
from collections import Counter
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")

from PyQt5.QtWidgets import QApplication

from khervecad import document, mesh, scadparse, sweep
from khervecad.model import CadNode, DocumentModel, validate

SQUARE = [(-5.0, -2.0), (5.0, -2.0), (5.0, 2.0), (-5.0, 2.0)]   # 10 x 4
CIRCLE = [(3 * math.cos(2 * math.pi * k / 24),
           3 * math.sin(2 * math.pi * k / 24)) for k in range(24)]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


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


# ------------------------------------------------------------ geometry
def test_a_straight_vertical_sweep_is_the_linear_extrude():
    tris = sweep.sweep([SQUARE], [[0, 0, 0], [0, 0, 30]], smooth=0)
    assert _closed(tris)
    lo, hi = _bounds(tris)
    assert lo == pytest.approx([-5, -2, 0]) and hi == pytest.approx([5, 2, 30])
    assert _volume(tris) == pytest.approx(10 * 4 * 30)


def test_a_horizontal_sweep_keeps_profile_y_up():
    """Seen with the path coming towards you, x is right and y up:
    along +X the 10 mm width lies across Y and the 4 mm height in Z."""
    tris = sweep.sweep([SQUARE], [[0, 0, 0], [40, 0, 0]], smooth=0)
    lo, hi = _bounds(tris)
    assert hi[1] - lo[1] == pytest.approx(10)
    assert hi[2] - lo[2] == pytest.approx(4)
    assert _volume(tris) == pytest.approx(10 * 4 * 40)


def test_smoothing_keeps_every_given_point_on_the_path():
    path = [[0, 0, 0], [0, 0, 30], [30, 0, 50]]
    centres = sweep.densify(path, 3)
    for p in path:
        assert any(all(abs(c[i] - p[i]) < 1e-9 for i in range(3))
                   for c in centres)
    assert len(centres) == 2 * 4 + 1
    assert sweep.densify(path, 0) == [tuple(map(float, p)) for p in path]


def test_a_bent_sweep_is_one_closed_outward_solid():
    tris = sweep.sweep([CIRCLE], [[0, 0, 0], [0, 0, 30], [30, 0, 50],
                                  [60, 20, 50]], smooth=3)
    assert tris and _closed(tris) and _volume(tris) > 0
    # roughly the section area times the path length
    centres = sweep.densify([[0, 0, 0], [0, 0, 30], [30, 0, 50],
                             [60, 20, 50]], 3)
    length = sum(math.dist(a, b) for a, b in zip(centres, centres[1:]))
    area = math.pi * 9 * (math.sin(2 * math.pi / 24) * 24 / (2 * math.pi))
    assert _volume(tris) == pytest.approx(area * length, rel=0.03)


def test_frames_do_not_flip_and_are_orthonormal():
    path = [[10 * math.cos(a), 10 * math.sin(a), 4 * a]
            for a in [i * 0.4 for i in range(20)]]
    centres = sweep.densify(path, 2)
    t, u, v = sweep.frames(centres)
    for i in range(len(centres)):
        assert abs(sum(a * b for a, b in zip(t[i], u[i]))) < 1e-9
        assert abs(sum(a * b for a, b in zip(u[i], v[i]))) < 1e-9
        assert math.dist(v[i], (0, 0, 0)) == pytest.approx(1.0)
        if i:
            assert sum(a * b for a, b in zip(u[i], u[i - 1])) > 0.9


def test_wall_thickness_hollows_the_tube():
    path = [[0, 0, 0], [0, 0, 20]]
    solid = sweep.sweep([SQUARE], path, smooth=0)
    hollow = sweep.sweep([SQUARE], path, smooth=0, wall=1.0)
    assert _closed(hollow)
    assert _volume(hollow) == pytest.approx(_volume(solid) - 8 * 2 * 20)
    # a wall thicker than the profile simply gives the solid
    assert _volume(sweep.sweep([SQUARE], path, smooth=0, wall=5)) == \
        pytest.approx(_volume(solid))


def test_a_closed_loop_has_no_caps_and_joins_its_seam():
    ring = [[20 * math.cos(math.radians(a)), 20 * math.sin(math.radians(a)),
             0.0] for a in range(0, 360, 30)]
    tris = sweep.sweep([CIRCLE], ring, smooth=2, closed=True)
    assert tris and _closed(tris)
    torus = 2 * math.pi * 20 * math.pi * 9
    assert _volume(tris) == pytest.approx(torus, rel=0.05)
    # typing the first point again at the end is the same loop
    again = sweep.sweep([CIRCLE], ring + [ring[0]], smooth=2, closed=True)
    assert len(again) == len(tris)


def test_twist_and_scale_act_over_the_length():
    path = [[0, 0, 0], [0, 0, 30]]
    twisted = sweep.sweep([SQUARE], path, smooth=0, twist=90)
    lo, hi = _bounds(twisted)
    assert hi[1] - lo[1] == pytest.approx(10)       # turned onto Y at the top
    tapered = sweep.sweep([SQUARE], path, smooth=0, scale=0.5)
    assert _closed(tapered)
    assert _volume(tapered) == pytest.approx(10 * 4 * 30 * (1 + 0.5 + 0.25) / 3)


def test_degenerate_paths_make_nothing():
    assert sweep.sweep([SQUARE], [[0, 0, 0]]) == []
    assert sweep.sweep([SQUARE], [[0, 0, 0], [0, 0, 0]]) == []
    assert sweep.sweep([SQUARE], [[0, 0, 0], [1, 0, 0]], closed=True) == []
    assert sweep.sweep([], [[0, 0, 0], [0, 0, 9]]) == []


# ---------------------------------------------------------- the node
def _pipe(doc, **params):
    settings = dict(
        path=[[0.0, 0.0, 0.0], [0.0, 0.0, 30.0], [30.0, 0.0, 50.0]],
        smooth=2, twist=0.0, scale=1.0, wall=0.0, closed=False)
    settings.update(params)
    node = doc.add_node("sweep", settings)
    doc.add_node("circle", dict(radius=4.0, segments=16), parent=node)
    return node


def test_the_node_previews_as_a_closed_tube(app):
    doc = DocumentModel()
    _pipe(doc, wall=1.0)
    tris = mesh.tessellate(doc.root)
    assert tris and _closed(tris) and _volume(tris) > 0
    assert not validate(doc.root)


def test_codegen_bakes_a_polyhedron_and_keeps_the_profile(app):
    doc = DocumentModel()
    _pipe(doc, closed=False)
    code = doc.to_scad()
    assert "module kcad_sweep(" in code and "closed = false" in code
    call = next(ln for ln in code.splitlines()
                if ln.lstrip().startswith("kcad_sweep("))
    assert "path = [[0, 0, 0], [0, 0, 30], [30, 0, 50]]" in call
    assert "points = [" in code and "faces = [" in code
    assert "circle(" in code                       # the profile stays


def test_the_sweep_round_trips_through_its_program(app, tmp_path):
    doc = DocumentModel()
    # each shape keeps its own $fn in the program (the document-wide
    # count would otherwise replace the profile's 16 segments on import)
    doc.set_global_fn(False)
    _pipe(doc, wall=1.5, closed=True, twist=45.0)
    code1 = doc.to_scad()
    path = tmp_path / "sweep.scad"
    document.export_scad(doc, str(path))
    other = DocumentModel()
    other.set_global_fn(False)
    assert not scadparse.import_scad(other, str(path))
    assert other.to_scad().splitlines()[3:] == code1.splitlines()[3:]
    node = next(n for n in other.root.walk() if n.type == "sweep")
    assert node.params["closed"] is True
    assert node.params["wall"] == 1.5 and node.params["smooth"] == 2
    assert [c.type for c in node.children] == ["circle"]


def test_the_sweep_wraps_a_drawn_profile_from_the_toolbar(app):
    doc = DocumentModel()
    rect = doc.add_node("rect")
    node = doc.wrap_nodes([rect], "sweep")
    assert node.type == "sweep" and rect.parent is node
    assert mesh.tessellate(doc.root)


def test_sweep_validation(app):
    doc = DocumentModel()
    solid = doc.add_node("sweep")
    doc.add_node("cube", parent=solid)
    empty = doc.add_node("sweep")
    short = doc.add_node("sweep", dict(path=[[0.0, 0.0, 0.0]]))
    doc.add_node("circle", parent=short)
    loop = doc.add_node("for_loop")
    nested = doc.add_node("sweep", parent=loop)
    doc.add_node("circle", parent=nested)
    cut = doc.add_node("sweep")
    doc.wrap_nodes([doc.add_node("circle", parent=cut),
                    doc.add_node("circle", dict(radius=2.0), parent=cut)],
                   "difference")
    typo = doc.add_node("sweep", dict(path=[[0.0, 0.0, "h"],
                                            [0.0, 0.0, 9.0]]))
    doc.add_node("circle", parent=typo)
    errors = validate(doc.root)
    assert "3D" in errors[solid.id]
    assert "2D profile" in errors[empty.id]
    assert "at least 2" in errors[short.id]
    assert "for" in errors[nested.id]
    assert "Wall thickness" in errors[cut.id]
    assert "path point 0" in errors[typo.id]
    # an extrude around a sweep is 3D inside an extrude
    ext = doc.add_node("linear_extrude")
    inner = doc.add_node("sweep", parent=ext)
    doc.add_node("circle", parent=inner)
    assert "3D" in validate(doc.root)[ext.id]


def test_the_example_loads_and_previews(app):
    from khervecad import examples
    doc = DocumentModel()
    build = next(b for n, _c, b in examples.EXAMPLES if "sweep" in n)
    examples.load_example(doc, build)
    assert not validate(doc.root)
    tris = mesh.tessellate(doc.root)
    assert len(tris) > 1000


# --------------------------------------------------------- the engine
def _openscad_binary():
    for candidate in (shutil.which("openscad"), "/opt/homebrew/bin/openscad",
                      "/usr/local/bin/openscad",
                      "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"):
        if candidate and Path(candidate).exists():
            return candidate
    return None


def test_openscad_renders_the_baked_sweep(app, tmp_path):
    binary = _openscad_binary()
    if binary is None:
        pytest.skip("OpenSCAD is not installed")
    from khervecad import engine
    doc = DocumentModel()
    _pipe(doc, wall=1.0)
    scad, stl = tmp_path / "sweep.scad", tmp_path / "sweep.stl"
    scad.write_text(doc.to_scad())
    run = subprocess.run([binary, "-o", str(stl), str(scad)],
                         capture_output=True, text=True, timeout=180)
    assert run.returncode == 0, run.stderr[-1500:]
    exact = engine.parse_stl(str(stl))
    preview = mesh.tessellate(doc.root)
    for got, want in zip(_bounds(exact), _bounds(preview)):
        assert got == pytest.approx(want, abs=0.01)
    assert _volume(exact) == pytest.approx(_volume(preview), rel=0.002)
