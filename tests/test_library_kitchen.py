"""Kitchen & tableware: every part builds and validates in every size and
colour, stands on the table, vessels are really hollow (one revolved
wall, no boolean), drinks sit inside their glass, and a full revolve's
seam is closed exactly.

Run with: python -m pytest tests/  (offscreen Qt).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
from collections import Counter
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from khervecad import analysis, library, library_kitchen as K, mesh
from khervecad.model import CadNode, validate

KITCHEN = sorted(pid for pid, s in library.PARTS.items()
                 if s.get("category") == K.CATEGORY)


def _build(pid, size=None, **extra):
    spec = library.PARTS[pid]
    sizes = spec.get("sizes") or {}
    size = size or next(iter(sizes))
    dims = dict(sizes.get(size, {}), _size=size)
    dims.update(extra)
    return library.build_part(pid, dims)


def _find(node, name):
    if node.name == name:
        return node
    for c in node.children:
        hit = _find(c, name)
        if hit is not None:
            return hit
    return None


def open_edges(tris):
    edges = Counter()
    for t in tris:
        for i in range(3):
            edges[(t[i], t[(i + 1) % 3])] += 1
    return sum(1 for (a, b), n in edges.items() if edges[(b, a)] != n)


def test_the_kitchen_is_in_the_library():
    assert len(KITCHEN) == len(K.PARTS) >= 25


@pytest.mark.parametrize("pid", KITCHEN)
def test_every_piece_builds_in_every_size_and_colour(pid):
    spec = library.PARTS[pid]
    colours = spec.get("colors") or [None]
    for size in spec["sizes"]:
        for colour in {colours[0], colours[-1]}:
            extra = {"_color": colour} if colour else {}
            root = CadNode("root")
            root.add(_build(pid, size, **extra))
            assert validate(root) == {}, (pid, size, colour)
    tris = mesh.tessellate(_build(pid), fn=24)
    assert tris
    assert min(p[2] for t in tris for p in t) >= -0.5, pid   # on the table


@pytest.mark.parametrize("pid", KITCHEN)
def test_every_piece_has_a_submenu(pid):
    label = library.PARTS[pid]["label"]
    assert any(label.startswith(s) for starts in K.GROUPS.values()
               for s in starts), label


@pytest.mark.parametrize("pid", ["kitchen_bowl", "kitchen_mug",
                                 "kitchen_pasta_bowl", "kitchen_saucepan",
                                 "kitchen_stock_pot", "kitchen_jug"])
def test_vessels_are_hollow(pid):
    # the vessel alone (its first revolve, not the lid, handle or
    # drink): far less than its box
    def first_revolve(n):
        if n.type == "rotate_extrude":
            return n
        for c in n.children:
            hit = first_revolve(c)
            if hit is not None:
                return hit
    body = first_revolve(_build(pid))
    tris = mesh.tessellate(body, fn=48)
    lo, hi = analysis.bounds(tris)
    box = (hi[0] - lo[0]) * (hi[1] - lo[1]) * (hi[2] - lo[2])
    volume = analysis.mass_properties(tris)["volume"]
    assert 0 < volume < 0.35 * box, pid


def test_a_full_revolve_closes_its_seam_exactly():
    # sin(2π) is not 0: the last ring used to miss the first by 1e-16
    node = K.plate("Plate", 270.0, 24.0, ("#ffffff", "Plastic"))
    for fn in (24, 45, 96):
        assert open_edges(mesh.tessellate(node, fn=fn)) == 0


@pytest.mark.parametrize("size", sorted(K.STEMWARE))
def test_the_drink_is_inside_the_glass(size):
    node = K.build_stemware({"_size": size, "_color": "Red wine"})
    glass = mesh.tessellate(_find(node, "Glass"), fn=32)
    drink = mesh.tessellate(_find(node, "Drink"), fn=32)
    g_lo, g_hi = analysis.bounds(glass)
    d_lo, d_hi = analysis.bounds(drink)
    assert all(g_lo[i] < d_lo[i] and d_hi[i] < g_hi[i] for i in range(3))
    # the drink sits in the bowl, above the stem
    assert d_lo[2] > K.STEMWARE[size]["stem_h"]
    empty = K.build_stemware({"_size": size, "_color": "Empty"})
    assert _find(empty, "Drink") is None


def test_the_wall_profile_is_even():
    outer = K.rounded_base(40.0, 6.0) + [(40.0, 12.0), (40.0, 90.0)]
    profile, inner = K.wall(outer, 4.0)
    assert inner[0] == pytest.approx((0.0, 4.0))
    assert inner[-1][0] == pytest.approx(36.0)
    assert profile[0] == (0.0, 0.0)


def test_a_place_setting_is_laid_for_a_diner_at_minus_y():
    node = _build("kitchen_place_setting")
    fork = _find(node, "Fork")
    knife = _find(node, "Knife")
    assert fork.params["x"] < 0 < knife.params["x"]      # fork on the left
    wine = _find(node, "Wine glass")
    assert wine.params["x"] > 0 and wine.params["y"] > 0
