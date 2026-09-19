"""The Sport library (library_sport.py) and the stadium builder
(stadium.py): every piece builds in every size without a boolean,
standing on the ground; bowls are closed rings (or C shapes where the
tunnel or a horseshoe's open end cuts them); stadiums say how many they
seat, and the changing rooms sit behind the south stand.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import re

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import library, library_groups, library_sport, mesh, stadium
from khervecad.model import validate

SMALL = {pid: spec for pid, spec in library_sport.PARTS.items()}


@pytest.fixture(autouse=True, scope="module")
def app():
    """Text (the podium's numbers) is laid out by Qt's fonts."""
    return QApplication.instance() or QApplication([])


def _build(part_id, size, colour=None, **extra):
    spec = library.PARTS[part_id]
    return library.build_part(part_id, dict(spec["sizes"][size], _size=size,
                                            _color=colour, **extra))


@pytest.mark.parametrize("part_id", sorted(SMALL))
def test_every_sport_piece_builds_on_the_ground(part_id):
    spec = SMALL[part_id]
    colours = spec.get("colors") or [None]
    for size in spec["sizes"]:
        for colour in {colours[0], colours[-1]}:
            node = _build(part_id, size, colour)
            assert not validate(node), (part_id, size)
            assert "difference" not in {n.type for n in node.walk()}
            tris = mesh.tessellate(node, fn=12)
            assert tris, (part_id, size)
            assert min(p[2] for t in tris for p in t) == pytest.approx(
                0.0, abs=1.0), (part_id, size)


def test_every_stadium_shape_builds_for_its_sports_without_booleans():
    for part_id, spec in stadium.PARTS.items():
        for size in spec["sizes"]:
            node = _build(part_id, size, "Blue", changing=0, rows=4,
                          upper_rows=2 if spec["sizes"][size].get("upper_rows")
                          else 0)
            assert not validate(node), (part_id, size)
            if part_id != "sport_changing_rooms":   # House Builder rooms
                assert "difference" not in {n.type for n in node.walk()}


def test_a_stadium_says_how_many_it_seats_and_grows_with_its_rows():
    small = _build("stadium_rounded", "Football", rows=10, upper_rows=0,
                   changing=0)
    big = _build("stadium_rounded", "Football", rows=26, upper_rows=30,
                 changing=0)
    seats = [int(re.search(r"\(([\d ]+) seats\)", n.name).group(1)
                 .replace(" ", "")) for n in (small, big)]
    assert 6000 < seats[0] < 12000
    assert 45000 < seats[1] < 80000       # the size of a Premier League bowl


def test_ring_polygons_are_closed_loops_or_cut_by_the_tunnel():
    a, b, p = stadium.base_axes("rounded", 56500, 38000)
    full = stadium.ring_polygon("rounded", a, b, p, 3000, 3800)
    assert len(full.params["paths"]) == 2
    cut = stadium.ring_polygon("rounded", a, b, p, 3000, 3800, tunnel=True)
    assert "paths" not in cut.params
    pts = cut.params["points"]
    # the C shape leaves the south side open, TUNNEL wide, at x = 0
    south = [x for x, y in pts if y < -b and abs(x) < stadium.TUNNEL]
    assert south and min(abs(x) for x in south) == pytest.approx(
        stadium.TUNNEL / 2, rel=0.02)


def test_the_field_corners_sit_inside_every_bowl():
    for shape in ("rounded", "oval", "circular", "arena"):
        a, b, p = stadium.base_axes(shape, 56500, 38000)
        assert (56500 / a) ** p + (38000 / b) ** p <= 1.0 + 1e-9, shape


def test_changing_rooms_and_tunnel_sit_behind_the_south_stand():
    node = _build("stadium_rounded_single", "Football", rows=8, changing=1)
    names = {n.name for n in node.walk()}
    assert {"Changing rooms", "Players tunnel", "Dugout"} <= names
    rooms = next(n for n in node.walk() if n.name == "Changing rooms")
    tris = mesh.tessellate(rooms, fn=8)
    assert max(p[1] for t in tris for p in t) < -38000


def test_the_sport_menu_places_every_sport_category():
    cats = {spec["category"] for spec in library.PARTS.values()
            if spec["category"].startswith("Sport:")}
    placed = {c for _t, entries in library_groups.SECTIONS
              for _n, _i, spec in entries
              for c in library_groups.entry_categories(spec, cats)[1]}
    assert cats <= placed
    assert stadium.COUNT_FIELDS | library_sport.COUNT_FIELDS \
        <= library._COUNT_FIELDS
