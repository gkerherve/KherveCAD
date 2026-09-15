"""The Prusa pieces (library_prusa.py): a little Prusa man and a Prusa
MINI+ at its real size, both boolean-free and standing on the floor.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest

from khervecad import library, library_prusa, mesh
from khervecad.model import validate


def _extent(part_id, size):
    spec = library_prusa.PARTS[part_id]
    node = library.build_part(part_id, dict(spec["sizes"][size],
                                            _size=size))
    assert not validate(node)
    assert "difference" not in {n.type for n in node.walk()}
    pts = [p for t in mesh.tessellate(node, fn=16) for p in t]
    return [(min(p[i] for p in pts), max(p[i] for p in pts))
            for i in range(3)]


@pytest.mark.parametrize("part_id", sorted(library_prusa.PARTS))
def test_every_prusa_piece_builds_in_every_size_and_colour(part_id):
    spec = library_prusa.PARTS[part_id]
    for size, entry in spec["sizes"].items():
        for colour in (spec["colors"][0], spec["colors"][-1]):
            node = library.build_part(part_id,
                                      dict(entry, _size=size, _color=colour))
            assert not validate(node), (part_id, size, colour)
            zs = [p[2] for t in mesh.tessellate(node, fn=12) for p in t]
            assert min(zs) == pytest.approx(0.0, abs=0.5), (part_id, size)
    assert part_id in library.PARTS


def test_the_prusa_man_is_as_tall_as_asked():
    for size, h in (("Figure (100 mm)", 100.0),
                    ("Desk figure (180 mm)", 180.0)):
        (_x, _y, (z0, z1)) = _extent("prusa_man", size)
        assert z1 - z0 == pytest.approx(h, rel=0.05)


def test_the_prusa_mini_is_its_real_size():
    (x0, x1), (y0, y1), (z0, z1) = _extent("prusa_mini", "Real size (1:1)")
    assert x1 - x0 == pytest.approx(380.0, abs=15.0)
    assert y1 - y0 == pytest.approx(330.0, abs=15.0)
    assert z1 - z0 == pytest.approx(380.0, abs=15.0)
    (x0, x1), _y, _z = _extent("prusa_mini", "Desk model (1:4)")
    assert x1 - x0 == pytest.approx(95.0, abs=5.0)
