"""The City Builder's trees and street lights (Qt-free).

Trees are GROWN by `treegen` — trunk, branches and leaves — at "city"
detail (a few hundred triangles each). Every tree of one species and
variant is an iteration of ONE loop over rows ``[x, y, scale, turn,
z]`` (scale 1 = the species' natural height), so a park is a handful of
nodes however many trees stand in it; each tree picks one of `VARIANTS`
grown shapes from its position, so a row of limes is not a row of
clones.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from .city_buildings import _f, _num, box, color, cyl, group, move, turn
from .model import CadNode

from . import treegen

#: species -> natural height, mm (every species `treegen` grows)
TREE_KINDS = {k: sp["height"] for k, sp in treegen.SPECIES.items()}
#: the first city's kinds, still read from saved documents
ALIASES = {"broadleaf": "oak", "conifer": "spruce", "round": "lime"}
#: variations per species in one city (seeds), so a row is not clones
VARIANTS = 3

DARK_LEAF = {k: sp["greens"][0] for k, sp in treegen.SPECIES.items()}
LIGHT_LEAF = {k: sp["greens"][-1] for k, sp in treegen.SPECIES.items()}


def species(kind):
    kind = ALIASES.get(kind, kind)
    return kind if kind in TREE_KINDS else "oak"


CONIFERS = {"pine", "spruce", "cypress", "poplar"}


def tree_body(kind, seed=1, detail="city", season="Summer"):
    """One grown tree (`treegen`) at the origin, at its natural height —
    branches and leaves, at the detail a whole city can afford. "low" is
    a trunk and a crown (~60 triangles), for a map import's hundreds."""
    kind = species(kind)
    if detail == "low":
        return low_tree(kind, seed)
    return [treegen.build(kind, season=season, detail=detail, seed=seed)]


def low_tree(kind, seed=1):
    """Trunk + crown at natural height: a cone for conifers and poplars,
    a squashed 8-sided ball for broadleaves."""
    h = TREE_KINDS[kind]
    trunk_h = h * (0.25 if kind in CONIFERS else 0.4)
    r = h * (0.14 if kind in CONIFERS else 0.3) * (0.9 + 0.1 * (seed % 3))
    parts = [color(cyl("Trunk", 0, 0, 0, trunk_h + r * 0.3, h * 0.025,
                       h * 0.015, seg=5), "#6b4a32", "Bark")]
    leaf = DARK_LEAF[kind] if seed % 2 else LIGHT_LEAF[kind]
    if kind in CONIFERS:
        parts.append(color(cyl("Crown", 0, 0, trunk_h * 0.6, h - trunk_h * 0.6,
                               r, 0.0, seg=7), leaf, "Leaves"))
    else:
        ball = CadNode("sphere", "Crown", dict(x=0.0, y=0.0, z=0.0, radius=r,
                                               segments=8))
        sc = CadNode("scale", "Crown", dict(x=1.0, y=1.0,
                                            z=(h - trunk_h) / (2 * r)))
        sc.add(ball)
        parts.append(color(move(sc, 0, 0, trunk_h + (h - trunk_h) / 2,
                                "Crown"), leaf, "Leaves"))
    return parts


def _values(rows):
    """Rows as a loop value list. A single row is bracketed once more:
    a lone vector would be iterated element by element."""
    text = ", ".join("[" + ", ".join(_num(v) for v in row) + "]"
                     for row in rows)
    return f"[{text}]" if len(rows) == 1 else text


def build_trees(trees, detail="city", season="Summer") -> CadNode:
    """One loop per species and variant over [x, y, scale, turn, z]
    rows, so a park of fifty trees is a few loops of grown trees."""
    out = group("Trees")
    groups = {}
    for t in trees:
        kind = species(t.get("kind", "oak"))
        natural = TREE_KINDS[kind]
        x, y = _f(t.get("x")), _f(t.get("y"))
        seed = int(t.get("seed", 0)) or 1 + int(abs(x * 7 + y * 13)) % VARIANTS
        groups.setdefault((kind, seed), []).append(
            (x, y, round(max(0.2, _f(t.get("height"), natural) / natural), 2),
             _f(t.get("rz"), 0.0), _f(t.get("z"), 0.0)))
    for (kind, seed), rows in sorted(groups.items()):
        sc = CadNode("scale", "Size", dict(x="p[2]", y="p[2]", z="p[2]"))
        rot = CadNode("rotate", "Turn", dict(x=0.0, y=0.0, z="p[3]"))
        for part in tree_body(kind, seed, detail, season):
            rot.add(part)
        sc.add(rot)
        at = CadNode("translate", "At", dict(x="p[0]", y="p[1]", z="p[4]"))
        at.add(sc)
        label = treegen.SPECIES[kind]["label"]
        lp = CadNode("for_loop", f"{label} ({seed})",
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
    # a fourth value is the ground height under a light (a hilly city)
    at = CadNode("translate", "At", dict(x="p[0]", y="p[1]",
                                         z=f"p[3] + {_num(kerb)}"))
    at.add(rot)
    lp = CadNode("for_loop", "Lights", dict(
        variable="p", start=0.0, end=0.0, step=1.0,
        values=_values([(p[0], p[1], p[2], p[3] if len(p) > 3 else 0.0)
                        for p in points])))
    lp.add(at)
    return group("Street lights", [lp])
