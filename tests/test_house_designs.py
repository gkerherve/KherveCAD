"""Finished houses (house_designs.py): bungalows and two-storey houses
with 1-3 bedrooms and a ten-storey block, as Library parts and House
Builder templates; the stairwells and open-plan rooms they rely on.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest

from khervecad import house as H
from khervecad import house_designs as D
from khervecad import house_templates, library
from khervecad.model import validate


@pytest.mark.parametrize("pid", list(D.DESIGNS))
def test_every_design_builds_clean_in_every_brick(pid):
    label, make = D.DESIGNS[pid]
    for brick in D.BRICKS:
        home = H.house_from_spec(make(brick, False))
        assert home.outer_wall == brick
    node = D.build_design(pid, {"_color": "Buff brick", "furnished": 1})
    assert not validate(node)
    home = H.house_from_spec(make("Red brick", True))
    for floor in home.floors:
        for room in floor.rooms:
            for f in room.furniture:          # nothing stands outside
                assert room.x - 1 <= f.x <= room.x + room.w + 1, \
                    (label, room.name, f.part_id)
                assert room.y - 1 <= f.y <= room.y + room.d + 1, \
                    (label, room.name, f.part_id)


def test_the_range_the_user_asked_for():
    homes = {pid: H.house_from_spec(make("Red brick", True))
             for pid, (_l, make) in D.DESIGNS.items()}
    beds = lambda h: sum(1 for f in h.floors for r in f.rooms
                         if "bedroom" in r.name.lower())
    for n in (1, 2, 3):
        bung = homes[f"house_bungalow_{n}"]
        two = homes[f"house_two_storey_{n}"]
        assert len(bung.floors) == 1 and beds(bung) == n
        assert len(two.floors) == 2 and beds(two) == n
    block = homes["house_flats_10"]
    assert len(block.floors) == 10 and block.roof.style == "Flat"


def test_a_stairwell_is_open_to_the_landing_and_rooms_of_one_name_join():
    home = H.house_from_spec(D.two_storey(2))
    upper = home.floors[1]
    segs = H.wall_segments(upper)
    rails = [sg for sg in segs if sg.rail]
    assert rails                                  # a balustrade, no wall
    landing = [r for r in upper.rooms if r.name == "Landing"]
    assert len(landing) == 3
    # no wall between the landing's own rectangles: where the front and
    # back landing pieces meet the long one (x = 4800), nothing stands
    for y in (350.0, 4800.0):
        assert not [sg for sg in segs if not sg.horizontal
                    and sg.c == 4800.0 and sg.a < y < sg.b]
    # and the stairwell's edge along it is a balustrade
    assert [sg for sg in rails if not sg.horizontal and sg.c == 4800.0
            and sg.a < 2500.0 < sg.b]
    # the stairs below climb inside the house, under the stairwell
    stairs = next(f for r in home.floors[0].rooms for f in r.furniture
                  if "stairs" in f.part_id)
    well = next(r for r in upper.rooms if r.surface == "void")
    assert well.x <= stairs.x <= well.x + well.w
    # a stairwell has no floor, and a lift shaft is walled, not railed
    group = H.build_floor(upper, is_top=False)
    assert not [n for n in group.children if n.name == "Stairwell slab"]
    block = H.house_from_spec(D.apartment_block(3))
    lift_walls = [sg for sg in H.wall_segments(block.floors[1])
                  if not sg.rail and sg.horizontal and sg.c == 6900.0
                  and sg.a <= 11600.0 < sg.b]
    assert lift_walls


def test_designs_are_library_parts_and_builder_templates():
    for pid, (label, _make) in D.DESIGNS.items():
        spec = library.PARTS[pid]
        assert spec["category"] == "Finished houses"
        assert spec["colors"] == list(D.BRICKS)
        assert label in house_templates.names()
    # one click: a furnished house, but only the shell of the tall block
    assert library.default_part("house_bungalow_2") is not None
    sizes = library.PARTS["house_flats_10"]["sizes"]
    assert list(sizes)[1] == "Empty (shell)"
    assert list(library.PARTS["house_bungalow_2"]["sizes"])[1] == "Furnished"
