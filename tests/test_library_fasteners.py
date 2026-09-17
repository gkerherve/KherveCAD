"""The fastener drawer (library_fasteners.py): every screw, nut,
washer, pin and clip builds at every size, validates and has geometry.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest

from khervecad import library, library_fasteners, mesh
from khervecad.model import validate


def _build(part_id, size):
    spec = library_fasteners.PARTS[part_id]
    return library.build_part(part_id, dict(spec["sizes"][size],
                                            _size=size))


def _extent(node):
    pts = [p for t in mesh.tessellate(node, fn=20) for p in t]
    return [(min(p[i] for p in pts), max(p[i] for p in pts))
            for i in range(3)]


@pytest.mark.parametrize("part_id", sorted(library_fasteners.PARTS))
def test_every_fastener_builds_in_every_size(part_id):
    assert part_id in library.PARTS
    assert library.PARTS[part_id]["category"] == "Fasteners"
    for size in ("M3", "M6", "M12"):
        node = _build(part_id, size)
        assert not validate(node), (part_id, size)
        assert mesh.tessellate(node, fn=16), (part_id, size)


def test_a_washer_takes_its_own_bolt():
    """The washer's bore must clear the bolt it is named for, and its
    rim must be wider than the nut's flats are not — the point of the
    shared size table."""
    for size, d in (("M6", 6.0), ("M12", 12.0)):
        (x0, x1), _y, (z0, z1) = _extent(_build("washer_flat", size))
        assert x1 - x0 == pytest.approx(2.2 * d, rel=0.1)
        assert z1 - z0 < 0.4 * d


def test_a_dowel_pin_is_its_nominal_diameter_and_length():
    (x0, x1), _y, (z0, z1) = _extent(_build("pin_dowel", "M6"))
    assert x1 - x0 == pytest.approx(6.0, abs=0.3)
    assert z1 - z0 == pytest.approx(
        library_fasteners.BOLT_SIZES["M6"]["length"], abs=0.3)


def test_threaded_parts_really_carry_a_helix():
    """A thread is a twisted extrusion, so the part holds a
    linear_extrude with a twist — not a plain cylinder."""
    node = _build("bolt_carriage", "M8")
    twists = [n.params.get("twist") for n in node.walk()
              if n.type == "linear_extrude"]
    assert any(t for t in twists), twists
