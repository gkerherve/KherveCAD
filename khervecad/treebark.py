"""Bark and trunks for the grown trees (Qt-free).

`treegen` used to give every branch, the trunk included, a plain
6-sided tapered tube: a trunk read as a pipe. This module makes it a
trunk:

- the path is **smoothed** (Catmull-Rom) so a limb bends instead of
  kinking between its few growth segments;
- the trunk gets **many more sides** and a **furrowed bark**: three
  sine harmonics round the circumference that drift and turn along the
  height (deep for an oak, a smooth skin for a birch), fading towards
  the tip;
- the foot **flares** into a few **buttress roots** (a lobed swelling
  that dies out over about three trunk radii);
- every side limb starts with a **collar** — the swelling where a
  branch leaves its parent — so limbs grow out of the trunk instead of
  being pushed into it;
- a silver birch carries its dark horizontal **lenticels**, small
  closed lozenges lying on the bark.

Everything is written through `treegen.Mesh.tube`'s `radial` hook, so a
trunk is still ONE closed tube (no shared vertices with anything else).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
import random

#: species -> (ridge depth as a fraction of the radius, root flare,
#: buttress lobes). Anything not listed uses DEFAULT_STYLE.
STYLES = {
    "oak": (0.17, 1.3, 5), "maple": (0.11, 0.8, 4),
    "lime": (0.09, 0.7, 4), "birch": (0.012, 0.3, 3),
    "cherry": (0.05, 0.4, 3), "apple": (0.12, 0.7, 4),
    "willow": (0.16, 1.3, 5), "poplar": (0.13, 0.6, 4),
    "pine": (0.13, 0.8, 4), "spruce": (0.06, 0.4, 5),
    "cypress": (0.05, 0.3, 3), "palm": (0.0, 0.0, 3),
    "shrub": (0.03, 0.0, 3),
}
DEFAULT_STYLE = (0.06, 0.4, 4)

#: detail -> (trunk sides, limb sides, extra rings per growth segment);
#: "city" keeps the old cheap tubes
SIDES = {"high": (14, 8, 4), "medium": (10, 6, 3)}


def style_of(species: str):
    return STYLES.get(species, DEFAULT_STYLE)


# ----------------------------------------------------------- smoothing
def smooth(path, radii, sub):
    """*path* / *radii* with *sub* points per segment on a Catmull-Rom
    curve through the given points (they stay on it)."""
    if sub <= 1 or len(path) < 3:
        return list(path), list(radii)
    out_p, out_r = [], []
    n = len(path)
    for i in range(n - 1):
        p0, p1 = path[max(i - 1, 0)], path[i]
        p2, p3 = path[i + 1], path[min(i + 2, n - 1)]
        for k in range(sub):
            t = k / sub
            t2, t3 = t * t, t * t * t
            out_p.append(tuple(
                0.5 * ((2 * p1[c]) + (-p0[c] + p2[c]) * t
                       + (2 * p0[c] - 5 * p1[c] + 4 * p2[c] - p3[c]) * t2
                       + (-p0[c] + 3 * p1[c] - 3 * p2[c] + p3[c]) * t3)
                for c in range(3)))
            out_r.append(radii[i] + (radii[i + 1] - radii[i]) * t)
    out_p.append(tuple(path[-1]))
    out_r.append(radii[-1])
    return out_p, out_r


# --------------------------------------------------------- the surface
def radial(species, level, count, floor_z, r0, rng):
    """`factor(i, angle, z) -> multiplier` for ring *i* of *count*: bark
    furrows, the root flare (trunk only) and the collar (side limbs).
    *floor_z* is the height of the first ring, *r0* the base radius."""
    ridge, flare, lobes = style_of(species)
    if level > 1:
        ridge = 0.0
    ph = [rng.uniform(0, 2 * math.pi) for _ in range(4)]
    harm = (3 + rng.randrange(3), 6 + rng.randrange(4),
            11 + rng.randrange(5))
    last = max(count - 1, 1)

    def factor(i, a, z=0.0):
        t = i / last
        m = 1.0
        if ridge:
            fade = 1.0 - 0.55 * t
            v = (0.5 * math.sin(harm[0] * a + ph[0] + 3.0 * t)
                 + 0.3 * math.sin(harm[1] * a + ph[1] - 5.0 * t)
                 + 0.2 * math.sin(harm[2] * a + ph[2] + 11.0 * t))
            m += ridge * fade * v
        if level == 0 and flare:
            w = math.exp(-(z - floor_z) / max(r0 * 2.6, 1.0))
            buttress = max(0.0, math.cos(lobes * a + ph[3])) ** 2
            m += flare * w * (0.3 + 0.7 * buttress)
        elif level >= 1 and floor_z > r0 * 3.0:      # off the ground
            m += 0.55 * math.exp(-i * 1.4)          # the collar
        return m
    return factor


def limb(mesh, branch, species, sides, sub, rng):
    """One branch as a smoothed, furrowed closed tube; returns the
    smoothed (path, radii)."""
    path, radii = smooth(branch.path, branch.radii, sub)
    factor = radial(species, branch.level, len(path), path[0][2],
                    branch.radii[0], rng)
    mesh.tube(path, radii, sides,
              radial=lambda i, a: factor(i, a, path[i][2]))
    return path, radii


# ------------------------------------------------------------ lenticels
def lenticels(mesh, rng, path, radii, height, count=64):
    """The birch's dark horizontal marks: small closed lozenges lying
    on the trunk, at random heights and angles."""
    n = len(path)
    if n < 3:
        return
    for _ in range(count):
        f = rng.uniform(0.04, 0.72) * (n - 1)
        i = min(int(f), n - 2)
        k = f - i
        p = tuple(path[i][c] + (path[i + 1][c] - path[i][c]) * k
                  for c in range(3))
        r = radii[i] + (radii[i + 1] - radii[i]) * k
        a = rng.uniform(0, 2 * math.pi)
        out = (math.cos(a), math.sin(a), 0.0)
        tan = (-math.sin(a), math.cos(a), 0.0)
        at = (p[0] + out[0] * r * 0.98, p[1] + out[1] * r * 0.98, p[2])
        length = rng.uniform(0.05, 0.16) * r * 2 * math.pi * 0.5 + 25.0
        half = tuple(tan[c] * length / 2 for c in range(3))
        h = max(height * 0.0015, 4.0)
        pts = [tuple(at[c] - half[c] for c in range(3)),
               (at[0], at[1], at[2] - h * 1.4),
               tuple(at[c] + half[c] for c in range(3)),
               (at[0], at[1], at[2] + h * 1.4),
               tuple(at[c] + out[c] * h * 0.9 for c in range(3)),
               tuple(at[c] - out[c] * h * 1.6 for c in range(3))]
        mesh.convex(pts, [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4),
                          (1, 0, 5), (2, 1, 5), (3, 2, 5), (0, 3, 5)])


def seeded(species, seed, salt):
    return random.Random(f"bark:{species}:{seed}:{salt}")
