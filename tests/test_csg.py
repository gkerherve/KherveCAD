"""Exact preview booleans through Manifold (csg.py).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")

from khervecad import analysis, csg, mesh, scadparse

pytestmark = pytest.mark.skipif(not csg.available(),
                                reason="manifold3d not installed")


def _run(code, fn=48):
    root, _warnings = scadparse.parse_scad(code)
    rows = mesh.tessellate_colored(root, fn=fn)
    tris = [t for t, _c in rows]
    return root, tris, {c for _t, c in rows}


def _volume(tris):
    return analysis.mass_properties(tris)["volume"]


def _polygon_area(r, n):
    return 0.5 * n * r * r * math.sin(2 * math.pi / n)


def test_a_difference_cuts_the_hole_in_the_preview():
    root, tris, _c = _run(
        "difference() { cube(10); "
        "translate([5, 5, -1]) cylinder(r = 2, h = 12); }")
    assert _volume(tris) == pytest.approx(
        1000 - 10 * _polygon_area(2, 48), rel=1e-6)
    assert not mesh.approximates(root)
    assert mesh.uses_booleans(root)          # it still HAS a boolean
    assert not mesh.needs_exact(root)        # but needs no OpenSCAD


def test_intersection_and_minkowski_are_exact():
    _r, tris, _c = _run("intersection() { cube(10, center = true); "
                        "cube([4, 4, 20], center = true); }")
    assert _volume(tris) == pytest.approx(160, rel=1e-9)
    _r, tris, _c = _run("minkowski() { cube(10); cube(2, center=true); }")
    assert _volume(tris) == pytest.approx(12 ** 3, rel=1e-9)


def test_overlapping_solids_in_one_operand_are_unioned_first():
    _r, tris, _c = _run(
        "difference() { union() { cube(10); translate([5, 0, 0]) "
        "cube(10); } translate([-1, -1, 5]) cube([20, 20, 10]); }")
    assert _volume(tris) == pytest.approx(15 * 10 * 5, rel=1e-9)


def test_colours_survive_and_the_cut_wears_the_tool_colour():
    _r, tris, colours = _run(
        'color("red") difference() { cube(10); color("blue") '
        'translate([5, 5, -1]) cylinder(r = 2, h = 12); }')
    assert colours == {("red", 1.0), ("blue", 1.0)}


def test_a_flat_operand_falls_back_and_stays_approximated():
    root, tris, _c = _run("difference() { cube(10); square(3); }")
    assert _volume(tris) == pytest.approx(1000)       # first operand
    assert mesh.approximates(root)


def test_a_hidden_first_child_is_not_the_one_kept():
    _r, tris, _c = _run("difference() { *cube(50); cube(10); "
                        "translate([5, -1, -1]) cube(12); }")
    assert _volume(tris) == pytest.approx(500, rel=1e-9)


def test_the_selection_pass_still_shows_a_selected_tool():
    root, _warnings = scadparse.parse_scad(
        "difference() { cube(10); "
        "translate([5, 5, -1]) cylinder(r = 2, h = 12); }")
    tool = next(n for n in root.walk() if n.type == "cylinder")
    lit = mesh.selected_world_tris(root, {tool.id}, fn=24)
    zs = [v[2] for tri in lit for v in tri]
    assert min(zs) == pytest.approx(-1) and max(zs) == pytest.approx(11)


def test_a_fillet_preview_cuts_its_convex_edge():
    from khervecad.model import DocumentModel
    doc = DocumentModel()
    root, _w = scadparse.parse_scad("cube([40, 30, 20]);")
    cube = root.children[0]
    doc.root.add(cube)
    node = doc.wrap_nodes([cube], "fillet")
    node.params.update(radius=4.0, edges=[[0, 0, 20, 40, 0, 20]])
    tris = mesh.tessellate(doc.root)
    removed = 40 * 4 * 4 * (1 - math.pi / 4)
    assert _volume(tris) == pytest.approx(24000 - removed, rel=0.01)
    assert not mesh.approximates(doc.root)
