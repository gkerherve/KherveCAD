"""Regular polyhedra and stars (solids.py), rounded polygons and Bézier
shapes (curves2d.py), knurls and honeycombs (textures.py)."""

import math
import subprocess

import pytest

from khervecad import analysis, curves2d, engine, mesh, solids, textures
from khervecad.model import DocumentModel, validate
from khervecad.scadparse import parse_scad

from test_gears import OPENSCAD


def _doc(type_, extrude=False, **params):
    model = DocumentModel()
    node = model.add_node(type_, params)
    if extrude:
        ext = model.add_node("linear_extrude", dict(
            height=2.0, twist=0.0, scale=1.0, center=False, segments=0))
        node.parent.remove(node)
        ext.add(node)
        node = ext
    return model, node


def _lossless(model):
    code = model.to_scad()
    again = DocumentModel()
    again.root = parse_scad(code)[0]
    return again.to_scad() == code


@pytest.mark.parametrize("kind", solids.SOLIDS)
def test_polyhedra_are_regular(kind):
    model, node = _doc("polyhedron_solid", kind=kind, radius=10.0)
    assert validate(model.root) == {}
    tris = mesh.tessellate(node)
    radii = {round(math.dist(v, (0, 0, 0)), 6) for tri in tris for v in tri}
    assert radii == {10.0}                       # every vertex on the sphere
    assert _lossless(model)


def test_vertex_counts():
    counts = {k: len(solids.raw_vertices(k)) for k in solids.SOLIDS}
    assert counts == {"tetrahedron": 4, "cube": 8, "octahedron": 6,
                      "dodecahedron": 20, "icosahedron": 12,
                      "cuboctahedron": 12, "truncated_tetrahedron": 12,
                      "truncated_cube": 24, "truncated_octahedron": 24,
                      "truncated_icosahedron": 60, "rhombicuboctahedron": 24,
                      "icosidodecahedron": 30}


def test_star_and_polygon():
    model, ext = _doc("star", extrude=True, points=6, radius=10.0,
                      inner_radius=0.0)
    area = analysis.mass_properties(mesh.tessellate(ext))["volume"] / 2
    assert area == pytest.approx(1.5 * math.sqrt(3) * 100)   # hexagon
    assert _lossless(model)


def test_rounded_polygon_corners():
    pts = curves2d.rounded_outline([[0, 0, 5], [20, 0, 0], [20, 20, 5],
                                    [0, 20, 0]], 8)
    assert (20.0, 0.0) in pts and (0.0, 20.0) in pts          # sharp ones
    assert min(x for x, _ in pts) == pytest.approx(0)
    area = abs(mesh.polygon_area(pts))
    assert area == pytest.approx(400 - 2 * (25 - math.pi * 25 / 4), rel=1e-3)


def test_bezier_passes_through_its_points():
    pts = curves2d.bezier_outline([[0, 0], [5, -5], [15, -5], [20, 0],
                                   [25, 5], [5, 25], [0, 20]], 16)
    assert pts[0] == (0, 0) and (20.0, 0.0) in pts


def test_bad_bezier_is_red():
    model, node = _doc("bezier_shape", controls=[[0, 0], [1, 1]])
    assert "threes" in validate(model.root)[node.id]


def test_honeycomb_has_whole_cells_as_holes():
    model, ext = _doc("honeycomb", extrude=True, width=60.0, height=40.0,
                      cell=8.0, wall=1.2, margin=3.0)
    centres = textures.honeycomb_centres(60, 40, 8, 1.2, 3)
    assert centres and all(3 <= cx - 4 and cx + 4 <= 57 for cx, _ in centres)
    volume = analysis.mass_properties(mesh.tessellate(ext))["volume"]
    hexagon = math.sqrt(3) / 2 * 8 * 8
    assert volume == pytest.approx(2 * (2400 - len(centres) * hexagon),
                                   rel=1e-6)
    assert _lossless(model)


def test_knurl_is_closed_and_within_its_radius():
    model, node = _doc("knurl", diameter=20.0, length=10.0, count=16,
                       depth=1.0)
    tris = mesh.tessellate(node)
    checks = {c["name"]: c["status"]
              for c in analysis.print_check(tris)["checks"]}
    assert checks["Watertight"] == "pass"
    radii = [math.hypot(v[0], v[1]) for tri in tris for v in tri
             if 0 < v[2] < 10]
    assert max(radii) <= 10 + 1e-6 and min(radii) >= 9 - 1e-6
    assert _lossless(model)


@pytest.mark.skipif(not OPENSCAD, reason="OpenSCAD not installed")
@pytest.mark.parametrize("type_, extrude, params", [
    ("polyhedron_solid", False, dict(kind="truncated_icosahedron")),
    ("rounded_polygon", True, {}), ("bezier_shape", True, {}),
    ("honeycomb", True, {}), ("knurl", False, {})])
def test_matches_openscad(type_, extrude, params, tmp_path):
    model, node = _doc(type_, extrude=extrude, **params)
    scad, stl = tmp_path / "s.scad", tmp_path / "s.stl"
    scad.write_text(model.to_scad())
    subprocess.run([OPENSCAD, *engine.openscad_args(OPENSCAD, stl, scad)],
                   check=True, capture_output=True, timeout=300)
    exact = analysis.mass_properties(engine.parse_stl(str(stl)))["volume"]
    preview = analysis.mass_properties(mesh.tessellate(node))["volume"]
    assert preview == pytest.approx(exact, rel=0.01)


# ------------------------------------------------ textures and svg paths

from khervecad import textured  # noqa: E402


@pytest.mark.parametrize("shape", textured.SHAPES)
@pytest.mark.parametrize("pattern", textured.PATTERNS)
def test_textured_is_closed_and_round_trips(shape, pattern):
    model, node = _doc("textured", shape=shape, pattern=pattern,
                       height=6.0 if shape == "cylinder" else 3.0,
                       diameter=16.0, width=20.0, depth=12.0)
    assert validate(model.root) == {}
    tris = mesh.tessellate(node)
    checks = {c["name"]: c["status"]
              for c in analysis.print_check(tris)["checks"]}
    assert checks["Watertight"] == "pass"
    assert analysis.mass_properties(tris)["volume"] > 0
    assert _lossless(model)


def test_cylinder_texture_closes_round_the_seam():
    p = dict(textured.NODE_TYPES["textured"]["params"])
    cols, _rows, period = textured.grid(p)
    assert abs(math.pi * p["diameter"] / period
               - round(math.pi * p["diameter"] / period)) < 1e-9


def test_svg_path_shape_with_a_hole():
    model, ext = _doc("svg_path", extrude=True,
                      d="M 0 0 h 20 v 10 h -20 z M 5 3 h 4 v 4 h -4 z")
    assert validate(model.root) == {}
    volume = analysis.mass_properties(mesh.tessellate(ext))["volume"]
    assert volume == pytest.approx(2 * (200 - 16))
    assert _lossless(model)


@pytest.mark.skipif(not OPENSCAD, reason="OpenSCAD not installed")
@pytest.mark.parametrize("pattern", ["diamonds", "hexes"])
def test_textured_matches_openscad(pattern, tmp_path):
    model, node = _doc("textured", pattern=pattern, height=6.0,
                       diameter=16.0)
    scad, stl = tmp_path / "t.scad", tmp_path / "t.stl"
    scad.write_text(model.to_scad())
    subprocess.run([OPENSCAD, *engine.openscad_args(OPENSCAD, stl, scad)],
                   check=True, capture_output=True, timeout=300)
    exact = analysis.mass_properties(engine.parse_stl(str(stl)))["volume"]
    preview = analysis.mass_properties(mesh.tessellate(node))["volume"]
    assert preview == pytest.approx(exact, rel=0.005)
