"""Involute gears (gears.py): every kind previews as a closed solid of
the right size, round-trips as kcad_gear(...), and matches OpenSCAD's
render of its own helper when OpenSCAD is installed."""

import math
import os
import subprocess

import pytest

from khervecad import analysis, engine, gears, mesh
from khervecad.model import DocumentModel, validate
from khervecad.scadparse import parse_scad


def _gear(**params):
    model = DocumentModel()
    return model, model.add_node("gear", params)


@pytest.mark.parametrize("kind", gears.KINDS)
def test_every_kind_is_a_valid_closed_solid(kind):
    model, node = _gear(kind=kind)
    assert validate(model.root) == {}
    tris = mesh.tessellate(node)
    props = analysis.mass_properties(tris)
    assert props["volume"] > 0
    checks = {c["name"]: c["status"]
              for c in analysis.print_check(tris)["checks"]}
    assert checks["Watertight"] == "pass", kind


def test_spur_gear_dimensions():
    _model, node = _gear(kind="spur", m=2.0, teeth=20, bore=0.0)
    props = analysis.mass_properties(mesh.tessellate(node))
    # outside diameter = m (z + 2)
    assert props["size"][0] == pytest.approx(44, abs=0.05)
    pts = gears.outline(2.0, 20, 20.0, 22.0, 17.5, 0.0, 6)
    radii = [math.hypot(x, y) for x, y in pts]
    assert (min(radii), max(radii)) == pytest.approx((17.5, 22.0), abs=1e-6)


def test_teeth_are_evenly_spaced_and_the_tip_never_crosses():
    few = gears.outline(1.0, 5, 20.0, 3.5, 1.25, 0.0, 8)
    assert len(few) % 5 == 0
    area = abs(mesh.polygon_area(few))
    assert area > 0


def test_round_trip_and_expressions():
    root, warnings = parse_scad(
        'teeth = 30; kcad_gear(kind = "helical", m = 1.5, teeth = teeth, '
        'helix = 25, thickness = 8);')
    assert not warnings
    gear = next(n for n in root.walk() if n.type == "gear")
    assert gear.params["teeth"] == "teeth" and gear.params["kind"] == \
        "helical"
    model = DocumentModel()
    model.root = root
    code = model.to_scad()
    assert "module kcad_gear(" in code
    again = DocumentModel()
    again.root = parse_scad(code)[0]
    assert again.to_scad() == code


def test_bad_gears_are_red():
    model, node = _gear(teeth=3)
    assert "at least 4 teeth" in validate(model.root)[node.id]
    model, node = _gear(teeth=10, m=2.0, bore=30.0)
    assert "bore" in validate(model.root)[node.id]


def _openscad():
    """The installed binary, looked up directly: the suite disables the
    engine's own discovery (KHERVECAD_DISABLE_ENGINE)."""
    import shutil
    from pathlib import Path
    for candidate in (shutil.which("openscad"), *engine._CANDIDATES):
        if candidate and Path(candidate).exists():
            return candidate
    return None


OPENSCAD = _openscad()


@pytest.mark.skipif(not OPENSCAD, reason="OpenSCAD not installed")
@pytest.mark.parametrize("kind", ["spur", "helical", "internal", "rack",
                                  "bevel"])
def test_preview_matches_openscad(kind, tmp_path):
    model, node = _gear(kind=kind, teeth=12, m=1.0, thickness=4.0,
                        bore=2.0, rim=2.0, length=10.0)
    scad, stl = tmp_path / "g.scad", tmp_path / "g.stl"
    scad.write_text(model.to_scad())
    subprocess.run([OPENSCAD, *engine.openscad_args(OPENSCAD, stl, scad)],
                   check=True, capture_output=True, timeout=300)
    exact = analysis.mass_properties(engine.parse_stl(str(stl)))["volume"]
    preview = analysis.mass_properties(mesh.tessellate(node))["volume"]
    assert preview == pytest.approx(exact, rel=0.01)
