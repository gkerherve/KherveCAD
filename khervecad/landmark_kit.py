"""A construction kit for landmarks and bridges (Qt-free).

Famous structures are mostly MANY members — a truss deck is thousands
of bars, a suspension bridge hundreds of hangers, the Eiffel Tower a
lattice. As nodes that would be tens of thousands of cylinders; here
every member is written straight into one closed `polyhedron` per
colour and material (`treegen.Mesh`: pieces appended point by point,
never welded), so a whole bridge is a handful of nodes and previews
exactly.

`Kit` collects pieces by (colour, material):
- `bar(p, q, r)`: a square (or n-sided) tube between two points;
- `path(points, r)`: a tube along a polyline (cables);
- `box(x0, y0, z0, x1, y1, z1)`: an axis box; `obox(centre, size, rz)`
  one turned about Z;
- `frustum(x, y, z0, z1, (w0, d0), (w1, d1))`: a tapering box;
- `prism(outline, z0, z1)`: a CONVEX outline extruded; `solid(pts)` any
  convex point cloud's hull-like closed piece (`Mesh.convex` winding);
- `ring_bars(...)`, `lattice_face(...)` for braced faces;
- `node(name)` returns the coloured union; `add(node)` keeps an
  ordinary CadNode alongside (text, revolved shapes).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from .model import CadNode
from .treegen import Mesh


def _f(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def lerp(a, b, t):
    return a + (b - a) * t


class Kit:
    def __init__(self):
        self.meshes = {}
        self.order = []
        self.extra = []

    def mesh(self, colour, material="Matte"):
        key = (colour, material)
        if key not in self.meshes:
            self.meshes[key] = Mesh()
            self.order.append(key)
        return self.meshes[key]

    # ----------------------------------------------------------- members
    def bar(self, p, q, r, colour, material="Matte", sides=4):
        if math.dist(p, q) < 1e-6:
            return
        self.mesh(colour, material).tube([tuple(p), tuple(q)], [r, r], sides)

    def path(self, points, r, colour, material="Matte", sides=8):
        pts = [tuple(p) for p in points]
        clean = [pts[0]]
        for p in pts[1:]:
            if math.dist(p, clean[-1]) > 1e-6:
                clean.append(p)
        if len(clean) >= 2:
            self.mesh(colour, material).tube(clean, [r] * len(clean), sides)

    def solid(self, pts, colour, material="Matte"):
        """The convex hull of *pts* as one closed piece (`geom3d`), for
        wedges, gables and chamfered blocks."""
        from .geom3d import convex_hull
        tris = convex_hull(pts)
        if not tris:
            return
        index, verts, faces = {}, [], []
        for tri in tris:
            ids = []
            for v in tri:
                if v not in index:
                    index[v] = len(verts)
                    verts.append(v)
                ids.append(index[v])
            faces.append(tuple(ids))
        self.mesh(colour, material).piece(verts, faces)

    def box(self, x0, y0, z0, x1, y1, z1, colour, material="Matte"):
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        z0, z1 = sorted((z0, z1))
        pts = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
               (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        self.mesh(colour, material).convex(pts, BOX_TRIS)

    def obox(self, cx, cy, z0, w, d, h, rz, colour, material="Matte"):
        a = math.radians(rz)
        ca, sa = math.cos(a), math.sin(a)
        pts = []
        for z in (z0, z0 + h):
            for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                x, y = sx * w / 2, sy * d / 2
                pts.append((cx + x * ca - y * sa, cy + x * sa + y * ca, z))
        self.mesh(colour, material).convex(pts, BOX_TRIS)

    def frustum(self, x, y, z0, z1, bottom, top, colour, material="Matte"):
        (w0, d0), (w1, d1) = bottom, top
        pts = [(x - w0 / 2, y - d0 / 2, z0), (x + w0 / 2, y - d0 / 2, z0),
               (x + w0 / 2, y + d0 / 2, z0), (x - w0 / 2, y + d0 / 2, z0),
               (x - w1 / 2, y - d1 / 2, z1), (x + w1 / 2, y - d1 / 2, z1),
               (x + w1 / 2, y + d1 / 2, z1), (x - w1 / 2, y + d1 / 2, z1)]
        self.mesh(colour, material).convex(pts, BOX_TRIS)

    def cone(self, x, y, z0, z1, r0, r1, colour, material="Matte", sides=16,
             phase=0.0):
        """A (truncated) cone or pyramid: *sides* 4 is a square pyramid."""
        ring0, ring1 = [], []
        for k in range(sides):
            a = phase + 2 * math.pi * k / sides
            ring0.append((x + math.cos(a) * r0, y + math.sin(a) * r0, z0))
            if r1 > 1e-6:
                ring1.append((x + math.cos(a) * r1, y + math.sin(a) * r1, z1))
        pts = ring0 + (ring1 if ring1 else [(x, y, z1)])
        n = sides
        # fan caps and sides; winding fixed by convex()
        tris = [(0, k, k + 1) for k in range(1, n - 1)]
        if ring1:
            tris += [(n, n + k, n + k + 1) for k in range(1, n - 1)]
            for k in range(n):
                a, b = k, (k + 1) % n
                tris += [(a, b, n + b), (a, n + b, n + a)]
        else:
            apex = n
            tris += [(k, (k + 1) % n, apex) for k in range(n)]
        self.mesh(colour, material).convex(pts, tris)

    def prism(self, outline, z0, z1, colour, material="Matte"):
        """A convex 2D outline (counter-clockwise) extruded z0..z1."""
        n = len(outline)
        pts = [(x, y, z0) for x, y in outline] + \
              [(x, y, z1) for x, y in outline]
        tris = [(0, k, k + 1) for k in range(1, n - 1)]
        tris += [(n, n + k, n + k + 1) for k in range(1, n - 1)]
        for k in range(n):
            a, b = k, (k + 1) % n
            tris += [(a, b, n + b), (a, n + b, n + a)]
        self.mesh(colour, material).convex(pts, tris)

    def sphere(self, c, r, colour, material="Matte"):
        """A low-poly ball (split octahedron)."""
        import random
        self.mesh(colour, material).clump(_Steady(), c, r)

    # --------------------------------------------------------- patterns
    def truss(self, a0, a1, b0, b1, panels, r_chord, r_web, colour,
              material="Matte", verticals=True):
        """A planar truss between the top chord a0-a1 and the bottom chord
        b0-b1: chords, verticals and alternating diagonals (Warren /
        Pratt), *panels* bays long."""
        self.bar(a0, a1, r_chord, colour, material)
        self.bar(b0, b1, r_chord, colour, material)
        for k in range(panels + 1):
            t = k / panels
            ta = [lerp(a0[i], a1[i], t) for i in range(3)]
            tb = [lerp(b0[i], b1[i], t) for i in range(3)]
            if verticals:
                self.bar(ta, tb, r_web, colour, material)
            if k < panels:
                t2 = (k + 1) / panels
                na = [lerp(a0[i], a1[i], t2) for i in range(3)]
                nb = [lerp(b0[i], b1[i], t2) for i in range(3)]
                if k % 2 == 0:
                    self.bar(ta, nb, r_web, colour, material)
                else:
                    self.bar(tb, na, r_web, colour, material)

    def lattice_face(self, p00, p10, p01, p11, rows, r, colour,
                     material="Matte"):
        """X-bracing over a quadrilateral face (corners bottom-left,
        bottom-right, top-left, top-right), *rows* bays high."""
        for k in range(rows):
            t0, t1 = k / rows, (k + 1) / rows
            l0 = [lerp(p00[i], p01[i], t0) for i in range(3)]
            r0 = [lerp(p10[i], p11[i], t0) for i in range(3)]
            l1 = [lerp(p00[i], p01[i], t1) for i in range(3)]
            r1 = [lerp(p10[i], p11[i], t1) for i in range(3)]
            self.bar(l0, r1, r, colour, material)
            self.bar(r0, l1, r, colour, material)
            self.bar(l1, r1, r, colour, material)

    # ------------------------------------------------------------ nodes
    def add(self, node):
        self.extra.append(node)
        return node

    def node(self, name):
        group = CadNode("union", name, {})
        for colour, material in self.order:
            m = self.meshes[(colour, material)]
            if not m.faces:
                continue
            c = CadNode("color", name, dict(color=colour, alpha=1.0,
                                            material=material))
            c.add(m.node(name))
            group.add(c)
        for n in self.extra:
            group.add(n)
        return group


class _Steady:
    """A random stand-in that never jitters (round balls)."""

    def uniform(self, a, b):
        return (a + b) / 2


BOX_TRIS = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
            (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
