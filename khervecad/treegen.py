"""Procedural trees (Qt-free): a real branching skeleton with bark and
individual leaves, for the Trees library and the City Builder.

A tree is grown, not assembled from balls:

- the SKELETON is a set of branches, each a gently bending polyline whose
  radius tapers from its base; children leave a parent along its length
  (not only at the tip), turned round it by the golden angle and tilted
  out by the species' branch angle, pulled down by gravity (a willow's
  strands hang) or up towards the light; depth, count, length and radius
  ratios come from `SPECIES`. Conifers grow a straight leader with whorls
  of drooping branches; a palm a curved ringed trunk and arching fronds.
- each branch becomes ONE closed tube — rings carried along the
  polyline by parallel transport, capped at both ends — so bark
  triangles stay few and no two pieces share a vertex;
- LEAVES: a broadleaf at high / medium detail carries the Leaves
  library's real blades in bunches (`treeleaves`); the rest are small
  closed diamonds (a flat bipyramid, 8 triangles; a 4-triangle
  tetrahedron at city detail) set along the last twigs, facing outward,
  in several greens; blossom, needles, fronds and fruit are the same
  pieces in other shapes and colours. Trunks and limbs get their bark
  from `treebark` (smoothed, furrowed, flared foot, collars).

Everything is written as `polyhedron` nodes built point by point (no
welding: coincident vertices of neighbouring pieces would pair one edge
three times and fail validation) — a whole tree is a handful of nodes
whatever its leaf count, and it previews exactly. `tree_node` caches by
(species, height, season, detail, seed).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import copy
import math
import random
from functools import lru_cache

from . import treebark, treeleaves
from .model import CadNode

GOLDEN = math.radians(137.5)

#: species -> growth parameters. Lengths are fractions of the height.
#:   trunk     fraction of height the trunk runs before it branches
#:   radius    trunk radius at the base, fraction of height
#:   depth     branching levels below the trunk
#:   children  children per branch at each level
#:   angle     degrees a child leans away from its parent
#:   ratio     child length / parent length
#:   taper     child base radius / parent radius at that point
#:   gravity   pull per unit length (+ down, - up)
#:   bend      random bend per segment, degrees
#:   crown     "round" | "cone" | "column" | "weeping" | "palm" | "shrub"
#:   leaf      (length, width) in mm at 10 m, "broad"/"needle"/"frond"
#:   leaves    leaves per twig (at full detail)
SPECIES = {
    "oak": dict(label="Oak", trunk=0.32, radius=0.035, depth=3,
                children=(5, 4, 3), angle=(48, 42, 38), ratio=(0.62, 0.55,
                                                               0.5),
                taper=0.62, gravity=0.18, bend=16, crown="round",
                leaf=(150, 90, "broad"), leaves=9, height=14000.0,
                bark="#5e4a3a", greens=("#3f6b2e", "#4f7d35", "#5f8e3c")),
    "maple": dict(label="Maple", trunk=0.34, radius=0.028, depth=3,
                  children=(5, 4, 3), angle=(40, 38, 35),
                  ratio=(0.6, 0.55, 0.5), taper=0.6, gravity=0.08,
                  bend=12, crown="round", leaf=(160, 150, "broad"),
                  leaves=8, height=12000.0, bark="#6a5a4c",
                  greens=("#4a7f34", "#5b913c", "#6aa046")),
    "lime": dict(label="Lime / linden (street tree)", trunk=0.38,
                 radius=0.026, depth=3, children=(4, 4, 3),
                 angle=(34, 36, 34), ratio=(0.6, 0.55, 0.5), taper=0.6,
                 gravity=0.05, bend=10, crown="cone", leaf=(120, 110, "broad"),
                 leaves=8, height=10000.0, bark="#5d5248",
                 greens=("#557f36", "#66923f", "#78a448")),
    "birch": dict(label="Silver birch", trunk=0.30, radius=0.017, depth=3,
                  children=(6, 3, 3), angle=(36, 42, 45),
                  ratio=(0.5, 0.55, 0.55), taper=0.55, gravity=0.35,
                  bend=14, crown="column", leaf=(90, 60, "broad"), leaves=9,
                  height=11000.0, bark="#e9e5dc",
                  greens=("#6d9c3c", "#82ad48", "#95bc55")),
    "cherry": dict(label="Cherry blossom", trunk=0.28, radius=0.03, depth=3,
                   children=(5, 3, 3), angle=(55, 45, 40),
                   ratio=(0.62, 0.55, 0.5), taper=0.6, gravity=0.12,
                   bend=18, crown="round", leaf=(80, 70, "blossom"),
                   leaves=10, height=7000.0, bark="#4b3a33",
                   greens=("#f4bfd0", "#f7d3df", "#eaa2bb")),
    "apple": dict(label="Apple tree", trunk=0.24, radius=0.035, depth=3,
                  children=(5, 3, 3), angle=(58, 48, 42),
                  ratio=(0.6, 0.55, 0.5), taper=0.6, gravity=0.25, bend=22,
                  crown="round", leaf=(90, 55, "broad"), leaves=8,
                  height=5000.0, bark="#5a4a3c", fruit="#c0392b",
                  greens=("#4c7a32", "#5a8a3a", "#6a9a44")),
    "willow": dict(label="Weeping willow", trunk=0.30, radius=0.035,
                   depth=3, children=(5, 4, 5), angle=(55, 45, 30),
                   ratio=(0.55, 0.7, 0.9), taper=0.55, gravity=1.6, bend=8,
                   crown="weeping", leaf=(130, 22, "broad"), leaves=12,
                   height=11000.0, bark="#5b4f40",
                   greens=("#8aa845", "#9bb553", "#a9c160")),
    "poplar": dict(label="Lombardy poplar", trunk=0.12, radius=0.022,
                   depth=2, children=(18, 4), angle=(14, 20),
                   ratio=(0.35, 0.5), taper=0.5, gravity=-0.4, bend=6,
                   crown="column", leaf=(90, 80, "broad"), leaves=9,
                   height=20000.0, bark="#6b6152",
                   greens=("#46703a", "#557f42", "#63904b")),
    "pine": dict(label="Pine tree (Scots pine)", trunk=0.62, radius=0.022, depth=2,
                 children=(9, 5), angle=(62, 45), ratio=(0.32, 0.45),
                 taper=0.5, gravity=0.1, bend=18, crown="round",
                 leaf=(110, 14, "needle"), leaves=14, height=18000.0,
                 crown_start=0.72, tufts=True,
                 bark="#8a5a3c", greens=("#2f5a3a", "#3b6a42", "#27503a")),
    "spruce": dict(label="Spruce / fir tree (Norway spruce)", trunk=1.0, radius=0.02, depth=2,
                   children=(34, 6), angle=(95, 50), ratio=(0.34, 0.4),
                   taper=0.45, gravity=0.35, bend=6, crown="cone",
                   leaf=(70, 12, "needle"), leaves=12, height=16000.0,
                   bark="#4d3a2c", greens=("#1f4a33", "#27573a", "#2f6040")),
    "cypress": dict(label="Italian cypress", trunk=1.0, radius=0.016,
                    depth=2, children=(24, 4), angle=(22, 25),
                    ratio=(0.12, 0.5), taper=0.45, gravity=-0.6, bend=5,
                    tufts=True, spread=0.045, crown_start=0.08,
                    crown="column", leaf=(60, 16, "needle"), leaves=10,
                    height=12000.0, bark="#5a4a3a",
                    greens=("#264a2e", "#2e5534", "#1f3f28")),
    "palm": dict(label="Palm tree", trunk=1.0, radius=0.022, depth=0,
                 children=(), angle=(), ratio=(), taper=0.9, gravity=0.0,
                 bend=0, crown="palm", leaf=(700, 70, "frond"), leaves=0,
                 height=9000.0, bark="#8b7355",
                 greens=("#4c7d2e", "#5a8d36", "#3f6d27")),
    "shrub": dict(label="Shrub / bush", trunk=0.02, radius=0.03, depth=2,
                  children=(16, 4), spread=0.14, angle=(40, 45), ratio=(0.8, 0.55),
                  taper=0.6, gravity=0.1, bend=20, crown="shrub",
                  leaf=(80, 50, "broad"), leaves=9, height=1500.0,
                  bark="#5a4a3a", greens=("#3f6e30", "#4d7e37", "#5b8e40")),
}

#: leaf colours by season for deciduous trees (evergreens ignore it)
SEASONS = {
    "Summer": None,
    "Spring": ("#7fb24a", "#93c257", "#a7d066"),
    "Autumn": ("#c0612b", "#d58b2f", "#b8442a"),
    "Winter": (),                      # bare
}
EVERGREEN = {"pine", "spruce", "cypress", "palm"}

#: detail -> (leaf fraction, branch sides, depth cut, bipyramid leaves)
DETAIL = {"high": (1.0, 6, 0, True), "medium": (0.45, 5, 0, True),
          "city": (0.3, 4, 0, False)}
#: city detail: leaf size and cloud spread multipliers — fewer, much
#: bigger leaves spread wider, so a crown still reads as a mass
CITY_LEAF, CITY_SPREAD = 3.6, 2.2
#: at most this many foliage clumps a city tree (32 faces each)
CITY_CLUMPS = 18


# -------------------------------------------------------------- vectors
def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _norm(a):
    length = math.sqrt(_dot(a, a)) or 1.0
    return (a[0] / length, a[1] / length, a[2] / length)


def _rotate(v, axis, angle):
    """Rodrigues: *v* turned *angle* radians about unit *axis*."""
    c, s = math.cos(angle), math.sin(angle)
    k = axis
    return _add(_add(_mul(v, c), _mul(_cross(k, v), s)),
                _mul(k, _dot(k, v) * (1 - c)))


def _perp(d):
    """A unit vector perpendicular to *d*."""
    ref = (0.0, 0.0, 1.0) if abs(d[2]) < 0.9 else (1.0, 0.0, 0.0)
    return _norm(_cross(d, ref))


# ---------------------------------------------------------------- mesh
class Mesh:
    """Closed pieces written straight into points/faces (clockwise from
    outside, OpenSCAD's order)."""

    def __init__(self):
        self.points, self.faces = [], []

    def piece(self, pts, tris):
        """*tris* index *pts*, counter-clockwise seen from outside."""
        base = len(self.points)
        self.points.extend([round(p[0], 1), round(p[1], 1), round(p[2], 1)]
                           for p in pts)
        self.faces.extend([base + a, base + c, base + b] for a, b, c in tris)

    def convex(self, pts, tris):
        """Like `piece`, winding each triangle outward from the centre —
        for convex pieces built without care for order."""
        n = len(pts)
        cx = sum(p[0] for p in pts) / n
        cy = sum(p[1] for p in pts) / n
        cz = sum(p[2] for p in pts) / n
        fixed = []
        for a, b, c in tris:
            nrm = _cross(_sub(pts[b], pts[a]), _sub(pts[c], pts[a]))
            mid = _mul(_add(_add(pts[a], pts[b]), pts[c]), 1 / 3)
            out = _dot(nrm, _sub(mid, (cx, cy, cz)))
            fixed.append((a, b, c) if out >= 0 else (a, c, b))
        self.piece(pts, fixed)

    def tube(self, path, radii, sides, radial=None):
        """A closed tube through *path* (points), radius per point:
        rings by parallel transport, capped with fans. *radial*
        (ring index, angle) -> multiplier roughens the surface (bark)."""
        if len(path) < 2:
            return
        d = _norm(_sub(path[1], path[0]))
        u = _perp(d)
        rings = []
        for i, p in enumerate(path):
            if i > 0:
                nd = _norm(_sub(path[i], path[i - 1]) if i == len(path) - 1
                           else _sub(path[i + 1], path[i - 1]))
                axis = _cross(d, nd)
                s = math.sqrt(_dot(axis, axis))
                if s > 1e-9:
                    u = _rotate(u, _mul(axis, 1 / s),
                                math.atan2(s, _dot(d, nd)))
                d = nd
            v = _cross(d, u)
            r = max(radii[i], 0.5)
            rings.append([
                _add(p, _add(_mul(u, math.cos(a) * r * (
                    radial(i, a) if radial else 1.0)),
                    _mul(v, math.sin(a) * r * (
                        radial(i, a) if radial else 1.0))))
                for a in (k * 2 * math.pi / sides for k in range(sides))])
        pts = [q for ring in rings for q in ring]
        tris = []
        for i in range(len(rings) - 1):
            for k in range(sides):
                a, b = i * sides + k, i * sides + (k + 1) % sides
                c, e = a + sides, b + sides
                tris += [(a, b, e), (a, e, c)]
        first, last = len(pts), len(pts) + 1
        pts += [path[0], path[-1]]
        top = (len(rings) - 1) * sides
        for k in range(sides):
            tris.append((first, (k + 1) % sides, k))
            tris.append((last, top + k, top + (k + 1) % sides))
        self.piece(pts, tris)

    def leaf(self, p, d, w, length, width, thick, full=True):
        """A flat leaf from *p* along *d*, *w* across: a bipyramid
        diamond (8 triangles) or a tetrahedron (4)."""
        n = _norm(_cross(d, w))
        if full:
            mid = _add(p, _mul(d, length * 0.45))
            pts = [p, _add(mid, _mul(w, width / 2)), _add(p, _mul(d, length)),
                   _add(mid, _mul(w, -width / 2)), _add(mid, _mul(n, thick)),
                   _add(mid, _mul(n, -thick))]
            tris = [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4),
                    (1, 0, 5), (2, 1, 5), (3, 2, 5), (0, 3, 5)]
            self.convex(pts, tris)
        else:
            mid = _add(p, _mul(d, length * 0.5))
            pts = [_add(p, _mul(w, width / 2)), _add(p, _mul(w, -width / 2)),
                   _add(p, _mul(d, length)), _add(mid, _mul(n, thick))]
            self.convex(pts, [(0, 1, 2), (0, 3, 1), (1, 3, 2), (2, 3, 0)])

    def blob(self, c, r):
        """A small octahedron (fruit, blossom heart)."""
        pts = [_add(c, (r, 0, 0)), _add(c, (-r, 0, 0)), _add(c, (0, r, 0)),
               _add(c, (0, -r, 0)), _add(c, (0, 0, r)), _add(c, (0, 0, -r))]
        tris = [(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4),
                (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)]
        self.convex(pts, tris)

    def clump(self, rng, c, r):
        """An irregular ball of foliage: an octahedron split once (32
        faces), each vertex pushed in or out at random — a leaf mass
        that is not a sphere."""
        base = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1),
                (0, 0, -1)]
        faces = [(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4),
                 (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)]
        verts = list(base)
        mids = {}

        def mid(a, b):
            key = (min(a, b), max(a, b))
            if key not in mids:
                mids[key] = len(verts)
                verts.append(_norm(_mul(_add(verts[a], verts[b]), 0.5)))
            return mids[key]
        split = []
        for a, b, c2 in faces:
            ab, bc, ca = mid(a, b), mid(b, c2), mid(c2, a)
            split += [(a, ab, ca), (ab, b, bc), (ca, bc, c2), (ab, bc, ca)]
        pts = [_add(c, _mul((v[0], v[1], v[2] * 0.8),
                            r * rng.uniform(0.75, 1.15))) for v in verts]
        self.convex(pts, split)

    def node(self, name):
        return CadNode("polyhedron", name, dict(points=self.points,
                                                faces=self.faces))


# -------------------------------------------------------------- growth
class _Branch:
    __slots__ = ("path", "radii", "level", "length")

    def __init__(self, path, radii, level, length):
        self.path, self.radii, self.level = path, radii, level
        self.length = length


def _grow_path(rng, start, direction, length, r0, r1, sp, segs,
               floor=-1e9):
    """A bending polyline from *start*: each step turns a little at
    random and bends under gravity (or towards the light), never below
    *floor*."""
    path, radii = [start], [r0]
    d = _norm(direction)
    step = length / segs
    p = start
    for i in range(segs):
        bend = math.radians(sp["bend"])
        d = _rotate(d, _perp(d), rng.uniform(-bend, bend))
        d = _norm(_add(d, (0.0, 0.0, -sp["gravity"] * step / max(length,
                                                                  1.0))))
        p = _add(p, _mul(d, step))
        if p[2] < floor:                    # nothing grows into the ground
            p = (p[0], p[1], floor)
            d = _norm((d[0], d[1], max(d[2], 0.0)))
        path.append(p)
        radii.append(r0 + (r1 - r0) * (i + 1) / segs)
    return path, radii


def _point_at(branch, t):
    """Point, direction and radius a fraction *t* along a branch."""
    path = branch.path
    f = t * (len(path) - 1)
    i = min(int(f), len(path) - 2)
    k = f - i
    p = _add(path[i], _mul(_sub(path[i + 1], path[i]), k))
    d = _norm(_sub(path[i + 1], path[i]))
    r = branch.radii[i] + (branch.radii[i + 1] - branch.radii[i]) * k
    return p, d, r


def _envelope(sp, z_frac):
    """How far a branch may reach at a height (fraction of the tree),
    as a fraction of the height — gives each crown its silhouette."""
    crown = sp["crown"]
    if crown == "cone":
        return max(0.05, 0.42 * (1.0 - z_frac))
    if crown == "column":
        return 0.16 * math.sin(math.pi * min(max(z_frac, 0.0), 1.0)) + 0.03
    if crown == "shrub":
        return 0.7
    return 0.55


def grow(species: str, height: float, seed: int = 1, depth_cut: int = 0):
    """The skeleton: a list of `_Branch`, level 0 the trunk."""
    sp = SPECIES[species]
    rng = random.Random(f"{species}:{seed}")
    h = float(height)
    trunk_len = h * (sp["trunk"] if sp["crown"] not in ("cone", "column")
                     or species not in ("spruce", "cypress") else 0.97)
    lean = (rng.uniform(-0.06, 0.06), rng.uniform(-0.06, 0.06), 1.0)
    r0 = h * sp["radius"]
    if sp["crown"] == "shrub":
        branches = []
        base = _Branch([(0, 0, 0), (0, 0, 10)], [r0, r0], 0, 10.0)
        branches.append(base)
        parents = []
        n = sp["children"][0]
        for i in range(n):
            a = i * GOLDEN
            tilt = math.radians(rng.uniform(20, 60))
            d = (math.cos(a) * math.sin(tilt), math.sin(a) * math.sin(tilt),
                 math.cos(tilt))
            path, radii = _grow_path(rng, (0, 0, 0), d, h * 0.75, r0 * 0.5,
                                     r0 * 0.15, sp, 4)
            b = _Branch(path, radii, 1, h * 0.75)
            branches.append(b)
            parents.append(b)
        _children(rng, sp, branches, parents, 2, h, depth_cut)
        return _fit_height(branches, h)
    segs = 8 if sp["crown"] in ("cone", "column") else 5
    path, radii = _grow_path(rng, (0.0, 0.0, 0.0), lean, trunk_len, r0,
                             r0 * (0.25 if trunk_len > 0.9 * h else 0.6),
                             dict(sp, gravity=0.0, bend=sp["bend"] * 0.3),
                             segs)
    trunk = _Branch(path, radii, 0, trunk_len)
    branches = [trunk]
    if sp["crown"] == "palm":
        return branches
    _children(rng, sp, branches, [trunk], 1, h, depth_cut)
    return _fit_height(branches, h)


def _fit_height(branches, h):
    """Scale the grown skeleton about its foot so its top is at *h*
    (the crown's own leaves add a little on top): growth rules give the
    shape, the species' height gives the size."""
    top = max(p[2] for b in branches for p in b.path)
    k = (h * 0.93) / top if top > 1.0 else 1.0
    for b in branches:
        b.path = [_mul(p, k) for p in b.path]
        b.radii = [r * min(k, 1.6) for r in b.radii]
        b.length *= k
    return branches


def _children(rng, sp, branches, parents, level, h, depth_cut):
    depth = sp["depth"] - depth_cut
    if level > depth:
        return
    count = sp["children"][level - 1]
    angle = sp["angle"][level - 1]
    ratio = sp["ratio"][level - 1]
    nxt = []
    for parent in parents:
        whorl = sp["crown"] in ("cone", "column") and level == 1
        n = max(1, int(round(count * (1.0 if parent.level == 0 else
                                      rng.uniform(0.7, 1.2)))))
        if depth_cut and level > 1:
            n = max(1, n // 2)
        phase = rng.uniform(0, 2 * math.pi)
        for i in range(n):
            if whorl:
                t = 0.18 + 0.8 * i / max(n - 1, 1)
            elif parent.level == 0:
                start = sp.get("crown_start", 0.45)
                t = 1.0 - (1.0 - start) * (i / max(n, 1)) ** 1.1
            else:
                t = rng.uniform(0.35, 1.0)
            p, d, r = _point_at(parent, min(t, 0.999))
            around = _perp(d)
            around = _rotate(around, d, phase + i * GOLDEN)
            tilt = math.radians(angle * rng.uniform(0.8, 1.2))
            cd = _norm(_add(_mul(d, math.cos(tilt)),
                            _mul(around, math.sin(tilt))))
            z_frac = p[2] / h
            reach = _envelope(sp, z_frac) * h
            length = parent.length * ratio * rng.uniform(0.8, 1.15)
            if parent.level == 0:
                length = min(max(length, reach * 0.9), reach * 1.2) if \
                    sp["crown"] in ("cone", "column") else \
                    min(parent.length * 1.6 * ratio + h * 0.18, reach)
                if sp["crown"] == "cone":
                    length = reach * rng.uniform(0.85, 1.05)
            rb = max(r * sp["taper"], h * 0.0008)
            segs = 5 if level == 1 else 3
            grow_sp = sp
            if sp["crown"] == "weeping":
                if level == depth:           # only the strands hang
                    segs, length = 7, length * 1.7
                else:                        # the limbs arch up and out
                    grow_sp = dict(sp, gravity=-0.25)
            path, radii = _grow_path(rng, p, cd, length, rb, rb * 0.35,
                                     grow_sp, segs, floor=h * 0.06)
            b = _Branch(path, radii, level, length)
            branches.append(b)
            nxt.append(b)
    _children(rng, sp, branches, nxt, level + 1, h, depth_cut)


# --------------------------------------------------------------- build
def _colour(node, colour, material, name):
    c = CadNode("color", name, dict(color=colour, alpha=1.0,
                                    material=material))
    c.add(node)
    return c


def build(species: str, height: float = 0.0, season: str = "Summer",
          detail: str = "high", seed: int = 1) -> CadNode:
    """The whole tree as a group: bark, leaves in three greens, and
    blossom / fruit where the species has them."""
    return copy.deepcopy(_build(species, float(height or 0.0), season,
                                detail, int(seed)))


@lru_cache(maxsize=64)
def _build(species, height, season, detail, seed):
    sp = SPECIES[species]
    h = height or sp["height"]
    frac, sides, cut, full = DETAIL.get(detail, DETAIL["high"])
    rng = random.Random(f"leaves:{species}:{seed}")
    bark, marks = Mesh(), Mesh()
    greens = sp["greens"]
    if species not in EVERGREEN and season in SEASONS and \
            SEASONS[season] is not None and species != "cherry":
        greens = SEASONS[season]
    if species == "cherry" and season == "Summer":
        greens = ("#4f7d35", "#5f8e3c", "#6a9a44")
    leaves = [Mesh(), Mesh(), Mesh()]
    extras, mass = Mesh(), Mesh()
    scale = h / 10000.0
    ll, lw, shape = sp["leaf"]
    ll, lw = ll * max(scale, 0.35) ** 0.5, lw * max(scale, 0.35) ** 0.5
    if detail == "city":                       # fewer, bigger leaves
        ll, lw = ll * 2.6, lw * 2.6
    elif detail == "medium":
        ll, lw = ll * 1.5, lw * 1.5
    thick = max(lw * 0.08, 3.0)

    if sp["crown"] == "palm":
        _palm(rng, sp, h, bark, leaves, sides, full, frac)
    else:
        branches = grow(species, h, seed, cut)
        depth = max(b.level for b in branches)
        rich = treebark.SIDES.get(detail)       # furrowed bark, flared foot
        for b in branches:
            s = sides if b.level < 2 else max(3, sides - 2)
            if detail == "city" and b.level >= max(2, depth) and \
                    sp["crown"] != "weeping":
                continue                     # twigs hide in the leaves
            if rich and b.level <= 1:
                trunk_sides, limb_sides, sub = rich
                path, radii = treebark.limb(
                    bark, b, species,
                    trunk_sides if b.level == 0 else limb_sides,
                    sub if b.level == 0 else max(2, sub // 2),
                    treebark.seeded(species, seed, len(bark.faces)))
                if b.level == 0 and species == "birch":
                    treebark.lenticels(marks, treebark.seeded(
                        species, seed, "marks"), path, radii, h)
            else:
                bark.tube(b.path, b.radii, s)
        if greens:
            _foliage(rng, sp, species, branches, h, leaves, extras, detail,
                     full, season, mass)
    group = CadNode("union", f"{sp['label']}", {})
    group.add(_colour(bark.node("Branches"), sp["bark"], "Bark", "Bark"))
    if marks.faces:
        group.add(_colour(marks.node("Lenticels"), "#2b2a28", "Matte",
                          "Bark marks"))
    for i, m in enumerate(leaves):
        if m.faces:
            mat = "Leaves" if shape != "blossom" or season != "Spring" and \
                species != "cherry" else "Matte"
            group.add(_colour(m.node("Leaves"), greens[i % len(greens)],
                              mat, "Leaves"))
    if mass.faces:                    # the dense core the real leaves sit on
        group.add(_colour(mass.node("Foliage mass"),
                          treeleaves.shade(greens[0], 0.72), "Leaves",
                          "Foliage mass"))
    if extras.faces:
        group.add(_colour(extras.node("Fruit"), sp["fruit"], "Plastic",
                          "Fruit"))
    return group


#: leaves around each twig at full detail, and the leaf size as a
#: fraction of the tree's height, by leaf shape
FOLIAGE = {"broad": (60, 0.02), "blossom": (70, 0.018),
           "needle": (26, 0.03)}
#: at most this many leaf bunches a crown (one per outer twig)
MAX_BUNCHES = 150
#: the smallest leaf, mm — a shrub's leaves at 2 % of 1.5 m vanished
MIN_LEAF = 70.0


def weeping_leaf(sp):
    return sp["crown"] == "weeping"


def _foliage(rng, sp, species, branches, h, leaves, extras, detail, full,
             season, mass=None):
    """Leaves as a CLOUD round every twig — a real crown is thousands of
    leaves in clumps, which the eye reads as mass with light between.
    Broad leaves fill a ball round the twig's outer half, facing out
    and a little down; needles lie in flat sprays along conifer
    branches, pointing out and drooping; a willow's hang along its
    strands."""
    ll, lw, shape = sp["leaf"]
    per, size = FOLIAGE.get(shape, FOLIAGE["broad"])
    frac = DETAIL.get(detail, DETAIL["high"])[0]
    grow_k = {"high": 1.0, "medium": 1.35, "city": CITY_LEAF}.get(detail, 1.0)
    spread_k = CITY_SPREAD if detail == "city" else 1.0
    length = max(h * size, MIN_LEAF) * grow_k
    width = length * (lw / ll)
    if weeping_leaf(sp):
        width = max(width, length * 0.3)
    if shape == "needle":
        width = max(width, length * 0.4)
    thick = max(width * 0.06, 4.0)
    depth = max(b.level for b in branches)
    twigs = [b for b in branches if b.level == depth]
    n = max(2, int(round(per * frac)))
    if detail == "city" and shape != "needle":
        # clumps of foliage at the twigs, a few loose leaves round them
        if len(twigs) > CITY_CLUMPS:
            twigs = rng.sample(twigs, CITY_CLUMPS)
        for b in twigs:
            p, d, _r = _point_at(b, 0.85)
            rad = h * 0.075 * rng.uniform(0.8, 1.2)
            c = _add(p, _mul(d, rad * 0.4))
            c = (c[0], c[1], max(c[2], rad * 0.9))    # never in the ground
            leaves[rng.randrange(3)].clump(rng, c, rad)
            for _k in range(3):
                off = _mul(_norm((rng.gauss(0, 1), rng.gauss(0, 1),
                                  rng.gauss(0, 1))), rad * 1.05)
                ld = _norm(_add(_norm(off), (0, 0, -0.3)))
                wv = _norm(_cross(ld, (0.3, 0.2, 1.0)))
                at = _add(c, off)
                at = (at[0], at[1], max(at[2], length))
                leaves[rng.randrange(3)].leaf(at, ld, wv,
                                              length * 0.5, width * 0.5,
                                              thick, False)
        return
    real = treeleaves.uses_real_leaves(species, shape, season, detail)
    if real:                               # the Leaves library's blades
        n = treeleaves.per_twig(detail, len(twigs))
        length *= treeleaves.SIZE_K[detail] * treeleaves.SIZE_BOOST.get(
            species, 1.0)
        if weeping_leaf(sp):                # strands: more of them
            n = max(n, 8)
        tpl = treeleaves.template(species, round(length / 10.0) * 10.0)
        unit = length / max(round(length / 10.0) * 10.0, 1.0)
    if real and mass is not None and not weeping_leaf(sp):
        _real_crown(rng, dict(sp, species=species), branches, h, leaves, mass,
                    tpl, unit, detail, extras, season, length)
        return
    tufts = sp.get("tufts", False)
    if shape == "needle":                   # sprays on every side branch
        if not tufts:
            twigs = [b for b in branches if b.level >= 1]
        full = False                        # needles: 4 triangles each
        if detail == "city":
            n = 3 if not tufts else 4
        elif tufts:
            n *= 2
    weeping = sp["crown"] == "weeping"
    for b in twigs:
        count = n * (2 if weeping and not real else 1)
        if shape == "needle" and b.level < depth:
            count = max(2, n // 2)
        for _k in range(count):
            t = rng.uniform(0.15, 1.0) if weeping or (
                shape == "needle" and not tufts) else rng.uniform(0.45, 1.0)
            p, d, r = _point_at(b, min(t, 0.999))
            if shape == "needle" and not tufts:
                side = _norm(_cross(d, (0, 0, 1)))
                side = _mul(side, 1 if _k % 2 else -1)
                ld = _norm(_add(_add(_mul(side, 0.8), _mul(d, 0.7)),
                                (0, 0, -0.35)))
                wv = _norm(_cross(ld, (0, 0, 1)))
                q = p
            else:
                spread = (0.012 if weeping else
                          sp.get("spread", 0.028 if tufts else 0.038)) * h \
                    * spread_k
                off = _mul(_norm((rng.gauss(0, 1), rng.gauss(0, 1),
                                  rng.gauss(0, 1))),
                           spread * rng.random() ** 0.5)
                q = _add(p, off)
                out = _norm(_add(_norm(off) if _dot(off, off) > 1 else d,
                                 _mul(d, 0.5)))
                droop = -1.4 if weeping else -0.3
                ld = _norm(_add(out, (0, 0, droop)))
                wv = _norm(_cross(ld, _add(out, (0.2, 0.1, 0.9))))
            k = rng.uniform(0.7, 1.3)
            q = (q[0], q[1], max(q[2], length * k * 1.1))
            if real:
                treeleaves.place(leaves[rng.randrange(3)], tpl, q, ld,
                                 (rng.gauss(0, 0.35), rng.gauss(0, 0.35),
                                  0.0), unit * k, rng.uniform(-0.5, 0.5))
            else:
                leaves[rng.randrange(3)].leaf(q, ld, wv, length * k,
                                              width * k, thick, full)
            if sp.get("fruit") and season in ("Summer", "Autumn") \
                    and rng.random() < 0.06:
                extras.blob(_add(q, (0, 0, -length * 0.3)), length * 0.3)


def _real_crown(rng, sp, branches, h, leaves, mass, tpl, unit, detail,
                extras, season, reach):
    """A crown of leaf BUNCHES: at each outer twig a small dark core
    (32 triangles, hidden by its own leaves) with the Leaves library's
    real blades radiating from it, pointing out and drooping, like the
    rosette a real shoot carries — from a distance the tree is a full
    mass, close up every leaf has its species' true outline."""
    depth = max(b.level for b in branches)
    spots = []                       # (branch, fraction along it)
    for b in branches:
        if b.level == depth:
            spots += [(b, 1.0), (b, rng.uniform(0.55, 0.8))]
        elif b.level == depth - 1 and depth > 1:
            spots.append((b, rng.uniform(0.6, 0.95)))
    if len(spots) > MAX_BUNCHES:
        spots = rng.sample(spots, MAX_BUNCHES)
    n = treeleaves.per_twig(detail, len(spots))
    for b, t in spots:
        p, d, _r = _point_at(b, min(t, 0.999))
        rad = reach * 0.5 * rng.uniform(0.85, 1.15)
        c = _add(p, _mul(d, rad * 0.5))
        c = (c[0], c[1], max(c[2], reach * 1.1))      # never in the ground
        mass.clump(rng, c, rad)
        for _k in range(n):
            out = _norm((rng.gauss(0, 1), rng.gauss(0, 1),
                         rng.gauss(0, 1) * 0.7))
            at = _add(c, _mul(out, rad * 0.8))
            side = _norm(_cross(out, (rng.gauss(0, 1), rng.gauss(0, 1),
                                      rng.gauss(0, 1))))
            ld = _norm(_add(_add(_mul(out, 0.9), _mul(side, 0.25)),
                            (0.0, 0.0, -0.15)))
            at = (at[0], at[1], max(at[2], reach * 0.4))
            # a leaf near the ground points sideways, never into it
            floor_z = -(at[2] - reach * 0.35) / (reach * 1.2)
            if ld[2] < floor_z:
                ld = _norm((ld[0], ld[1], floor_z))
            treeleaves.place(leaves[rng.randrange(3)], tpl, at, ld,
                             (rng.gauss(0, 0.4), rng.gauss(0, 0.4), 0.0),
                             unit * rng.uniform(0.8, 1.25),
                             rng.uniform(-0.6, 0.6))
        if sp.get("fruit") and season in ("Summer", "Autumn") \
                and rng.random() < 0.5:
            extras.blob(_add(c, (rad * 0.3, 0, -rad * 0.9)), rad * 0.3)


def _palm(rng, sp, h, bark, leaves, sides, full, frac):
    """A curved ringed trunk and arching fronds of paired leaflets."""
    r0 = h * sp["radius"]
    lean = (rng.uniform(0.15, 0.3), rng.uniform(-0.1, 0.1), 1.0)
    path, radii = [], []
    segs = 12
    d = _norm(lean)
    p = (0.0, 0.0, 0.0)
    for i in range(segs + 1):
        path.append(p)
        radii.append(r0 * (1.0 - 0.35 * i / segs) *
                     (1.08 if i % 2 else 1.0))
        d = _norm(_add(d, (0.0, 0.0, 0.08)))
        p = _add(p, _mul(d, h * 0.92 / segs))
    bark.tube(path, radii, max(sides, 6))
    top = path[-1]
    fronds = int(14 * max(frac, 0.5))
    ll, lw = sp["leaf"][0] * h / 9000.0, sp["leaf"][1] * h / 9000.0
    if not full:                              # city: fewer, broader
        lw *= 3.0
    for f in range(fronds):
        a = f * GOLDEN
        up = rng.uniform(0.2, 0.7) if f % 2 else rng.uniform(-0.3, 0.2)
        d = _norm((math.cos(a), math.sin(a), up))
        rachis, rr = _grow_path(rng, top, d, h * 0.42, r0 * 0.18, r0 * 0.05,
                                dict(sp, gravity=1.1, bend=4), 7)
        bark.tube(rachis, rr, 3)
        target = leaves[f % 3]
        n_leaflets = int(18 * max(frac, 0.35))
        for k in range(1, n_leaflets):
            t = k / n_leaflets
            q, qd, _r = _point_at(_Branch(rachis, rr, 2, 0), t)
            across = _norm(_cross(qd, (0, 0, 1)))
            size = math.sin(math.pi * min(t + 0.1, 1.0))
            for side in (-1, 1):
                ld = _norm(_add(_mul(across, side), _mul(qd, 0.5)))
                ld = _norm(_add(ld, (0, 0, -0.35)))
                wv = _norm(_cross(ld, (0, 0, 1)))
                target.leaf(q, ld, wv, ll * (0.4 + 0.6 * size), lw,
                            max(lw * 0.1, 3.0), full)


def triangle_count(node) -> int:
    return sum(len(n.params.get("faces") or []) for n in node.walk()
               if n.type == "polyhedron")
