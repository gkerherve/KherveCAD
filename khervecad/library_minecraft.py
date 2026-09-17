"""Minecraft characters and mobs for the parts library: Steve, Alex,
Zombie, Skeleton, Wither skeleton, Creeper, Enderman, Witch, Piglin,
Spider, Iron golem, Snow golem, Slime, Ghast, Blaze, Chicken, Sheep,
Bee and Axolotl.

Each is built in Minecraft PIXELS (a block is 16) at the game's own
proportions — the 8x8x8 head, 8x4x12 body, 4x4x12 limbs — and scaled by
the size's pixel length. Every body part wears a SKIN like the game's
textures (`Skin`): each pixel of each face is either a letter of pixel
art (a face, hair, a sleeve, a shoe) or a seeded shade of the base
colour, so a creeper is mottled and a golem cracked all the way round.
A pixel that differs from the base is a thin tile standing `TILE`
proud of the box; tiles are merged along their row and written, with
the box, into one polyhedron per colour (`landmark_kit.Kit`), so a
figure is a few dozen nodes rather than thousands of cubes. A part may
be turned about a pivot (a zombie's arms, a ghast's tentacles) — its
corners are rotated before the piece is written, so the skin turns
with it.

Nothing is booleaned; every mob faces -Y and stands on z = 0.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import zlib

from .landmark_kit import BOX_TRIS, Kit
from .library_home import _box
from .library_room import _dims
from .model import CadNode

CATEGORY = "Minecraft"

#: how far a skin pixel stands proud of its box, in pixels
TILE = 0.1
#: the preview material of the blocky skin, and of anything that glows
MAT = "Default"
GLOW = "Emissive"


# ----------------------------------------------------------------- maths

def _rotation(angles):
    """OpenSCAD's rotate([x, y, z]) as a 3x3 matrix (x first)."""
    ax, ay, az = (math.radians(a) for a in angles)
    cx, sx = math.cos(ax), math.sin(ax)
    cy, sy = math.cos(ay), math.sin(ay)
    cz, sz = math.cos(az), math.sin(az)
    rx = ((1, 0, 0), (0, cx, -sx), (0, sx, cx))
    ry = ((cy, 0, sy), (0, 1, 0), (-sy, 0, cy))
    rz = ((cz, -sz, 0), (sz, cz, 0), (0, 0, 1))

    def mul(a, b):
        return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3))
                           for j in range(3)) for i in range(3))
    return mul(rz, mul(ry, rx))


def _hash(*key):
    """A steady 0..1 from any key — the skins never flicker."""
    return zlib.crc32(repr(key).encode()) / 0xFFFFFFFF


def mirror(rows):
    return [r[::-1] for r in rows]


def rows_of(char, n, cols):
    return [char * cols] * n


# ------------------------------------------------------------------ skins

class Skin:
    """How a part's pixels are coloured: a *base* colour, seeded
    *shades* sprinkled at *density*, and *art* per face — rows of
    letters top down looked up in *palette* ('.' falls back to the
    shading). Faces: front (-Y), back, left (+X, the mob's left, column
    0 at the front), right (-X, column 0 at the back), top (row 0 at
    the back), bottom; 'sides' stands for the four vertical faces and
    'all' for every one. A face's art may also be a callable
    (i, j, rows, cols) -> letter, for stripes and cracks."""

    def __init__(self, base, shades=(), density=0.35, palette=None,
                 seed=0, **art):
        self.base, self.shades, self.density = base, tuple(shades), density
        self.palette = palette or {}
        self.seed = seed
        self.art = art

    def with_art(self, **art):
        merged = dict(self.art)
        merged.update(art)
        return Skin(self.base, self.shades, self.density, self.palette,
                    self.seed, **merged)

    def pixel(self, face, i, j, rows, cols, key):
        art = self.art.get(face)
        if art is None and face not in ("top", "bottom"):
            art = self.art.get("sides")
        if art is None:
            art = self.art.get("all")
        ch = None
        if callable(art):
            ch = art(i, j, rows, cols)
        elif art and i < len(art) and j < len(art[i]):
            ch = art[i][j]
        if ch and ch != ".":
            return self.palette[ch]
        if self.shades and face != "bottom" and \
                _hash(self.seed, key, face, i, j) < self.density:
            k = int(_hash(key, face, j, i, self.seed) * len(self.shades))
            return self.shades[min(k, len(self.shades) - 1)]
        return self.base


def _split(entry):
    """A palette entry is a colour, or (colour, material)."""
    return entry if isinstance(entry, tuple) else (entry, MAT)


class _Mob:
    """A figure in pixels: skinned parts gathered under one group."""

    def __init__(self, name):
        self.root = CadNode("union", name)
        self.extra = Kit()

    def part(self, name, x, y, z, w, d, h, skin, pivot=None,
             angles=(0, 0, 0)):
        """A skinned box from its low corner, optionally turned by
        *angles* about *pivot*."""
        kit = Kit()
        rot = _rotation(angles) if any(angles) else None
        pv = pivot or (0.0, 0.0, 0.0)

        def place(pts):
            if rot is None:
                return pts
            out = []
            for p in pts:
                q = [p[k] - pv[k] for k in range(3)]
                out.append(tuple(pv[r] + sum(rot[r][k] * q[k]
                                             for k in range(3))
                                 for r in range(3)))
            return out

        def cube(x0, y0, z0, x1, y1, z1, entry):
            colour, material = _split(entry)
            pts = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                   (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
            kit.mesh(colour, material).convex(place(pts), BOX_TRIS)

        cube(x, y, z, x + w, y + d, z + h, skin.base)
        t = TILE
        nx, ny, nz = (max(1, round(v)) for v in (w, d, h))
        sx, sy, sz = w / nx, d / ny, h / nz
        # each face: how many rows and columns of pixels, and the tile
        # covering pixels j = a .. b - 1 of row i
        faces = {
            "front": (nz, nx, lambda i, a, b: (
                x + a * sx, y - t, z + h - (i + 1) * sz,
                x + b * sx, y, z + h - i * sz)),
            "back": (nz, nx, lambda i, a, b: (
                x + w - b * sx, y + d, z + h - (i + 1) * sz,
                x + w - a * sx, y + d + t, z + h - i * sz)),
            "left": (nz, ny, lambda i, a, b: (
                x + w, y + a * sy, z + h - (i + 1) * sz,
                x + w + t, y + b * sy, z + h - i * sz)),
            "right": (nz, ny, lambda i, a, b: (
                x - t, y + d - b * sy, z + h - (i + 1) * sz,
                x, y + d - a * sy, z + h - i * sz)),
            "top": (ny, nx, lambda i, a, b: (
                x + a * sx, y + d - (i + 1) * sy, z + h,
                x + b * sx, y + d - i * sy, z + h + t)),
            "bottom": (ny, nx, lambda i, a, b: (
                x + a * sx, y + i * sy, z - t,
                x + b * sx, y + (i + 1) * sy, z)),
        }
        for face, (rows, cols, corners) in faces.items():
            for i in range(rows):
                j = 0
                while j < cols:
                    c = skin.pixel(face, i, j, rows, cols, name)
                    k = j + 1
                    while k < cols and \
                            skin.pixel(face, i, k, rows, cols, name) == c:
                        k += 1
                    if c != skin.base:
                        cube(*corners(i, j, k), c)
                    j = k
        self.root.add(kit.node(name))

    def glass(self, name, x, y, z, w, d, h, colour, alpha):
        """A see-through piece (slime, wings, a blaze's smoke)."""
        self.root.add(_box(name, x, y, z, w, d, h, colour, alpha=alpha))

    def build(self, px):
        node = self.extra.node("Details")
        if node.children:
            self.root.add(node)
        wrap = CadNode("scale", self.root.name, dict(x=px, y=px, z=px))
        wrap.add(self.root)
        return wrap


# ------------------------------------------------------------ the players

def _limbs(m, skin_leg, skin_arm, arm_w=4, arm_angles=((0, 0, 0),) * 2):
    """Player legs and arms around the 8x4x12 torso."""
    m.part("Left leg", 0, -2, 0, 4, 4, 12, skin_leg)
    m.part("Right leg", -4, -2, 0, 4, 4, 12, skin_leg)
    for (side, x), ang in zip((("Left arm", 4), ("Right arm", -4 - arm_w)),
                              arm_angles):
        m.part(side, x, -2, 12, arm_w, 4, 12, skin_arm,
               pivot=(x + arm_w / 2, 0, 22), angles=ang)


def steve():
    m = _Mob("Steve")
    pal = dict(H="#2f1f0f", h="#3d2812", S="#b98a6c", s="#aa7d5e",
               W="#ffffff", B="#523d89", N="#8f5e40", M="#6a4030",
               C="#00a8a8", c="#009090", G="#5f5f5f", g="#4c4c4c")
    hair_side = ["HHHHHHHH", "HHHHHHHH", "sSSSHHHH", "SSSSSHHH",
                 "SSSSSSHH", "SSSSSSSH", "SSSSSSSS", "SSSSSSSS"]
    head = Skin("#b98a6c", ("#aa7d5e", "#c4957a"), 0.12, pal, 1,
                front=["HHHHHHHH", "HHHHHHHH", "HSSSSSSH", "SSSSSSSS",
                       "SWBSSBWS", "SSSNNSSS", "SSMSSMSS", "SSMMMMSS"],
                left=hair_side, right=mirror(hair_side),
                back=rows_of("H", 7, 8) + ["hHHhHHhH"],
                top=rows_of("H", 8, 8))
    shirt = Skin("#00a8a8", ("#009c9c", "#00b4b4"), 0.25, pal, 2,
                 front=["CCCSSCCC", "CCCCSCCC"])
    arm = Skin("#b98a6c", ("#aa7d5e",), 0.15, pal, 3,
               sides=rows_of("C", 4, 4) + ["cccc"], top=rows_of("C", 4, 4))
    leg = Skin("#3b3a9a", ("#34338f", "#4241a6"), 0.3, pal, 4,
               sides=["." * 4] * 10 + ["GGGG", "gGgG"])
    m.part("Head", -4, -4, 24, 8, 8, 8, head)
    m.part("Body", -4, -2, 12, 8, 4, 12, shirt)
    _limbs(m, leg, arm)
    return m


def alex():
    m = _Mob("Alex")
    pal = dict(H="#e37b1d", h="#c9650f", S="#f2c9a2", W="#ffffff",
               E="#3b8526", M="#d99e80", T="#6aa84f", t="#5a9540",
               B="#4a3526")
    hair_side = ["HHHHHHHH", "HHHHHHHH", "SSHHHHHH", "SSSHHHHH",
                 "SSSSHHHH", "SSSSHHHH", "SSSSSHHH", "SSSSSHHH"]
    head = Skin("#f2c9a2", ("#ebbf97",), 0.1, pal, 5,
                front=["HHHHHHHH", "HHHHHHHH", "HHHhSSSH", "HSSSSSSH",
                       "HWESSEWH", "HSSSSSSH", "SSSMMSSS", "SSSSSSSS"],
                left=hair_side, right=mirror(hair_side),
                back=rows_of("H", 8, 8), top=rows_of("H", 8, 8))
    tunic = Skin("#6aa84f", ("#5f9a46", "#76b45a"), 0.3, pal, 6,
                 front=["TTSSSSTT", "TTTSSTTT"])
    arm = Skin("#f2c9a2", ("#ebbf97",), 0.1, pal, 7,
               sides=rows_of("T", 4, 3) + ["ttt"], top=rows_of("T", 3, 3))
    leg = Skin("#6b4a2a", ("#5f4124", "#775333"), 0.3, pal, 8,
               sides=["." * 4] * 9 + ["BBBB"] * 3)
    m.part("Head", -4, -4, 24, 8, 8, 8, head)
    m.part("Hair at the back", -4, 4, 20, 8, 1, 6,
           Skin("#e37b1d", ("#c9650f", "#f08a2a"), 0.4, pal, 9))
    m.part("Body", -4, -2, 12, 8, 4, 12, tunic)
    _limbs(m, leg, arm, arm_w=3)
    return m


# ------------------------------------------------------------ the undead

def zombie():
    m = _Mob("Zombie")
    pal = dict(S="#52803a", D="#3a5e27", K="#0d1a09", N="#35561f",
               M="#27411a", C="#00a3a3")
    head = Skin("#52803a", ("#476f32", "#5d9043", "#3f6a2c"), 0.35, pal,
                11, front=["DDSDDDSD", "SDSSSDSS", "SSSSSSSS", "SKKSSKKS",
                           "SSSNNSSS", "SSSSSSSS", "SSMMMMSS", "SSSSSSSS"],
                top=lambda i, j, r, c: "D" if (i * 3 + j) % 4 else ".")
    shirt = Skin("#00a3a3", ("#009090", "#00b0b0"), 0.3, pal, 12,
                 front=["CCCSSCCC"] + ["." * 8] * 9 +
                 ["CSCCSSCC", "SSCSSSCS"],
                 back=["." * 8] * 10 + ["CCSCCCSC", "SCSSCSSS"])
    arm = Skin("#52803a", ("#476f32", "#5d9043"), 0.35, pal, 13,
               sides=rows_of("C", 3, 4) + ["CSCS"], top=rows_of("C", 4, 4))
    leg = Skin("#3b3a9a", ("#34338f", "#4241a6"), 0.3, pal, 14,
               sides=["." * 4] * 10 + ["SSSS", "SSSS"])
    m.part("Head", -4, -4, 24, 8, 8, 8, head)
    m.part("Body", -4, -2, 12, 8, 4, 12, shirt)
    _limbs(m, leg, arm, arm_angles=((-90, 0, 0), (-90, 0, 0)))
    return m


def _skeleton(name, bone, shades, dark, weapon, seed):
    """A skeleton's rib cage and skull; *weapon* is its pose."""
    m = _Mob(name)
    pal = dict(K=dark, T=shades[-1])
    head = Skin(bone, shades, 0.3, pal, seed,
                front=["........", "........", "........", ".KK..KK.",
                       ".KK..KK.", "...KK...", ".KTKTKT.", "........"])
    bones = Skin(bone, shades, 0.3, pal, seed + 1)
    m.part("Head", -4, -4, 24, 8, 8, 8, head)
    m.part("Left leg", 1, -1, 0, 2, 2, 12, bones)
    m.part("Right leg", -3, -1, 0, 2, 2, 12, bones)
    m.part("Pelvis", -4, -1.5, 12, 8, 3, 2, bones)
    m.part("Spine", -1, -1, 14, 2, 2, 10, bones)
    for k in range(4):
        m.part(f"Rib {k + 1}", -4, -2, 15 + 2.2 * k, 8, 4, 1, bones)
    m.part("Shoulders", -4, -2, 23, 8, 4, 1, bones)
    if weapon == "bow":
        m.part("Left arm", 4, -1, 12, 2, 2, 12, bones, pivot=(5, 0, 22),
               angles=(-90, 0, 0))
        m.part("Right arm", -6, -1, 12, 2, 2, 12, bones,
               pivot=(-5, 0, 22), angles=(-90, 0, -20))
        arc = [(5, -10 - 2.5 * math.cos(math.radians(a)),
                22 + 8 * math.sin(math.radians(a)))
               for a in range(-70, 71, 14)]
        m.extra.path(arc, 0.5, "#6b4a2a", MAT, sides=4)       # the bow
        m.extra.path([arc[0], (5, -6.5, 22), arc[-1]], 0.15, "#e6e6e6",
                     MAT, sides=4)                            # the string
        m.extra.path([(5, -6.5, 22), (5, -17, 22)], 0.2, "#8a6a42", MAT,
                     sides=4)                                 # the arrow
        m.extra.box(4.6, -18.5, 21.6, 5.4, -16.8, 22.4, "#9a9a9a", MAT)
    else:
        m.part("Left arm", 4, -1, 12, 2, 2, 12, bones)
        m.part("Right arm", -6, -1, 12, 2, 2, 12, bones,
               pivot=(-5, 0, 22), angles=(-60, 0, 0))
        hand = (-5, -9.5, 17.5)                    # a stone sword, raised
        m.extra.box(hand[0] - 0.6, hand[1] - 0.6, hand[2] - 3,
                    hand[0] + 0.6, hand[1] + 0.6, hand[2] + 1,
                    "#6b4a2a", MAT)
        m.extra.box(hand[0] - 0.5, hand[1] - 2, hand[2] + 1,
                    hand[0] + 0.5, hand[1] + 2, hand[2] + 1.8,
                    "#555555", MAT)
        m.extra.box(hand[0] - 0.4, hand[1] - 1, hand[2] + 1.8,
                    hand[0] + 0.4, hand[1] + 1, hand[2] + 12,
                    "#8d8d8d", MAT)
    return m


def skeleton():
    return _skeleton("Skeleton", "#c9c9c9",
                     ("#b5b5b5", "#d8d8d8", "#a4a4a4"), "#3a3a3a",
                     "bow", 21)


def wither_skeleton():
    """The same bones a fifth taller (2.4 blocks), sword in hand."""
    m = _skeleton("Wither skeleton", "#2b2b2b",
                  ("#222222", "#343434", "#1a1a1a"), "#0a0a0a",
                  "sword", 31)
    tall = CadNode("scale", "Wither skeleton", dict(x=1.2, y=1.2, z=1.2))
    tall.add(m.root)
    m.root = CadNode("union", "Wither skeleton")
    m.root.add(tall)
    return m


# ---------------------------------------------------------------- hostile

def creeper():
    m = _Mob("Creeper")
    pal = dict(K="#0b0b0b", k="#262626")
    skin = Skin("#5fbd4f", ("#3f9b35", "#87d672", "#2c7a26", "#a8e098"),
                0.62, pal, 41)
    m.part("Head", -4, -4, 18, 8, 8, 8, skin.with_art(
        front=["........", "........", ".KK..KK.", ".KkK.KK.",
               "...KK...", "..KkKK..", "..KKKK..", "..K..K.."]))
    m.part("Body", -4, -2, 6, 8, 4, 12, skin)
    for name, x, y in (("Front left foot", 0, -6),
                       ("Front right foot", -4, -6),
                       ("Back left foot", 0, 2), ("Back right foot", -4, 2)):
        m.part(name, x, y, 0, 4, 4, 6,
               skin.with_art(sides=["." * 4] * 5 + ["kkkk"]))
    return m


def enderman():
    m = _Mob("Enderman")
    pal = dict(P=("#e079fa", GLOW), Q=("#cc00fa", GLOW))
    black = Skin("#161616", ("#0e0e0e", "#1e1e1e", "#1a1320"), 0.3, pal, 51)
    m.part("Head", -4, -4, 42, 8, 8, 8, black.with_art(
        front=["........", "........", "........", "........",
               "QPQ..QPQ", "........", "........", "........"]))
    m.part("Jaw", -4, -4, 40.5, 8, 8, 1.5, black)
    m.part("Body", -4, -2, 28, 8, 4, 12, black)
    m.part("Left leg", 1, -1, 0, 2, 2, 28, black)
    m.part("Right leg", -3, -1, 0, 2, 2, 28, black)
    m.part("Left arm", 4, -1, 10, 2, 2, 30, black)
    m.part("Right arm", -6, -1, 10, 2, 2, 30, black)
    for k in range(9):          # the purple particles drifting round it
        a = 2 * math.pi * _hash("end", k)
        r = 6 + 4 * _hash("r", k)
        zc = 6 + 40 * _hash("z", k)
        s = 0.35 + 0.35 * _hash("s", k)
        m.extra.box(r * math.cos(a) - s, r * math.sin(a) - s, zc - s,
                    r * math.cos(a) + s, r * math.sin(a) + s, zc + s,
                    "#b84de0", GLOW)
    return m


def witch():
    m = _Mob("Witch")
    pal = dict(S="#b58a6b", B="#3a2a1c", W="#ffffff", G="#2f8a2f",
               M="#6a4030", r="#32213f", g="#4d7d2e")
    head = Skin("#b58a6b", ("#a97f60", "#c09576"), 0.15, pal, 61,
                front=["SSSSSSSS", "SSSSSSSS", "SSSSSSSS", "SBBBBBBS",
                       "SWGSSGWS", "SSSSSSSS", "SSSSSSSS", "SSSSSSSS",
                       "SSMMMMSS", "SSSSSSSS"])
    robe = Skin("#3e2a52", ("#35234a", "#48325e", "#2e1f40"), 0.35, pal, 62)
    hat = Skin("#1f1427", ("#271a31", "#170f1d"), 0.3, pal, 64)
    m.part("Head", -4, -4, 24, 8, 8, 10, head)
    m.part("Nose", -1, -6, 26, 2, 2, 4,
           Skin("#b58a6b", ("#a97f60",), 0.2, pal, 63))
    m.extra.box(0.5, -6.5, 26.2, 1.3, -5.9, 27.0, "#4e8a3a", MAT)  # wart
    m.part("Robe", -4, -3, 2, 8, 6, 22, robe.with_art(
        sides=["." * 8] * 18 + ["rrrrrrrr"] * 4))
    m.part("Left shoe", 0, -2, 0, 4, 4, 2, Skin("#2a1f18"))
    m.part("Right shoe", -4, -2, 0, 4, 4, 2, Skin("#2a1f18"))
    m.part("Crossed arms", -4, -7, 16, 8, 4, 4, robe)
    for side, x in (("Left upper arm", 4), ("Right upper arm", -8)):
        m.part(side, x, -3, 14, 4, 4, 9, robe,
               pivot=(x + 2, -1, 22), angles=(-40, 0, 0))
    m.part("Hat brim", -5, -5, 34, 10, 10, 1, hat)
    m.part("Hat band", -3.5, -3.5, 35, 7, 7, 3,
           hat.with_art(sides=["." * 7, "ggggggg", "." * 7]))
    m.part("Hat middle", -2.5, -1.5, 38, 5, 5, 3, hat,
           pivot=(0, 0, 38), angles=(-8, 0, 0))
    m.part("Hat top", -1.5, 0.8, 40.5, 3, 3, 2.5, hat,
           pivot=(0, 0, 38), angles=(-18, 0, 0))
    m.part("Hat tip", -0.5, 3.4, 42.4, 1, 1, 2, hat,
           pivot=(0, 0, 38), angles=(-30, 0, 0))
    return m


def piglin():
    m = _Mob("Piglin")
    pal = dict(K="#161010", W="#f1f1f1", N="#8a4a44", Y="#f2c630",
               y="#c99a1a")
    pink = ("#d98a79", "#eeb0a0", "#cf7f6e")
    m.part("Head", -5, -4, 24, 10, 8, 8,
           Skin("#e39d8c", pink, 0.3, pal, 71,
                front=["." * 10] * 3 + [".KW....WK."] + ["." * 10] * 4))
    m.part("Snout", -2, -5, 24.5, 4, 1, 3,
           Skin("#d27f71", pink[:1], 0.1, pal, 72,
                front=["....", "N..N", "...."]))
    m.part("Left tusk", 2.3, -4.8, 23.4, 0.8, 0.8, 1.8, Skin("#f4efdf"))
    m.part("Right tusk", -3.1, -4.8, 23.4, 0.8, 0.8, 1.8, Skin("#f4efdf"))
    for side, x, ang in (("Left ear", 5, 30), ("Right ear", -6, -30)):
        m.part(side, x, -1.5, 25, 1, 5, 5,
               Skin("#d98a79", pink, 0.3, pal, 73),
               pivot=(x + 0.5, 0, 30), angles=(0, ang, 0))
    tunic = Skin("#7a5a2e", ("#6e5028", "#86653a"), 0.35, pal, 74,
                 sides=["." * 8] * 8 + ["YyYYyYYy"] + ["." * 8] * 3)
    arm = Skin("#e39d8c", pink, 0.3, pal, 75)
    leg = Skin("#5a3a1c", ("#4f3218", "#654322"), 0.35, pal, 76,
               sides=["." * 4] * 10 + ["KKKK"] * 2)
    m.part("Body", -4, -2, 12, 8, 4, 12, tunic)
    _limbs(m, leg, arm, arm_angles=((0, 0, 0), (-50, 0, 0)))
    hand = (-6, -9.2, 15.2)                    # a golden sword, raised
    m.extra.box(hand[0] - 0.6, hand[1] - 0.6, hand[2] - 3, hand[0] + 0.6,
                hand[1] + 0.6, hand[2] + 1, "#6b4a2a", MAT)
    m.extra.box(hand[0] - 0.5, hand[1] - 2, hand[2] + 1, hand[0] + 0.5,
                hand[1] + 2, hand[2] + 1.8, "#c99a1a", "Gold")
    m.extra.box(hand[0] - 0.4, hand[1] - 1, hand[2] + 1.8, hand[0] + 0.4,
                hand[1] + 1, hand[2] + 12, "#f2d04a", "Gold")
    return m


# ----------------------------------------------------------- large mobs

def spider():
    m = _Mob("Spider")
    pal = dict(R=("#d01818", GLOW), r=("#8a0f0f", GLOW))
    body = Skin("#342d27", ("#2a241f", "#3d352e", "#4a4038", "#221d19"),
                0.45, pal, 81)
    m.part("Abdomen", -5, 3, 4, 10, 12, 8, body)
    m.part("Thorax", -3, -3, 5, 6, 6, 6, body)
    m.part("Head", -4, -11, 4, 8, 8, 8, body.with_art(
        front=["........", "..r..r..", ".RR..RR.", "R.R..R.R",
               "........", "........", "........", "........"]))
    for k, y in enumerate((-2.5, -0.8, 0.8, 2.5)):
        spread = math.radians((-40, -14, 14, 40)[k])
        for sign in (1, -1):
            dx, dy = sign * math.cos(spread), math.sin(spread)
            hip = (sign * 3, y, 8)
            knee = (hip[0] + dx * 9, hip[1] + dy * 9, 14)
            foot = (hip[0] + dx * 19, hip[1] + dy * 19, 0.65)
            m.extra.path([hip, knee], 1.0, "#2e2823", MAT, sides=4)
            m.extra.path([knee, foot], 0.9, "#3a322c", MAT, sides=4)
    return m


def iron_golem():
    m = _Mob("Iron golem")
    pal = dict(K="#8f877e", k="#a79e94", V="#4c7a24", v="#3a611a",
               R=("#b02020", GLOW), B="#4a4038", F="#c9c0b6")
    iron = ("#c9c0b6", "#e8e2dc", "#b8afa5")

    def cracks(seed):
        return lambda i, j, r, c: ("K" if _hash("crack", seed, i, j) < 0.05
                                   else "k" if _hash("c2", seed, i, j) < 0.06
                                   else ".")

    def vines(i, j, rows, cols):
        if j in (1, 2) and i < rows * 0.7 and _hash("v", i) < 0.8:
            return "V"
        if j in (3, 12) and i % 3 == 0 and i < rows * 0.7:
            return "v"
        if j == 13 and 3 < i < 10:
            return "V"
        return cracks(1)(i, j, rows, cols)

    m.part("Head", -4, -7.5, 33, 8, 10, 10,
           Skin("#dcd4cc", iron, 0.3, pal, 91,
                front=["." * 8] * 3 + ["BBBBBBBB", "FRBFFBRF"] +
                ["." * 8] * 5))
    m.part("Nose", -1, -9.5, 34, 2, 2, 4,
           Skin("#b8afa5", iron, 0.3, pal, 92))
    m.part("Chest", -9, -5.5, 21, 18, 11, 12,
           Skin("#dcd4cc", iron, 0.3, pal, 93, front=vines, all=cracks(2)))
    m.part("Waist", -4.5, -3, 16, 9, 6, 5,
           Skin("#dcd4cc", iron, 0.3, pal, 94, all=cracks(3)))
    arm = Skin("#cfc6bc", iron, 0.35, pal, 95, all=cracks(4))
    m.part("Left arm", 9, -3, 3, 4, 6, 30, arm)
    m.part("Right arm", -13, -3, 3, 4, 6, 30, arm.with_art(
        left=lambda i, j, r, c: "V" if 6 < i < 20 and j == 2 else "."))
    legs = Skin("#dcd4cc", iron, 0.3, pal, 96, all=cracks(5))
    m.part("Left leg", 1, -2.5, 0, 6, 5, 16, legs)
    m.part("Right leg", -7, -2.5, 0, 6, 5, 16, legs.with_art(
        front=lambda i, j, r, c: "v" if j == 1 and i > 6 else "."))
    m.extra.path([(-11, -4, 4), (-11, -8, 7)], 0.2, "#3d7a22", MAT,
                 sides=4)                                    # the poppy
    m.extra.box(-12, -9, 6.5, -10, -7, 8.5, "#d81f1f", MAT)
    m.extra.box(-11.3, -9.2, 7.2, -10.7, -8.9, 7.8, "#1a1a1a", MAT)
    return m


def snow_golem():
    m = _Mob("Snow golem")
    pal = dict(K="#3a1e05", D="#c4750f", Y=("#ffcf4a", GLOW))
    snow = Skin("#f2f6f6", ("#e3eaea", "#ffffff", "#d8e2e2"), 0.3, pal, 101)
    m.part("Lower snowball", -6, -6, 0, 12, 12, 12, snow)
    m.part("Upper snowball", -5, -5, 12, 10, 10, 10, snow)
    pumpkin = Skin("#e3901d", ("#d7841a", "#ef9d2c"), 0.25, pal, 102,
                   sides=lambda i, j, r, c: "D" if j in (1, 4, 6) else ".",
                   top=lambda i, j, r, c: "D" if j in (1, 6) or i in (1, 6)
                   else ".")
    m.part("Pumpkin", -4, -4, 22, 8, 8, 8, pumpkin.with_art(
        front=["D..D..D.", "D..D..D.", "KK.D.KK.", "KY.D.YK.",
               "D..D..D.", "KKKKKKK.", "KYKYKYK.", "D.KD.K.."]))
    m.part("Stalk", -1, -1, 30, 2, 2, 1.5, Skin("#5a7a2a"))
    for sign in (1, -1):                        # the two stick arms
        s0, s1 = (sign * 4.5, 0, 18), (sign * 11, 0, 22)
        m.extra.path([s0, s1], 0.5, "#6b4a2a", MAT, sides=4)
        m.extra.path([s1, (sign * 13, -1.5, 24)], 0.35, "#6b4a2a", MAT,
                     sides=4)
        m.extra.path([s1, (sign * 13, 1.2, 23)], 0.35, "#6b4a2a", MAT,
                     sides=4)
    return m


def slime():
    m = _Mob("Slime")
    pal = dict(K="#1f3d14")
    core = Skin("#5fae3e", ("#539a36", "#6cbf49"), 0.35, pal, 111,
                front=["......", "KK..KK", "KK..KK", "......", "...K..",
                       "......"])
    m.part("Core", -3, -3, 1, 6, 6, 6, core)
    m.glass("Outer jelly", -4, -4, 0, 8, 8, 8, "#7ccf5a", 0.45)
    return m


def ghast():
    m = _Mob("Ghast")
    pal = dict(K="#1c1c1c", G="#9e9e9e", g="#bdbdbd")
    white = ("#e4e4e4", "#fafafa", "#d6d6d6")
    face = ["." * 16] * 4 + [
        "..KK........KK..", "..KK........KK..", "..G..........G..",
        "..g..........G..", "..G.KKKKKKKK.g..", "....KKKKKKKK....",
        "....K......K...."] + ["." * 16] * 5
    m.part("Body", -8, -8, 14, 16, 16, 16,
           Skin("#f0f0f0", white, 0.3, pal, 121, front=face))
    for k, h in enumerate((12, 14, 10, 13, 9, 14, 11, 12, 10)):
        i, j = divmod(k, 3)
        sway = (_hash("sway", k) - 0.5) * 30
        m.part(f"Tentacle {k + 1}", -6 + j * 5, -6 + i * 5, 14 - h,
               2, 2, h, Skin("#f0f0f0", white, 0.3, pal, 122 + k),
               pivot=(-5 + j * 5, -5 + i * 5, 14), angles=(sway, 0, 0))
    return m


def blaze():
    m = _Mob("Blaze")
    pal = dict(K="#3a2508", k="#6a4410", O="#e8901c")
    m.part("Head", -4, -4, 22, 8, 8, 8,
           Skin("#f7d23e", ("#e8b12a", "#fff06a", "#d9901c"), 0.4, pal, 131,
                front=["........", "OOOOOOOO", "........", ".KK..KK.",
                       "........", "..kKKk..", "........", "OOOOOOOO"]))
    m.glass("Smoke", -1.2, -1.2, 0, 2.4, 2.4, 22, "#4a4038", 0.35)
    rod = Skin("#f6a51e", ("#e07c12", "#ffd44d"), 0.4, pal, 132)
    for ring, (r, z, tilt) in enumerate(((7, 13, 4), (6, 7, -3), (5, 1, 2))):
        for k in range(4):
            a = math.radians(90.0 * k + 45 * ring)
            cx, cy = r * math.cos(a), r * math.sin(a)
            m.part(f"Rod {ring + 1}.{k + 1}", cx - 1, cy - 1, z, 2, 2, 8,
                   rod, pivot=(cx, cy, z + 4), angles=(tilt, tilt, 0))
    return m


# ------------------------------------------------------ passive animals

def chicken():
    m = _Mob("Chicken")
    pal = dict(K="#101010")
    feathers = Skin("#f5f5f0", ("#e6e6e0", "#ffffff"), 0.3, pal, 141)
    orange = Skin("#e8a922", ("#d6961a",), 0.2, pal, 142)
    for side, x in (("Left", 0.5), ("Right", -2.5)):
        m.part(f"{side} leg", x + 0.5, -0.5, 0.5, 1, 1, 4.5, orange)
        m.part(f"{side} foot", x - 0.5, -2.5, 0, 3, 3, 0.5, orange)
    m.part("Body", -3, -4, 5, 6, 8, 6, feathers)
    m.part("Tail", -2, 4, 8, 4, 1, 4, feathers)
    m.part("Left wing", 3, -3, 6, 1, 6, 4, feathers)
    m.part("Right wing", -4, -3, 6, 1, 6, 4, feathers)
    m.part("Head", -2, -6, 9, 4, 3, 6, feathers.with_art(
        left=["...", "...", "K..", "...", "...", "..."],
        right=["...", "...", "..K", "...", "...", "..."]))
    m.part("Beak", -1, -7.5, 12, 2, 2, 2, orange)
    m.part("Wattle", -0.5, -7, 10.5, 1, 1, 1.5,
           Skin("#d02020", ("#b81a1a",), 0.3))
    return m


def sheep():
    m = _Mob("Sheep")
    pal = dict(W="#ffffff", K="#101010", N="#e3a2a2", w="#e9e9e9")
    wool = Skin("#e9e9e9", ("#dcdcdc", "#f6f6f6", "#d0d0d0"), 0.55, pal, 151)
    face = Skin("#d8b69c", ("#ccaa90",), 0.2, pal, 152,
                front=["......", "......", "WK..KW", "......", "..NN..",
                       "......"])
    legs = Skin("#d8b69c", ("#ccaa90",), 0.2, pal, 153,
                sides=["wwww"] * 6 + ["." * 4] * 6)
    for name, x, y in (("Front left leg", 0.5, -6),
                       ("Front right leg", -4.5, -6),
                       ("Back left leg", 0.5, 4),
                       ("Back right leg", -4.5, 4)):
        m.part(name, x, y, 0, 4, 4, 12, legs)
    m.part("Body", -5, -8, 11, 10, 18, 9, wool)
    m.part("Head", -3, -14, 15, 6, 8, 6, face)
    m.part("Head wool", -3.5, -12, 15.5, 7, 6, 6, wool)
    return m


def bee():
    m = _Mob("Bee")
    pal = dict(B="#3a2a12", K="#111111", W="#ffffff")

    def stripes(i, j, rows, cols):
        return "B" if (j // 2) % 2 else "."

    m.part("Body", -3.5, -5, 3, 7, 10, 7,
           Skin("#f2c230", ("#e8b420", "#f8d050"), 0.2, pal, 161,
                left=stripes,
                right=lambda i, j, r, c: stripes(i, c - 1 - j, r, c),
                top=lambda i, j, r, c: "B" if ((r - 1 - i) // 2) % 2
                else ".",
                front=[".......", ".......", "WK...KW", "KK...KK",
                       ".......", ".......", "......."],
                back=["BBBBBBB"] * 7))
    m.part("Stinger", -0.5, 5, 5, 1, 1.5, 1, Skin("#bdbdbd"))
    for sign in (1, -1):
        m.extra.path([(sign * 1.5, -5, 9.5), (sign * 2, -7.5, 11)], 0.15,
                     "#3a2a12", MAT, sides=4)                 # antenna
        for k in range(3):                                    # legs
            m.extra.box(sign * 3.5 - 0.3, -3 + 2.5 * k - 0.3, 0,
                        sign * 3.5 + 0.3, -3 + 2.5 * k + 0.3, 3.2,
                        "#3a2a12", MAT)
        x0 = 1.0 if sign > 0 else -6.5
        m.glass("Wing", x0, -3, 10.2, 5.5, 7, 0.3, "#dfefff", 0.4)
    return m


def axolotl():
    m = _Mob("Axolotl")
    pal = dict(K="#1a1a1a", M="#b04d72", G="#d6708f")
    pink = Skin("#f2a6c7", ("#eb97bb", "#f8b8d3"), 0.25, pal, 171)
    gills = Skin("#d6708f", ("#c85e80",), 0.3, pal, 172)
    m.part("Body", -4, -5, 1, 8, 10, 4, pink)
    m.part("Head", -4, -10, 1, 8, 5, 5, pink.with_art(
        front=["........", "K......K", "........", "..MMMM..",
               "........"]))
    m.part("Top gills", -4, -8, 6, 8, 1, 3, gills)
    for sign in (1, -1):
        x = 4 if sign > 0 else -7
        m.part("Side gills", x, -8, 3, 3, 1, 4, gills,
               pivot=(sign * 4, -7.5, 5), angles=(0, 0, sign * -25))
        for y in (-4, 3):
            m.part("Leg", x + (0 if sign > 0 else 1.5), y, 0, 1.5, 1.5,
                   1.5, pink)
    m.part("Tail", -0.5, 5, 1.5, 1, 12, 5, pink.with_art(
        left=["." * 12] + ["...........G"] * 4))
    return m


# ------------------------------------------------------------- registry

MOBS = {
    "mc_steve": ("Steve", steve),
    "mc_alex": ("Alex", alex),
    "mc_zombie": ("Zombie", zombie),
    "mc_skeleton": ("Skeleton", skeleton),
    "mc_wither_skeleton": ("Wither skeleton", wither_skeleton),
    "mc_creeper": ("Creeper", creeper),
    "mc_enderman": ("Enderman", enderman),
    "mc_witch": ("Witch", witch),
    "mc_piglin": ("Piglin", piglin),
    "mc_spider": ("Spider", spider),
    "mc_iron_golem": ("Iron golem", iron_golem),
    "mc_snow_golem": ("Snow golem", snow_golem),
    "mc_slime": ("Slime", slime),
    "mc_ghast": ("Ghast", ghast),
    "mc_blaze": ("Blaze", blaze),
    "mc_chicken": ("Chicken", chicken),
    "mc_sheep": ("Sheep", sheep),
    "mc_bee": ("Bee", bee),
    "mc_axolotl": ("Axolotl", axolotl),
}

SIZES = {"Figure (1 px = 5 mm)": dict(px=5.0),
         "Small (1 px = 2.5 mm)": dict(px=2.5),
         "Large (1 px = 10 mm)": dict(px=10.0),
         "Game size (1 block = 1 m)": dict(px=62.5)}


def _builder(maker):
    def build(dims):
        p = _dims(dims, SIZES)
        return maker().build(float(p["px"]))
    return build


PARTS = {
    part_id: dict(label=label, category=CATEGORY, sizes=SIZES,
                  fields=[("px", "Pixel size")], build=_builder(maker))
    for part_id, (label, maker) in MOBS.items()
}
