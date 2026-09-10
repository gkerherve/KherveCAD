"""Tests for the smooth blend: signed distance fields and surface
extraction (sdf.py) and the baked `blend` node (bake.py).

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

from khervecad import document, mesh, scadparse, sdf
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="session")
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


def _two_spheres(app, radius, detail=24, apart=10.0):
    doc = DocumentModel()
    a = doc.add_node("sphere", dict(radius=5.0))
    b = doc.add_node("sphere", dict(x=apart, radius=5.0))
    blend = doc.wrap_nodes([a, b], "blend")
    blend.params.update(radius=radius, detail=detail)
    return doc, blend


# ── distance functions ─────────────────────────────────────────────

def test_primitive_distances_are_right():
    f, _lo, _hi = sdf._PRIMITIVES["sphere"](dict(x=0.0, y=0.0, z=0.0,
                                                 radius=5.0))
    assert f(10, 0, 0) == pytest.approx(5.0)
    assert f(0, 0, 0) == pytest.approx(-5.0)
    f, _lo, _hi = sdf._PRIMITIVES["cube"](dict(
        x=0.0, y=0.0, z=0.0, width=10.0, depth=10.0, height=10.0,
        center=False))
    assert f(5, 5, 5) == pytest.approx(-5.0)
    assert f(15, 5, 5) == pytest.approx(5.0)
    assert f(13, 14, 5) == pytest.approx(5.0)         # off the corner
    f, _lo, _hi = sdf._PRIMITIVES["capsule"](dict(
        x1=0.0, y1=0.0, z1=0.0, x2=0.0, y2=0.0, z2=20.0, radius=2.0))
    assert f(5, 0, 10) == pytest.approx(3.0)
    assert f(0, 0, 25) == pytest.approx(3.0)          # past the end cap
    f, _lo, _hi = sdf._PRIMITIVES["ellipsoid"](dict(
        x=0.0, y=0.0, z=0.0, rx=10.0, ry=5.0, rz=2.0))
    assert f(10, 0, 0) == pytest.approx(0.0, abs=1e-9)
    assert f(0, 0, 0) < 0 < f(0, 6, 0)
    f, _lo, _hi = sdf._PRIMITIVES["cylinder"](dict(
        x=0.0, y=0.0, z=0.0, height=10.0, radius_bottom=3.0,
        radius_top=3.0, center=False))
    assert f(0, 0, 5) == pytest.approx(-3.0)
    assert f(0, 0, 12) == pytest.approx(2.0)


def test_the_blend_fills_the_neck_a_union_leaves_open(app):
    doc, blend = _two_spheres(app, radius=4.0)
    parts = sdf.leaves(blend, {})
    neck = (5.0, 3.0, 0.0)          # between the spheres, just off both
    assert sdf.field(parts, 0.0)(*neck) > 0          # a union misses it
    assert sdf.field(parts, 4.0)(*neck) < 0          # the blend fills it


# ── the extracted surface ──────────────────────────────────────────

def test_the_blend_surface_is_watertight_and_outward(app):
    doc, _blend = _two_spheres(app, radius=4.0)
    tris = mesh.tessellate(doc.root)
    assert len(tris) > 200
    assert _closed(tris)
    assert _volume(tris) > 0


def test_a_zero_radius_blend_is_the_plain_union(app):
    doc, _blend = _two_spheres(app, radius=0.0, detail=40, apart=30.0)
    tris = mesh.tessellate(doc.root)
    lo, hi = _bounds(tris)
    assert lo == pytest.approx([-5, -5, -5], abs=0.6)
    assert hi == pytest.approx([35, 5, 5], abs=0.6)
    two_balls = 2 * 4 / 3 * math.pi * 125
    assert _volume(tris) == pytest.approx(two_balls, rel=0.06)


def test_transforms_and_loops_inside_a_blend_are_followed(app):
    doc = DocumentModel()
    loop = doc.add_node("for_loop", dict(variable="k", start=0.0,
                                         end=2.0, step=1.0))
    doc.add_node("sphere", dict(x="k * 12", radius=4.0), parent=loop)
    moved = doc.wrap_nodes([loop], "translate")
    moved.params.update(z=50.0)
    doc.wrap_nodes([moved], "blend").params.update(radius=3.0, detail=30)
    lo, hi = _bounds(mesh.tessellate(doc.root))
    assert lo[2] == pytest.approx(46.0, abs=0.6)
    assert hi[0] == pytest.approx(28.0, abs=0.6)


# ── the node: code, spans, round trip, validation ──────────────────

def test_blend_codegen_bakes_a_polyhedron_over_several_lines(app):
    doc, blend = _two_spheres(app, radius=4.0, detail=16)
    after = doc.add_node("cube")
    code, spans = doc.to_scad_map()
    lines = code.splitlines()
    assert code.count("module kcad_blend(") == 1
    call = next(i for i, ln in enumerate(lines)
                if ln.lstrip().startswith("kcad_blend(radius"))
    assert lines[call + 1].lstrip().startswith("points = [")
    assert "sphere(" in code
    # the line spans still point at the right code after it
    start, _end = spans[after.id]
    assert "cube(" in lines[start]
    start, _end = spans[blend.id]
    assert "kcad_blend(radius" in lines[start]


def test_blend_round_trips_through_its_baked_arrays(app, tmp_path):
    doc, _blend = _two_spheres(app, radius=3.0, detail=16)
    code1 = doc.to_scad()
    path = tmp_path / "blend.scad"
    document.export_scad(doc, str(path))
    other = DocumentModel()
    assert not scadparse.import_scad(other, str(path))
    assert other.to_scad() .splitlines()[3:] == code1.splitlines()[3:]
    blend = next(n for n in other.root.walk() if n.type == "blend")
    assert [c.type for c in blend.children] == ["sphere", "sphere"]


def test_blend_validation(app):
    doc = DocumentModel()
    cut = doc.wrap_nodes([doc.add_node("cube"), doc.add_node("sphere")],
                         "difference")
    bad = doc.wrap_nodes([cut], "blend")
    loop = doc.add_node("for_loop")
    inner = doc.add_node("blend", parent=loop)
    doc.add_node("sphere", parent=inner)
    errors = validate(doc.root)
    assert "difference" in errors[bad.id]
    assert "for" in errors[inner.id]
    fine, blend = _two_spheres(app, radius=2.0, detail=10)
    assert blend.id not in validate(fine.root)


def test_get_code_summarises_the_baked_arrays(app):
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(MainWindow())
    out = ex.execute("apply_code", {"code": (
        "kcad_blend(radius = 3, detail = 16) {\n"
        "    sphere(r = 5);\n    translate([8, 0, 0]) sphere(r = 5);\n}")})
    assert "error" not in out
    short = ex.execute("get_code", {})["code"]
    full = ex.execute("get_code", {"full": True})["code"]
    assert "baked rows" in short and "baked rows" not in full
    assert len(short) * 5 < len(full)
    # a summarised program still re-applies: the arrays are recomputed
    again = ex.execute("check_code", {"code": short})
    assert again["types"].get("blend") == 1 and not again["problems"]


def _openscad_binary():
    for candidate in (shutil.which("openscad"), "/opt/homebrew/bin/openscad",
                      "/usr/local/bin/openscad",
                      "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"):
        if candidate and Path(candidate).exists():
            return candidate
    return None


def test_openscad_accepts_and_renders_the_baked_blend(app, tmp_path):
    binary = _openscad_binary()
    if binary is None:
        pytest.skip("OpenSCAD is not installed")
    from khervecad import engine
    doc, _blend = _two_spheres(app, radius=4.0, detail=20)
    scad, stl = tmp_path / "blend.scad", tmp_path / "blend.stl"
    scad.write_text(doc.to_scad())
    run = subprocess.run([binary, "-o", str(stl), str(scad)],
                         capture_output=True, text=True, timeout=180)
    assert run.returncode == 0, run.stderr[-1500:]
    exact = engine.parse_stl(str(stl))
    preview = mesh.tessellate(doc.root)
    for got, want in zip(_bounds(exact), _bounds(preview)):
        assert got == pytest.approx(want, abs=0.01)
    assert _volume(exact) == pytest.approx(_volume(preview), rel=0.005)
