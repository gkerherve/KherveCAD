"""Library ▸ Science ▸ Solar System: every planet, dwarf planet and
moon builds at its diameter with its features, boolean-free and
closed; the orreries insert with prefixed sliders, put each planet
where Kepler says, run at real periods, keep a synchronous moon facing
its planet, and render in OpenSCAD.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import subprocess

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import (analysis, anchors, library, library_solar as ls,
                       mesh, solar_bodies, solar_data as D, solar_maps,
                       solar_surface as S)
from khervecad.model import CadNode, DocumentModel, validate


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _bbox(tris):
    return anchors.bbox(tris)


# ------------------------------------------------------------------ data

def test_every_body_is_in_the_library_with_its_kind():
    for body in D.BODIES:
        spec = library.PARTS[f"body_{body['key']}"]
        assert spec["category"] == (ls.CATEGORY_MOONS if body["kind"]
                                    == "moon" else ls.CATEGORY_PLANETS)
        if body["kind"] == "moon":
            assert body["parent"] in D.BY_KEY
            assert D.BY_KEY[body["parent"]]["label"] in spec["label"]
    assert len(D.PLANETS) == 8
    assert {m["key"] for m in D.moons_of("jupiter")} >= {
        "io", "europa", "ganymede", "callisto"}


def test_kepler_positions_are_sane():
    # Earth: 1 AU, a full lap in a year, at its J2000 mean longitude
    x, y, z = D.position(D.BY_KEY["earth"], 0.0)
    assert abs(math.hypot(x, y) - 1.0) < 0.02 and abs(z) < 1e-9
    assert abs(math.degrees(math.atan2(y, x)) - 100.46) < 3
    again = D.position(D.BY_KEY["earth"], 365.256)
    assert math.dist((x, y, z), again) < 0.01
    # Mercury swings between perihelion and aphelion
    merc = D.BY_KEY["mercury"]
    dist = [math.hypot(*D.position(merc, d)[:2]) for d in range(0, 88)]
    assert min(dist) < 0.32 and max(dist) > 0.46
    # Pluto climbs out of the ecliptic
    assert max(abs(D.position(D.BY_KEY["pluto"], d)[2])
               for d in range(0, 90000, 1000)) > 5


def test_earth_map_has_the_continents_where_they_are():
    rows = solar_maps.EARTH
    assert len(rows) == 36 and all(len(r) == 72 for r in rows)

    def cell(lat, lon):
        return rows[int((90 - lat) // 5)][int((lon + 180) // 5)]
    assert cell(52, 0) == "g"            # London
    assert cell(40, -100) == "g"         # Kansas
    assert cell(23, 10) == "d"           # Sahara
    assert cell(-25, 135) == "d"         # the outback
    assert cell(72, -40) == "i"          # Greenland
    assert cell(-80, 0) == "i"           # Antarctica
    assert cell(0, -30) == "."           # mid-Atlantic
    assert cell(30, -150) == "."         # mid-Pacific
    assert cell(-15, -55) == "g"         # Brazil
    assert cell(62, 100) == "t"          # Siberia


# ----------------------------------------------------------------- globes

@pytest.mark.parametrize("key", list(D.BY_KEY))
def test_body_builds_closed_at_its_diameter(app, key):
    body = D.BY_KEY[key]
    root = CadNode("root")
    node = solar_bodies.build_body(key, 60.0, fine=True)
    root.add(node)
    assert not validate(root), validate(root)
    assert not mesh.uses_booleans(node)
    tris = mesh.tessellate(node, env={}, fn=45)
    lo, hi = _bbox(tris)
    a, b, c = body["radii"]
    # the equator spans the diameter (rings and haze aside)
    if key not in ("saturn", "uranus", "neptune", "haumea", "titan",
                   "earth", "sun"):
        assert abs((hi[0] - lo[0]) - 60.0) < 2.5, (key, lo, hi)
        assert abs((hi[2] - lo[2]) - 60.0 * c / a) < 2.5, (key, lo, hi)
    volume = analysis.mass_properties(tris)["volume"]
    assert volume > 0.9 * 4 / 3 * math.pi * 30 ** 3 * (b / a) * (c / a)
    colours = {row[1] for row in mesh.tessellate_colored(node, env={},
                                                         fn=45)}
    assert len(colours) >= 2, key


def test_saturn_wears_its_rings_and_the_earth_its_land(app):
    saturn = solar_bodies.build_body("saturn", 60.0)
    lo, hi = _bbox(mesh.tessellate(saturn, env={}, fn=45))
    assert abs((hi[0] - lo[0]) - 60.0 * 140_500 / 60_268) < 1.0
    earth = solar_bodies.build_body("earth", 60.0)
    land = next(n for n in earth.walk() if n.name == "Land")
    classes = {c.name[-1] for c in land.children}
    assert classes == {"g", "t", "d", "i"}
    tris = mesh.tessellate(land, env={}, fn=45)
    assert analysis.mass_properties(tris)["volume"] > 0
    coarse = solar_bodies.build_body("earth", 60.0, fine=False)
    assert len(mesh.tessellate(coarse, env={}, fn=45)) < len(
        mesh.tessellate(earth, env={}, fn=45))


def test_features_sit_on_the_surface(app):
    r = 30.0
    for node in (S.patch("P", r, 40, 60, 10, 15, "#fff"),
                 S.crater("C", r, -20, 120, 8, "#fff"),
                 S.mountain("M", r, 18, -134, 12, 1.0, "#fff")):
        tris = mesh.tessellate(node, env={}, fn=45)
        lo, hi = _bbox(tris)
        centre = [(a + b) / 2 for a, b in zip(lo, hi)]
        assert abs(math.dist(centre, (0, 0, 0)) - r) < 0.08 * r, node.name
    line = S.arc_line("L", r, (0, 0), (0, 90), 0.3, "#fff")
    lo, hi = _bbox(mesh.tessellate(line, env={}, fn=45))
    assert hi[0] > r * 0.98 and hi[1] > r * 0.98 and abs(hi[2]) < 1


def test_part_library_sizes_include_a_true_scale(app):
    spec = library.PARTS["body_jupiter"]
    scale = [k for k in spec["sizes"] if k.startswith("To scale")]
    assert scale and abs(spec["sizes"][scale[0]]["d"] - 571.9) < 0.5
    node = library.default_part("body_moon")
    lo, hi = _bbox(mesh.tessellate(node, env={}, fn=45))
    assert abs((hi[0] - lo[0]) - 60.0) < 1.0


# --------------------------------------------------------------- orreries

def _var(doc, suffix):
    return next(n for n in doc.global_assigns()
                if n.params["variable"].endswith(suffix))


def _object(doc, name):
    return next(c for c in doc.all_components() if c.name == name)


def _centre(doc, node):
    """World centre of *node*'s bounding box (ancestors applied)."""
    tris = mesh.selected_world_tris(doc.root, {node.id},
                                    env=anchors.doc_env(doc),
                                    fn=doc.effective_fn())
    lo, hi = _bbox(tris)
    return [(a + b) / 2 for a, b in zip(lo, hi)]


def _locals(doc, comp, env=None):
    """An Object's own variables evaluated in order, over the document
    globals (and *env*, an enclosing Object's locals)."""
    env = dict(env or anchors.doc_env(doc))
    for child in comp.children:
        if child.type == "assign":
            env[child.params["variable"]] = mesh.rv(child.params["value"],
                                                    env)
    return env


@pytest.mark.parametrize("sid", list(ls.SYSTEMS))
def test_orrery_inserts_with_sliders_and_runs(app, sid):
    from khervecad.customizer_panel import annotated
    assert sid in library.PARTS
    doc = DocumentModel()
    comps = ls.insert_system(sid, doc)
    assert comps and all(c.type == "component" for c in comps)
    assert not validate(doc.root), validate(doc.root)
    sliders = annotated(doc)
    prefix = ls.SYSTEMS[sid]["prefix"] + "_"
    assert sliders and all(n.params["variable"].startswith(prefix)
                           for n in sliders)
    days = _var(doc, "_days")
    moving = [c for c in comps if c.name not in ("Sun", "Orbits")]
    before = [_centre(doc, c) for c in moving]
    days.params["value"] = 40
    after = [_centre(doc, c) for c in moving]
    assert all(math.dist(a, b) > 0.01 for a, b in zip(before, after))


def test_orrery_planets_stand_where_kepler_puts_them(app):
    doc = DocumentModel()
    ls.insert_system("solar_system", doc)
    orbit = float(_var(doc, "_orbit").params["value"])
    comp = float(_var(doc, "_compression").params["value"])
    for day in (0.0, 500.0):
        _var(doc, "_days").params["value"] = day
        for key in ("mercury", "earth", "jupiter", "pluto"):
            body = D.BY_KEY[key]
            want = D.position(body, day, lambda r: orbit * r ** comp)
            v = _locals(doc, _object(doc, body["label"]))
            assert math.dist(want, (v["px"], v["py"], v["pz"])) < 1e-3
            got = _centre(doc, _object(doc, body["label"] + " globe"))
            assert math.dist(want, got) < 0.6, (key, day, want, got)


def test_orrery_keeps_real_periods_and_a_synchronous_moon(app):
    doc = DocumentModel()
    ls.insert_system("system_earth", doc)
    days = _var(doc, "_days")
    globe = _object(doc, "Moon globe")
    moon = _object(doc, "Moon")

    def where():
        v = _locals(doc, moon, _locals(doc, _object(doc, "Earth")))
        return (v["dist"] * math.cos(math.radians(v["angle"])),
                v["dist"] * math.sin(math.radians(v["angle"]))), v
    days.params["value"] = 0.0
    start, _v = where()
    world_start = _centre(doc, globe)
    days.params["value"] = 27.3217
    assert math.dist(start, where()[0]) < 0.05
    assert math.dist(world_start, _centre(doc, globe)) < 0.05
    days.params["value"] = 13.66
    assert math.dist(start, where()[0]) > 10
    assert math.dist(world_start, _centre(doc, globe)) > 10
    # the Moon's 0° meridian (its +x axis at spin 0) faces the Earth
    centre, v = where()
    rz = mesh.rv(globe.params["rz"], v)
    facing = (math.cos(math.radians(rz)), math.sin(math.radians(rz)))
    dot = facing[0] * centre[0] + facing[1] * centre[1]
    assert dot < -0.99 * math.hypot(*centre)


def test_two_orreries_get_their_own_variables(app):
    doc = DocumentModel()
    first = ls.insert_system("system_mars", doc)
    second = ls.insert_system("system_mars", doc)
    names = [n.params["variable"] for n in doc.global_assigns()]
    assert "mars_days" in names and "mars2_days" in names
    assert len({c.name for c in first + second}) == len(first) * 2
    code = doc.to_scad_map()[0]
    assert "module Phobos" in code and "mars2_days" in code


def test_orrery_round_trips_through_openscad_text(app):
    from khervecad import scadparse
    doc = DocumentModel()
    ls.insert_system("system_jupiter", doc)
    code = doc.to_scad_map()[0]
    root, warnings = scadparse.parse_scad(code)
    assert not warnings, warnings
    back = DocumentModel()
    back.root = root
    names = {c.name for c in back.all_components()}
    assert {"Jupiter", "Io", "Europa", "Ganymede", "Callisto"} <= names


def test_orrery_renders_in_openscad(app, tmp_path):
    from tests.test_gears import _openscad
    binary = _openscad()
    if binary is None:
        pytest.skip("OpenSCAD not installed")
    doc = DocumentModel()
    ls.insert_system("system_earth", doc)
    src = tmp_path / "earth.scad"
    src.write_text(doc.to_scad_map()[0])
    out = tmp_path / "earth.stl"
    run = subprocess.run([binary, "-o", str(out), str(src)],
                         capture_output=True, text=True, timeout=600)
    assert run.returncode == 0, run.stderr
    assert out.stat().st_size > 1000
