"""The Pattern node (pattern.py): linear / polar / grid copies — the
preview, the program, the round trip, validation and the real
OpenSCAD engine.

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
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")

from PyQt5.QtWidgets import QApplication

from khervecad import document, mesh, pattern, scadparse
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _bounds(tris):
    pts = [v for tri in tris for v in tri]
    return ([min(p[i] for p in pts) for i in range(3)],
            [max(p[i] for p in pts) for i in range(3)])


def _volume(tris) -> float:
    total = 0.0
    for a, b, c in tris:
        total += (a[0] * (b[1] * c[2] - b[2] * c[1])
                  - a[1] * (b[0] * c[2] - b[2] * c[0])
                  + a[2] * (b[0] * c[1] - b[1] * c[0]))
    return total / 6.0


def _pattern(doc, kind, x=0.0, parent=None, **params):
    """A pattern of one 10 mm cube at (x, 0, 0)."""
    settings = dict(kind=kind, count=4, dx=20.0, dy=0.0, dz=0.0,
                    angle=360.0, axis="z", count_x=3, count_y=3, count_z=1)
    settings.update(params)
    node = doc.add_node("pattern", settings, parent=parent)
    cube = doc.add_node("cube", dict(x=x, y=0.0, z=0.0, width=10.0,
                                     depth=10.0, height=10.0, center=False),
                        parent=node)
    return node, cube


CUBE_TRIS = 12


# ------------------------------------------------------------ preview
def test_a_linear_pattern_steps_its_copies(app):
    doc = DocumentModel()
    _pattern(doc, "linear", count=4, dx=20.0, dy=5.0, dz=6.0)
    tris = mesh.tessellate(doc.root)
    assert len(tris) == 4 * CUBE_TRIS
    lo, hi = _bounds(tris)
    assert lo == pytest.approx([0, 0, 0])
    assert hi == pytest.approx([60 + 10, 15 + 10, 18 + 10])
    assert not validate(doc.root)


def test_a_full_polar_pattern_spreads_evenly_and_never_doubles_up(app):
    doc = DocumentModel()
    _pattern(doc, "polar", x=30.0, count=4, angle=360.0, axis="z")
    tris = mesh.tessellate(doc.root)
    assert len(tris) == 4 * CUBE_TRIS
    lo, hi = _bounds(tris)
    # copies at 0, 90, 180, 270: the cube's far corner (40, 10) sweeps
    # the extent to +-40 on both axes
    assert lo == pytest.approx([-40, -40, 0])
    assert hi == pytest.approx([40, 40, 10])
    corners = {tuple(round(c, 6) for c in v) for tri in tris for v in tri}
    # the cube's (30, 0, 0) corner turned by 0, 90, 180 and 270 degrees
    for want in ((30, 0, 0), (0, 30, 0), (-30, 0, 0), (0, -30, 0)):
        assert tuple(float(c) for c in want) in corners
    assert len(corners) == 4 * 8


def test_a_partial_polar_pattern_spans_its_angle(app):
    doc = DocumentModel()
    _pattern(doc, "polar", x=30.0, count=3, angle=90.0, axis="z")
    tris = mesh.tessellate(doc.root)
    assert len(tris) == 3 * CUBE_TRIS
    lo, hi = _bounds(tris)
    # first copy at 0 deg (x 30..40), last at 90 deg (y 30..40): the
    # copies span the angle rather than stopping at 60 deg
    assert hi[0] == pytest.approx(40) and hi[1] == pytest.approx(40)
    assert lo[0] == pytest.approx(-10) and lo[1] == pytest.approx(0)


def test_a_polar_rise_makes_a_helix_about_any_axis(app):
    doc = DocumentModel()
    _pattern(doc, "polar", x=30.0, count=4, angle=360.0, axis="z", dz=5.0)
    lo, hi = _bounds(mesh.tessellate(doc.root))
    assert hi[2] == pytest.approx(10 + 3 * 5)
    other = DocumentModel()
    _pattern(other, "polar", x=30.0, count=4, angle=360.0, axis="x", dz=5.0)
    lo, hi = _bounds(mesh.tessellate(other.root))
    assert hi[0] == pytest.approx(40 + 15)      # the rise is along X
    assert lo[1] == pytest.approx(-10) and hi[2] == pytest.approx(10)


def test_a_grid_pattern_counts_in_three_directions(app):
    doc = DocumentModel()
    _pattern(doc, "grid", count_x=2, count_y=3, count_z=2, dx=15.0,
             dy=20.0, dz=25.0)
    tris = mesh.tessellate(doc.root)
    assert len(tris) == 2 * 3 * 2 * CUBE_TRIS
    lo, hi = _bounds(tris)
    assert lo == pytest.approx([0, 0, 0])
    assert hi == pytest.approx([15 + 10, 40 + 10, 25 + 10])


def test_a_selected_child_glows_in_every_copy(app):
    doc = DocumentModel()
    node, cube = _pattern(doc, "linear", count=3)
    tris = mesh.selected_world_tris(doc.root, {cube.id})
    assert len(tris) == 3 * CUBE_TRIS


def test_parameters_take_expressions_and_loop_variables(app):
    doc = DocumentModel()
    doc.add_node("assign", dict(variable="n", value="3"))
    loop = doc.add_node("for_loop", dict(variable="i", start=0, end=1,
                                         step=1, values=""))
    _pattern(doc, "linear", parent=loop, count="n", dx="10 * (i + 1)",
             dy="i * 50")
    assert not validate(doc.root)
    tris = mesh.tessellate(doc.root)
    assert len(tris) == 2 * 3 * CUBE_TRIS
    lo, hi = _bounds(tris)
    # i = 0: steps of 10 -> x up to 30; i = 1: steps of 20 in x and 50
    # in y -> the third copy at (40, 100)
    assert hi == pytest.approx([2 * 20 + 10, 2 * 50 + 10, 10])


def test_a_pattern_of_2d_shapes_extrudes_every_copy(app):
    doc = DocumentModel()
    ext = doc.add_node("linear_extrude", dict(height=5.0, twist=0.0,
                                              scale=1.0, center=False,
                                              segments=0))
    node = doc.add_node("pattern", dict(kind="linear", count=3, dx=20.0,
                                        dy=0.0, dz=0.0), parent=ext)
    doc.add_node("rect", dict(x=0.0, y=0.0, width=10.0, height=10.0),
                 parent=node)
    assert not validate(doc.root)
    tris = mesh.tessellate(doc.root)
    assert _volume(tris) == pytest.approx(3 * 10 * 10 * 5)
    assert _bounds(tris)[1][0] == pytest.approx(50)


def test_wrapping_from_the_toolbar_and_the_empty_node(app):
    doc = DocumentModel()
    cube = doc.add_node("cube")
    node = doc.wrap_nodes([cube], "pattern")
    assert node.type == "pattern" and cube.parent is node
    assert len(mesh.tessellate(doc.root)) == 4 * CUBE_TRIS
    empty = doc.add_node("pattern")
    assert "empty" in validate(doc.root)[empty.id]


# ------------------------------------------------------------ program
def test_codegen_calls_the_helper_defined_once(app):
    doc = DocumentModel()
    _pattern(doc, "polar", x=30.0, count=6, angle=360.0, axis="y", dz=2.0)
    _pattern(doc, "grid", count_x=2, count_y=3, count_z=1, dx=5.0,
             dy=6.0, dz=0.0)
    _pattern(doc, "linear", count="n", dx=20.0, dy=0.0, dz=1.0)
    code = doc.to_scad()
    assert code.count("module kcad_pattern(") == 1
    assert code.index("module kcad_pattern(") < code.index("kcad_pattern(kind")
    calls = [ln.strip() for ln in code.splitlines()
             if ln.lstrip().startswith("kcad_pattern(")]
    assert calls == [
        'kcad_pattern(kind = "polar", count = 6, angle = 360, axis = "y", '
        'rise = 2) {',
        'kcad_pattern(kind = "grid", counts = [2, 3, 1], step = [5, 6, 0]) {',
        'kcad_pattern(kind = "linear", count = n, step = [20, 0, 1]) {']
    assert "children()" in code                   # real OpenSCAD, not baked


def test_the_pattern_round_trips_through_its_program(app, tmp_path):
    doc = DocumentModel()
    doc.set_global_fn(False)
    _pattern(doc, "polar", x=30.0, count=5, angle=120.0, axis="x", dz=3.0)
    _pattern(doc, "grid", count_x=2, count_y=2, count_z=3, dx=5.0,
             dy=6.0, dz=7.0)
    _pattern(doc, "linear", count="n", dx="w * 2", dy=0.0, dz=1.0)
    code1 = doc.to_scad()
    path = tmp_path / "pattern.scad"
    document.export_scad(doc, str(path))
    other = DocumentModel()
    other.set_global_fn(False)
    assert not scadparse.import_scad(other, str(path))
    assert other.to_scad().splitlines()[3:] == code1.splitlines()[3:]
    polar, grid, linear = [n for n in other.root.walk()
                           if n.type == "pattern"]
    assert polar.params["kind"] == "polar" and polar.params["axis"] == "x"
    assert polar.params["count"] == 5 and polar.params["dz"] == 3.0
    assert polar.params["angle"] == 120.0
    assert (grid.params["count_x"], grid.params["count_y"],
            grid.params["count_z"]) == (2, 2, 3)
    assert linear.params["count"] == "n" and linear.params["dx"] == "w * 2"
    assert [c.type for c in polar.children] == ["cube"]


def test_an_assistant_can_write_the_call_by_hand(app, tmp_path):
    path = tmp_path / "hand.scad"
    path.write_text('kcad_pattern(kind = "polar", count = 6) {\n'
                    '    translate([30, 0, 0]) cylinder(h = 10, r = 3);\n'
                    '}\n'
                    'kcad_pattern(kind = "grid", counts = [2, 2, 1], '
                    'step = [20, 20, 0]) cube(5);\n')
    doc = DocumentModel()
    assert not scadparse.import_scad(doc, str(path))
    nodes = [n for n in doc.root.walk() if n.type == "pattern"]
    assert [n.params["kind"] for n in nodes] == ["polar", "grid"]
    assert nodes[0].params["count"] == 6 and nodes[0].params["angle"] == 360.0
    assert not validate(doc.root)
    assert len(pattern.matrices(nodes[0], {})) == 6
    assert len(pattern.matrices(nodes[1], {})) == 4


# --------------------------------------------------------- validation
def test_pattern_validation(app):
    doc = DocumentModel()
    zero, _c = _pattern(doc, "linear", count=0)
    too_many, _c = _pattern(doc, "grid", count_x=20, count_y=20, count_z=3)
    flat, _c = _pattern(doc, "grid", count_x=2, count_y=0, count_z=1)
    typo, _c = _pattern(doc, "linear", count="n +")
    unknown, _c = _pattern(doc, "linear", dx="width_of_nothing")
    bogus, _c = _pattern(doc, "spiral")
    fine, _c = _pattern(doc, "polar", count=1000)
    errors = validate(doc.root)
    assert "count must be at least 1" in errors[zero.id]
    assert "1200 copies" in errors[too_many.id]
    assert "1000" in errors[too_many.id]
    assert "count_y must be at least 1" in errors[flat.id]
    assert errors[typo.id].startswith("count:")
    assert errors[unknown.id].startswith("dx:")
    assert "kind" in errors[bogus.id]
    assert fine.id not in errors


def test_the_example_loads_and_previews(app):
    from khervecad import examples
    doc = DocumentModel()
    build = next(b for n, _c, b in examples.EXAMPLES if "pattern" in n)
    examples.load_example(doc, build)
    assert not validate(doc.root)
    kinds = sorted(n.params["kind"] for n in doc.root.walk()
                   if n.type == "pattern")
    assert kinds == ["grid", "linear", "polar", "polar"]
    assert len(mesh.tessellate(doc.root)) > 1000


# --------------------------------------------------------- the engine
def _openscad_binary():
    for candidate in (shutil.which("openscad"), "/opt/homebrew/bin/openscad",
                      "/usr/local/bin/openscad",
                      "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"):
        if candidate and Path(candidate).exists():
            return candidate
    return None


def test_openscad_renders_the_same_copies_as_the_preview(app, tmp_path):
    binary = _openscad_binary()
    if binary is None:
        pytest.skip("OpenSCAD is not installed")
    from khervecad import engine
    doc = DocumentModel()
    # four patterns in four regions of space, so no copy touches another
    _pattern(doc, "polar", x=30.0, count=5, angle=200.0, axis="z", dz=4.0)
    _pattern(doc, "polar", x=60.0, count=6, angle=360.0, axis="y")
    _pattern(doc, "linear", x=-100.0, count=3, dx=0.0, dy=-30.0, dz=3.0)
    _pattern(doc, "grid", x=100.0, count_x=2, count_y=2, count_z=2,
             dx=12.0, dy=12.0, dz=40.0)
    scad, stl = tmp_path / "pattern.scad", tmp_path / "pattern.stl"
    scad.write_text(doc.to_scad())
    run = subprocess.run([binary, "-o", str(stl), str(scad)],
                         capture_output=True, text=True, timeout=180)
    assert run.returncode == 0, run.stderr[-1500:]
    exact = engine.parse_stl(str(stl))
    preview = mesh.tessellate(doc.root)
    for got, want in zip(_bounds(exact), _bounds(preview)):
        assert got == pytest.approx(want, abs=0.01)
    # the copies do not overlap, so the union's volume is the sum
    assert _volume(exact) == pytest.approx(_volume(preview), rel=0.002)
