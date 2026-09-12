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

import math
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

    def __init__(self, seed=1, seg=SEGMENTS):
        self.pieces = []
        self.rng = random.Random(seed)
        self.seg = seg

    def add(self, kind, i, j, nx, ny, z, colour_name, group,
            height=BRICK_H, facing="-Y", seg=None):
        """One piece: kind "brick" (any height), "tile" or "slope"
        (2 deep, *nx* wide, low edge towards *facing* — along X for
        "-Y"/"+Y", along Y for "-X"/"+X")."""
        if isinstance(colour_name, tuple):
            colour_name = self.rng.choice(colour_name)
        n = nx
        if kind == "slope":
            nx, ny = (n, 2) if facing in ("-Y", "+Y") else (2, n)
        self.pieces.append(dict(
            kind=kind, i=i, j=j, nx=nx, ny=ny, n=n,
            z=z, h=BRICK_H if kind == "slope" else height,
            colour=colour_name, group=group, facing=facing, seg=seg))

    def add_voxels(self, cells, z0=0.0, height=BRICK_H, kind="brick"):
        """*cells*: {(i, j, k): (colour, group)}; layer k sits at
        z0 + k * height. *kind* "tile" makes smooth, studless pieces."""
        layers = {}
        for (i, j, k), value in cells.items():
            layers.setdefault(k, {})[(i, j)] = value
        for k in sorted(layers):
            for i, j, nx, ny, (col, group) in pack(layers[k], k):
                self.add(kind, i, j, nx, ny, z0 + k * height, col,
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
            x, y, seg = p["i"] * PITCH, p["j"] * PITCH, p["seg"] or self.seg
            if p["kind"] == "slope":
                facing = p["facing"]
                if facing in ("-Y", "+Y"):           # the back stud row
                    row = 1 if facing == "-Y" else 0
                    keep = {a for a, b in bare if b == row}
                else:
                    col = 1 if facing == "-X" else 0
                    keep = {b for a, b in bare if a == col}
                node = slope(p["n"], facing, studs=keep, x=x, y=y,
                             z=p["z"], seg=seg, name=f"Slope 2x{p['n']}")
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


# Figures in the Minecraft style, two studs to a Minecraft pixel: a 4x4
# head, a 4x2 body, 2x2 arms and legs, the face on the front (-Y) row of
# the head. They stand on a patch of grass, facing -Y.

def _grass(s, w=10, d=6):
    """A patch of grass plates under a figure; returns its top."""
    base = {}
    box(base, 0, w - 1, 0, d - 1, 0, 0, ("Bright green", "Grass"))
    s.add_voxels(base, height=PLATE_H)
    return PLATE_H


def _face(v, k, colours):
    """One row of the face, left to right as you look at it."""
    for x, name in zip(range(3, 7), colours):
        v[(x, 1, k)] = (name, "Face")


def _legs(v, shoe, leg, top_k):
    """Two 2x2 legs — separate bricks, so the seam between them shows —
    on shoes, up to layer *top_k*."""
    for x0, side in ((3, "Left leg"), (5, "Right leg")):
        box(v, x0, x0 + 1, 2, 3, 0, 0, (shoe, side))
        box(v, x0, x0 + 1, 2, 3, 1, top_k, (leg, side))


def lego_man() -> CadNode:
    """A brick-built man in the Minecraft Steve style, 14 bricks tall:
    brown hair, a turquoise shirt with an open collar, blue trousers,
    and a diamond pickaxe in his hand."""
    s = Scene(seed=11)
    z0 = _grass(s)
    skin, hair, shirt = "Nougat", "Dark brown", "Dark turquoise"
    v = {}
    _legs(v, "Dark bluish grey", "Blue", 4)
    box(v, 3, 6, 2, 3, 5, 9, (shirt, "Body"))
    box(v, 4, 5, 2, 2, 9, 9, (skin, "Body"))               # the collar
    for x0 in (1, 7):
        box(v, x0, x0 + 1, 2, 3, 5, 7, (skin, "Arms"))
        box(v, x0, x0 + 1, 2, 3, 8, 9, (shirt, "Arms"))     # sleeves
    box(v, 3, 6, 1, 4, 10, 12, (skin, "Head"))
    box(v, 3, 6, 1, 4, 13, 13, (hair, "Hair"))
    box(v, 3, 6, 4, 4, 10, 12, (hair, "Hair"))             # the back
    for x in (3, 6):
        box(v, x, x, 2, 3, 12, 12, (hair, "Hair"))         # over the ears
    _face(v, 12, [hair] * 4)
    _face(v, 11, ["White", "Blue", "Blue", "White"])
    _face(v, 10, [skin, "Reddish brown", "Reddish brown", skin])
    # a diamond pickaxe, its handle just in front of the hand; the head
    # sits against the bare forearm (at the sleeve its azure vanished
    # into the turquoise shirt)
    box(v, 8, 8, 1, 1, 2, 6, ("Reddish brown", "Pickaxe"))
    box(v, 6, 9, 1, 1, 7, 7, ("Medium azure", "Pickaxe"))
    v[(6, 1, 6)] = v[(9, 1, 6)] = ("Medium azure", "Pickaxe")
    s.add_voxels(v, z0=z0)
    return _root(s.to_node("Man"))


def lego_woman() -> CadNode:
    """A brick-built woman in the Minecraft Alex style: long orange hair
    down her back and over her shoulders, a side-swept fringe, green
    eyes, a green top, a flared lavender skirt and brown boots."""
    s = Scene(seed=12)
    z0 = _grass(s)
    skin, hair, top = "Light nougat", "Orange", "Bright green"
    v = {}
    _legs(v, "Reddish brown", skin, 2)
    box(v, 2, 7, 1, 4, 3, 3, ("Medium lavender", "Skirt"))  # flared hem
    box(v, 3, 6, 1, 4, 4, 4, ("Medium lavender", "Skirt"))
    box(v, 3, 6, 2, 3, 5, 9, (top, "Body"))
    box(v, 4, 5, 2, 2, 9, 9, (skin, "Body"))               # the neckline
    for x in (2, 7):                                        # slim arms
        box(v, x, x, 2, 3, 5, 7, (skin, "Arms"))
        box(v, x, x, 2, 3, 8, 9, (top, "Arms"))
    box(v, 3, 6, 1, 4, 10, 12, (skin, "Head"))
    box(v, 3, 6, 1, 4, 13, 13, (hair, "Hair"))
    box(v, 3, 6, 4, 4, 6, 12, (hair, "Hair"))         # down her back
    for x in (3, 6):
        box(v, x, x, 2, 3, 10, 12, (hair, "Hair"))    # past the ears
        box(v, x, x, 1, 1, 8, 9, (hair, "Hair"))      # over the shoulders
    _face(v, 12, [hair, hair, hair, skin])            # side-swept fringe
    _face(v, 11, ["White", "Green", "Green", "White"])
    _face(v, 10, [skin, "Dark pink", "Dark pink", skin])
    s.add_voxels(v, z0=z0)
    s.add("brick", 5, 2, 1, 1, z0 + 14 * BRICK_H, "Dark pink", "Hair",
          height=PLATE_H)                             # a hair clip
    return _root(s.to_node("Woman"))


# The same two figures at full resolution: ONE stud to a Minecraft
# pixel, so the proportions are the game's own — an 8x8x8 head, an 8x4x12
# body, 4x4x12 arms and legs (a brick layer is 9.6 mm to the stud's 8,
# so they stand a fifth taller) — and the face is 8x8 bricks of pixel
# art instead of 4x4. About 31 cm tall, on an 18x10 patch of grass.

def _paint(v, rows, x0, y, k_top, legend, group):
    """Pixel art on the plane y = *y*: *rows* from the top down, one
    character per stud from x = *x0*; "." leaves a cell as it is."""
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            if ch != ".":
                v[(x0 + c, y, k_top - r)] = (legend[ch], group)


def _big_legs(v, shoe, shoe_top, leg, leg_top):
    """Two 4x4 legs, separate bricks so the seam between them shows."""
    for x0, side in ((5, "Left leg"), (9, "Right leg")):
        box(v, x0, x0 + 3, 3, 6, 0, shoe_top, (shoe, side))
        box(v, x0, x0 + 3, 3, 6, shoe_top + 1, leg_top, (leg, side))


MAN_FACE = ["HHHHHHHH",
            "HHHHHHHH",
            "HSSSSSSH",
            "SSSSSSSS",
            "SWESSEWS",
            "SSSNNSSS",
            "SSMMMMSS",
            "SSSSSSSS"]

WOMAN_FACE = ["HHHHHHHH",
              "HHHHHHHH",
              "HHHHHHSH",
              "HHSSSSSH",
              "HWGSSGWH",
              "HSSSSSSH",
              "HSSPPSSH",
              "HSSSSSSH"]

COLLAR = ["..SSSS..",
          "...SS..."]


def lego_man_hd() -> CadNode:
    """The Minecraft-style man at one stud per pixel: an 8x8 pixel-art
    face (hairline, eyes, nose, mouth), a turquoise shirt with an open
    collar, blue trousers, and a diamond pickaxe in front of his hand."""
    s = Scene(seed=21)
    z0 = _grass(s, 18, 10)
    skin, hair, shirt = "Nougat", "Dark brown", "Dark turquoise"
    v = {}
    _big_legs(v, "Dark bluish grey", 1, "Blue", 11)
    box(v, 5, 12, 3, 6, 12, 23, (shirt, "Body"))
    _paint(v, COLLAR, 5, 3, 23, {"S": skin}, "Body")
    for x0 in (1, 13):
        box(v, x0, x0 + 3, 3, 6, 12, 19, (skin, "Arms"))
        box(v, x0, x0 + 3, 3, 6, 20, 23, (shirt, "Arms"))   # sleeves
    box(v, 5, 12, 1, 8, 24, 31, (skin, "Head"))
    box(v, 5, 12, 1, 8, 30, 31, (hair, "Hair"))
    box(v, 5, 12, 5, 8, 26, 29, (hair, "Hair"))    # the back of the head
    for x in (5, 12):
        box(v, x, x, 1, 4, 29, 29, (hair, "Hair"))  # the hairline's sides
    _paint(v, MAN_FACE, 5, 1, 31,
           {"H": hair, "S": skin, "W": "White", "E": "Blue",
            "N": "Medium nougat", "M": "Reddish brown"}, "Face")
    # a diamond pickaxe; the head sits against the bare forearm
    box(v, 2, 2, 2, 2, 8, 17, ("Reddish brown", "Pickaxe"))
    box(v, 0, 4, 2, 2, 18, 18, ("Medium azure", "Pickaxe"))
    v[(0, 2, 17)] = v[(4, 2, 17)] = ("Medium azure", "Pickaxe")
    s.add_voxels(v, z0=z0)
    return _root(s.to_node("Man"))


def lego_woman_hd() -> CadNode:
    """The Minecraft-style woman at one stud per pixel: long streaked
    orange hair framing an 8x8 face and falling down her back and over
    her shoulders, green eyes, a green top with a pink belt, a flared
    lavender skirt, brown boots and a flower clip in her hair."""
    s = Scene(seed=22)
    z0 = _grass(s, 18, 10)
    skin, hair, top = "Light nougat", "Orange", "Bright green"
    streaks = ("Orange",) * 3 + ("Dark orange",)    # 1 in 2 was blotchy
    v = {}
    _big_legs(v, "Reddish brown", 2, skin, 7)
    skirt = ("Medium lavender", "Skirt")
    box(v, 4, 13, 2, 7, 8, 9, skirt)                 # the flared hem
    box(v, 5, 12, 2, 7, 10, 11, skirt)
    box(v, 5, 12, 3, 6, 12, 13, skirt)
    box(v, 5, 12, 3, 6, 14, 14, ("Dark pink", "Body"))     # the belt
    box(v, 5, 12, 3, 6, 15, 23, (top, "Body"))
    _paint(v, COLLAR, 5, 3, 23, {"S": skin}, "Body")
    for x0 in (2, 13):                               # slim, 3-wide arms
        box(v, x0, x0 + 2, 3, 6, 12, 19, (skin, "Arms"))
        box(v, x0, x0 + 2, 3, 6, 20, 23, (top, "Arms"))
    box(v, 5, 12, 1, 8, 24, 31, (skin, "Head"))
    box(v, 5, 12, 1, 8, 30, 31, (streaks, "Hair"))
    box(v, 5, 12, 4, 8, 24, 29, (streaks, "Hair"))   # the back of the head
    for x in (5, 12):
        box(v, x, x, 1, 3, 24, 29, (hair, "Hair"))   # framing the face
    box(v, 5, 12, 7, 8, 16, 23, (streaks, "Hair"))   # down her back
    for x0 in (5, 11):
        box(v, x0, x0 + 1, 2, 2, 19, 23, (hair, "Hair"))   # over the chest
    _paint(v, WOMAN_FACE, 5, 1, 31,
           {"H": hair, "S": skin, "W": "White", "G": "Green",
            "P": "Dark pink"}, "Face")
    s.add_voxels(v, z0=z0)
    top_z = z0 + 32 * BRICK_H                        # a flower hair clip
    s.add("brick", 10, 2, 2, 2, top_z, "Dark pink", "Hair",
          height=PLATE_H)
    s.add("brick", 10, 2, 1, 1, top_z + PLATE_H, "Yellow", "Hair",
          height=PLATE_H)
    return _root(s.to_node("Woman"))


SANDSTONE = ("Tan",) * 3 + ("Dark tan",)
STAINED = ("Trans-red", "Trans-yellow", "Trans-dark blue",
           "Trans-dark blue", "Trans-green")


def gable_roof(s, x0, x1, y0, y1, z, colour, ridge, group="Roof",
               skip=()):
    """A roof with its ridge along X over rows y0..y1 (eaves included,
    an even number of rows): courses of 45° slopes, each stepping in a
    stud onto the stud row of the one below, and ridge tiles on top.
    Returns the number of courses — the gable end under course r spans
    rows y0 + r + 2 .. y1 - r - 2."""
    courses = (y1 - y0 + 1) // 2 - 1
    for r in range(courses):
        for start, n in runs(x0, x1, skip):
            s.add("slope", start, y0 + r, n, 2, z + r * BRICK_H, colour,
                  group, facing="-Y")
            s.add("slope", start, y1 - 1 - r, n, 2, z + r * BRICK_H,
                  colour, group, facing="+Y")
    for start, n in runs(x0, x1, skip):
        s.add("tile", start, y0 + courses, n, 2, z + courses * BRICK_H,
              ridge, group, height=PLATE_H)
    return courses


def lego_church() -> CadNode:
    """A village church: a sandstone nave with stained-glass windows
    and a rose window, a slate roof, and a bell tower with a wooden
    door, an open belfry, a stepped spire and a golden cross; a hedge,
    a path and gravestones round it."""
    s = Scene(seed=31)
    rng = random.Random(31)
    s.add("brick", 0, 0, 32, 20, 0.0, "Green", "Baseplate",
          height=BASEPLATE_H, seg=12)
    z0 = BASEPLATE_H
    wall, base = (SANDSTONE, "Walls"), ("Dark bluish grey", "Foundation")
    slate = "Dark bluish grey"

    def glass(cells):
        for cell in cells:
            v[cell] = (rng.choice(STAINED), "Stained glass")

    v = {}
    # the nave, 18 x 10 studs and eight bricks high
    ring(v, 10, 27, 5, 14, 0, base)
    for k in range(1, 8):
        ring(v, 10, 27, 5, 14, k, wall)
    for x in (12, 16, 20, 24):
        glass((xx, y, k) for xx in (x, x + 1) for y in (5, 14)
              for k in range(2, 7))
    glass((27, y, k) for y in (9, 10) for k in range(2, 7))   # east end
    for r, (g0, g1) in enumerate(((6, 13), (7, 12), (8, 11), (9, 10))):
        for x in (10, 27):
            box(v, x, x, g0, g1, 8 + r, 8 + r, wall)
    glass([(27, y, k) for y in range(8, 12) for k in (8, 9)]
          + [(27, 9, 10), (27, 10, 10)])                       # rose window
    # the bell tower, 6 x 6 and fifteen bricks high
    ring(v, 4, 9, 7, 12, 0, base)
    for k in range(1, 15):
        ring(v, 4, 9, 7, 12, k, wall)
    box(v, 4, 4, 9, 10, 1, 4, ("Reddish brown", "Door"))
    box(v, 4, 4, 9, 10, 5, 5, ("Dark tan", "Door"))           # the lintel
    for k in (7, 8, 11, 12):                                   # slits, belfry
        for cell in ((6, 7), (7, 7), (6, 12), (7, 12)):
            v.pop((*cell, k), None)
    for k in (11, 12):
        for cell in ((4, 9), (4, 10), (9, 9), (9, 10)):
            v.pop((*cell, k), None)
    box(v, 5, 8, 8, 11, 10, 10, (slate, "Belfry"))            # its floor
    box(v, 6, 7, 9, 10, 11, 11, ("Yellow", "Belfry"))          # the bell
    # the churchyard: a hedge along the front
    box(v, 8, 29, 1, 1, 0, 0, (LEAVES, "Churchyard"))
    s.add_voxels(v, z0=z0)

    gable_roof(s, 10, 28, 4, 15, z0 + 8 * BRICK_H, slate, "Black")
    # the spire: a course of slopes on all four sides of the tower, a
    # smaller shaft with its own roof, a slender top and the cross
    zs = z0 + 15 * BRICK_H
    for start, n in runs(4, 9):
        s.add("slope", start, 7, n, 2, zs, slate, "Spire", facing="-Y")
        s.add("slope", start, 11, n, 2, zs, slate, "Spire", facing="+Y")
    s.add("slope", 4, 9, 2, 2, zs, slate, "Spire", facing="-X")
    s.add("slope", 8, 9, 2, 2, zs, slate, "Spire", facing="+X")
    s.add("brick", 6, 9, 2, 2, zs, slate, "Spire")
    shaft = {}
    box(shaft, 5, 8, 8, 11, 0, 3, (SANDSTONE, "Spire"))
    s.add_voxels(shaft, z0=zs + BRICK_H)
    s.add("slope", 5, 8, 4, 2, zs + 5 * BRICK_H, slate, "Spire",
          facing="-Y")
    s.add("slope", 5, 10, 4, 2, zs + 5 * BRICK_H, slate, "Spire",
          facing="+Y")
    top = {}
    box(top, 6, 7, 9, 10, 0, 2, (slate, "Spire"))
    s.add_voxels(top, z0=zs + 6 * BRICK_H)
    zc = zs + 9 * BRICK_H
    gold = "Yellow"
    for k, (i, nx) in enumerate(((6, 1), (6, 1), (5, 3), (6, 1))):
        s.add("brick", i, 9, nx, 1, zc + k * BRICK_H, gold, "Cross")

    for x in (0, 2):
        s.add("tile", x, 9, 2, 2, z0, "Dark tan", "Path", height=PLATE_H)
    for x in (13, 17, 21, 25):                                # gravestones
        s.add("brick", x, 17, 2, 1, z0, "Light bluish grey", "Churchyard")
        s.add("tile", x, 17, 2, 1, z0 + BRICK_H, "Light bluish grey",
              "Churchyard", height=PLATE_H)
    return _root(s.to_node("Church"))


def _car(s, i, j, body):
    """A little car four studs long on X, on the road at (i, j): black
    wheels two plates high, a chassis, the body, a clear cabin and a
    roof."""
    z = BASEPLATE_H
    for di in (0, 3):
        for dj in (0, 1):
            s.add("brick", i + di, j + dj, 1, 1, z, "Black", "Cars",
                  height=2 * PLATE_H)
    z += 2 * PLATE_H
    s.add("brick", i, j, 4, 2, z, "Dark bluish grey", "Cars",
          height=PLATE_H)
    s.add("brick", i, j, 4, 2, z + PLATE_H, body, "Cars")
    s.add("brick", i + 1, j, 2, 2, z + PLATE_H + BRICK_H, "Trans-clear",
          "Cars")
    s.add("brick", i + 1, j, 2, 2, z + PLATE_H + 2 * BRICK_H, body,
          "Cars", height=PLATE_H)


def lego_building() -> CadNode:
    """A seven-storey block on a city street: a glass lobby with doors
    under a canopy, six floors of white bands and blue glass between
    pillars (floors inside, seen through the glass), a roof with a
    parapet, air conditioners, a water tank and an antenna; sidewalks
    with trees and lamps, a road with lane markings and two cars."""
    s = Scene(seed=41)
    s.add("brick", 0, 0, 24, 18, 0.0, "Dark bluish grey", "Street",
          height=BASEPLATE_H, seg=12)
    z0 = BASEPLATE_H
    x0, x1, y0, y1 = 8, 17, 6, 13                     # the block
    walk = {(i, j, 0): ("Light bluish grey", "Sidewalk")
            for i in range(6, 20) for j in range(4, 16)
            if not (x0 <= i <= x1 and y0 <= j <= y1)}
    s.add_voxels(walk, z0=z0, height=PLATE_H, kind="tile")
    for i in range(1, 23, 4):                         # the lane markings
        s.add("tile", i, 2, 2, 1, z0, "White", "Road", height=PLATE_H)

    v = {}
    for k in range(4):                                # the glass lobby
        ring(v, x0, x1, y0, y1, k, ("Trans-clear", "Lobby"))
        for corner in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
            v[(*corner, k)] = ("Dark bluish grey", "Lobby")
    for k in range(3):                                # the door frame
        for i in (11, 14):
            v[(i, y0, k)] = ("Black", "Entrance")
    box(v, 11, 14, y0, y0, 3, 3, ("Black", "Entrance"))
    glass, band = ("Trans-light blue", "Windows"), ("White", "Floors")
    for floor in range(6):
        kb = 4 + 3 * floor
        box(v, x0, x1, y0, y1, kb, kb, band)
        for k in (kb + 1, kb + 2):
            ring(v, x0, x1, y0, y1, k, glass)
            for i in (8, 11, 14, 17):
                v[(i, y0, k)] = v[(i, y1, k)] = band
            for j in (6, 9, 10, 13):
                v[(x0, j, k)] = v[(x1, j, k)] = band
        # a smooth floor inside: the slab's studs would show through
        # the glass, six hundred of them
        inside = {(i, j, 0): ("Light bluish grey", "Floors")
                  for i in range(x0 + 1, x1) for j in range(y0 + 1, y1)}
        s.add_voxels(inside, z0=z0 + (kb + 1) * BRICK_H, height=PLATE_H,
                     kind="tile")
    kr = 22
    box(v, x0, x1, y0, y1, kr, kr, ("Light bluish grey", "Roof"))
    ring(v, x0, x1, y0, y1, kr + 1, ("White", "Roof"))
    box(v, 10, 11, 8, 9, kr + 1, kr + 1, ("Light bluish grey", "Rooftop"))
    box(v, 13, 14, 8, 9, kr + 1, kr + 1, ("Light bluish grey", "Rooftop"))
    box(v, 14, 15, 10, 11, kr + 1, kr + 3, ("Reddish brown", "Rooftop"))
    box(v, 10, 10, 11, 11, kr + 1, kr + 5, ("Black", "Antenna"))
    s.add_voxels(v, z0=z0)
    s.add("brick", 10, 11, 1, 1, z0 + (kr + 6) * BRICK_H, "Trans-red",
          "Antenna", height=PLATE_H)
    s.add("brick", 11, 5, 4, 1, z0 + 3 * BRICK_H, "Black", "Entrance",
          height=PLATE_H)                             # the canopy

    street, zw = {}, z0 + PLATE_H                     # on the sidewalk
    for t in (6, 19):
        box(street, t, t, 5, 5, 0, 1, ("Reddish brown", "Trees"))
        box(street, t - 1, t + 1, 4, 6, 2, 2, (LEAVES, "Trees"))
        box(street, t, t, 5, 5, 3, 3, (LEAVES, "Trees"))
    for t in (10, 15):
        box(street, t, t, 4, 4, 0, 3, ("Black", "Lamps"))
    s.add_voxels(street, z0=zw)
    for t in (10, 15):
        s.add("brick", t, 4, 1, 1, zw + 4 * BRICK_H, "Trans-yellow",
              "Lamps", height=PLATE_H)
    _car(s, 1, 0, "Red")
    _car(s, 18, 0, "Blue")
    return _root(s.to_node("Apartment building"))


# Sculpting in bricks: shapes are given in millimetres and every cell
# whose centre falls inside becomes a voxel, so a curved body comes out
# terraced the way a real brick-built creature does.

def blob(v, centre, radii, paint):
    """Fill the ellipsoid at *centre* with semi-axes *radii* (mm);
    *paint(x, y, z)* gives each cell its (colour, group)."""
    cx, cy, cz = centre
    rx, ry, rz = radii
    for i in range(math.floor((cx - rx) / PITCH),
                   math.floor((cx + rx) / PITCH) + 1):
        x = (i + 0.5) * PITCH
        for j in range(math.floor((cy - ry) / PITCH),
                       math.floor((cy + ry) / PITCH) + 1):
            y = (j + 0.5) * PITCH
            for k in range(max(0, math.floor((cz - rz) / BRICK_H)),
                           math.floor((cz + rz) / BRICK_H) + 1):
                z = (k + 0.5) * BRICK_H
                if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 \
                        + ((z - cz) / rz) ** 2 <= 1.0:
                    v[(i, j, k)] = paint(x, y, z)


def sweep(v, path, radii, paint, step=4.0):
    """Spheres swept along the polyline *path* (mm), the radius running
    through *radii*; *paint(x, y, z, centre, r)*."""
    for (a, ra), (b, rb) in zip(zip(path, radii),
                                zip(path[1:], radii[1:])):
        n = max(1, int(math.dist(a, b) / step))
        for t in range(n + 1):
            f = t / n
            c = tuple(p + (q - p) * f for p, q in zip(a, b))
            r = ra + (rb - ra) * f
            blob(v, c, (r, r, r),
                 lambda x, y, z, c=c, r=r: paint(x, y, z, c, r))


def box_mm(v, x0, x1, y0, y1, z0, z1, value):
    """The cells whose centres lie in a box given in mm."""
    for i in range(math.floor(x0 / PITCH), math.ceil(x1 / PITCH) + 1):
        x = (i + 0.5) * PITCH
        for j in range(math.floor(y0 / PITCH), math.ceil(y1 / PITCH) + 1):
            y = (j + 0.5) * PITCH
            for k in range(max(0, math.floor(z0 / BRICK_H)),
                           math.ceil(z1 / BRICK_H) + 1):
                z = (k + 0.5) * BRICK_H
                if x0 <= x <= x1 and y0 <= y <= y1 and z0 <= z <= z1:
                    v[(i, j, k)] = value


RED_SCALES = ("Red",) * 3 + ("Dark red",)


def lego_dragon() -> CadNode:
    """A red dragon breathing fire, sculpted in bricks: a tan belly,
    a long neck and tail, horns, yellow eyes, an open jaw with teeth,
    spikes down its back, four clawed legs, wings of smooth tiles with
    red ribs, and a cone of flame in clear yellow, orange and red."""
    s = Scene(seed=51)
    rng = random.Random(51)
    body = RED_SCALES

    def scales(x, y, z, c, r):
        belly = z < c[2] - 0.45 * r and abs(y) < 0.8 * r
        return ("Tan", "Belly") if belly else (body, "Body")

    v = {}
    blob(v, (0, 0, 95), (56, 32, 38),
         lambda x, y, z: scales(x, y, z, (0, 0, 95), 38))
    sweep(v, [(40, 0, 110), (70, 0, 145), (92, 0, 178)], [24, 20, 17],
          scales)                                                 # neck
    sweep(v, [(-50, 0, 90), (-95, 0, 65), (-140, 0, 42), (-185, 0, 28),
              (-222, 14, 30)], [26, 20, 14, 9, 6], scales)         # tail
    blob(v, (-230, 18, 32), (10, 10, 7),
         lambda x, y, z: ("Dark red", "Tail"))                    # its tip
    for lx in (32, -38):
        for ly in (-26, 26):
            blob(v, (lx, ly, 72), (18, 14, 22),
                 lambda x, y, z: (body, "Legs"))
            box_mm(v, lx - 8, lx + 8, ly - 8, ly + 8, 0, 62, (body, "Legs"))
            box_mm(v, lx - 12, lx + 14, ly - 12, ly + 12, 0, 9,
                   (body, "Legs"))
            box_mm(v, lx + 14, lx + 26, ly - 8, ly + 8, 0, 9,
                   ("White", "Claws"))
    # the head: a skull, a snout, and a lower jaw hanging open a brick
    blob(v, (105, 0, 190), (24, 19, 20), lambda x, y, z: (body, "Head"))
    box_mm(v, 112, 150, -12, 12, 172, 192, (body, "Head"))
    box_mm(v, 104, 142, -10, 10, 146, 163, (body, "Jaw"))
    box_mm(v, 104, 116, -10, 10, 146, 180, (body, "Jaw"))       # the hinge
    for i in (15, 17):
        for j in (-2, 1):
            v[(i, j, 17)] = ("White", "Teeth")
    for j in (-3, 2):
        v[(13, j, 20)] = ("Yellow", "Eyes")
    for j in (-2, 1):
        v[(18, j, 19)] = ("Black", "Head")                      # nostrils
        for step in range(4):                                   # horns
            v[(math.floor((92 - 7 * step) / PITCH), j, 21 + step)] = \
                ("Tan", "Horns")
    # spikes down the back, from the neck to the tail
    for i in range(-26, 11, 2):
        tops = [k for (ci, cj, k) in v if ci == i and cj in (-1, 0)]
        if tops:
            top = max(tops) + 1
            v[(i, -1, top)] = v[(i, 0, top)] = ("Tan", "Spikes")
    # the flame: a cone out of the mouth, ragged at its edge — a solid
    # yellow and orange core under a clear orange skin (all see-through,
    # it read as a pale pink block)
    for i in range(14, 19):
        for j in (-1, 0):
            v[(i, j, 17)] = ("Orange", "Fire")
    for i in range(19, 29):
        x = (i + 0.5) * PITCH
        r = 6 + 0.25 * (x - 150)
        for j in range(math.floor(-r / PITCH), math.floor(r / PITCH) + 1):
            y = (j + 0.5) * PITCH
            for k in range(max(0, math.floor((167 - r) / BRICK_H)),
                           math.floor((167 + r) / BRICK_H) + 1):
                d = math.hypot(y, ((k + 0.5) * BRICK_H - 167) * 0.9)
                if d <= r * (0.85 + 0.3 * rng.random()):
                    f = d / r
                    v[(i, j, k)] = ("Yellow" if f < 0.45 else
                                    "Orange" if f < 0.8 else
                                    "Trans-orange", "Fire")
    s.add_voxels(v)

    # the wings: smooth tiles rising steeply from the shoulders in a V
    # (flatter and smaller, they vanished edge-on in a side view),
    # scalloped at the trailing edge, a red bone along the front and
    # ribs; three plates thick so the steps between rows close up
    wing = {}
    for j in range(-28, 28):
        y = (j + 0.5) * PITCH
        out = abs(y) - 32
        if out < 0:
            continue
        lead = 55 - 0.2 * out
        trail = -75 + 0.5 * out + 14 * abs(math.sin(out / 30.0))
        if trail >= lead - PITCH:
            continue
        kp = math.floor((110 + 0.9 * out) / PLATE_H)
        for i in range(math.floor(trail / PITCH), math.floor(lead / PITCH) + 1):
            x = (i + 0.5) * PITCH
            if trail <= x <= lead:
                rib = int(out) % 48 < 8 or x > lead - PITCH
                value = ("Red" if rib else "Dark red", "Wings")
                for dk in range(3):
                    wing[(i, j, kp - dk)] = value
    s.add_voxels(wing, height=PLATE_H, kind="tile")
    return _root(s.to_node("Dragon"))


EXAMPLES.extend([
    ("Minecraft tower", "Lego", lego_minecraft_tower),
    ("House", "Lego", lego_house),
    ("Church", "Lego", lego_church),
    ("Apartment building", "Lego", lego_building),
    ("Dragon", "Lego", lego_dragon),
    ("Man (Minecraft style)", "Lego", lego_man_hd),
    ("Woman (Minecraft style)", "Lego", lego_woman_hd),
    ("Man (Minecraft style, small)", "Lego", lego_man),
    ("Woman (Minecraft style, small)", "Lego", lego_woman),
])
