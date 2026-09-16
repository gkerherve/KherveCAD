"""Landscapes (Qt-free): hills, mountains, cliffs, valleys, mesas,
islands, canyons and dunes as coloured solid terrain.

A landscape is a HEIGHT FIELD on a grid (seeded value-noise fBm shaped
by the kind — a peak's falloff, a cliff's wavy escarpment, a valley's
channel), then every grid cell is given a SURFACE by its height and
slope: grass, darker woodland floor, scree, rock in alternating strata
on steep faces, snow above the snow line, sand at the water's edge.

One colour needs one solid, so each surface becomes a closed COLUMN:
its top triangles, the same triangles flat on the base underneath, and
vertical walls down every boundary edge. Where two cells of a surface
touch at a corner only, the boundary would pinch — one vertical edge
shared by four walls, which is not a closed surface — so such cells are
first handed to a neighbouring surface (`_unpinch`) until none is left.
Columns of neighbouring surfaces meet wall to wall, hidden inside the
ground. Water is a flat slab at the water level wherever the ground
dips below it.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
import random

from .model import CadNode

KINDS = ("hills", "mountain", "cliff", "valley", "mesa", "island", "canyon",
         "dunes")

#: surface -> (colour, material)
SURFACES = {
    "grass": ("#6f9e4c", "Matte"),
    "woodland": ("#4f7a3a", "Matte"),
    "scree": ("#9b8c74", "Stone"),
    "rock": ("#8a8176", "Stone"),
    "rock2": ("#76695c", "Stone"),
    "snow": ("#f1f3f4", "Matte"),
    "sand": ("#d8c38f", "Render"),
    "desert": ("#c9955e", "Render"),
    "desert2": ("#b07a4a", "Stone"),
    "riverbed": ("#6b6250", "Stone"),
}
WATER = "#3f7fa3"


# ---------------------------------------------------------------- noise
class Noise:
    """Seeded 2D value noise with fBm and ridged variants."""

    def __init__(self, seed):
        rng = random.Random(seed)
        self.table = [rng.random() for _ in range(512)]
        self.perm = list(range(256))
        rng.shuffle(self.perm)
        self.perm += self.perm

    def _h(self, i, j):
        return self.table[self.perm[(self.perm[i & 255] + j) & 255]]

    def value(self, x, y):
        i, j = math.floor(x), math.floor(y)
        fx, fy = x - i, y - j
        fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        a, b = self._h(i, j), self._h(i + 1, j)
        c, d = self._h(i, j + 1), self._h(i + 1, j + 1)
        return (a + (b - a) * fx) + ((c + (d - c) * fx) - (a + (b - a) * fx)) \
            * fy

    def fbm(self, x, y, octaves=5):
        total, amp, freq, norm = 0.0, 1.0, 1.0, 0.0
        for _ in range(octaves):
            total += amp * self.value(x * freq, y * freq)
            norm += amp
            amp *= 0.5
            freq *= 2.03
        return total / norm

    def ridged(self, x, y, octaves=5):
        total, amp, freq, norm = 0.0, 1.0, 1.0, 0.0
        for _ in range(octaves):
            v = 1.0 - abs(2.0 * self.value(x * freq, y * freq) - 1.0)
            total += amp * v * v
            norm += amp
            amp *= 0.5
            freq *= 2.1
        return total / norm


def _smooth(e0, e1, x):
    t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------- the heights
def height_field(kind, n, length, width, height, seed):
    """(n+1) x (n+1) heights in mm, index [j][i] (y rows, x columns),
    and the water level (None for dry land)."""
    nz = Noise(seed)
    water = None
    rows = []
    for j in range(n + 1):
        v = j / n
        row = []
        for i in range(n + 1):
            u = i / n
            # noise coordinates in units of 70 m: hills and ridges at a
            # landscape's scale, not a rock garden's
            x, y = u * length / 70000.0, v * width / 70000.0
            f = nz.fbm(x * 0.9 + 3.1, y * 0.9 + 7.7)
            if kind == "hills":
                h = height * (0.1 + 0.9 * _smooth(0.2, 0.8, f)) \
                    * (0.8 + 0.2 * nz.fbm(x * 3.0, y * 3.0))
            elif kind == "mountain":
                r = math.hypot(u - 0.5, v - 0.5) * 2.0
                peak = max(0.0, 1.0 - r) ** 1.5
                ridges = nz.ridged(x * 2.2 + 1.3, y * 2.2 + 4.1)
                h = height * (0.04 + 0.96 * peak * (0.6 + 0.4 * ridges))
                h += height * 0.05 * f * (1 - peak)
            elif kind == "cliff":
                edge = 0.45 + 0.12 * (nz.fbm(v * 3.0, 11.0) - 0.5) * 2
                step = _smooth(edge - 0.015, edge + 0.015, u)
                low = height * 0.06 * nz.fbm(x * 2, y * 2)
                top = height * (0.9 + 0.1 * nz.fbm(x * 1.5, y * 1.5))
                h = low + (top - low) * step
            elif kind == "valley":
                meander = 0.5 + 0.12 * math.sin(v * math.pi * 2.2 + seed) \
                    + 0.05 * (f - 0.5)
                dist = abs(u - meander) * 2.0
                h = height * (0.08 + 0.92 * _smooth(0.05, 0.9, dist) ** 0.9)
                h += height * 0.1 * nz.fbm(x * 2, y * 2)
                water = height * 0.1
            elif kind == "mesa":
                r = math.hypot((u - 0.5) * 1.1, (v - 0.5)) * 2.0
                r += 0.25 * (nz.fbm(u * 4, v * 4) - 0.5)
                tier = _smooth(0.62, 0.66, 1 - r) * 0.55 + \
                    _smooth(0.35, 0.39, 1 - r) * 0.45
                h = height * (0.05 + 0.95 * tier) + height * 0.03 * f
            elif kind == "island":
                r = math.hypot(u - 0.5, v - 0.5) * 2.0
                r += 0.35 * (nz.fbm(u * 3 + 5, v * 3 + 1) - 0.5)
                land = _smooth(0.0, 0.85, 1.0 - r)
                h = height * (land ** 1.4) * (0.6 + 0.4 * nz.ridged(x, y))
                water = height * 0.12
            elif kind == "canyon":
                meander = 0.5 + 0.18 * math.sin(v * math.pi * 3.0 + seed) \
                    + 0.08 * (nz.fbm(v * 5, 3.3) - 0.5)
                dist = abs(u - meander)
                wall = _smooth(0.04, 0.09, dist)
                shelf = _smooth(0.16, 0.2, dist)
                h = height * (0.08 + 0.45 * wall + 0.47 * shelf)
                h += height * 0.04 * f
                water = height * 0.12
            else:                                       # dunes
                ridge = math.sin((u * 7 + 0.9 * nz.fbm(u * 3, v * 3)) *
                                 math.pi)
                h = height * (0.5 + 0.35 * ridge * abs(ridge) +
                              0.3 * (f - 0.5))
            row.append(max(h, 0.0))
        rows.append(row)
    return rows, water


def surface_of(kind, h, slope, height, water, noise):
    """The surface a cell wears from its mean height and slope (rise per
    run)."""
    desert = kind in ("mesa", "canyon", "dunes")
    if water is not None and h < water + height * 0.03:
        return "riverbed" if kind in ("valley", "canyon") else "sand"
    if kind == "dunes":
        return "sand" if noise < 0.62 else "desert"
    if kind == "mountain" and h > height * 0.6 and slope < 1.6:
        return "snow"
    if slope > 1.1:
        band = int(h / max(height * 0.07, 1.0)) % 2
        if desert:
            return "desert2" if band else "desert"
        return "rock2" if band else "rock"
    if kind == "mountain" and h > height * 0.72:
        return "snow" if slope < 0.9 else "rock"
    if slope > 0.6:
        return "desert2" if desert else "scree"
    if desert:
        return "desert"
    return "woodland" if noise > 0.58 else "grass"


# ------------------------------------------------------------- the mesh
def _unpinch(cells, n):
    """Hand one cell of every corner-only contact to a neighbour's
    surface until no vertex has a surface on two diagonal cells only."""
    for _round in range(50):
        changed = False
        for j in range(1, n):
            for i in range(1, n):
                a, b = cells[j - 1][i - 1], cells[j - 1][i]
                c, d = cells[j][i - 1], cells[j][i]
                if a == d and b != a and c != a:
                    cells[j][i] = b
                    changed = True
                elif b == c and a != b and d != b:
                    cells[j][i - 1] = a
                    changed = True
        if not changed:
            return cells
    return cells


def build(kind="hills", length=200000.0, width=200000.0, height=30000.0,
          seed=1, cells=48, base_depth=None):
    """The landscape as a group of coloured closed columns plus water."""
    n = max(8, min(int(cells), 128))
    hs, water = height_field(kind, n, length, width, height, seed)
    nz = Noise(seed + 101)
    dx, dy = length / n, width / n
    x0, y0 = -length / 2, -width / 2
    base = -(base_depth if base_depth is not None else 1500.0)
    grid = []
    for j in range(n):
        row = []
        for i in range(n):
            h00, h10 = hs[j][i], hs[j][i + 1]
            h01, h11 = hs[j + 1][i], hs[j + 1][i + 1]
            mean = (h00 + h10 + h01 + h11) / 4
            sx = abs((h10 + h11) - (h00 + h01)) / 2 / dx
            sy = abs((h01 + h11) - (h00 + h10)) / 2 / dy
            slope = math.hypot(sx, sy)
            # woodland patches a few dozen metres across, whatever the grid
            row.append(surface_of(kind, mean, slope, height, water,
                                  nz.fbm(i * dx / 40000.0, j * dy / 40000.0,
                                         3)))
        grid.append(row)
    grid = _unpinch(grid, n)

    group = CadNode("union", kind.capitalize(), {})
    by_surface = {}
    for j in range(n):
        for i in range(n):
            by_surface.setdefault(grid[j][i], []).append((i, j))
    for surf, members in sorted(by_surface.items()):
        colour, material = SURFACES[surf]
        poly = _column(members, hs, x0, y0, dx, dy, base, n)
        c = CadNode("color", surf.capitalize(), dict(color=colour, alpha=1.0,
                                                     material=material))
        c.add(poly)
        group.add(c)
    if water is not None:
        inset = min(length, width) * 0.004 + 100   # clear of the skirts
        w = CadNode("cube", "Water", dict(x=x0 + inset, y=y0 + inset,
                                          z=base + 10,
                                          width=length - 2 * inset,
                                          depth=width - 2 * inset,
                                          height=water - base - 10,
                                          center=False))
        c = CadNode("color", "Water", dict(color=WATER, alpha=1.0,
                                           material="Plastic"))
        c.add(w)
        group.add(c)
    return group


def _column(members, hs, x0, y0, dx, dy, base, n):
    """A closed polyhedron: the cells' top faces, their shadow on the
    base, and walls round the boundary."""
    points, faces = [], []
    top_ids, bottom_ids = {}, {}

    def top(i, j):
        k = (i, j)
        if k not in top_ids:
            top_ids[k] = len(points)
            points.append([round(x0 + i * dx, 1), round(y0 + j * dy, 1),
                           round(hs[j][i], 1)])
        return top_ids[k]

    def bottom(i, j):
        k = (i, j)
        if k not in bottom_ids:
            bottom_ids[k] = len(points)
            points.append([round(x0 + i * dx, 1), round(y0 + j * dy, 1),
                           round(base, 1)])
        return bottom_ids[k]

    def tri_ccw(a, b, c):                     # OpenSCAD: clockwise outside
        faces.append([a, c, b])

    edges = {}
    for i, j in members:
        a, b, c, d = (i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)
        for t in ((a, b, c), (a, c, d)):
            tri_ccw(top(*t[0]), top(*t[1]), top(*t[2]))       # up
            faces.append([bottom(*t[0]), bottom(*t[1]), bottom(*t[2])])
        for e in ((a, b), (b, c), (c, d), (d, a)):             # cell edges
            edges[e] = edges.get(e, 0) + 1
    for (p, q), _count in edges.items():
        if (q, p) in edges:
            continue                                  # interior edge
        # p -> q runs counter-clockwise round the region: outside is on
        # the right; wall p, q down to the base
        tp, tq = top(*p), top(*q)
        bp, bq = bottom(*p), bottom(*q)
        tri_ccw(tq, tp, bp)
        tri_ccw(tq, bp, bq)
    return CadNode("polyhedron", "Ground", dict(points=points, faces=faces))


def triangle_count(node):
    return sum(len(p.params.get("faces") or []) for p in node.walk()
               if p.type == "polyhedron")
