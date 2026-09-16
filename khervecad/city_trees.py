"""The City Builder's trees and street lights (Qt-free).

Every tree of one kind is an iteration of ONE loop over rows
``[x, y, scale, turn, z]`` (scale 1 = the kind's natural height), so a
park is a handful of nodes however many trees stand in it. A tree is
still modelled, not a lollipop: a tapered trunk in the Bark surface,
branches reaching into the crown, and a crown of overlapping leaf
clumps in two greens wearing the Leaves surface (dappled by the OpenGL
shader) — tiers of cones for a fir, a tall column for a poplar, a white
stem for a birch.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from .city_buildings import _f, _num, box, color, cyl, group, move, turn
from .model import CadNode

#: kind -> natural height, mm
TREE_KINDS = {"broadleaf": 8000.0, "conifer": 9000.0, "round": 6000.0,
              "birch": 9000.0, "poplar": 12000.0}

BARK = "#6b4b33"
DARK_LEAF = {"broadleaf": "#3f7a32", "round": "#4d8a36", "birch": "#6f9e3a",
             "poplar": "#3d7236", "conifer": "#2b5634"}
LIGHT_LEAF = {"broadleaf": "#62a043", "round": "#74ad48", "birch": "#93be52",
              "poplar": "#5a9443", "conifer": "#3f6f45"}


def _sphere(name, x, y, z, r, seg=8):
    return CadNode("sphere", name, dict(x=x, y=y, z=z, radius=r,
                                        segments=seg))


def _branch(z, length, r, tilt, heading):
    """A branch leaving the trunk at height z, tilted from vertical."""
    c = cyl("Branch", 0.0, 0.0, 0.0, length, r, r * 0.45, seg=5)
    return move(turn(turn(c, y=tilt), z=heading), 0.0, 0.0, z, "Branch")


def _clumps(centres, colour_split=2):
    """Leaf clumps as two colour groups (alternating), Leaves surface."""
    dark = [_sphere("Clump", *c) for c in centres[::colour_split]]
    light = [_sphere("Clump", *c) for i, c in enumerate(centres)
             if i % colour_split]
    return dark, light


def tree_body(kind):
    """One tree of *kind* at the origin, at its natural height."""
    parts = []
    if kind == "conifer":
        parts.append(color(cyl("Trunk", 0, 0, 0, 2000, 260, 120, seg=6),
                           BARK, "Bark"))
        tiers = []
        for k in range(6):
            z = 1100 + k * 1250
            r = 2300 - k * 330
            tiers.append(cyl("Tier", 0, 0, z, 2000 - k * 120, r, 60, seg=8))
        parts.append(color(group("Tiers", tiers[::2]), DARK_LEAF[kind],
                           "Leaves"))
        parts.append(color(group("Tiers", tiers[1::2]), LIGHT_LEAF[kind],
                           "Leaves"))
        parts.append(color(cyl("Leader", 0, 0, 8300, 700, 90, 0, seg=5),
                           DARK_LEAF[kind], "Leaves"))
        return parts
    if kind == "poplar":
        parts.append(color(cyl("Trunk", 0, 0, 0, 3000, 240, 120, seg=6),
                           BARK, "Bark"))
        col = []
        for k in range(8):
            z = 2700 + k * 1150
            r = 1250 - abs(k - 2.5) * 110
            col.append(_sphere("Clump", 180 * math.cos(k * 2.3),
                               180 * math.sin(k * 2.3), z, r))
        parts.append(color(group("Crown", col[::2]), DARK_LEAF[kind],
                           "Leaves"))
        parts.append(color(group("Crown", col[1::2]), LIGHT_LEAF[kind],
                           "Leaves"))
        return parts
    if kind == "birch":
        trunk = [cyl("Stem", 0, 0, 0, 6500, 170, 60, seg=6),
                 _branch(3800, 2000, 70, 35, 20),
                 _branch(4700, 1800, 60, 40, 200)]
        parts.append(color(group("Trunk", trunk), "#e8e4dc", "Bark"))
        centres = [(0, 0, 6800, 1300), (900, 300, 5600, 1100),
                   (-800, -400, 5400, 1150), (300, -900, 6200, 1000),
                   (-400, 900, 6400, 950), (100, 200, 4600, 900)]
    else:
        big = kind == "broadleaf"
        s = 1.0 if big else 0.72
        trunk = [cyl("Trunk", 0, 0, 0, 3200 * s + 400, 330 * s, 170 * s,
                     seg=7)]
        for k in range(3 if big else 2):
            trunk.append(_branch((2400 + k * 350) * s, 2200 * s, 130 * s,
                                 38 + k * 6, k * 125 + 15))
        parts.append(color(group("Trunk and branches", trunk), BARK, "Bark"))
        r = 1500.0 * s
        centres = [(0, 0, 5000 * s + 600, r * 1.25)]
        ring = 5 if big else 4
        for k in range(ring):
            a = k * 2 * math.pi / ring + 0.4
            centres.append((math.cos(a) * r * 1.05, math.sin(a) * r * 1.05,
                            (4200 + 500 * (k % 2)) * s + 400,
                            r * (0.95 - 0.08 * (k % 3))))
        centres.append((r * 0.2, -r * 0.3, 6200 * s + 700, r * 0.85))
    dark, light = _clumps(centres)
    parts.append(color(group("Crown", dark), DARK_LEAF.get(kind, "#3f7a32"),
                       "Leaves"))
    parts.append(color(group("Crown", light), LIGHT_LEAF.get(kind, "#62a043"),
                       "Leaves"))
    return parts


def _values(rows):
    """Rows as a loop value list. A single row is bracketed once more:
    a lone vector would be iterated element by element."""
    text = ", ".join("[" + ", ".join(_num(v) for v in row) + "]"
                     for row in rows)
    return f"[{text}]" if len(rows) == 1 else text


def build_trees(trees) -> CadNode:
    """One loop per kind over [x, y, scale, turn, z] rows."""
    out = group("Trees")
    by_kind = {}
    for t in trees:
        kind = t.get("kind", "broadleaf")
        kind = kind if kind in TREE_KINDS else "broadleaf"
        natural = TREE_KINDS[kind]
        by_kind.setdefault(kind, []).append(
            (_f(t.get("x")), _f(t.get("y")),
             round(max(0.2, _f(t.get("height"), natural) / natural), 2),
             _f(t.get("rz"), 0.0), _f(t.get("z"), 0.0)))
    for kind, rows in by_kind.items():
        sc = CadNode("scale", "Size", dict(x="p[2]", y="p[2]", z="p[2]"))
        rot = CadNode("rotate", "Turn", dict(x=0.0, y=0.0, z="p[3]"))
        for part in tree_body(kind):
            rot.add(part)
        sc.add(rot)
        at = CadNode("translate", "At", dict(x="p[0]", y="p[1]", z="p[4]"))
        at.add(sc)
        lp = CadNode("for_loop", f"{kind.capitalize()} trees",
                     dict(variable="p", start=0.0, end=0.0, step=1.0,
                          values=_values(rows)))
        lp.add(at)
        out.add(lp)
    return out


def build_lights(points, kerb=150.0) -> CadNode:
    """Every light is one iteration of ONE loop: a base, a tapered pole
    with a collar, a curved arm over the road (local -Y) and a lantern
    whose glass glows."""
    dark = "#30343a"
    metal = color(group("Column", [
        cyl("Base", 0, 0, 0, 700, 170, 130, seg=8),
        cyl("Pole", 0, 0, 700, 6300, 95, 55, seg=8),
        cyl("Collar", 0, 0, 2600, 150, 120, seg=8),
        move(turn(cyl("Arm", 0, 0, 0, 900, 45, seg=6), x=50.0), 0, 0, 6800,
             "Arm rise"),
        move(turn(cyl("Arm", 0, 0, 0, 1000, 45, seg=6), x=90.0), 0, -690,
             7380, "Arm reach"),
        box("Lantern hood", -230, -2050, 7250, 460, 700, 160),
    ]), dark, "Metal")
    glow = color(box("Lantern glass", -170, -1990, 7120, 340, 580, 130),
                 "#fff3c4", "Emissive")
    rot = CadNode("rotate", "Face the road", dict(x=0.0, y=0.0, z="p[2]"))
    rot.add(metal)
    rot.add(glow)
    at = CadNode("translate", "At", dict(x="p[0]", y="p[1]", z=kerb))
    at.add(rot)
    lp = CadNode("for_loop", "Lights", dict(
        variable="p", start=0.0, end=0.0, step=1.0,
        values=_values([(p[0], p[1], p[2]) for p in points])))
    lp.add(at)
    return group("Street lights", [lp])
