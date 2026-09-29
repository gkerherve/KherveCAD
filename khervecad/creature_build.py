"""Monsters and beasts for PlanetCraft, built to walk (Qt-free, 2026-09-29).

The user's question: "I'm still so unsure how to add monsters, create
monsters for PlanetCraft through KherveCAD". A creature PlanetCraft can
make walk has to arrive as NAMED parts — a Head, a Tail, a Left and a Right
wing, and each leg by its end and side (see planetcraft.py) — and nothing
said so, least of all to an assistant building one over MCP. This module
builds creatures that already are: a body plan and a preset (or a handful
of features), and every piece lands in the group the game turns it about.

Body plans:

- ``biped``      troll, ogre, goblin, orc, minotaur, yeti, cyclops — two
                 legs, arms that belong to the body, a head on a neck;
- ``winged``     a biped with a pair of wings: gargoyle, imp;
- ``quadruped``  dire wolf, cave bear, boar, basilisk, and the dragon,
                 which has wings as well;
- ``spider``     eight legs dealt into the game's four joints, two to each;
- ``serpent`` and ``slime`` — no legs; the game bobs them along.

Everything is drawn in solids the built-in tessellator draws exactly —
kcad_ellipsoid, kcad_capsule, cylinders and thin polyhedron plates for a
wing's membrane — never a hull or a boolean, which it only approximates,
because the export to the game tessellates without OpenSCAD.

Conventions (planetcraft.py): Z up, the front facing -Y, +X the
creature's LEFT. Each part is one ``kcad_material() color() { ... }``
block whose label is the part's name ("Head", "Left leg", "Front right
leg", "Tail", "Left wing"); the pieces inside carry plain labels that
never use those words, so nothing inside a part is mistaken for another.
The creature is drawn at a nominal metre and scaled to its height, feet
on z = 0.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
from contextlib import contextmanager

H = 1000.0                      # the nominal height everything is drawn at

PLANS = ("biped", "winged", "quadruped", "spider", "serpent", "slime")
HORNS = ("none", "bull", "ram", "straight", "swept", "nubs")
EARS = ("none", "round", "pointy", "long")
NOSES = ("none", "big", "snout")
# a biped's tail: thin, tuft or spade; a quadruped's: bushy, stub, curly,
# thin or long (and spade_tip=True for a dragon's)
TAILS = ("none", "thin", "tuft", "spade", "bushy", "stub", "curly", "long")
WEAPONS = ("none", "club", "spiked club", "axe", "spear", "dagger")
NATURES = ("auto", "animal", "person", "monster")

#: every colour a creature is painted in, and what each is for
COLOURS = {
    "skin": "the hide, fur or scales",
    "belly": "the belly, chest, face or muzzle",
    "accent": "horns, tusks, claws, teeth and spikes",
    "eyes": "the eyes (drawn Emissive: they glow)",
    "cloth": "a loincloth",
    "wood": "a weapon's haft",
    "metal": "a weapon's head, armour",
    "wing": "a wing's membrane",
    "hair": "a mane, a tuft, bristles",
}

_DEFAULT_COLOURS = dict(skin="#7d8f62", belly="#98a67a", accent="#e9e2c9",
                        eyes="#f4c430", cloth="#6b4a2b", wood="#5a3d22",
                        metal="#6d7076", wing="#5a2a24", hair="#3b2a1e",
                        pupil="#141014", mouth="#3a1818")

# What each plan reads, with its defaults. Lengths are fractions of the
# height; the rest are counts, names or multipliers.
_BIPED = dict(leg=0.40, torso=0.33, bulk=0.30, depth=0.62, belly_size=0.5,
              head=0.15, neck=0.02, hunch=0.0, arm=0.44, arm_r=1.0,
              leg_r=1.0, ears="round", nose="big", horns="none",
              tusks=False, fangs=False, eyes_n=2, eye_size=1.0, brow=True,
              face=False, tail="none", wings=False, wing_span=0.55,
              weapon="none", loincloth=True, spikes=0, claws=True,
              pauldron=False)
_QUAD = dict(leg=0.42, length=1.3, bulk=0.30, body=0.32, neck=0.20,
             neck_up=0.55, head=0.28, snout=0.8, leg_r=1.0, ears="pointy",
             horns="none", tusks=False, fangs=True, eyes_n=2, eye_size=1.0,
             tail="bushy", wings=False, wing_span=1.2, spikes=0, ruff=False,
             claws=True)
_SPIDER = dict(bulk=1.0, eye_size=1.0)
_SERPENT = dict(hood=False, bulk=1.0, eye_size=1.0)
_SLIME = dict(bulk=1.0, eye_size=1.0)
_PLAN_KEYS = dict(biped=_BIPED, winged=dict(_BIPED, wings=True),
                  quadruped=_QUAD, spider=_SPIDER, serpent=_SERPENT,
                  slime=_SLIME)

#: Ready-made creatures: a plan, a real height in mm, the features and
#: colours that make it what it is, and how the game should play it.
PRESETS = {
    "Troll": dict(
        plan="biped", height=2600, blurb="a hunched brute with a club",
        leg=0.36, torso=0.34, bulk=0.34, belly_size=0.6, head=0.14,
        neck=0.0, hunch=0.8, arm=0.56, arm_r=1.25, leg_r=1.3, ears="round",
        nose="big", tusks=True, weapon="club", skin="#7d8f62",
        belly="#98a67a", eyes="#f4c430", speed=0.8, health=40, damage=6,
        nature="monster"),
    "Ogre": dict(
        plan="biped", height=2800, blurb="fat, strong, a spiked club",
        leg=0.36, torso=0.36, bulk=0.42, depth=0.72, belly_size=1.0,
        head=0.15, neck=0.0, hunch=0.3, arm=0.46, arm_r=1.35, leg_r=1.4,
        ears="round", nose="big", tusks=True, weapon="spiked club",
        skin="#c49a72", belly="#d9b089", eyes="#e8502a", cloth="#4a3b2c",
        speed=0.7, health=50, damage=7, nature="monster"),
    "Goblin": dict(
        plan="biped", height=1100, blurb="small, quick, long ears, a knife",
        leg=0.36, torso=0.30, bulk=0.24, belly_size=0.4, head=0.26,
        neck=0.02, hunch=0.5, arm=0.42, ears="long", nose="big",
        fangs=True, weapon="dagger", skin="#6f9a3c", belly="#8fb35a",
        eyes="#ff4a1c", cloth="#5b4636", speed=1.3, health=12, damage=2,
        nature="monster"),
    "Orc": dict(
        plan="biped", height=2000, blurb="a warrior with tusks and an axe",
        leg=0.42, torso=0.33, bulk=0.33, head=0.15, hunch=0.2,
        arm=0.46, arm_r=1.15, leg_r=1.15, ears="pointy", tusks=True,
        weapon="axe", pauldron=True, skin="#4f6b3a", belly="#607d47",
        eyes="#ff3020", cloth="#3b2f28", speed=1.0, health=26, damage=5,
        nature="monster"),
    "Minotaur": dict(
        plan="biped", height=2700, blurb="a bull's head, horns and an axe",
        leg=0.44, torso=0.33, bulk=0.34, head=0.16, hunch=0.2,
        arm=0.46, arm_r=1.2, leg_r=1.2, ears="round", nose="snout",
        horns="bull", tail="tuft", weapon="axe", brow=False,
        skin="#6e4a33", belly="#8c6446", hair="#2e2119", accent="#efe6cf",
        eyes="#ff5a1f", speed=1.1, health=45, damage=7, nature="monster"),
    "Yeti": dict(
        plan="biped", height=2500, blurb="white fur, a blue face",
        leg=0.38, torso=0.36, bulk=0.38, depth=0.7, belly_size=0.6,
        head=0.15, neck=0.0, hunch=0.5, arm=0.52, arm_r=1.4, leg_r=1.4,
        ears="none", nose="none", fangs=True, face=True, loincloth=False,
        skin="#eef0f2", belly="#8aa0b8", eyes="#6ad1ff", speed=1.0,
        health=38, damage=6, nature="monster"),
    "Cyclops": dict(
        plan="biped", height=3200, blurb="one great eye, a club",
        leg=0.40, torso=0.34, bulk=0.34, belly_size=0.7, head=0.15,
        eyes_n=1, eye_size=1.3, horns="straight", nose="big",
        weapon="club", skin="#b89a7c", belly="#caa98a", eyes="#fff4c8",
        speed=0.8, health=55, damage=8, nature="monster"),
    "Gargoyle": dict(
        plan="winged", height=1900, blurb="stone wings, ram's horns",
        leg=0.36, torso=0.34, bulk=0.30, head=0.16, hunch=0.7,
        arm=0.48, ears="pointy", horns="ram", fangs=True, tail="spade",
        wing_span=0.85, loincloth=False, skin="#7f8084", belly="#96979b",
        wing="#5d5e63", accent="#3f4044", eyes="#7cff6b", speed=1.1,
        health=30, damage=5, nature="monster"),
    "Imp": dict(
        plan="winged", height=900, blurb="a little red devil",
        leg=0.38, torso=0.30, bulk=0.26, head=0.24, hunch=0.3,
        arm=0.42, ears="pointy", horns="straight", fangs=True,
        tail="spade", wing_span=0.7, loincloth=False, skin="#b3261e",
        belly="#d0453a", wing="#6d1510", accent="#2a1a18", eyes="#ffd400",
        speed=1.5, health=10, damage=2, nature="monster"),
    "Dragon": dict(
        plan="quadruped", height=3500, blurb="wings, horns, a spade tail",
        leg=0.30, length=1.7, bulk=0.36, body=0.34, neck=0.45,
        neck_up=0.95, head=0.24, snout=1.0, ears="none", horns="swept",
        fangs=True, tail="long", spade_tip=True, wings=True,
        wing_span=1.1, spikes=9,
        skin="#a8261e", belly="#e2b04a", wing="#7a1c16", accent="#f2e6c4",
        eyes="#ffd23f", speed=1.2, health=80, damage=8, nature="monster"),
    "Dire wolf": dict(
        plan="quadruped", height=1300, blurb="red eyes, a ruff, fangs",
        leg=0.46, length=1.25, bulk=0.28, body=0.30, neck=0.22,
        neck_up=0.5, head=0.28, snout=0.9, ears="pointy", fangs=True,
        tail="bushy", ruff=True, skin="#4b4f57", belly="#8a8f98",
        hair="#3a3d44", eyes="#ff3b30", speed=1.6, health=20, damage=4,
        nature="monster"),
    "Cave bear": dict(
        plan="quadruped", height=1800, blurb="huge, clawed, round ears",
        leg=0.34, length=1.2, bulk=0.42, body=0.44, neck=0.12,
        neck_up=0.3, head=0.30, snout=0.55, leg_r=1.5, ears="round",
        fangs=True, tail="stub", skin="#5b3f2a", belly="#7a573c",
        eyes="#2a1a12", speed=1.1, health=45, damage=6, nature="monster"),
    "Boar": dict(
        plan="quadruped", height=1000, blurb="tusks and a bristled back",
        leg=0.36, length=1.3, bulk=0.34, body=0.42, neck=0.08,
        neck_up=0.2, head=0.32, snout=0.8, ears="pointy", tusks=True,
        fangs=False, tail="curly", spikes=7, bristle=True, skin="#5e4636",
        belly="#77604e", hair="#2f231b", eyes="#2a1a12", speed=1.3,
        health=18, damage=3, nature="animal"),
    "Basilisk": dict(
        plan="quadruped", height=1000, blurb="a long lizard with a crest",
        leg=0.26, length=2.0, bulk=0.34, body=0.28, neck=0.22,
        neck_up=0.3, head=0.30, snout=0.9, leg_r=1.1, ears="none",
        horns="nubs", fangs=True, tail="long", spikes=12, skin="#3f6b3a",
        belly="#b3c28a", accent="#d9c36a", eyes="#ffe14a", speed=0.9,
        health=30, damage=5, nature="monster"),
    "Giant spider": dict(
        plan="spider", height=1300, blurb="eight legs, eight eyes",
        skin="#1f1b1d", belly="#2d2729", accent="#c0271f", eyes="#ff2d20",
        speed=1.4, health=22, damage=4, nature="monster"),
    "Serpent": dict(
        plan="serpent", height=1500, blurb="a hooded snake, reared up",
        hood=True, skin="#3d7a3a", belly="#d9cf8a", accent="#c8241c",
        eyes="#ffd400", speed=1.0, health=25, damage=5, nature="monster"),
    "Slime": dict(
        plan="slime", height=1000, blurb="a wobbling green blob",
        skin="#5fd35f", belly="#3fa33f", eyes="#ffffff", speed=0.7,
        health=14, damage=2, nature="monster"),
}


class CreatureError(ValueError):
    """The creature cannot be built (the message says why)."""


# ------------------------------------------------------------ vectors
def _f(v):
    return f"{v:.1f}"


def _v(p):
    return "[" + ", ".join(_f(c) for c in p) + "]"


def _add(a, b, k=1.0):
    return [a[i] + b[i] * k for i in range(3)]


def _sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def _len(a):
    return math.sqrt(sum(c * c for c in a))


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]]


def _norm(a):
    n = _len(a) or 1.0
    return [c / n for c in a]


def _fn(r):
    """Round segments for a piece *r* nominal mm across: a claw needs few,
    a torso more. Every triangle is a triangle the game draws."""
    return 8 if r < 14 else 12 if r < 40 else 16 if r < 90 else 22


# ------------------------------------------------------------- sketch
class Sketch:
    """OpenSCAD lines for one creature, and the box they fill."""

    def __init__(self, colours):
        self.c = colours
        self.lines = []
        self.lo = [math.inf] * 3
        self.hi = [-math.inf] * 3
        self.parts = []
        self._depth = 1

    def _line(self, text):
        self.lines.append("  " * self._depth + text)

    def _grow(self, p, r):
        r = r if isinstance(r, (list, tuple)) else (r, r, r)
        for i in range(3):
            self.lo[i] = min(self.lo[i], p[i] - r[i])
            self.hi[i] = max(self.hi[i], p[i] + r[i])

    @contextmanager
    def part(self, label, colour="skin", material="Skin"):
        """One part of the rig — or the body — as a labelled block."""
        self.parts.append(label)
        self._line(f'kcad_material("{material}") color("{self.c[colour]}") '
                   f"{{  // {label}")
        self._depth += 1
        try:
            yield
        finally:
            self._depth -= 1
            self._line("}")

    def _shape(self, stmt, label, colour, material):
        pre = ""
        if colour:
            pre = f'color("{self.c.get(colour, colour)}") '
            if material:
                pre = f'kcad_material("{material}") ' + pre
        self._line(f"{pre}{stmt}  // {label}")

    def ell(self, c, r, label, colour=None, material=None):
        r = list(r) if isinstance(r, (list, tuple)) else [r, r, r]
        self._shape(f"kcad_ellipsoid(c = {_v(c)}, r = {_v(r)}, "
                    f"$fn = {_fn(max(r))});", label, colour, material)
        self._grow(c, r)

    def cap(self, a, b, r, label, colour=None, material=None):
        self._shape(f"kcad_capsule(a = {_v(a)}, b = {_v(b)}, r = {_f(r)}, "
                    f"$fn = {_fn(r)});", label, colour, material)
        self._grow(a, r)
        self._grow(b, r)

    def chain(self, pts, radii, label, colour=None, material=None):
        for i in range(len(pts) - 1):
            self.cap(pts[i], pts[i + 1], radii[min(i, len(radii) - 1)],
                     f"{label} {i + 1}", colour, material)

    def cone(self, base, tip, r0, r1, label, colour=None, material=None):
        d = _sub(tip, base)
        length = _len(d) or 1.0
        tilt = math.degrees(math.acos(max(-1.0, min(1.0, d[2] / length))))
        turn = math.degrees(math.atan2(d[1], d[0]))
        self._shape(f"translate({_v(base)}) rotate([0, {_f(tilt)}, "
                    f"{_f(turn)}]) cylinder(h = {_f(length)}, r1 = "
                    f"{_f(r0)}, r2 = {_f(r1)}, $fn = {_fn(r0)});",
                    label, colour, material)
        self._grow(base, r0)
        self._grow(tip, r1)

    def plate(self, pts, thick, label, colour=None, material=None):
        """A thin flat plate through three points — a wing's membrane.
        OpenSCAD's own winding: every face clockwise seen from outside."""
        n = _norm(_cross(_sub(pts[1], pts[0]), _sub(pts[2], pts[0])))
        h = thick / 2.0
        top = [_add(p, n, h) for p in pts]
        bot = [_add(p, n, -h) for p in pts]
        k = len(pts)
        faces = [list(range(k - 1, -1, -1)), list(range(k, 2 * k))]
        for i in range(k):
            j = (i + 1) % k
            faces.append([i, j, k + j, k + i])
        pts_s = "[" + ", ".join(_v(p) for p in top + bot) + "]"
        faces_s = "[" + ", ".join(
            "[" + ", ".join(str(i) for i in f) + "]" for f in faces) + "]"
        self._shape(f"polyhedron(points = {pts_s}, faces = {faces_s});",
                    label, colour, material)
        for p in pts:
            self._grow(p, h)


# --------------------------------------------------------------- face
def _eyes(sk, centre, hs, count, size, spread=0.17, fwd=0.40, up=0.02,
          slit=False):
    """Glowing eyes with a dark pupil, on the front of a head."""
    if count == 1:
        e = _add(centre, [0, -hs * (fwd + 0.02), hs * (up + 0.04)])
        sk.ell(e, hs * 0.15 * size, "Eye", "eyes", "Emissive")
        sk.ell(_add(e, [0, -hs * 0.10 * size, 0]), hs * 0.07 * size,
               "Pupil", "pupil", "Plastic")
        return
    for sx, side in ((1, "Left"), (-1, "Right")):
        e = _add(centre, [sx * hs * spread, -hs * fwd, hs * up])
        sk.ell(e, hs * 0.075 * size, f"{side} eye", "eyes", "Emissive")
        pr = ([hs * 0.018 * size, hs * 0.02 * size, hs * 0.05 * size]
              if slit else hs * 0.035 * size)
        sk.ell(_add(e, [0, -hs * 0.05 * size, 0]), pr, f"{side} pupil",
               "pupil", "Plastic")


def _horns(sk, centre, hs, style, quad=False):
    if style in (None, "none"):
        return
    for sx, side in ((1, "Left"), (-1, "Right")):
        if style == "bull":
            p0 = _add(centre, [sx * hs * 0.30, hs * 0.02, hs * 0.34])
            p1 = _add(p0, [sx * hs * 0.30, -hs * 0.04, hs * 0.02])
            p2 = _add(p1, [sx * hs * 0.20, -hs * 0.08, hs * 0.22])
            sk.chain([p0, p1, p2], [hs * 0.10, hs * 0.075], f"{side} horn",
                     "accent", "Plastic")
            sk.cone(p2, _add(p2, [sx * hs * 0.02, -hs * 0.05, hs * 0.20]),
                    hs * 0.075, hs * 0.012, f"{side} horn tip", "accent",
                    "Plastic")
        elif style == "ram":
            c = _add(centre, [sx * hs * 0.44, hs * 0.10, hs * 0.16])
            pts, radii = [], []
            for i in range(9):
                a = math.radians(100 + i * 36)
                pts.append(_add(c, [sx * hs * 0.04 * i / 8,
                                    math.cos(a) * hs * 0.22,
                                    math.sin(a) * hs * 0.22]))
                radii.append(hs * (0.10 - i * 0.007))
            sk.chain(pts, radii, f"{side} horn", "accent", "Plastic")
        elif style == "straight":
            b = _add(centre, [sx * hs * 0.20, -hs * 0.10, hs * 0.40])
            sk.cone(b, _add(b, [sx * hs * 0.10, hs * 0.08, hs * 0.42]),
                    hs * 0.08, hs * 0.01, f"{side} horn", "accent", "Plastic")
        elif style == "swept":
            p0 = _add(centre, [sx * hs * 0.18, hs * 0.12, hs * 0.30])
            p1 = _add(p0, [sx * hs * 0.08, hs * 0.36, hs * 0.16])
            p2 = _add(p1, [sx * hs * 0.04, hs * 0.30, hs * 0.03])
            sk.chain([p0, p1, p2], [hs * 0.08, hs * 0.055], f"{side} horn",
                     "accent", "Plastic")
            sk.cone(p2, _add(p2, [sx * hs * 0.02, hs * 0.22, -hs * 0.02]),
                    hs * 0.055, hs * 0.01, f"{side} horn tip", "accent",
                    "Plastic")
        elif style == "nubs":
            b = _add(centre, [sx * hs * 0.18, hs * (0.08 if quad else -0.02),
                              hs * 0.36])
            sk.cone(b, _add(b, [sx * hs * 0.03, hs * 0.04, hs * 0.14]),
                    hs * 0.06, hs * 0.015, f"{side} horn", "accent", "Plastic")


def _ears(sk, centre, hs, style, quad=False):
    if style in (None, "none"):
        return
    for sx, side in ((1, "Left"), (-1, "Right")):
        if style == "round":
            at = ([sx * hs * 0.30, hs * 0.10, hs * 0.32] if quad
                  else [sx * hs * 0.44, 0, 0])
            r = ([hs * 0.10, hs * 0.06, hs * 0.10] if quad
                 else [hs * 0.06, hs * 0.12, hs * 0.14])
            sk.ell(_add(centre, at), r, f"{side} ear")
        else:
            long = style == "long"
            if quad:
                b = _add(centre, [sx * hs * 0.22, hs * 0.08, hs * 0.28])
                tip = _add(b, [sx * hs * 0.06, hs * 0.08, hs * 0.30])
            else:
                b = _add(centre, [sx * hs * 0.40, hs * 0.02, hs * 0.05])
                tip = _add(b, [sx * hs * (0.62 if long else 0.30),
                               hs * (0.12 if long else 0.10),
                               hs * (0.12 if long else 0.22)])
            sk.cone(b, tip, hs * (0.11 if long else 0.10), hs * 0.01,
                    f"{side} ear")


# -------------------------------------------------------------- biped
def _weapon(sk, s, fist, grip_r):
    kind = s["weapon"]
    if kind in (None, "none"):
        return
    top = _add(fist, [0, -H * 0.01, H * 0.035])
    if kind == "dagger":
        sk.cap(top, _add(fist, [0, -H * 0.01, -H * 0.03]), grip_r * 0.45,
               "Knife grip", "wood", "Matte")
        b = _add(fist, [0, -H * 0.012, -H * 0.03])
        sk.cone(b, _add(b, [0, -H * 0.03, -H * 0.13]), grip_r * 0.55,
                grip_r * 0.05, "Knife blade", "metal", "Metal")
        return
    reach = 0.55 if kind == "spear" else 0.34
    end = _add(fist, [0, -H * 0.12, -H * reach])
    end[2] = max(end[2], H * 0.06)
    sk.cap(top, end, H * 0.018, "Haft", "wood", "Matte")
    d = _norm(_sub(end, top))
    if kind in ("club", "spiked club"):
        head = _add(end, d, H * 0.05)
        sk.ell(head, [H * 0.05, H * 0.05, H * 0.07], "Club", "wood", "Matte")
        if kind == "spiked club":
            for i, (a, z) in enumerate(((0, 0.02), (72, -0.02), (144, 0.03),
                                        (216, -0.01), (288, 0.01))):
                r = math.radians(a)
                base = _add(head, [math.cos(r) * H * 0.045,
                                   math.sin(r) * H * 0.045, z * H])
                sk.cone(base, _add(base, [math.cos(r) * H * 0.04,
                                          math.sin(r) * H * 0.04, 0]),
                        H * 0.012, H * 0.002, f"Stud {i + 1}", "metal",
                        "Metal")
    elif kind == "axe":
        near = _add(end, d, -H * 0.02)
        sk.plate([_add(near, [0, 0, H * 0.02]),
                  _add(near, [0, -H * 0.13, H * 0.08]),
                  _add(near, [0, -H * 0.13, -H * 0.08])], H * 0.01,
                 "Axe blade", "metal", "Metal")
    elif kind == "spear":
        sk.cone(end, _add(end, d, H * 0.12), H * 0.025, H * 0.002,
                "Spear point", "metal", "Metal")


def _biped(sk, s):
    hip = s["leg"] * H
    bw = s["bulk"] * H
    bd = bw * s["depth"]
    th = s["torso"] * H
    sz = hip + th
    lean = s["hunch"] * 0.08 * H
    leg_r = 0.050 * H * s["leg_r"]
    arm_r = 0.042 * H * s["arm_r"]

    with sk.part("Body"):
        sk.ell([0, 0, hip + 0.02 * H], [bw * 0.46, bd * 0.48, 0.07 * H],
               "Pelvis")
        sk.ell([0, -lean * 0.4, hip + th * 0.45], [bw * 0.5, bd * 0.5,
                                                    th * 0.55], "Torso")
        sk.ell([0, -lean * 0.8, hip + th * 0.78], [bw * 0.56, bd * 0.52,
                                                    th * 0.32], "Chest")
        b = s["belly_size"]
        if b > 0:
            sk.ell([0, -bd * (0.18 + 0.12 * b) - lean * 0.3, hip + th * 0.36],
                   [bw * (0.38 + 0.08 * b), bd * (0.36 + 0.14 * b),
                    th * (0.30 + 0.08 * b)], "Belly", "belly")
        if s["loincloth"]:
            sk.ell([0, 0, hip], [bw * 0.5, bd * 0.52, 0.055 * H], "Loincloth",
                   "cloth", "Matte")
            for y, name in ((-1, "Front flap"), (1, "Back flap")):
                sk.ell([0, y * bd * 0.44, hip - 0.06 * H],
                       [bw * 0.2, 0.012 * H, 0.08 * H], name, "cloth", "Matte")
        for i in range(s["spikes"]):
            z = sz - 0.02 * H - i * (th * 0.8 / max(1, s["spikes"]))
            base = [0, bd * 0.46 - lean * 0.5, z]
            sk.cone(base, _add(base, [0, 0.06 * H, 0.03 * H]), 0.018 * H,
                    0.002 * H, f"Spike {i + 1}", "accent", "Plastic")
        # the arms are the body's: the game has no joint for them
        fists = {}
        for sx, side in ((1, "Left"), (-1, "Right")):
            sh = [sx * (bw * 0.5 + arm_r * 0.3), -lean, sz - arm_r]
            al = s["arm"] * H
            elbow = [sh[0] * 1.08, -lean - 0.01 * H, sz - al * 0.47]
            wrist = [sh[0] * 1.10, -lean - 0.04 * H, sz - al * 0.93]
            sk.ell(sh, arm_r * 1.35, f"{side} shoulder")
            sk.cap(sh, elbow, arm_r, f"{side} upper arm")
            sk.cap(elbow, wrist, arm_r * 0.9, f"{side} forearm")
            fist = _add(wrist, [0, -0.005 * H, -arm_r * 0.9])
            sk.ell(fist, [arm_r * 1.25, arm_r * 1.2, arm_r * 1.3],
                   f"{side} fist")
            fists[sx] = fist
            if s["pauldron"]:
                sk.ell(_add(sh, [sx * arm_r * 0.2, 0, arm_r * 0.5]),
                       [arm_r * 1.7, arm_r * 1.6, arm_r * 1.0],
                       f"{side} shoulder plate", "metal", "Metal")
        _weapon(sk, s, fists[-1], arm_r)

    for sx, side in ((1, "Left"), (-1, "Right")):
        x = sx * bw * 0.27
        with sk.part(f"{side} leg"):
            knee = [x, -0.012 * H, hip * 0.52]
            ankle = [x, 0.004 * H, 0.055 * H]
            sk.cap([x, 0, hip + leg_r * 0.3], knee, leg_r, "Thigh")
            sk.cap(knee, ankle, leg_r * 0.82, "Shin")
            sk.ell([x, -0.045 * H, 0.03 * H], [leg_r * 1.05, 0.075 * H,
                                                0.03 * H], "Foot")
            if s["claws"]:
                for i, dx in enumerate((-0.5, 0, 0.5)):
                    base = [x + dx * leg_r, -0.105 * H, 0.02 * H]
                    sk.cone(base, _add(base, [0, -0.035 * H, -0.008 * H]),
                            0.012 * H, 0.002 * H, f"Toe claw {i + 1}",
                            "accent", "Plastic")

    hs = s["head"] * H
    hc = [0, -lean - hs * 0.10 - s["hunch"] * 0.03 * H,
          sz + s["neck"] * H + hs * 0.52]
    with sk.part("Head"):
        sk.cap([0, -lean, sz - 0.01 * H], _add(hc, [0, hs * 0.05, -hs * 0.3]),
               hs * 0.3, "Neck")
        sk.ell(hc, [hs * 0.44, hs * 0.46, hs * 0.52], "Skull")
        if s["face"]:
            sk.ell(_add(hc, [0, -hs * 0.25, -hs * 0.02]),
                   [hs * 0.30, hs * 0.25, hs * 0.36], "Face", "belly")
        sk.ell(_add(hc, [0, -hs * 0.16, -hs * 0.28]),
               [hs * 0.38, hs * 0.34, hs * 0.22], "Jaw")
        if s["brow"]:
            sk.cap(_add(hc, [-hs * 0.30, -hs * 0.38, hs * 0.10]),
                   _add(hc, [hs * 0.30, -hs * 0.38, hs * 0.10]),
                   hs * 0.075, "Brow")
        _eyes(sk, hc, hs, s["eyes_n"], s["eye_size"])
        if s["nose"] == "big":
            sk.ell(_add(hc, [0, -hs * 0.52, -hs * 0.06]),
                   [hs * 0.10, hs * 0.11, hs * 0.13], "Nose")
        elif s["nose"] == "snout":
            mz = _add(hc, [0, -hs * 0.50, -hs * 0.18])
            sk.ell(mz, [hs * 0.26, hs * 0.22, hs * 0.18], "Muzzle", "belly")
            for sx in (1, -1):
                sk.ell(_add(mz, [sx * hs * 0.09, -hs * 0.20, hs * 0.02]),
                       hs * 0.035, "Nostril", "pupil", "Plastic")
        sk.cap(_add(hc, [-hs * 0.16, -hs * 0.47, -hs * 0.24]),
               _add(hc, [hs * 0.16, -hs * 0.47, -hs * 0.24]), hs * 0.03,
               "Mouth", "mouth", "Plastic")
        for sx, side in ((1, "Left"), (-1, "Right")):
            if s["tusks"]:
                b = _add(hc, [sx * hs * 0.15, -hs * 0.44, -hs * 0.30])
                sk.cone(b, _add(b, [sx * hs * 0.03, -hs * 0.05, hs * 0.20]),
                        hs * 0.045, hs * 0.012, f"{side} tusk", "accent",
                        "Plastic")
            if s["fangs"]:
                b = _add(hc, [sx * hs * 0.08, -hs * 0.47, -hs * 0.20])
                sk.cone(b, _add(b, [0, -hs * 0.01, -hs * 0.10]), hs * 0.025,
                        hs * 0.004, f"{side} fang", "accent", "Plastic")
        _ears(sk, hc, hs, s["ears"])
        _horns(sk, hc, hs, s["horns"])

    _biped_tail(sk, s, hip, bd)
    if s["wings"]:
        _wings(sk, s, [bw * 0.18, bd * 0.42, sz - 0.04 * H],
               s["wing_span"] * H, 1.0)


def _biped_tail(sk, s, hip, bd):
    kind = s["tail"]
    if kind in (None, "none"):
        return
    root = [0, bd * 0.45, hip + 0.03 * H]
    p1 = _add(root, [0, 0.12 * H, -0.06 * H])
    p2 = _add(p1, [0, 0.10 * H, -0.10 * H])
    p3 = _add(p2, [0, 0.08 * H, 0.02 * H])
    with sk.part("Tail"):
        sk.chain([root, p1, p2, p3], [0.024 * H, 0.018 * H, 0.013 * H],
                 "Segment")
        if kind == "tuft":
            sk.ell(p3, [0.03 * H, 0.05 * H, 0.03 * H], "Tuft", "hair",
                   "Matte")
        elif kind == "spade":
            sk.plate([_add(p3, [0, -0.01 * H, 0]),
                      _add(p3, [0.045 * H, 0.05 * H, 0.01 * H]),
                      _add(p3, [0, 0.10 * H, 0.02 * H])], 0.008 * H,
                     "Spade", "accent", "Plastic")
            sk.plate([_add(p3, [0, -0.01 * H, 0]),
                      _add(p3, [0, 0.10 * H, 0.02 * H]),
                      _add(p3, [-0.045 * H, 0.05 * H, 0.01 * H])],
                     0.008 * H, "Spade back", "accent", "Plastic")


def _wings(sk, s, root, span, up):
    """A pair of bat wings from *root* (the left one; the right mirrored):
    an arm bone to the wrist, three fingers, and the membrane between them
    in flat plates."""
    for sx, side in ((1, "Left"), (-1, "Right")):
        r0 = [sx * root[0], root[1], root[2]]
        p1 = _add(r0, [sx * span * 0.35, 0.08 * H, 0.16 * H * up])
        p2 = _add(p1, [sx * span * 0.30, 0.05 * H, 0.10 * H * up])
        f1 = _add(p2, [sx * span * 0.35, 0.03 * H, 0.0])
        f2 = _add(p2, [sx * span * 0.26, 0.12 * H, -0.20 * H * up])
        f3 = _add(p2, [sx * span * 0.10, 0.16 * H, -0.36 * H * up])
        low = _add(r0, [sx * 0.02 * H, 0.08 * H, -0.26 * H * up])
        with sk.part(f"{side} wing", "wing"):
            bone = max(0.012 * H, span * 0.025)
            sk.chain([r0, p1, p2], [bone, bone * 0.8], "Arm bone", "skin",
                     "Skin")
            for i, f in enumerate((f1, f2, f3)):
                sk.cap(p2, f, bone * 0.45, f"Finger {i + 1}", "skin", "Skin")
            t = max(0.006 * H, span * 0.008)
            for i, tri in enumerate(((r0, p1, p2), (r0, p2, f3),
                                     (p2, f3, f2), (p2, f2, f1),
                                     (r0, f3, low))):
                sk.plate(list(tri), t, f"Membrane {i + 1}")


# ---------------------------------------------------------- quadruped
def _quadruped(sk, s):
    leg = s["leg"] * H
    ln = s["length"] * H
    bw = s["bulk"] * H
    bh = s["body"] * H
    bz = leg + bh * 0.42
    leg_r = 0.055 * H * s["leg_r"]

    with sk.part("Body"):
        sk.ell([0, 0, bz], [bw * 0.5, ln * 0.5, bh * 0.5], "Trunk")
        sk.ell([0, -ln * 0.28, bz + bh * 0.05], [bw * 0.56, ln * 0.28,
                                                 bh * 0.56], "Chest")
        sk.ell([0, ln * 0.30, bz + bh * 0.02], [bw * 0.52, ln * 0.25,
                                                bh * 0.50], "Haunch")
        sk.ell([0, -ln * 0.05, bz - bh * 0.22], [bw * 0.40, ln * 0.36,
                                                 bh * 0.28], "Belly", "belly")
        if s["ruff"]:
            sk.ell([0, -ln * 0.36, bz + bh * 0.18], [bw * 0.64, ln * 0.18,
                                                     bh * 0.62], "Ruff",
                   "hair", "Matte")
        n = s["spikes"]
        for i in range(n):
            y = -ln * 0.30 + i * (ln * 0.72 / max(1, n - 1))
            t = max(0.0, 1 - (y / (ln * 0.5)) ** 2)
            top = bz + bh * 0.5 * math.sqrt(t) - 0.012 * H
            size = 0.07 * H * (1.0 - 0.3 * abs(i - n / 2) / max(1, n / 2))
            sk.cone([0, y, top], [0, y + size * 0.5, top + size], 0.03 * H,
                    0.003 * H, f"Spike {i + 1}",
                    "hair" if s.get("bristle") else "accent", "Plastic")

    fy, by, lx = -ln * 0.30, ln * 0.32, bw * 0.34
    for end, y in (("Front", fy), ("Back", by)):
        for sx, side in ((1, "left"), (-1, "right")):
            x = sx * lx
            with sk.part(f"{end} {side} leg"):
                top = [x, y, bz - bh * 0.05]
                if end == "Front":
                    knee = [x, y + 0.01 * H, leg * 0.5]
                    ankle = [x, y - 0.005 * H, 0.07 * H]
                    sk.cap(top, knee, leg_r * 1.15, "Upper")
                    sk.cap(knee, ankle, leg_r * 0.85, "Lower")
                else:
                    knee = [x, y - 0.05 * H, leg * 0.62]
                    hock = [x, y + 0.05 * H, leg * 0.28]
                    ankle = [x, y + 0.01 * H, 0.07 * H]
                    sk.cap(top, knee, leg_r * 1.25, "Upper")
                    sk.cap(knee, hock, leg_r * 0.95, "Middle")
                    sk.cap(hock, ankle, leg_r * 0.8, "Lower")
                paw = [x, y - 0.03 * H, 0.035 * H]
                sk.ell(paw, [leg_r * 1.3, leg_r * 1.7, 0.035 * H], "Paw")
                if s["claws"]:
                    for i, dx in enumerate((-0.6, 0, 0.6)):
                        b = [x + dx * leg_r, paw[1] - leg_r * 1.4, 0.02 * H]
                        sk.cone(b, _add(b, [0, -0.03 * H, -0.01 * H]),
                                0.011 * H, 0.002 * H, f"Claw {i + 1}",
                                "accent", "Plastic")

    hs = s["head"] * H
    nb = [0, -ln * 0.40, bz + bh * 0.18]
    nl = s["neck"] * H
    up = s["neck_up"]
    hb = _add(nb, [0, -nl * math.cos(up), nl * math.sin(up)])
    hc = _add(hb, [0, -hs * 0.35, hs * 0.05])
    with sk.part("Head"):
        mid = [0, (nb[1] + hb[1]) / 2 + nl * 0.05, (nb[2] + hb[2]) / 2
               + nl * 0.08]
        sk.chain([nb, mid, hb], [hs * 0.36, hs * 0.30], "Neck")
        sk.ell(hc, [hs * 0.40, hs * 0.45, hs * 0.40], "Skull")
        sn = s["snout"]
        sc = _add(hc, [0, -hs * (0.45 + sn * 0.35), -hs * 0.10])
        sr = [hs * 0.24, hs * (0.20 + sn * 0.35), hs * 0.20]
        sk.ell(sc, sr, "Snout")
        sk.ell(_add(sc, [0, hs * 0.06, -hs * 0.12]),
               [hs * 0.21, hs * (0.18 + sn * 0.30), hs * 0.09], "Jaw",
               "belly")
        sk.ell(_add(sc, [0, -sr[1] * 0.92, hs * 0.06]),
               [hs * 0.09, hs * 0.06, hs * 0.07], "Nose", "pupil", "Plastic")
        _eyes(sk, hc, hs, s["eyes_n"], s["eye_size"], spread=0.25,
              fwd=0.30, up=0.12, slit=True)
        for sx, side in ((1, "Left"), (-1, "Right")):
            if s["fangs"]:
                b = _add(sc, [sx * hs * 0.14, -sr[1] * 0.6, -hs * 0.12])
                sk.cone(b, _add(b, [0, -hs * 0.02, -hs * 0.12]), hs * 0.03,
                        hs * 0.004, f"{side} fang", "accent", "Plastic")
            if s["tusks"]:
                b = _add(sc, [sx * hs * 0.20, -sr[1] * 0.5, -hs * 0.10])
                sk.cone(b, _add(b, [sx * hs * 0.12, -hs * 0.10, hs * 0.22]),
                        hs * 0.05, hs * 0.01, f"{side} tusk", "accent",
                        "Plastic")
        _ears(sk, hc, hs, s["ears"], quad=True)
        _horns(sk, hc, hs, s["horns"], quad=True)

    _quad_tail(sk, s, [0, ln * 0.52, bz + bh * 0.12])
    if s["wings"]:
        _wings(sk, s, [bw * 0.28, -ln * 0.18, bz + bh * 0.45],
               s["wing_span"] * H, 1.2)


def _quad_tail(sk, s, root):
    kind = s["tail"]
    if kind in (None, "none"):
        return
    with sk.part("Tail"):
        if kind == "stub":
            sk.ell(_add(root, [0, 0.02 * H, 0]), 0.04 * H, "Stub")
            return
        if kind == "curly":
            pts = [_add(root, [0, 0.03 * H * math.sin(a) + 0.02 * H * i / 5,
                               0.03 * H * math.cos(a)])
                   for i, a in enumerate(math.radians(d)
                                         for d in (0, 70, 140, 210, 280, 350))]
            sk.chain(pts, [0.012 * H], "Curl")
            return
        if kind == "bushy":
            p1 = _add(root, [0, 0.14 * H, -0.06 * H])
            p2 = _add(p1, [0, 0.12 * H, -0.14 * H])
            sk.chain([root, p1, p2], [0.03 * H, 0.04 * H], "Brush")
            sk.ell(_add(p1, [0, 0.05 * H, -0.06 * H]),
                   [0.055 * H, 0.14 * H, 0.06 * H], "Fur", "hair", "Matte")
            return
        # thin or long: segments back and down, tapering, and a ridge
        # along the top of a long one
        n = 7 if kind == "long" else 4
        seg = 0.16 * H if kind == "long" else 0.08 * H
        pts = [root]
        for i in range(1, n + 1):
            droop = 0.05 * H * math.sin(math.pi * i / (n + 1))
            pts.append(_add(root, [0, seg * i, -droop - 0.02 * H * i]))
        radii = [max(0.012 * H, 0.08 * H * (1 - i / (n + 0.5)) *
                     (s["bulk"] / 0.3)) for i in range(n)]
        sk.chain(pts, radii, "Segment")
        if kind == "long" and s["spikes"]:
            for i in range(1, n):
                p = pts[i]
                sk.cone(_add(p, [0, 0, radii[i] * 0.8]),
                        _add(p, [0, 0.03 * H, radii[i] * 0.8 + 0.05 * H]),
                        0.02 * H, 0.002 * H, f"Ridge {i}", "accent",
                        "Plastic")
        end = pts[-1]
        if s.get("spade_tip") or kind == "spade":
            for sx, name in ((1, "Spade"), (-1, "Spade back")):
                sk.plate([_add(end, [0, -0.02 * H, 0]),
                          _add(end, [sx * 0.07 * H, 0.07 * H, 0]),
                          _add(end, [0, 0.14 * H, 0])], 0.01 * H, name,
                         "accent", "Plastic")


# --------------------------------------------------- spider, serpent, slime
def _spider(sk, s):
    b = s["bulk"]
    bz = 0.30 * H
    with sk.part("Body"):
        sk.ell([0, -0.08 * H, bz], [0.20 * H * b, 0.24 * H * b, 0.13 * H * b],
               "Thorax")
        sk.ell([0, 0.32 * H, bz + 0.06 * H], [0.30 * H * b, 0.36 * H * b,
                                              0.26 * H * b], "Abdomen")
        sk.ell([0, 0.32 * H, bz + 0.06 * H + 0.25 * H * b],
               [0.08 * H, 0.12 * H, 0.025 * H], "Mark", "accent", "Plastic")
        sk.ell([0, 0.50 * H, bz + 0.06 * H + 0.17 * H * b],
               [0.06 * H, 0.06 * H, 0.03 * H], "Mark 2", "accent", "Plastic")
    reach = (-0.22, -0.08, 0.08, 0.22)
    for end, ks in (("Front", (0, 1)), ("Back", (2, 3))):
        for sx, side in ((1, "left"), (-1, "right")):
            with sk.part(f"{end} {side} leg", "belly"):
                for k in ks:
                    y = -0.24 * H + k * 0.10 * H
                    at = [sx * 0.16 * H * b, y, bz]
                    knee = [sx * 0.40 * H, y + reach[k] * H * 0.5, bz + 0.28 * H]
                    foot = [sx * 0.74 * H, y + reach[k] * H, 0.02 * H]
                    mid = [(knee[0] + foot[0]) / 2, (knee[1] + foot[1]) / 2,
                           (knee[2] + foot[2]) / 2 + 0.05 * H]
                    sk.chain([at, knee, mid, foot],
                             [0.032 * H, 0.026 * H, 0.018 * H],
                             f"Limb {k + 1}")
    hc = [0, -0.33 * H, bz + 0.02 * H]
    with sk.part("Head"):
        sk.ell(hc, [0.13 * H, 0.12 * H, 0.10 * H], "Cephalon")
        size = s["eye_size"]
        for i, (x, z, r) in enumerate(((0.035, 0.03, 0.022),
                                       (-0.035, 0.03, 0.022),
                                       (0.075, 0.045, 0.014),
                                       (-0.075, 0.045, 0.014),
                                       (0.02, 0.07, 0.012),
                                       (-0.02, 0.07, 0.012),
                                       (0.09, 0.0, 0.012),
                                       (-0.09, 0.0, 0.012))):
            sk.ell(_add(hc, [x * H, -0.105 * H, z * H]), r * H * size,
                   f"Eye {i + 1}", "eyes", "Emissive")
        for sx, side in ((1, "Left"), (-1, "Right")):
            b0 = _add(hc, [sx * 0.04 * H, -0.10 * H, -0.04 * H])
            b1 = _add(b0, [0, -0.03 * H, -0.06 * H])
            sk.cap(b0, b1, 0.022 * H, f"{side} chelicera", "belly")
            sk.cone(b1, _add(b1, [-sx * 0.015 * H, -0.01 * H, -0.05 * H]),
                    0.012 * H, 0.002 * H, f"{side} fang", "accent", "Plastic")


def _serpent(sk, s):
    b = s["bulk"]
    n = 14
    pts, radii = [], []
    for i in range(n):
        t = i / (n - 1)
        pts.append([0.16 * H * math.sin(t * 5.5), -0.05 * H + t * 1.05 * H,
                    0.0])
        radii.append(0.09 * H * b * (1 - 0.75 * t))
    for p, r in zip(pts, radii):
        p[2] = r
    cut = 9
    with sk.part("Body"):
        sk.chain(pts[:cut + 1], radii[:cut + 1], "Coil")
        sk.chain([_add(p, [0, 0, -r * 0.35]) for p, r in
                  zip(pts[:cut + 1], radii)], [r * 0.8 for r in radii[:cut]],
                 "Underside", "belly")
    with sk.part("Tail"):
        sk.chain(pts[cut:], radii[cut:], "Coil end")
        sk.cone(pts[-1], _add(pts[-1], [0.03 * H, 0.08 * H, 0]),
                radii[-1], 0.002 * H, "Tip")
    hc = [0, -0.36 * H, 0.84 * H]
    with sk.part("Head"):
        neck = [pts[0], [0, -0.14 * H, 0.30 * H], [0, -0.22 * H, 0.58 * H],
                _add(hc, [0, 0.06 * H, -0.06 * H])]
        sk.chain(neck, [0.085 * H * b, 0.075 * H * b, 0.07 * H * b], "Neck")
        sk.chain([_add(p, [0, -0.045 * H * b, 0]) for p in neck[1:]],
                 [0.05 * H * b], "Throat", "belly")
        if s["hood"]:
            sk.ell(_add(hc, [0, 0.10 * H, -0.12 * H]),
                   [0.19 * H * b, 0.03 * H, 0.17 * H * b], "Hood")
            sk.ell(_add(hc, [0, 0.07 * H, -0.12 * H]),
                   [0.12 * H * b, 0.02 * H, 0.11 * H * b], "Hood mark",
                   "belly")
        sk.ell(hc, [0.10 * H * b, 0.15 * H * b, 0.07 * H * b], "Skull")
        _eyes(sk, hc, 0.30 * H * b, 2, s["eye_size"], spread=0.22,
              fwd=0.30, up=0.10, slit=True)
        tip = _add(hc, [0, -0.15 * H * b, -0.02 * H])
        for sx in (1, -1):
            sk.cone(tip, _add(tip, [sx * 0.02 * H, -0.08 * H, -0.01 * H]),
                    0.006 * H, 0.001 * H, "Tongue", "accent", "Plastic")


def _slime(sk, s):
    b = s["bulk"]
    with sk.part("Body"):
        sk.ell([0, 0, 0.42 * H], [0.50 * H * b, 0.45 * H * b, 0.42 * H],
               "Blob")
        sk.ell([0, 0, 0.06 * H], [0.60 * H * b, 0.55 * H * b, 0.06 * H],
               "Puddle")
        sk.ell([0, 0.05 * H, 0.40 * H], [0.26 * H * b, 0.24 * H * b,
                                         0.22 * H], "Core", "belly")
        for i, a in enumerate((20, 95, 170, 250, 320)):
            r = math.radians(a)
            sk.ell([math.cos(r) * 0.46 * H * b, math.sin(r) * 0.42 * H * b,
                    0.16 * H], [0.07 * H, 0.07 * H, 0.10 * H],
                   f"Drip {i + 1}")
    hc = [0, -0.30 * H * b, 0.58 * H]
    with sk.part("Head", "eyes", "Emissive"):
        for sx, side in ((1, "Left"), (-1, "Right")):
            e = _add(hc, [sx * 0.14 * H, -0.08 * H, 0.0])
            sk.ell(e, 0.075 * H * s["eye_size"], f"{side} eye")
            sk.ell(_add(e, [0, -0.05 * H, 0]), 0.035 * H * s["eye_size"],
                   f"{side} pupil", "pupil", "Plastic")
        sk.cap(_add(hc, [-0.10 * H, -0.09 * H, -0.16 * H]),
               _add(hc, [0.10 * H, -0.09 * H, -0.16 * H]), 0.02 * H,
               "Mouth", "mouth", "Plastic")


_BUILDERS = dict(biped=_biped, winged=_biped, quadruped=_quadruped,
                 spider=_spider, serpent=_serpent, slime=_slime)


# --------------------------------------------------------------- spec
def options():
    """Everything build_creature accepts."""
    return {
        "plans": list(PLANS),
        "presets": {name: {"plan": p["plan"], "height_mm": p["height"],
                           "nature": p["nature"], "what": p["blurb"]}
                    for name, p in PRESETS.items()},
        "features": {
            "horns": list(HORNS), "ears": list(EARS), "nose": list(NOSES),
            "tail": list(TAILS), "weapon": list(WEAPONS),
            "tusks / fangs / claws / wings / loincloth / face / ruff /"
            " hood": "true or false",
            "eyes_n": "1 (a cyclops) or 2", "spikes": "how many, 0-14",
        },
        "shape": {
            "bulk": "how broad (0.2-0.5 of the height; biped default 0.30)",
            "leg": "leg length as a fraction of the height",
            "head": "head size as a fraction of the height",
            "arm": "arm length (bipeds)", "hunch": "0 upright - 1 stooped",
            "length": "body length (quadrupeds, x the height)",
            "neck": "neck length (quadrupeds)",
            "wing_span": "each wing's reach, x the height",
        },
        "colours": COLOURS,
        "game": {"speed": "0.3-2 (1 is a person's walk)",
                 "health": "hit points (a player has 20)",
                 "damage": "hearts a blow takes (monsters)",
                 "nature": list(NATURES)},
    }


def spec_of(params):
    """The full spec: the preset (if any), then every key given."""
    params = dict(params or {})
    preset = params.pop("preset", None)
    base = {}
    if preset:
        key = next((k for k in PRESETS if k.lower() == str(preset).lower()),
                   None)
        if key is None:
            raise CreatureError(
                f"No preset {preset!r}; there are {', '.join(PRESETS)}.")
        base = dict(PRESETS[key])
        base.setdefault("name", key)
        base["preset_name"] = key
    plan = str(params.get("plan") or base.get("plan") or "biped").lower()
    if plan not in PLANS:
        raise CreatureError(f"{plan!r} is not a body plan; use one of "
                            f"{', '.join(PLANS)}.")
    spec = dict(_PLAN_KEYS[plan])
    spec.update(_DEFAULT_COLOURS)
    spec.update(speed=1.0, health=16, damage=None, nature="monster",
                height=1800.0, name="Monster")
    # a preset's colours are stored under their own names; "belly" is both
    # a colour and (as belly_size) a shape, so the two are kept apart
    spec.update(base)
    for k, v in params.items():
        if v is not None:
            spec[k] = v
    spec["plan"] = plan
    if plan == "winged":
        spec["wings"] = True
    for key, allowed in (("horns", HORNS), ("ears", EARS), ("nose", NOSES),
                         ("tail", TAILS), ("weapon", WEAPONS),
                         ("nature", NATURES)):
        if key in spec and spec[key] not in allowed:
            raise CreatureError(f"{key} {spec[key]!r} is not one of "
                                f"{', '.join(allowed)}.")
    try:
        spec["height"] = float(spec["height"])
    except (TypeError, ValueError):
        raise CreatureError("height is in millimetres, a number.")
    if not 200 <= spec["height"] <= 12000:
        raise CreatureError("height is in millimetres: 200 to 12000 "
                            "(0.2 to 12 blocks in the game).")
    spec["spikes"] = max(0, min(14, int(spec.get("spikes") or 0)))
    spec["eyes_n"] = 1 if int(spec.get("eyes_n") or 2) == 1 else 2
    return spec


def program(params):
    """(OpenSCAD program, spec, part labels) for a creature."""
    spec = spec_of(params)
    colours = {k: spec[k] for k in _DEFAULT_COLOURS}
    sk = Sketch(colours)
    _BUILDERS[spec["plan"]](sk, spec)
    k = spec["height"] / (sk.hi[2] - sk.lo[2])
    name = str(spec["name"]).strip() or "Monster"
    x = float(spec.get("x") or 0.0)
    y = float(spec.get("y") or 0.0)
    head = (f"translate({_v([x, y, 0])}) scale([{k:.4f}, {k:.4f}, {k:.4f}]) "
            f"translate({_v([0, 0, -sk.lo[2]])}) {{")
    body = "\n".join(sk.lines)
    code = (f"union() {{  // {name}\n  {head}\n{body}\n  }}\n}}\n")
    return code, spec, sk.parts


def node_of(params):
    """The creature as one node, not yet in any document.
    Returns (node, spec, part labels)."""
    from .scadparse import parse_scad
    code, spec, parts = program(params)
    root, warnings = parse_scad(code)
    if warnings or len(root.children) != 1:
        raise CreatureError("The creature did not parse: "
                            + "; ".join(warnings[:4]))
    node = root.children[0]
    root.remove(node)
    node.params["creature"] = marker(spec)
    return node, spec, parts


def build(model, params):
    """The creature added to *model*'s root.
    Returns (the creature's node, spec, part labels)."""
    node, spec, parts = node_of(params)
    model.root.add(node)
    return node, spec, parts


#: plans the game walks on no legs at all: the exporter must not go looking
#: for legs in a coil lying on the ground or in a slime's puddle
LEGLESS = ("serpent", "slime")


def marker(spec):
    """What planetcraft.py needs to know about a built creature, kept in
    its node's params (so it is saved with the document): the plan, and the
    game numbers to send it with."""
    return {"plan": spec["plan"], "preset": spec.get("preset_name"),
            "height_mm": round(spec["height"], 1),
            "nature": spec.get("nature") or "monster",
            "speed": spec.get("speed"), "health": spec.get("health"),
            "damage": spec.get("damage")}
