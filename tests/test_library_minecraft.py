"""Minecraft characters and mobs (library_minecraft.py): every one
builds, validates, uses no boolean and stands on the floor.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest

from khervecad import library, library_minecraft, mesh
from khervecad.model import validate


@pytest.mark.parametrize("part_id", sorted(library_minecraft.PARTS))
def test_every_mob_builds_and_stands_on_the_floor(part_id):
    assert part_id in library.PARTS
    size = "Figure (1 px = 5 mm)"
    node = library.build_part(part_id, dict(
        library_minecraft.SIZES[size], _size=size))
    assert not validate(node)
    assert "difference" not in {n.type for n in node.walk()}
    zs = [p[2] for t in mesh.tessellate(node, fn=12) for p in t]
    assert min(zs) == pytest.approx(0.0, abs=0.5)


def test_steve_is_32_pixels_tall():
    size = "Large (1 px = 10 mm)"
    node = library.build_part("mc_steve", dict(
        library_minecraft.SIZES[size], _size=size))
    zs = [p[2] for t in mesh.tessellate(node) for p in t]
    assert max(zs) - min(zs) == pytest.approx(320.0, abs=5.0)
