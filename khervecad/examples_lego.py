"""LEGO models for the Examples menu (the "Lego" category), built from
the library's bricks (library_lego.py) at their real dimensions.

A model is sketched as VOXELS — one cell per stud and brick layer, each
holding a colour and a group label — and `Scene.add_voxels` packs every
layer into the fewest standard bricks (2x8 down to 1x1, one colour per
brick), turning the long axis layer by layer so seams do not stack: the
running bond a real build has. Pieces that are not a voxel (roof slopes,
tiles, plates) are added directly. `Scene.to_node` then emits every
piece through `library_lego.brick`/`slope`, dropping the studs another
piece sits on and the underside nobody sees, so a few hundred bricks
stay light enough for the 3D view.

A colour may be a tuple of names: those cells pack as one material and
each brick then draws one of the names (weighted by repeats, seeded, so
a model is the same every time) — cobblestone, moss, leaves.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import random

from .examples import EXAMPLES, _root
from .library_lego import (BASEPLATE_H, BRICK_H, PITCH, PLATE_H, brick,
                           colour, slope)
from .model import CadNode

#: standard brick footprints, largest first
FOOTPRINTS = [(2, 8), (2, 6), (2, 4), (2, 3), (2, 2),
              (1, 8), (1, 6), (1, 4), (1, 3), (1, 2), (1, 1)]
#: stud facets in a model: round enough at brick scale, light to draw
SEGMENTS = 16

STONE = ("Light bluish grey",) * 3 + ("Dark bluish grey",) * 2
MOSSY = STONE + ("Green",)
LEAVES = ("Green", "Green", "Bright green")


# ---------------------------------------------------------------- scene

def pack(layer, k):
    """Cover one layer — {(i, j): value} — with standard bricks, each of
    one value. Largest first; even layers run long along X and scan row
    by row, odd layers run along Y and scan column by column, so the
    joints of one layer sit over the middle of the bricks below.
    Returns [(i, j, nx, ny, value)]."""
    shapes = []
    for a, b in FOOTPRINTS:
        for s in (((b, a), (a, b)) if k % 2 == 0 else ((a, b), (b, a))):
            if s not in shapes:
                shapes.append(s)
    order = (lambda c: (c[1], c[0])) if k % 2 == 0 else (lambda c: c)
    free = dict(layer)
    out = []
    for cell in sorted(layer, key=order):
        if cell not in free:
            continue
        i, j = cell
        value = free[cell]
        for nx, ny in shapes:
            cover = [(i + a, j + b) for a in range(nx) for b in range(ny)]
            if all(free.get(c) == value for c in cover):
                for c in cover:
                    del free[c]
                out.append((i, j, nx, ny, value))
                break
    return out


def box(cells, i0, i1, j0, j1, k0, k1, value):
    """Fill the cells i0..i1 x j0..j1 x k0..k1 (inclusive) with *value*."""
    for i in range(i0, i1 + 1):
        for j in range(j0, j1 + 1):
            for k in range(k0, k1 + 1):
                cells[(i, j, k)] = value


def ring(cells, i0, i1, j0, j1, k, value):
    """The one-stud wall round i0..i1 x j0..j1 on layer k."""
    for i in range(i0, i1 + 1):
        for j in range(j0, j1 + 1):
            if i in (i0, i1) or j in (j0, j1):
                cells[(i, j, k)] = value


class Scene:
    """Pieces on the stud grid, emitted as one model node."""

    def __init__(self, seed=1):
        self.pieces = []
        self.rng = random.Random(seed)

    def add(self, kind, i, j, nx, ny, z, colour_name, group,
            height=BRICK_H, facing="-Y", seg=None):
        """One piece: kind "brick" (any height), "tile" or "slope"
        (2 deep, *nx* wide, low edge towards *facing*)."""
        if isinstance(colour_name, tuple):
            colour_name = self.rng.choice(colour_name)
        self.pieces.append(dict(
            kind=kind, i=i, j=j, nx=nx, ny=2 if kind == "slope" else ny,
            z=z, h=BRICK_H if kind == "slope" else height,
            colour=colour_name, group=group, facing=facing, seg=seg))

    def add_voxels(self, cells, z0=0.0, height=BRICK_H):
        """*cells*: {(i, j, k): (colour, group)}; layer k sits at
        z0 + k * height."""
        layers = {}
        for (i, j, k), value in cells.items():
            layers.setdefault(k, {})[(i, j)] = value
        for k in sorted(layers):
            for i, j, nx, ny, (col, group) in pack(layers[k], k):
                self.add("brick", i, j, nx, ny, z0 + k * height, col,
                         group, height)

    def to_node(self, name):
        """The model as a group of groups (one per label, in the order
        first used), each piece a coloured brick — studs another piece
        covers are left out."""
        bottoms = set()
        for p in self.pieces:
            for a in range(p["nx"]):
                for b in range(p["ny"]):
                    bottoms.add((p["i"] + a, p["j"] + b, round(p["z"], 3)))
        model = CadNode("union", name)
        groups = {}
        for p in self.pieces:
            top = round(p["z"] + p["h"], 3)
            bare = {(a, b) for a in range(p["nx"]) for b in range(p["ny"])
                    if (p["i"] + a, p["j"] + b, top) not in bottoms}
            x, y, seg = p["i"] * PITCH, p["j"] * PITCH, p["seg"] or SEGMENTS
            if p["kind"] == "slope":
                row = 1 if p["facing"] == "-Y" else 0
                node = slope(p["nx"], p["facing"],
                             studs={a for a, b in bare if b == row},
                             x=x, y=y, z=p["z"], seg=seg,
                             name=f"Slope 2x{p['nx']}")
            else:
                kind = "Tile" if p["kind"] == "tile" else (
                    "Brick" if p["h"] >= BRICK_H else "Plate")
                node = brick(p["nx"], p["ny"], p["h"],
                             studs=set() if kind == "Tile" else bare,
                             hollow=False, x=x, y=y, z=p["z"], seg=seg,
                             name=f"{kind} {p['nx']}x{p['ny']}")
            wrap = colour(node, p["colour"])
            wrap.name = f"{node.name}, {p['colour']}"
            group = groups.get(p["group"])
            if group is None:
                group = groups[p["group"]] = CadNode("union", p["group"])
                model.add(group)
            group.add(wrap)
        return model


# --------------------------------------------------------------- models

def lego_minecraft_tower() -> CadNode:
    """A Minecraft stone watchtower on a grass block: mossy cobblestone
    walls in a running bond, an oak door, glass windows on every side,
    an overhanging platform with battlements and torches."""
    s = Scene(seed=4)
    dirt, grass = {}, {}
    box(dirt, 0, 13, 0, 13, 0, 0, ("Reddish brown", "Grass block"))
    box(grass, 0, 13, 0, 13, 0, 0, ("Bright green", "Grass block"))
    s.add_voxels(dirt)
    s.add_voxels(grass, z0=BRICK_H, height=PLATE_H)
    z0 = BRICK_H + PLATE_H                     # the top of the grass

    v = {}
    for k in range(16):
        ring(v, 4, 9, 4, 9, k, (MOSSY if k < 5 else STONE, "Tower walls"))
    box(v, 6, 7, 4, 4, 0, 2, ("Dark tan", "Door"))
    glass = ("Trans-light blue", "Windows")
    for k in (7, 12):
        box(v, 6, 7, 4, 4, k, k + 1, glass)
        box(v, 6, 7, 9, 9, k, k + 1, glass)
        box(v, 4, 4, 6, 7, k, k + 1, glass)
        box(v, 9, 9, 6, 7, k, k + 1, glass)
    # the platform overhangs a stud all round, battlements on its rim
    box(v, 3, 10, 3, 10, 16, 16, (STONE, "Battlements"))
    for t in (0, 2, 5, 7):
        for cell in ((3 + t, 3), (3 + t, 10), (3, 3 + t), (10, 3 + t)):
            v[(*cell, 17)] = (STONE, "Battlements")
    # torches: on the corner merlons and either side of the door
    for i, j, k in ((3, 3, 18), (3, 10, 18), (10, 3, 18), (10, 10, 18),
                    (5, 3, 0), (8, 3, 0)):
        v[(i, j, k)] = ("Reddish brown", "Torches")
        v[(i, j, k + 1)] = ("Orange", "Torches")
    s.add_voxels(v, z0=z0)

    # a gravel path to the door, and poppies and dandelions in the grass
    for j in (0, 2):
        s.add("tile", 6, j, 2, 2, z0, "Dark bluish grey", "Path",
              height=PLATE_H)
    for i, j, bloom in ((1, 2, "Red"), (2, 10, "Yellow"), (11, 1, "Red"),
                        (12, 11, "Yellow"), (1, 6, "Blue")):
        s.add("brick", i, j, 1, 1, z0, "Green", "Flowers", height=PLATE_H)
        s.add("brick", i, j, 1, 1, z0 + PLATE_H, bloom, "Flowers",
              height=PLATE_H)
    return _root(s.to_node("Minecraft tower"))


def runs(i0, i1, skip=()):
    """(start, length) pieces covering i0..i1 minus *skip*, each at most
    4 long — how a row of 2x4 slopes or tiles is laid round a gap."""
    out, start, n = [], None, 0
    for i in range(i0, i1 + 2):
        if i <= i1 and i not in skip:
            start = i if start is None else start
            n += 1
            continue
        while n:
            take = min(4, n)
            out.append((start, take))
            start, n = start + take, n - take
        start = None
    return out


def _tree(v, i, j):
    """A little tree whose 2x2 trunk has its corner at (i, j): three
    bricks of trunk under a round canopy of mixed greens."""
    box(v, i, i + 1, j, j + 1, 0, 2, ("Reddish brown", "Trees"))
    leaves = (LEAVES, "Trees")
    for k in (3, 4):
        box(v, i - 2, i + 3, j - 2, j + 3, k, k, leaves)
        for ci in (i - 2, i + 3):
            for cj in (j - 2, j + 3):
                del v[(ci, cj, k)]                    # round the corners
    box(v, i - 1, i + 2, j - 1, j + 2, 5, 5, leaves)
    box(v, i, i + 1, j, j + 1, 6, 6, leaves)


def lego_house() -> CadNode:
    """A LEGO house on a 16 x 32 baseplate: a grey foundation, white
    walls, a blue door, clear windows on every side, a red roof of 45°
    slopes with a ridge and a chimney, a path, two trees and flowers."""
    s = Scene(seed=7)
    s.add("brick", 0, 0, 32, 16, 0.0, "Green", "Baseplate",
          height=BASEPLATE_H, seg=12)
    z0 = BASEPLATE_H
    i0, i1, j0, j1 = 9, 22, 4, 11                      # the walls
    v = {}
    ring(v, i0, i1, j0, j1, 0, ("Dark bluish grey", "Foundation"))
    for k in range(1, 6):
        ring(v, i0, i1, j0, j1, k, ("White", "Walls"))
    box(v, 15, 16, j0, j0, 1, 4, ("Blue", "Door"))
    glass = ("Trans-light blue", "Windows")
    for i in (11, 19):
        box(v, i, i + 1, j0, j0, 2, 3, glass)
    for i in (11, 15, 19):
        box(v, i, i + 1, j1, j1, 2, 3, glass)
    for i in (i0, i1):
        box(v, i, i, 7, 8, 2, 3, glass)
    # the gable ends: the wall's triangle under each end of the roof
    for r, (g0, g1) in enumerate(((5, 10), (6, 9), (7, 8))):
        for i in (i0, i1):
            box(v, i, i, g0, g1, 6 + r, 6 + r, ("White", "Gables"))
    chimney = range(18, 20)
    box(v, 18, 19, 7, 8, 9, 11, ("Dark red", "Chimney"))
    _tree(v, 3, 7)
    _tree(v, 27, 7)
    s.add_voxels(v, z0=z0)

    # the roof: each course of slopes steps in a stud and sits on the
    # stud row of the one below; it overhangs the walls by a stud
    eaves = z0 + 6 * BRICK_H
    for r in range(4):
        z = eaves + r * BRICK_H
        for start, n in runs(8, 23, chimney if r == 3 else ()):
            s.add("slope", start, 3 + r, n, 2, z, "Red", "Roof",
                  facing="-Y")
            s.add("slope", start, 11 - r, n, 2, z, "Red", "Roof",
                  facing="+Y")
    for start, n in runs(8, 23, chimney):
        s.add("tile", start, 7, n, 2, eaves + 4 * BRICK_H, "Dark red",
              "Roof", height=PLATE_H)
    s.add("tile", 18, 7, 2, 2, z0 + 12 * BRICK_H, "Black", "Chimney",
          height=PLATE_H)

    for j in (0, 2):
        s.add("tile", 15, j, 2, 2, z0, "Tan", "Path", height=PLATE_H)
    for i, j, bloom in ((10, 2, "Red"), (12, 2, "Yellow"),
                        (19, 2, "Yellow"), (21, 2, "Red"), (7, 2, "Red"),
                        (24, 2, "Yellow"), (6, 13, "Dark pink"),
                        (25, 13, "Medium lavender")):
        s.add("brick", i, j, 1, 1, z0, "Green", "Flowers", height=PLATE_H)
        s.add("brick", i, j, 1, 1, z0 + PLATE_H, bloom, "Flowers",
              height=PLATE_H)
    return _root(s.to_node("House"))


EXAMPLES.extend([
    ("Minecraft tower", "Lego", lego_minecraft_tower),
    ("House", "Lego", lego_house),
])
