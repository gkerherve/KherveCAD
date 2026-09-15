"""The furniture that fills every room of the House Builder
(library_home_more.py, library_home_extra.py): every piece builds in
every size, at true size, standing on the floor, without a boolean.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest

from khervecad import house as H
from khervecad import library, library_home_extra, library_home_more, mesh
from khervecad.model import validate

PARTS = dict(library_home_more.PARTS, **library_home_extra.PARTS)


def _tris(part_id, dims=None):
    dims = H.part_dims(part_id) if dims is None else dims
    return mesh.tessellate(library.build_part(part_id, dims), fn=12)


@pytest.mark.parametrize("part_id", sorted(PARTS))
def test_every_piece_builds_in_every_size_standing_on_the_floor(part_id):
    spec = PARTS[part_id]
    colours = spec.get("colors") or [None]
    for size, entry in spec["sizes"].items():
        for colour in {colours[0], colours[-1]}:
            node = library.build_part(part_id,
                                      dict(entry, _size=size, _color=colour))
            assert not validate(node), (part_id, size, colour)
            assert "difference" not in {n.type for n in node.walk()}
            tris = mesh.tessellate(node, fn=12)
            assert tris, (part_id, size)
            zs = [p[2] for t in tris for p in t]
            assert min(zs) == pytest.approx(0.0, abs=1.0), (part_id, size)


def test_every_room_has_plenty_to_choose_from():
    listed = {p for parts in H.FURNITURE_CATALOG.values() for p in parts}
    assert set(PARTS) <= listed
    for room in ("Garage", "Reception", "Hallway / corridor",
                 "Entrance / porch", "Garden / outdoor", "Stairs",
                 "Kids' room", "Utility / laundry"):
        assert room in H.FURNITURE_CATALOG, room
    for room, parts in H.FURNITURE_CATALOG.items():
        if room not in ("Stairs", "Other"):
            assert len(parts) >= 5, room
    assert library_home_extra.COUNT_FIELDS <= library._COUNT_FIELDS


def test_the_stairs_climb_a_whole_storey():
    for pid in ("home_stairs_straight", "home_stairs_spiral"):
        top = max(p[2] for t in _tris(pid) for p in t)
        assert top >= H.WALL_HEIGHT + H.SLAB_THICKNESS, pid


def test_a_car_and_a_tree_are_their_real_size():
    tris = _tris("home_car")
    xs = [p[0] for t in tris for p in t]
    ys = [p[1] for t in tris for p in t]
    assert max(ys) - min(ys) == pytest.approx(4000.0, abs=150.0)   # length
    assert 1700.0 < max(xs) - min(xs) < 1900.0                    # width
    tree = _tris("home_tree_broadleaf",
                 H.part_dims("home_tree_broadleaf", "Medium"))
    assert max(p[2] for t in tree for p in t) == pytest.approx(5000.0,
                                                               abs=60.0)


def test_wall_pieces_hang_at_their_height():
    for pid in ("home_pendant", "home_wall_shelf", "home_bath_cabinet",
                "home_wall_light", "home_wall_mirror"):
        assert H.part_rest_z(pid) > 800.0, pid
    for pid in ("home_table_lamp", "home_microwave", "home_laptop",
                "room_tv"):
        assert H.sits_on_top(pid), pid
    assert not H.sits_on_top("home_sofa")
