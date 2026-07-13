"""A grove of procedural tree examples for the Examples menu.

Each tree is built the way the fractal tree is — a Python builder loops
tiers, branches, fronds, strands or canopy blobs and unrolls them into the
object tree, using only coloured solids so every tree previews in the
built-in viewer. The shared primitive helpers live in
:mod:`khervecad.examples`; this module is imported at the end of that one
and registers its builders by extending ``EXAMPLES`` in place.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import random

from .examples import (EXAMPLES, _color, _cube, _cyl, _ext, _place, _root,
                       _rot, _sphere)
from .model import CadNode


def pine_tree() -> CadNode:
    """A conifer/fir: a brown trunk under a stack of green cone tiers
    tapering to a snow-capped point."""
    parts = []
    trunk_h = 40.0
    parts.append(_color("Trunk", "#6b4a2f",
                        _cyl("Trunk", 9.0, trunk_h, r2=7.0)))
    tiers, base_r, base_h, top_r, top_h = 7, 55.0, 55.0, 8.0, 22.0
    greens = ["#2e6b3a", "#357a41", "#2a5f34"]
    z = trunk_h - 6.0
    for i in range(tiers):
        t = i / (tiers - 1)
        radius = base_r + (top_r - base_r) * t
        height = base_h + (top_h - base_h) * t
        cone = _cyl(f"Foliage {i + 1}", radius, height, r2=0.0, segments=64)
        parts.append(_color(f"Foliage {i + 1}", greens[i % len(greens)],
                            _place(cone, z=z)))
        z += height - height * 0.35
    parts.append(_color("Snow cap", "#f4f8ff",
                        _sphere("Snow cap", top_r * 0.5, z=z + top_h * 0.55,
                                seg=32)))
    return _root(*parts)


def oak_tree() -> CadNode:
    """A stout broadleaf oak: a tapered trunk that forks into branches
    under a broad, lumpy, rounded canopy of overlapping leaf masses."""
    root = _root()
    trunk_h, trunk_r = 100.0, 20.0
    root.add(_color("Bark", "#6e5136",
                    _cyl("Trunk", trunk_r, trunk_h, r2=trunk_r * 0.72,
                         segments=32)))
    top = CadNode("translate", "Crown base", dict(x=0.0, y=0.0, z=trunk_h))
    for rz, tilt, scale in [(0.0, 22.0, 1.0), (72.0, 26.0, 0.92),
                            (144.0, 20.0, 0.85), (216.0, 26.0, 0.90),
                            (288.0, 20.0, 0.95)]:
        length, r0 = 58.0 * scale, 9.0 * scale
        branch = CadNode("union", f"Branch {int(rz)}")
        branch.add(_color("Bark2", "#6e5136",
                          _cyl("Limb", r0, length, r2=r0 * 0.55,
                               segments=18)))
        fork = CadNode("translate", "Fork base", dict(x=0.0, y=0.0, z=length))
        for frz in (-28.0, 28.0):
            twig = _rot(_color("Bark3", "#6e5136",
                               _cyl("Twig", r0 * 0.45, length * 0.55,
                                    r2=r0 * 0.2, segments=14)), y=26.0)
            fork.add(_rot(twig, z=frz))
        branch.add(fork)
        top.add(_rot(_rot(branch, y=tilt), z=rz))
    root.add(top)
    cz, greens = trunk_h + 40.0, ["#3f7a3a", "#579a44"]
    blobs = [(0.0, 0.0, cz + 25.0, 62.0, 0), (55.0, 0.0, cz + 5.0, 46.0, 1),
             (-55.0, 0.0, cz + 5.0, 46.0, 1), (0.0, 55.0, cz + 5.0, 46.0, 0),
             (0.0, -55.0, cz + 5.0, 46.0, 1), (40.0, 40.0, cz - 15.0, 40.0, 1),
             (-40.0, 40.0, cz - 15.0, 40.0, 0),
             (40.0, -40.0, cz - 15.0, 40.0, 0),
             (-40.0, -40.0, cz - 15.0, 40.0, 1), (0.0, 0.0, cz - 25.0, 44.0, 0),
             (0.0, 0.0, cz + 55.0, 38.0, 1)]
    canopy = CadNode("union", "Canopy")
    for i, (x, y, z, r, gi) in enumerate(blobs):
        canopy.add(_color(f"Leafmass {i}", greens[gi],
                          _sphere(f"Blob {i}", r, x=x, y=y, z=z, seg=24)))
    root.add(canopy)
    return root


def palm_tree() -> CadNode:
    """A palm: a curved, banded, tapering trunk topped by an arching crown
    of drooping fronds and a cluster of coconuts."""
    n, total_h = 13, 290.0
    seg_h, r_base, r_top, lean_max = total_h / n, 17.0, 7.0, 24.0
    trunk = CadNode("union", "Trunk")
    bands = CadNode("union", "Bark bands")
    x, y, z = 0.0, 0.0, 0.0
    for i in range(n):
        t0, t1 = i / n, (i + 1) / n
        theta0 = math.radians(lean_max * t0 * t0)
        r0 = r_base + (r_top - r_base) * t0
        r1 = r_base + (r_top - r_base) * t1
        seg = _cyl(f"Trunk seg {i}", r0, seg_h, r2=r1, segments=20)
        trunk.add(_place(_rot(seg, y=math.degrees(theta0)), x=x, y=y, z=z))
        x += seg_h * math.sin(theta0)
        z += seg_h * math.cos(theta0)
        if i < n - 1:
            theta1 = math.radians(lean_max * t1 * t1)
            ring = _cyl(f"Band {i}", r1 + 0.4, seg_h * 0.16,
                        r2=r1 * 0.94 + 0.3, segments=20)
            bands.add(_place(_rot(ring, y=math.degrees(theta1)),
                             x=x, y=y, z=z - seg_h * 0.08))
    top_x, top_y, top_z = x, y, z

    def blade(length, w_start, w_end, pointed):
        if pointed:
            pts = [[0.0, -w_start / 2], [length * 0.55, -w_end / 2],
                   [length, 0.0], [length * 0.55, w_end / 2],
                   [0.0, w_start / 2]]
        else:
            pts = [[0.0, -w_start / 2], [length, -w_end / 2],
                   [length, w_end / 2], [0.0, w_start / 2]]
        return CadNode("polygon", "Blade", dict(x=0, y=0, points=pts))

    def frond(name, la, lb, up_angle, droop_angle, w0, wm):
        node = CadNode("union", name)
        node.add(_rot(_ext(f"{name} base", 3.0,
                           blade(la, w0, wm, False)), y=up_angle))
        tip_ax = la * math.cos(math.radians(up_angle))
        tip_az = -la * math.sin(math.radians(up_angle))
        node.add(_place(_rot(_ext(f"{name} tip", 3.0,
                                  blade(lb, wm, wm * 0.12, True)),
                             y=droop_angle), x=tip_ax, z=tip_az))
        return node

    fronds = CadNode("union", "Crown fronds")
    shapes = [(70.0, 145.0, -18.0, 22.0, 32.0), (75.0, 165.0, -8.0, 42.0, 34.0),
              (80.0, 175.0, 4.0, 62.0, 32.0), (70.0, 155.0, 14.0, 80.0, 28.0)]
    for i in range(11):
        az = (360.0 / 11) * i + i * 7.0
        la, lb, up_a, droop_a, w0 = shapes[i % 4]
        green = "#3f8f3a" if i % 2 == 0 else "#347a30"
        f = frond(f"Frond {i}", la, lb, up_a, droop_a, w0, w0 * 0.55)
        fronds.add(_color(f"Frond {i}", green,
                          _place(_rot(f, z=az), x=top_x, y=top_y,
                                 z=top_z + 6.0)))
    coconuts = CadNode("union", "Coconuts")
    for i, (dx, dy, dz) in enumerate([(11.0, 5.0, -22.0), (-10.0, 10.0, -26.0),
                                      (3.0, -13.0, -18.0), (-7.0, -7.0, -28.0)]):
        coconuts.add(_sphere(f"Coconut {i}", 10.0, x=top_x + dx,
                             y=top_y + dy, z=top_z + dz, seg=24))
    return _root(_color("Trunk wood", "#9c7a4f", trunk),
                 _color("Bark rings", "#6b4a2a", bands), fronds,
                 _color("Coconuts", "#5a3a1e", coconuts))


def willow_tree() -> CadNode:
    """A weeping willow: a stout trunk under a broad green foliage dome
    from whose edge a dense curtain of thin strands hangs straight down."""
    random.seed(7)
    root = _root()
    trunk_h, trunk_r = 100.0, 12.0
    root.add(_color("Bark", "#6e5136",
                    _cyl("Trunk", trunk_r, trunk_h, r2=trunk_r * 0.7,
                         segments=16)))
    for i in range(4):                                  # limbs (hidden in dome)
        limb = _rot(_color("Bark", "#6e5136",
                           _cyl(f"Limb{i}", 3.4, 46.0, r2=1.6, segments=10)),
                    x=34.0)
        root.add(_place(_rot(limb, z=i * 90.0 + 20.0), z=trunk_h))
    crown_z = trunk_h + 40.0
    for dx, dy, dz, r in [(0.0, 0.0, 26.0, 47.0), (40.0, 0.0, 4.0, 35.0),
                          (-40.0, 0.0, 4.0, 35.0), (0.0, 40.0, 4.0, 35.0),
                          (0.0, -40.0, 4.0, 35.0), (0.0, 0.0, -8.0, 42.0)]:
        root.add(_color("Crown", "#7bb04a",
                        _sphere("Crown blob", r, x=dx, y=dy, z=crown_z + dz,
                                seg=22)))
    for i in range(100):                                # curtain of withes
        strand = _color("Withe", "#8fbf5a",
                        _cyl(f"Strand{i}", 0.5, random.uniform(70.0, 130.0),
                             segments=6))
        strand = _rot(strand, x=random.uniform(168.0, 179.0))  # near-vertical
        strand = _place(strand, x=random.uniform(26.0, 48.0),
                        z=crown_z + random.uniform(-6.0, 18.0))
        root.add(_rot(strand, z=i * 3.6 + random.uniform(-6.0, 6.0)))
    return root


def _birch_trunk(name, base_r, top_r, height, lean_x, lean_y, n_marks, seed):
    """A tapered near-white birch trunk studded with dark lenticel marks."""
    rnd = random.Random(seed)
    trunk = CadNode("union", name)
    trunk.add(_color("Bark", "#eae7de",
                     _cyl("Trunk", base_r, height, r2=top_r, segments=24)))
    for i in range(n_marks):
        z = height * (0.08 + 0.84 * (i / max(n_marks - 1, 1)))
        z += rnd.uniform(-height * 0.02, height * 0.02)
        r_here = base_r + (top_r - base_r) * (z / height)
        half_len = r_here * rnd.uniform(0.7, 1.6)
        band = _cube(f"Lenticel {i}", half_len * 2.0, r_here * 0.9,
                     rnd.uniform(1.2, 2.6), x=-half_len, y=r_here * 0.55, z=z)
        trunk.add(_color(f"Lenticel {i}", "#2b2b2b",
                         _rot(band, z=rnd.uniform(0.0, 360.0))))
    return _rot(trunk, x=lean_x, y=lean_y)


def _birch_blob(name, r, x, y, z, seed):
    """A loose, sparse cluster of one or two small birch leaf spheres."""
    grp = CadNode("union", name)
    rnd = random.Random(seed)
    for i in range(rnd.randint(1, 2)):
        grp.add(_color(f"Leaf {i}", "#9ac96a",
                       _sphere(f"Leaf {i}", r * rnd.uniform(0.7, 1.0),
                               x=rnd.uniform(-r * 0.5, r * 0.5),
                               y=rnd.uniform(-r * 0.5, r * 0.5),
                               z=rnd.uniform(-r * 0.3, r * 0.3), seg=20)))
    return _place(grp, x=x, y=y, z=z)


def birch_tree() -> CadNode:
    """A slender clump of white-barked silver birch trunks with dark
    lenticel marks, thin upward branches and a sparse, airy crown."""
    root = _root()
    specs = [dict(name="Trunk A", base_r=4.6, top_r=1.6, height=290.0,
                  lean_x=2.0, lean_y=-1.5, n_marks=11, seed=1, x=0.0, y=0.0),
             dict(name="Trunk B", base_r=3.4, top_r=1.1, height=255.0,
                  lean_x=-3.0, lean_y=3.0, n_marks=9, seed=2, x=14.0, y=6.0),
             dict(name="Trunk C", base_r=2.8, top_r=0.9, height=230.0,
                  lean_x=3.5, lean_y=2.0, n_marks=8, seed=3, x=-11.0, y=-9.0)]
    for s in specs:
        trunk = _birch_trunk(s["name"], s["base_r"], s["top_r"], s["height"],
                             s["lean_x"], s["lean_y"], s["n_marks"], s["seed"])
        root.add(_place(trunk, x=s["x"], y=s["y"]))
    mx, my, mh, mr = 0.0, 0.0, 290.0, 1.6
    for i, (length, ax, az, z, br) in enumerate(
            [(48.0, 55.0, 0.0, mh * 0.72, mr), (42.0, 60.0, 95.0, mh * 0.80,
              mr * 0.9), (38.0, 50.0, 190.0, mh * 0.87, mr * 0.8),
             (34.0, 65.0, 280.0, mh * 0.93, mr * 0.7)]):
        branch = _color(f"Branch {i}", "#eae7de",
                        _cyl(f"Branch {i}", br * 0.55, length, r2=br * 0.22,
                             segments=12))
        root.add(_place(_rot(_rot(branch, x=ax), z=az),
                        x=mx + br * 0.8, y=my, z=z))
    for i, (x, y, z, r, seed) in enumerate(
            [(0.0, 0.0, 292.0, 16.0, 11), (26.0, 18.0, 275.0, 13.0, 12),
             (-22.0, 20.0, 268.0, 13.0, 13), (18.0, -22.0, 258.0, 12.0, 14),
             (-20.0, -14.0, 248.0, 12.0, 15), (34.0, -6.0, 238.0, 11.0, 16),
             (-8.0, 30.0, 230.0, 10.0, 17)]):
        root.add(_birch_blob(f"Crown {i}", r, x, y, z, seed))
    return root


def cherry_blossom_tree() -> CadNode:
    """A spreading cherry tree in full sakura bloom: a forking trunk under
    an overlapping canopy of soft-pink blossom clusters."""
    trunk_h, wood = 102.0, "#5c4433"
    pink, pink_light = "#f6c6d4", "#fbdfe8"
    root = _root()
    root.add(_color("Trunk", wood,
                    _cyl("Trunk", 15.0, trunk_h, r2=9.0, segments=24)))

    def cluster(name):
        c = CadNode("union", name)
        c.add(_color("Petals", pink, _sphere("B1", 20.0, seg=16)))
        c.add(_place(_color("Petals light", pink_light,
                            _sphere("B2", 15.0, seg=16)), x=9.0, y=4.0, z=7.0))
        return c

    def limb(idx, rz):
        twig = CadNode("union", f"Twig{idx}")
        twig.add(_color("Branch", wood,
                        _cyl(f"Limb{idx}b", 2.6, 66.0, r2=1.3, segments=12)))
        tip = CadNode("translate", "Tip", dict(x=0.0, y=0.0, z=66.0))
        tip.add(cluster(f"Bloom{idx}"))
        twig.add(tip)
        base = CadNode("union", f"Limb{idx}")
        base.add(_color("Branch", wood,
                        _cyl(f"Limb{idx}a", 3.8, 64.0, r2=2.6, segments=12)))
        elbow = CadNode("translate", "Elbow", dict(x=0.0, y=0.0, z=64.0))
        elbow.add(_rot(twig, y=-24.0))
        base.add(elbow)
        return _rot(_rot(base, y=53.0), z=rz)

    for i in range(4):
        root.add(_place(limb(i, i * 90.0 + 45.0), z=trunk_h))
    root.add(_place(_color("Petals", pink, _sphere("Center1", 25.0, seg=18)),
                    z=trunk_h + 80.0))
    root.add(_place(_color("Petals light", pink_light,
                           _sphere("Center2", 18.0, seg=16)),
                    x=17.0, y=-9.0, z=trunk_h + 94.0))
    for i, (px, py) in enumerate([(24.0, 6.0), (-18.0, 20.0), (10.0, -25.0)]):
        root.add(_place(_color("Fallen petal", pink,
                               _cube(f"Petal{i}", 3.0, 3.0, 0.6, center=True)),
                        x=px, y=py, z=0.3))
    return root


#: (menu label, category, builder) — registered into examples.EXAMPLES.
TREE_EXAMPLES = [
    ("Pine / conifer", "Trees", pine_tree),
    ("Oak", "Trees", oak_tree),
    ("Palm", "Trees", palm_tree),
    ("Weeping willow", "Trees", willow_tree),
    ("Silver birch", "Trees", birch_tree),
    ("Cherry blossom tree", "Trees", cherry_blossom_tree),
]

# register into the shared list in place (see examples_flowers.py)
EXAMPLES.extend(TREE_EXAMPLES)
