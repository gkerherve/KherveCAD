"""Tests for the organic node types (organic.py) and the 3D convex
hull behind them (geom3d.py).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import os
import random
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

from khervecad import document, geom3d, mesh, organic, scadparse
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def model(app):
    return DocumentModel()


def _bounds(tris):
    pts = [v for tri in tris for v in tri]
    return ([min(p[i] for p in pts) for i in range(3)],
            [max(p[i] for p in pts) for i in range(3)])


def _closed(tris) -> bool:
    """Every edge used once each way: a closed, consistently wound
    surface."""
    count = Counter()
    for a, b, c in tris:
        for u, w in ((a, b), (b, c), (c, a)):
            count[(u, w)] += 1
    return all(n == 1 and count[(w, u)] == 1
               for (u, w), n in count.items())


def _volume(tris) -> float:
    """Signed volume: positive when the faces are wound outward."""
    total = 0.0
    for a, b, c in tris:
        total += (a[0] * (b[1] * c[2] - b[2] * c[1])
                  - a[1] * (b[0] * c[2] - b[2] * c[0])
                  + a[2] * (b[0] * c[1] - b[1] * c[0]))
    return total / 6.0


# ── convex hull ─────────────────────────────────────────────────────

def test_hull_of_a_cube_with_points_inside_is_the_cube():
    corners = [(x, y, z) for x in (0, 10) for y in (0, 10)
               for z in (0, 10)]
    tris = geom3d.convex_hull(corners + [(5, 5, 5), (2, 3, 4), (9, 1, 1)])
    assert len(tris) == 12
    assert _closed(tris)
    assert _volume(tris) == pytest.approx(1000.0)


def test_hull_of_scattered_points_is_closed_and_contains_them():
    rng = random.Random(4)
    pts = [(rng.uniform(-5, 5), rng.uniform(-5, 5), rng.uniform(-5, 5))
           for _ in range(400)]
    tris = geom3d.convex_hull(pts)
    assert _closed(tris) and _volume(tris) > 0
    for a, b, c in tris:                  # no point outside any face
        u = [b[i] - a[i] for i in range(3)]
        v = [c[i] - a[i] for i in range(3)]
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
             u[0] * v[1] - u[1] * v[0])
        scale = math.sqrt(sum(x * x for x in n))
        for p in pts:
            assert sum(n[i] * (p[i] - a[i]) for i in range(3)) \
                <= 1e-6 * scale


def test_degenerate_input_has_no_hull():
    assert geom3d.convex_hull([(i, 0, 0) for i in range(5)]) == []
    assert geom3d.convex_hull([(0, 0, 0), (1, 0, 0), (0, 1, 0),
                               (1, 1, 0)]) == []          # coplanar
    assert geom3d.convex_hull([(1, 2, 3)] * 6) == []


# ── primitives ──────────────────────────────────────────────────────

def test_capsule_spans_its_two_ends(model):
    model.add_node("capsule", dict(x1=0.0, y1=0.0, z1=0.0, x2=0.0,
                                   y2=0.0, z2=20.0, radius=5.0,
                                   segments=32))
    tris = mesh.tessellate(model.root)
    lo, hi = _bounds(tris)
    assert lo == pytest.approx([-5, -5, -5], abs=0.05)
    assert hi == pytest.approx([5, 5, 25], abs=0.05)
    assert _closed(tris) and _volume(tris) > 0


def test_a_slanted_capsule_follows_its_axis(model):
    model.add_node("capsule", dict(x1=0.0, y1=0.0, z1=0.0, x2=30.0,
                                   y2=40.0, z2=0.0, radius=2.0))
    lo, hi = _bounds(mesh.tessellate(model.root))
    assert lo == pytest.approx([-2, -2, -2], abs=0.05)
    assert hi == pytest.approx([32, 42, 2], abs=0.05)


def test_ellipsoid_has_three_radii(model):
    model.add_node("ellipsoid", dict(x=1.0, y=2.0, z=3.0, rx=10.0,
                                     ry=5.0, rz=2.0))
    lo, hi = _bounds(mesh.tessellate(model.root))
    assert lo == pytest.approx([-9, -3, 1], abs=0.05)
    assert hi == pytest.approx([11, 7, 5], abs=0.05)


def test_rounded_box_fills_its_box_and_rounds_every_corner(model):
    model.add_node("rounded_box", dict(width=20.0, depth=10.0,
                                       height=6.0, radius=2.0,
                                       center=True))
    tris = mesh.tessellate(model.root)
    lo, hi = _bounds(tris)
    assert lo == pytest.approx([-10, -5, -3], abs=0.05)
    assert hi == pytest.approx([10, 5, 3], abs=0.05)
    assert _closed(tris) and _volume(tris) > 0
    nearest = min(math.dist(v, (10, 5, 3)) for t in tris for v in t)
    assert nearest > 0.5                    # the sharp corner is gone


def test_rounded_box_without_radius_is_a_plain_box(model):
    model.add_node("rounded_box", dict(width=4.0, depth=4.0, height=4.0,
                                       radius=0.0, center=False))
    tris = mesh.tessellate(model.root)
    assert len(tris) == 12
    assert _bounds(tris) == ([0, 0, 0], [4, 4, 4])


def test_a_too_big_radius_is_clamped_to_the_box(model):
    model.add_node("rounded_box", dict(width=10.0, depth=10.0,
                                       height=2.0, radius=50.0))
    lo, hi = _bounds(mesh.tessellate(model.root))
    assert hi[2] - lo[2] == pytest.approx(2.0, abs=0.05)


# ── symmetry and joints ─────────────────────────────────────────────

def test_symmetry_adds_the_mirror_image(model):
    cube = model.add_node("cube", dict(x=10.0, width=10.0, depth=4.0,
                                       height=4.0))
    sym = model.wrap_nodes([cube], "symmetry")
    tris = mesh.tessellate(model.root)
    lo, hi = _bounds(tris)
    assert (lo[0], hi[0]) == pytest.approx((-20.0, 20.0))
    assert len(tris) == 24
    assert _volume(tris) > 0            # the mirrored half is not inside out
    sym.params.update(cx=5.0)           # mirror about x = 5 instead
    lo, hi = _bounds(mesh.tessellate(model.root))
    assert (lo[0], hi[0]) == pytest.approx((-10.0, 20.0))


def test_joint_rotates_about_its_pivot(model):
    cube = model.add_node("cube", dict(x=10.0, width=10.0, depth=2.0,
                                       height=2.0))
    joint = model.wrap_nodes([cube], "joint")
    joint.params.update(px=10.0, rz=90.0)
    lo, hi = _bounds(mesh.tessellate(model.root))
    assert lo == pytest.approx([8.0, 0.0, 0.0], abs=1e-6)
    assert hi == pytest.approx([10.0, 10.0, 2.0], abs=1e-6)


def test_nested_joints_chain_like_an_arm(model):
    """The elbow bends the hand; the shoulder then swings the elbow and
    everything below it — the tree is the armature."""
    hand = model.add_node("cube", dict(x=20.0, width=5.0, depth=1.0,
                                       height=1.0))
    elbow = model.wrap_nodes([hand], "joint")
    elbow.params.update(px=20.0, rz=90.0)
    shoulder = model.wrap_nodes([elbow], "joint")
    shoulder.params.update(rz=90.0)
    lo, hi = _bounds(mesh.tessellate(model.root))
    assert lo == pytest.approx([-5.0, 19.0, 0.0], abs=1e-6)
    assert hi == pytest.approx([0.0, 20.0, 1.0], abs=1e-6)


def test_validation_catches_a_zero_normal_and_joint_limits(model):
    sym = model.wrap_nodes([model.add_node("cube")], "symmetry")
    sym.params.update(x=0.0, y=0.0, z=0.0)
    joint = model.wrap_nodes([model.add_node("sphere")], "joint")
    joint.params.update(min_angle=-90.0, max_angle=90.0, rz=120.0)
    errors = validate(model.root)
    assert "normal" in errors[sym.id]
    assert "limits" in errors[joint.id]
    joint.params.update(rz=0.0, min_angle=50.0, max_angle=10.0)
    assert "above max" in validate(model.root)[joint.id]
    empty = model.add_node("symmetry")
    assert "empty" in validate(model.root)[empty.id]


# ── code: helper modules, round trip, the real engine ──────────────

def _body(code):
    return "\n".join(line for line in code.splitlines()
                     if not line.startswith("//")).strip()


def test_helper_modules_are_defined_once_and_only_when_used(model):
    model.add_node("capsule")
    model.add_node("capsule")
    model.add_node("ellipsoid")
    code = model.to_scad()
    assert code.count("module kcad_capsule(") == 1
    assert code.count("module kcad_ellipsoid(") == 1
    assert "module kcad_joint(" not in code
    calls = [ln for ln in code.splitlines()
             if ln.lstrip().startswith("kcad_capsule(")]
    assert len(calls) == 2
    plain = DocumentModel()
    plain.add_node("cube")
    assert "kcad_" not in plain.to_scad()


def _organic_document(model):
    # expressions on a loop variable stay symbolic through an import
    # (the parser substitutes a document variable's value, for every
    # node type — so the round trip is tested the way test_scadparse
    # tests it)
    loop = model.add_node("for_loop", dict(variable="k", start=0.0,
                                           end=1.0, step=1.0))
    model.add_node("capsule", dict(z2="k * 10 + 20", radius=4.0),
                   parent=loop)
    model.add_node("ellipsoid", dict(x=5.0, rx="k + 5"), parent=loop)
    model.add_node("rounded_box", dict(radius=1.5, center=False))
    sym = model.wrap_nodes([model.add_node("sphere", dict(x=12.0))],
                           "symmetry")
    sym.params.update(cx=2.0)
    joint = model.wrap_nodes([model.add_node("cube", dict(x=10.0))],
                             "joint")
    joint.params.update(px=10.0, rz=-30.0, min_angle=-45.0,
                        max_angle=45.0)
    return model


def test_organic_nodes_round_trip_losslessly(model, tmp_path):
    code1 = _organic_document(model).to_scad()
    path = tmp_path / "organic.scad"
    document.export_scad(model, str(path))
    other = DocumentModel()
    warnings = scadparse.import_scad(other, str(path))
    assert not warnings
    assert _body(other.to_scad()) == _body(code1)
    assert organic.TYPES <= {n.type for n in other.root.walk()}


def test_kcad_calls_import_without_the_helper_definitions(app):
    """An assistant can write kcad_* calls straight into apply_code."""
    root, warnings = scadparse.parse_scad(
        "kcad_joint(pivot = [0, 0, 10], a = [0, 45, 0]) {\n"
        "    kcad_capsule(a = [0, 0, 0], b = [0, 0, 20], r = 3);\n"
        "}\n")
    assert not warnings
    joint = root.children[0]
    assert joint.type == "joint" and joint.params["ry"] == 45.0
    assert joint.children[0].type == "capsule"
    assert joint.children[0].params["radius"] == 3.0


def _openscad_binary():
    for candidate in (shutil.which("openscad"), "/opt/homebrew/bin/openscad",
                      "/usr/local/bin/openscad",
                      "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"):
        if candidate and Path(candidate).exists():
            return candidate
    return None


CASES = {
    "capsule": lambda m: m.add_node("capsule", dict(
        x2=10.0, z2=20.0, radius=5.0, segments=24)),
    "ellipsoid": lambda m: m.add_node("ellipsoid", dict(
        x=1.0, y=2.0, z=3.0, rx=10.0, ry=5.0, rz=2.0, segments=24)),
    "rounded_box": lambda m: m.add_node("rounded_box", dict(
        width=20.0, depth=10.0, height=6.0, radius=2.0, segments=24)),
    "symmetry": lambda m: m.wrap_nodes([m.add_node("cube", dict(
        x=10.0, width=10.0, depth=4.0, height=4.0))], "symmetry"),
    "joint": lambda m: m.wrap_nodes([m.add_node("cube", dict(
        x=10.0, width=10.0, depth=2.0, height=2.0))], "joint").params
    .update(px=10.0, rz=90.0),
}


@pytest.mark.parametrize("kind", sorted(CASES))
def test_openscad_renders_what_the_preview_shows(app, tmp_path, kind):
    """The helper modules are real OpenSCAD, and the engine's exact
    mesh matches the built-in preview."""
    binary = _openscad_binary()
    if binary is None:
        pytest.skip("OpenSCAD is not installed")
    from khervecad import engine
    m = DocumentModel()
    m.global_fn_on = False
    CASES[kind](m)
    scad = tmp_path / f"{kind}.scad"
    stl = tmp_path / f"{kind}.stl"
    scad.write_text(m.to_scad())
    run = subprocess.run([binary, "-o", str(stl), str(scad)],
                         capture_output=True, text=True, timeout=180)
    assert run.returncode == 0, run.stderr[-1500:]
    exact = _bounds(engine.parse_stl(str(stl)))
    preview = _bounds(mesh.tessellate(m.root))
    for got, want in zip(exact, preview):
        assert got == pytest.approx(want, abs=0.35), (kind, exact, preview)


# ── set_pose ────────────────────────────────────────────────────────

@pytest.fixture
def ex(app):
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    win = MainWindow()
    win.resize(800, 600)
    return McpToolExecutor(win)


def test_set_pose_bends_joints_by_name_and_clamps(ex):
    out = ex.execute("apply_code", {"code": (
        "kcad_joint(pivot = [0, 0, 0], a = [0, 0, 0], "
        "limits = [-90, 90]) { cube([20, 2, 2]); }")})
    assert "error" not in out
    joint = next(n for n in ex._model.root.walk() if n.type == "joint")
    posed = ex.execute("set_pose", {"joints": {joint.name: {"rz": 45}}})
    assert "error" not in posed
    assert posed["joints"][0]["angles"] == [0.0, 0.0, 45.0]
    assert joint.params["rz"] == 45.0
    far = ex.execute("set_pose", {"joints": {str(joint.id): {"rz": 120}}})
    assert far["clamped"][0]["set"] == 90.0 and joint.params["rz"] == 90.0
    listed = ex.execute("set_pose", {"joints": {}})
    assert listed["posed"] == [] and len(listed["joints"]) == 1


def test_set_pose_changes_nothing_when_one_entry_is_wrong(ex):
    ex.execute("apply_code", {"code": (
        "kcad_joint(pivot = [0, 0, 0], a = [0, 0, 0]) { cube(1); }")})
    joint = next(n for n in ex._model.root.walk() if n.type == "joint")
    bad = ex.execute("set_pose", {"joints": {joint.name: {"rz": 30},
                                             "Nope": {"rz": 10}}})
    assert "Nope" in bad["error"] and joint.name in bad["error"]
    assert joint.params["rz"] == 0.0             # nothing half-applied
    assert "error" in ex.execute("set_pose", {"joints": {
        joint.name: {"rq": 1}}})
