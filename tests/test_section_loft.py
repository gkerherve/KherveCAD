"""Loft through sections: geometry (section_loft.py), the node, its
program and the real OpenSCAD engine.

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

from khervecad import document, mesh, scadparse, section_loft
from khervecad.model import DocumentModel, validate

RECT = [(-5.0, -2.0), (5.0, -2.0), (5.0, 2.0), (-5.0, 2.0)]        # 10 x 4
BIG = [(-5.0, -5.0), (5.0, -5.0), (5.0, 5.0), (-5.0, 5.0)]         # 10 x 10
SMALL = [(-2.5, -2.5), (2.5, -2.5), (2.5, 2.5), (-2.5, 2.5)]       # 5 x 5
CIRCLE = [(4 * math.cos(2 * math.pi * k / 24),
           4 * math.sin(2 * math.pi * k / 24)) for k in range(24)]
# a car-like section: flat bottom and sides, a shoulder, a flat top
CAR = [(-9.0, 0.0), (9.0, 0.0), (10.0, 3.0), (10.0, 6.0), (8.0, 8.0),
       (-8.0, 8.0), (-10.0, 6.0), (-10.0, 3.0)]


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
    return all(n == 1 and count[(w, u)] == 1 for (u, w), n in count.items())


def _volume(tris) -> float:
    return section_loft._volume(tris)


# ------------------------------------------------------------ geometry
def test_two_equal_sections_make_the_prism():
    tris = section_loft.loft_sections([RECT, RECT], [0, 30])
    assert _closed(tris)
    lo, hi = _bounds(tris)
    assert lo == pytest.approx([-5, -2, 0]) and hi == pytest.approx([5, 2, 30])
    assert _volume(tris) == pytest.approx(10 * 4 * 30)


def test_a_shrinking_square_is_the_exact_frustum():
    tris = section_loft.loft_sections([BIG, SMALL], [0, 30])
    assert _closed(tris)
    assert _volume(tris) == pytest.approx(30 / 3 * (100 + 25 + math.sqrt(2500)))


def test_corners_stay_sharp_vertices_of_the_solid():
    tris = section_loft.loft_sections([CAR, [(x * 0.8, y * 0.9) for x, y in CAR],
                                       CAR], [0, 20, 40])
    points = {v for tri in tris for v in tri}
    for z, sec in ((0, CAR), (40, CAR)):
        for x, y in sec:
            assert (pytest.approx(x), pytest.approx(y), pytest.approx(z)) in [
                (px, py, pz) for px, py, pz in points]
    # same counts join point to point: 8 points a ring, no resampling
    assert len({v for v in points if abs(v[2] - 20) < 1e-9}) == len(CAR)


def test_different_point_counts_are_resampled_keeping_every_corner():
    tris = section_loft.loft_sections([BIG, CIRCLE], [0, 20])
    assert _closed(tris) and _volume(tris) > 0
    bottom = {(round(v[0], 9), round(v[1], 9)) for tri in tris for v in tri
              if abs(v[2]) < 1e-9}
    for corner in BIG:
        assert corner in bottom
    assert len(bottom) == max(section_loft.MIN_POINTS, 2 * len(CIRCLE))
    # between the square's and the circle's areas, times the height
    assert 20 * math.pi * 16 < _volume(tris) < 20 * 100


def test_resample_keeps_vertices_and_count():
    out = section_loft.resample(RECT, 20)
    assert len(out) == 20 and all(p in out for p in RECT)
    assert section_loft.resample(RECT, 4) == RECT


def test_smoothing_keeps_every_given_section():
    heights = [0, 10, 30]
    sections = [RECT, [(x * 2, y * 2) for x, y in RECT], RECT]
    rough = section_loft.loft_sections(sections, heights)
    smooth = section_loft.loft_sections(sections, heights, smooth=3)
    assert _closed(smooth)
    zs = sorted({round(v[2], 6) for tri in smooth for v in tri})
    assert len(zs) == 2 * 4 + 1 and all(h in zs for h in heights)
    ring10 = {(round(v[0], 6), round(v[1], 6)) for tri in smooth for v in tri
              if abs(v[2] - 10) < 1e-9}
    assert ring10 == {(x * 2, y * 2) for x, y in RECT}
    assert _volume(smooth) != pytest.approx(_volume(rough))


def test_downward_heights_and_either_winding_still_face_out():
    tris = section_loft.loft_sections([RECT[::-1], RECT], [30, 0])
    assert _closed(tris) and _volume(tris) == pytest.approx(1200)


def test_degenerate_input_makes_nothing():
    assert section_loft.loft_sections([RECT], [0]) == []
    assert section_loft.loft_sections([], []) == []
    assert section_loft.loft_sections([RECT, [(0, 0), (1, 1)]], [0, 9]) == []


# ---------------------------------------------------------- the node
def _polygon(doc, parent, pts):
    return doc.add_node("polygon", dict(x=0.0, y=0.0,
                                        points=[list(p) for p in pts]),
                        parent=parent)


def _body(doc, heights=((0.0,), (20.0,), (40.0,)), smooth=0):
    node = doc.add_node("section_loft", dict(
        heights=[list(h) for h in heights], smooth=smooth))
    for scale in (1.0, 1.2, 0.8)[:len(heights)]:
        _polygon(doc, node, [(x * scale, y) for x, y in CAR])
    return node


def test_the_node_previews_as_a_closed_solid(app):
    doc = DocumentModel()
    _body(doc)
    tris = mesh.tessellate(doc.root)
    assert tris and _closed(tris) and _volume(tris) > 0
    assert not validate(doc.root)
    lo, hi = _bounds(tris)
    assert lo[2] == pytest.approx(0) and hi[2] == pytest.approx(40)
    assert hi[0] == pytest.approx(12)                # the 1.2x section


def test_codegen_bakes_a_polyhedron_and_keeps_the_sections(app):
    doc = DocumentModel()
    _body(doc, smooth=2)
    code = doc.to_scad()
    assert "module kcad_section_loft(" in code
    call = next(ln for ln in code.splitlines()
                if ln.lstrip().startswith("kcad_section_loft("))
    assert "heights = [[0], [20], [40]]" in call and "smooth = 2" in call
    assert "points = [" in code and "faces = [" in code
    assert code.count("polygon(") >= 3               # the sections stay


def test_the_section_loft_round_trips_through_its_program(app, tmp_path):
    doc = DocumentModel()
    doc.set_global_fn(False)
    _body(doc, smooth=1)
    code1 = doc.to_scad()
    path = tmp_path / "section_loft.scad"
    document.export_scad(doc, str(path))
    other = DocumentModel()
    other.set_global_fn(False)
    assert not scadparse.import_scad(other, str(path))
    assert other.to_scad().splitlines()[3:] == code1.splitlines()[3:]
    node = next(n for n in other.root.walk() if n.type == "section_loft")
    assert node.params["heights"] == [[0.0], [20.0], [40.0]]
    assert node.params["smooth"] == 1
    assert [c.type for c in node.children] == ["polygon"] * 3


def test_the_node_saves_and_loads(app, tmp_path):
    doc = DocumentModel()
    _body(doc, smooth=2)
    path = tmp_path / "loft.kcad"
    document.save_kcad(doc, str(path))
    other = DocumentModel()
    document.load_kcad(other, str(path))
    node = next(n for n in other.root.walk() if n.type == "section_loft")
    assert node.params["smooth"] == 2 and len(node.children) == 3


def test_the_node_wraps_drawn_shapes_from_the_toolbar(app):
    doc = DocumentModel()
    a = _polygon(doc, None, RECT)
    b = _polygon(doc, None, SMALL)
    node = doc.wrap_nodes([a, b], "section_loft")
    assert node.type == "section_loft" and a.parent is node
    node.params["heights"] = [[0.0], [15.0]]
    assert not validate(doc.root)
    assert mesh.tessellate(doc.root)


def test_section_loft_validation(app):
    doc = DocumentModel()
    solid = doc.add_node("section_loft")
    doc.add_node("cube", parent=solid)
    lonely = doc.add_node("section_loft", dict(heights=[[0.0]], smooth=0))
    _polygon(doc, lonely, RECT)
    mismatch = _body(doc, heights=((0.0,), (20.0,)))
    _polygon(doc, mismatch, RECT)
    typo = _body(doc, heights=((0.0,), ("h",), (40.0,)))
    loop = doc.add_node("for_loop")
    nested = _body(doc)
    doc.move_node(nested, loop) if hasattr(doc, "move_node") else None
    errors = validate(doc.root)
    assert "3D" in errors[solid.id]
    assert "at least 2" in errors[lonely.id]
    assert "3 sections" in errors[mismatch.id] or "height" in errors[mismatch.id]
    assert "height 1" in errors[typo.id]


def test_a_section_loft_inside_a_loop_is_refused(app):
    doc = DocumentModel()
    loop = doc.add_node("for_loop")
    node = doc.add_node("section_loft", dict(heights=[[0.0], [10.0]], smooth=0),
                        parent=loop)
    _polygon(doc, node, RECT)
    _polygon(doc, node, SMALL)
    assert "for" in validate(doc.root)[node.id]


# --------------------------------------------------------- the engine
def _openscad_binary():
    for candidate in (shutil.which("openscad"), "/opt/homebrew/bin/openscad",
                      "/usr/local/bin/openscad",
                      "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"):
        if candidate and Path(candidate).exists():
            return candidate
    return None


def test_openscad_renders_the_baked_section_loft(app, tmp_path):
    binary = _openscad_binary()
    if binary is None:
        pytest.skip("OpenSCAD is not installed")
    from khervecad import engine
    doc = DocumentModel()
    _body(doc, smooth=2)
    scad, stl = tmp_path / "loft.scad", tmp_path / "loft.stl"
    scad.write_text(doc.to_scad())
    run = subprocess.run([binary, "-o", str(stl), str(scad)],
                         capture_output=True, text=True, timeout=180)
    assert run.returncode == 0, run.stderr[-1500:]
    exact = engine.parse_stl(str(stl))
    preview = mesh.tessellate(doc.root)
    for got, want in zip(_bounds(exact), _bounds(preview)):
        assert got == pytest.approx(want, abs=0.01)
    assert _volume(exact) == pytest.approx(_volume(preview), rel=0.002)
