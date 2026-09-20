"""Grown trees (treegen.py, library_trees.py): every species at every
detail is valid closed geometry within its triangle budget, grows to its
height, has leaves and branches, and lands in Library ▸ City ▸ Trees.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest

from khervecad import bake, mesh, treegen as T

#: high / medium carry the Leaves library's real blades (~130 triangles
#: each, `treeleaves.BUDGET` of them), which is why a tree is ~150k
#: triangles now — it was 30k with diamond leaves; city trees are unchanged
BUDGET = {"high": 165000, "medium": 100000, "city": 6000}


@pytest.mark.parametrize("species", list(T.SPECIES))
@pytest.mark.parametrize("detail", ["high", "city"])
def test_every_species_is_valid_and_within_budget(species, detail):
    node = T.build(species, detail=detail)
    polys = [n for n in node.walk() if n.type == "polyhedron"]
    assert polys
    for p in polys:
        assert bake._check_polyhedron(p.params) is None, p.name
    assert T.triangle_count(node) < BUDGET[detail]
    tris = mesh.tessellate(node)
    top = max(v[2] for t in tris for v in t)
    h = T.SPECIES[species]["height"]
    assert 0.75 * h < top < 1.4 * h
    assert min(v[2] for t in tris for v in t) > -h * 0.02


def test_leaves_and_bark_are_separate_materials_and_seasons_change():
    node = T.build("maple", season="Summer")
    mats = {n.params.get("material") for n in node.walk()
            if n.type == "color"}
    assert {"Bark", "Leaves"} <= mats
    autumn = T.build("maple", season="Autumn")
    colours = {n.params["color"] for n in autumn.walk() if n.type == "color"}
    assert set(T.SEASONS["Autumn"]) & colours
    bare = T.build("maple", season="Winter")
    assert not [n for n in bare.walk() if n.name == "Leaves"]


def test_seed_grows_a_different_tree():
    a = T.build("oak", seed=1)
    b = T.build("oak", seed=2)
    pa = [n for n in a.walk() if n.type == "polyhedron"][0].params["points"]
    pb = [n for n in b.walk() if n.type == "polyhedron"][0].params["points"]
    assert pa != pb


def test_library_trees_and_city_trees():
    from khervecad.library import PARTS, build_part
    ids = [k for k, v in PARTS.items() if v.get("category") == "Trees"]
    assert len(ids) == len(T.SPECIES)
    assert build_part("tree_birch", dict(h=6000, seed=3, _color="Spring"))
    from khervecad import city_trees
    grove = city_trees.build_trees([dict(kind="broadleaf", x=0, y=0),
                                    dict(kind="spruce", x=9000, y=0)])
    assert len(mesh.tessellate(grove)) > 1000
