"""Real leaves for the grown trees (Qt-free).

`treegen` used to scatter flat 8-triangle diamonds over the twigs. The
Leaves library (`leafgen`) already draws every species' true blade —
lobed oak, palmate maple, toothed birch, heart-shaped lime, the
drooping willow strand — so a broadleaf tree now carries THOSE, at the
coarse level (`detail="low"`: about 130 triangles, no veins) and
several times life size so a crown still reads as foliage from a
distance.

One template blade per (species, length) is generated once, then copied
onto each twig position by a proper rotation + uniform scale (winding
preserved, so every leaf stays a closed solid). The leaf lies with its
upper face towards the sky, its stalk at the twig and a random roll.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
from functools import lru_cache


#: treegen species -> the leafgen species whose blade it carries
LEAF_OF = {"oak": "oak", "maple": "maple", "lime": "lime",
           "birch": "birch", "cherry": "cherry", "apple": "apple",
           "willow": "willow", "poplar": "poplar", "shrub": "bay"}

#: leaves a whole tree carries, and the size multiplier over the old
#: diamonds, by detail (each blade costs ~130 triangles, so the crown
#: gets a budget rather than a count per twig: a willow has ten times
#: an oak's twigs)
BUDGET = {"high": 950, "medium": 400}
SIZE_K = {"high": 2.1, "medium": 2.5}
#: narrow blades (a willow strand is 12 times as long as wide) need to be
#: bigger still to read as foliage
SIZE_BOOST = {"willow": 2.3, "cherry": 1.3, "poplar": 1.1, "shrub": 1.2}


def per_twig(detail, twigs) -> int:
    """Leaves per twig so the whole crown stays within the budget."""
    return max(4, min(9, round(BUDGET[detail] / max(twigs, 1))))


def shade(hexcol: str, factor: float) -> str:
    """*hexcol* scaled towards black (factor < 1)."""
    r, g, b = (int(hexcol[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(int(c * factor) for c in (r, g, b))


def uses_real_leaves(species, shape, season, detail) -> bool:
    """A broadleaf at high / medium detail: conifers keep needle
    sprays, palms their fronds, a cherry in blossom its petals."""
    if species not in LEAF_OF or detail not in BUDGET:
        return False
    if shape == "blossom" and season == "Spring":
        return False
    return True


@lru_cache(maxsize=64)
def template(species: str, length: float):
    """(points, faces) of one blade of *length* mm, stalk at the
    origin, midrib along +x, upper face +z."""
    from . import leafgen              # leafgen imports treegen
    sp = leafgen.SPECIES[LEAF_OF[species]]
    if sp["kind"] == "palm":
        blade, _v = leafgen.palm_mesh(sp, length / sp["R"], "low")
    else:
        blade, _v = leafgen.blade_mesh(sp, length, "low")
    return ([tuple(p) for p in blade.points],
            [tuple(f) for f in blade.faces])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _unit(a):
    n = math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2]) or 1.0
    return (a[0] / n, a[1] / n, a[2] / n)


def place(mesh, tpl, origin, direction, lean, scale=1.0, roll=0.0):
    """Copy the template blade into *mesh*: stalk at *origin*, midrib
    along *direction*, the upper face towards the sky tipped by *lean*
    (a vector added to "up": outward makes the leaf tilt that way),
    turned *roll* radians about the midrib."""
    d = _unit(direction)
    up = _unit((lean[0], lean[1], 1.0 + lean[2]))
    w = _cross(up, d)
    if w[0] * w[0] + w[1] * w[1] + w[2] * w[2] < 1e-4:   # a vertical leaf
        w = _cross((1.0, 0.0, 0.0), d)
    w = _unit(w)
    n = _cross(d, w)                   # (d, w, n) right-handed
    if roll:
        c, s = math.cos(roll), math.sin(roll)
        w, n = (tuple(w[i] * c + n[i] * s for i in range(3)),
                tuple(-w[i] * s + n[i] * c for i in range(3)))
    pts, faces = tpl
    base = len(mesh.points)
    ox, oy, oz = origin
    for x, y, z in pts:
        x, y, z = x * scale, y * scale, z * scale
        mesh.points.append([round(ox + d[0] * x + w[0] * y + n[0] * z, 1),
                            round(oy + d[1] * x + w[1] * y + n[1] * z, 1),
                            round(oz + d[2] * x + w[2] * y + n[2] * z, 1)])
    mesh.faces.extend([base + a, base + b, base + c] for a, b, c in faces)
