"""Grown trees with real leaves and a furrowed, flared trunk
(treegen / treebark / treeleaves), and the Stones library (stonegen,
library_stones).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest

from khervecad import library, model, stonegen, treebark, treegen, treeleaves
from khervecad.model import CadNode

BROADLEAF = sorted(treeleaves.LEAF_OF)


def _valid(node):
    root = CadNode("union", "root", {})
    root.add(node)
    return model.validate(root)


def _polys(node):
    return [n for n in node.walk() if n.type == "polyhedron"]


def _named(node, name):
    return [n for n in node.walk() if n.name == name]


# ---------------------------------------------------------------- trees
@pytest.mark.parametrize("species", sorted(treegen.SPECIES))
@pytest.mark.parametrize("detail", ["high", "medium", "city"])
def test_every_tree_builds_closed_solids(species, detail):
    tree = treegen.build(species, detail=detail, seed=2)
    assert _polys(tree)
    assert _valid(tree) == {}


@pytest.mark.parametrize("species", BROADLEAF)
def test_broadleaf_trees_carry_the_real_leaf_shapes(species):
    """A broadleaf at high detail is leaf bunches on small cores — the
    Leaves library's blades, not diamonds (a blade is ~100+ triangles)."""
    tree = treegen.build(species, detail="high")
    if species != "willow":          # a weeping crown has strands, no cores
        assert _named(tree, "Foliage mass")
    leaf_faces = sum(len(n.params["faces"]) for n in _named(tree, "Leaves")
                     if n.type == "polyhedron")
    blade = len(treeleaves.template(species, 300.0)[1])
    assert blade > 60
    assert leaf_faces >= 300 * 60            # hundreds of real blades
    assert treegen.triangle_count(tree) < 220000


def test_conifers_and_palms_keep_their_needles_and_fronds():
    for species in ("pine", "spruce", "cypress", "palm"):
        tree = treegen.build(species, detail="high")
        assert not _named(tree, "Foliage mass")


def test_city_trees_stay_cheap():
    for species in treegen.SPECIES:
        tree = treegen.build(species, detail="city")
        assert treegen.triangle_count(tree) < 20000, species


def test_a_cherry_in_blossom_keeps_its_petals():
    spring = treegen.build("cherry", season="Spring", detail="high")
    assert not _named(spring, "Foliage mass")
    assert _named(treegen.build("cherry", season="Summer"), "Foliage mass")


def test_the_leaf_template_is_a_closed_blade_standing_on_its_stalk():
    pts, faces = treeleaves.template("oak", 300.0)
    xs = [p[0] for p in pts]
    assert min(xs) >= -1.0 and 250 < max(xs) < 330      # 300 mm midrib
    assert max(p[2] for p in pts) - min(p[2] for p in pts) > 1.0


def test_a_placed_leaf_lies_upper_face_up_and_keeps_its_winding():
    from khervecad.treegen import Mesh
    tpl = treeleaves.template("oak", 300.0)
    m = Mesh()
    treeleaves.place(m, tpl, (0, 0, 1000), (1, 0, -0.1), (0, 0, 0), 1.0)
    assert len(m.points) == len(tpl[0]) and len(m.faces) == len(tpl[1])
    assert min(p[2] for p in m.points) > 900          # at the twig
    assert _valid(m.node("Leaf")) == {}
    # the blade's upper face is towards the sky: the stalk end is lower
    # than a leaf tip only by the droop, and no point is far below it
    assert max(p[2] for p in m.points) - min(p[2] for p in m.points) < 320


# ---------------------------------------------------------------- trunk
def test_the_oak_trunk_flares_at_the_foot_and_is_furrowed():
    h = 14000.0
    tree = treegen.build("oak", height=h, detail="high")
    bark = _named(tree, "Branches")[0]
    poly = [n for n in bark.walk() if n.type == "polyhedron"][0]
    r0 = h * treegen.SPECIES["oak"]["radius"]
    foot = [math.hypot(x, y) for x, y, z in poly.params["points"] if z < 150]
    assert max(foot) > r0 * 1.3, "no buttress at the foot"
    # many rings: the smoothed, densified trunk (a plain tube has ~6 sides)
    assert len(poly.params["points"]) > 1500


def test_the_birch_has_its_dark_lenticels_and_the_oak_does_not():
    assert _named(treegen.build("birch"), "Lenticels")
    assert not _named(treegen.build("oak"), "Lenticels")


def test_bark_smoothing_keeps_the_given_points_and_adds_between():
    path = [(0, 0, 0), (0, 0, 100), (50, 0, 200), (50, 0, 300)]
    radii = [10, 9, 8, 7]
    out, r = treebark.smooth(path, radii, 4)
    assert len(out) == (len(path) - 1) * 4 + 1 and len(r) == len(out)
    assert out[0] == path[0] and out[4] == pytest.approx(path[1])
    assert out[-1] == path[-1]


def test_trees_are_deterministic_per_seed():
    a = treegen.build("maple", seed=5)
    b = treegen.build("maple", seed=5)
    c = treegen.build("maple", seed=6)
    pa = _polys(a)[0].params["points"]
    assert pa == _polys(b)[0].params["points"]
    assert pa != _polys(c)[0].params["points"]


# --------------------------------------------------------------- stones
STONE_PARTS = sorted(p for p, s in library.PARTS.items()
                     if s["category"] == "Stones")


def test_the_stones_library_has_every_kind():
    assert {"stone_pebble", "stone_cobble", "stone_skipping",
            "stone_angular", "stone_boulder", "stone_menhir",
            "stone_flagstone", "stone_pebbles", "stone_gravel",
            "stone_rocks", "stone_cairn"} <= set(STONE_PARTS)


@pytest.mark.parametrize("pid", STONE_PARTS)
def test_every_stone_part_builds_valid_solids_at_every_size(pid):
    spec = library.PARTS[pid]
    assert len(spec["sizes"]) == 3
    for dims in spec["sizes"].values():
        node = library.build_part(pid, dict(dims))
        assert _polys(node)
        assert _valid(node) == {}


@pytest.mark.parametrize("kind", sorted(stonegen.KINDS))
def test_a_stone_sits_on_the_ground_at_about_its_size(kind):
    import random
    from khervecad.treegen import Mesh
    size = 400.0
    m = Mesh()
    height = stonegen.stone(m, random.Random(3), kind, size)
    zs = [p[2] for p in m.points]
    assert min(zs) == pytest.approx(0.0, abs=0.11)
    assert height == pytest.approx(max(zs), abs=0.2)
    longest = max(max(p[i] for p in m.points) - min(p[i] for p in m.points)
                  for i in range(3))
    assert 0.4 * size < longest < 1.4 * size


def test_a_skipping_stone_is_flat_and_a_menhir_is_tall():
    import random
    from khervecad.treegen import Mesh
    flat, tall = Mesh(), Mesh()
    stonegen.stone(flat, random.Random(1), "skipping", 100.0)
    stonegen.stone(tall, random.Random(1), "menhir", 3000.0)
    assert max(p[2] for p in flat.points) < 35
    assert max(p[2] for p in tall.points) > 2000


def test_stone_shape_number_and_colour_change_the_part():
    build = lambda **kw: library.build_part("stone_boulder", dict(
        {"size": 1200, "seed": 1}, **kw))
    a, b = build(), build(seed=2)
    assert _polys(a)[0].params["points"] != _polys(b)[0].params["points"]
    assert build(seed=1)  # deterministic
    assert _polys(build())[0].params["points"] == \
        _polys(a)[0].params["points"]
    colours = {n.params["color"] for n in build(_color="Basalt").walk()
               if n.type == "color"}
    assert colours != {n.params["color"] for n in build(
        _color="Marble").walk() if n.type == "color"}


def test_a_scatter_never_overlaps_its_stones():
    import random
    from khervecad.treegen import Mesh
    got = []
    m = Mesh()
    n = stonegen.scatter(lambda i: m, random.Random(4), 40, 2000.0,
                         (30.0, 150.0), ("pebble", "cobble"), level=1)
    assert 10 < n <= 40


def test_stones_are_listed_beside_leaves_in_nature_and_garden():
    from khervecad.library_groups import SECTIONS
    nature = dict((n, s) for t, es in SECTIONS for n, _i, s in es)
    cats = nature["Nature & garden"]
    assert cats.index("Stones") == cats.index("Leaves") + 1
