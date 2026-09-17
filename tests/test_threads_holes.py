"""Threads (threads.py) and hole tools (holes.py): valid, sized right,
round-tripped, and — threads — matching OpenSCAD's render."""

import math
import subprocess

import pytest

from khervecad import analysis, engine, holes, mesh, threads
from khervecad.model import DocumentModel, validate
from khervecad.scadparse import parse_scad

from test_gears import OPENSCAD


def _node(type_, **params):
    model = DocumentModel()
    return model, model.add_node(type_, params)


def _round_trip(model):
    code = model.to_scad()
    again = DocumentModel()
    again.root = parse_scad(code)[0]
    return again.to_scad() == code


@pytest.mark.parametrize("kind", threads.KINDS)
def test_thread_kinds(kind):
    model, node = _node("thread", kind=kind, diameter=10.0, pitch=2.0,
                        length=6.0)
    assert validate(model.root) == {}
    tris = mesh.tessellate(node)
    checks = {c["name"]: c["status"]
              for c in analysis.print_check(tris)["checks"]}
    assert checks["Watertight"] == "pass"
    size = analysis.mass_properties(tris)["size"]
    assert size[0] == pytest.approx(10, abs=0.05)
    assert size[2] == pytest.approx(6)
    assert _round_trip(model)


def test_metric_thread_depth_and_internal_clearance():
    pts = threads.section("metric", 8.0, 1.25)
    radii = [math.hypot(x, y) for x, y in pts]
    assert max(radii) == pytest.approx(4.0)
    assert min(radii) == pytest.approx(4.0 - 0.5413 * 1.25, abs=1e-6)
    inner = threads.section("metric", 8.0, 1.25, internal=True,
                            clearance=0.2)
    assert max(math.hypot(x, y) for x, y in inner) == pytest.approx(4.2)


def test_too_coarse_a_thread_is_red():
    model, node = _node("thread", diameter=2.0, pitch=4.0)
    assert "too coarse" in validate(model.root)[node.id]


@pytest.mark.skipif(not OPENSCAD, reason="OpenSCAD not installed")
@pytest.mark.parametrize("kind", ["metric", "buttress", "pipe"])
def test_thread_matches_openscad(kind, tmp_path):
    model, node = _node("thread", kind=kind, diameter=10.0, pitch=2.0,
                        length=4.0)
    scad, stl = tmp_path / "t.scad", tmp_path / "t.stl"
    scad.write_text(model.to_scad())
    subprocess.run([OPENSCAD, *engine.openscad_args(OPENSCAD, stl, scad)],
                   check=True, capture_output=True, timeout=300)
    exact = analysis.mass_properties(engine.parse_stl(str(stl)))["volume"]
    preview = analysis.mass_properties(mesh.tessellate(node))["volume"]
    assert preview == pytest.approx(exact, rel=0.01)


@pytest.mark.parametrize("kind", holes.KINDS)
def test_hole_kinds(kind):
    model, node = _node("hole", kind=kind)
    assert validate(model.root) == {}
    tris = mesh.tessellate(node)
    box = analysis.mass_properties(tris)
    if kind == "teardrop":
        assert box["size"][0] == pytest.approx(10)           # along X
        assert box["max"][2] > 3.2 / 2                        # pointed up
    else:
        assert box["min"][2] == pytest.approx(-10)
        assert box["max"][2] == pytest.approx(1)              # the extra
    assert _round_trip(model)


def test_holes_cut_a_plate():
    root, warnings = parse_scad(
        'difference() { translate([-10, -10, -8]) cube([20, 20, 8]); '
        'kcad_hole(kind = "countersink", diameter = 3.4, depth = 8, '
        'head_diameter = 7); }')
    assert not warnings and validate(root) == {}


def test_bad_holes_are_red():
    model, node = _node("hole", kind="counterbore", diameter=6.0,
                        head_diameter=5.0)
    assert "head diameter" in validate(model.root)[node.id]
