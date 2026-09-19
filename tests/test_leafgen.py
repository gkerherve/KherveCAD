"""Leaves (leafgen.py, library_leaves.py): every species builds as
closed, correctly wound polyhedra at every detail and season, standing
on z = 0 at its real size; the margins carry what makes a species —
lobes, teeth, a palmate outline.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest

from khervecad import leafgen, library, library_leaves, mesh
from khervecad.model import validate


@pytest.mark.parametrize("species", sorted(leafgen.SPECIES))
@pytest.mark.parametrize("detail", ["high", "low"])
def test_every_leaf_is_a_closed_solid_on_the_ground(species, detail):
    node = leafgen.build(species, "Autumn", 0, detail)
    assert not validate(node), species
    tris = mesh.tessellate(node, fn=8)
    assert tris
    assert min(p[2] for t in tris for p in t) == pytest.approx(0.0,
                                                              abs=0.2)


def test_leaves_are_their_real_size():
    for species in ("oak", "birch", "magnolia", "willow"):
        sp = leafgen.SPECIES[species]
        rows = leafgen.strip_grid(sp)
        xs = [p[0] for r in rows for p in r]
        ys = [p[1] for r in rows for p in r]
        assert max(xs) - min(xs) == pytest.approx(sp["L"], rel=0.15)
        assert max(ys) - min(ys) == pytest.approx(sp["W"], rel=0.35)


def test_lobes_and_teeth_shape_the_margin():
    oak, birch = leafgen.SPECIES["oak"], leafgen.SPECIES["birch"]
    def swings(sp):
        w = [leafgen.half_width(sp, s / 400) for s in range(40, 360)]
        return sum(1 for a, b, c in zip(w, w[1:], w[2:]) if b < a and b < c)
    assert swings(oak) >= 4            # a sinus between every lobe
    assert swings(birch) >= 6          # a notch between every tooth
    maple = leafgen.SPECIES["maple"]
    import math
    radii = [leafgen._palm_r(maple, math.radians(a)) for a in range(-130,
                                                                   131)]
    peaks = sum(1 for a, b, c in zip(radii, radii[1:], radii[2:])
                if b > a and b > c and b > maple["R"] * 0.7)
    assert peaks >= 5                  # five pointed lobes


def test_library_offers_every_species_in_its_seasons():
    assert set(library_leaves.PARTS) == {f"leaf_{k}"
                                         for k in leafgen.SPECIES}
    oak = library_leaves.PARTS["leaf_oak"]
    assert oak["category"] == "Leaves" and "Autumn" in oak["colors"]
    holly = library_leaves.PARTS["leaf_holly"]
    assert "Autumn" not in holly["colors"]         # evergreen
    node = library.build_part("leaf_maple", dict(size=90, detail=1,
                                                 _color="Autumn"))
    assert not validate(node)
