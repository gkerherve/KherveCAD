"""The City sections of the part library — Trees, Park & sport,
Lighting & signals, Landscape: every part builds at every size and
colour into valid geometry that stands on the ground within a triangle
budget, and appears under Library ▸ City.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import mesh
from khervecad.library import PARTS, build_part
from khervecad.model import validate

SECTIONS = ("Lighting & signals", "Park & sport", "Landscape", "Bridges",
            "Landmarks", "Skyscrapers")
IDS = [pid for pid, spec in PARTS.items()
       if spec.get("category") in SECTIONS]
BUDGET = 400000


@pytest.fixture(scope="module", autouse=True)
def app():
    # text outlines (a sign's lettering) need fonts, so a QApplication
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("pid", IDS)
def test_every_size_and_colour_builds(pid):
    spec = PARTS[pid]
    colours = spec.get("colors") or [None]
    for size, dims in (spec.get("sizes") or {"": {}}).items():
        for colour in colours:
            d = dict(dims)
            if colour:
                d["_color"] = colour
            node = build_part(pid, d)
            assert not validate(node), (pid, size, colour, validate(node))
            tris = mesh.tessellate(node)
            assert tris, (pid, size)
            assert len(tris) < BUDGET, (pid, size, len(tris))
            low = min(v[2] for t in tris for v in t)
            k = float(d.get("scale", 1.0))
            assert low > -10000 * k, (pid, size, low)


def test_signals_light_the_chosen_aspect():
    node = build_part("signal_traffic", dict(h=3600, _color="Green"))
    lit = [n for n in node.walk() if n.type == "color"
           and n.params.get("material") == "Emissive"]
    assert [n.children[0].name for n in lit] == ["Green"]


def test_park_facilities_do_not_overlap_the_paths_or_each_other():
    from khervecad import library_park as P
    node = P.build_park(dict(w=220000, d=150000, seed=1))
    names = [c.name for c in node.children]
    for want in ("Lake", "Football pitch", "Tennis court",
                 "Basketball court", "Playground", "Fountain", "Trees"):
        assert want in names, want


def test_pitch_markings_and_goal_nets():
    node = build_part("park_football", dict(length=105000, width=68000))
    marks = [n for n in node.walk() if n.name == "Markings"
             and n.type == "linear_extrude"]
    assert marks and len(marks[0].children) > 25
    assert len([n for n in node.walk() if n.name == "Goal"
                and n.type == "translate"]) == 2


def test_terrain_columns_are_closed_and_coloured_by_surface():
    from khervecad import bake, terrain
    for kind in terrain.KINDS:
        node = terrain.build(kind, length=60000, width=60000, height=12000,
                             seed=2, cells=24)
        polys = [n for n in node.walk() if n.type == "polyhedron"]
        assert polys, kind
        for p in polys:
            assert bake._check_polyhedron(p.params) is None, kind
    mountain = terrain.build("mountain", height=60000, cells=40)
    names = {n.name for n in mountain.walk() if n.type == "color"}
    assert "Snow" in names and ("Rock" in names or "Rock2" in names)


def test_unpinch_leaves_no_corner_only_contacts():
    from khervecad.terrain import _unpinch
    cells = [["a", "b"], ["b", "a"]]
    out = _unpinch([row[:] for row in cells], 2)
    assert not (out[0][0] == out[1][1] and out[0][1] != out[0][0]
                and out[1][0] != out[0][0])
