"""Sculpting: brush strokes that push a mesh about — Blender's sculpt
mode, kept as parameters.

A ``sculpt`` node wraps a solid (a blend, a subdivided cage, an
imported scan) and holds a list of STROKES. Each stroke is a brush
applied once at a point: ``grab`` drags the surface along a direction,
``inflate`` pushes it out along its own normals (negative pulls in),
``smooth`` relaxes it, ``flatten`` presses it onto a plane, ``pinch``
draws it towards the centre. Every stroke falls off smoothly to zero
at its radius, and ``mirror`` repeats each stroke across a plane so a
face is sculpted symmetrically from one side.

Strokes are rows ``[kind, x, y, z, radius, strength, dx, dy, dz]`` in
the frame of the node's children — a sculpted head keeps its strokes
when the Object is placed — with *kind* an index into KINDS. The mesh
is welded once (shared vertices stay shared), so pushing vertices about
never opens it: a closed solid stays closed.

Pure geometry, Qt-free; bake.py bakes the result like the deformers.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

KINDS = ("grab", "inflate", "smooth", "flatten", "pinch")
MIRRORS = ("none", "x", "y", "z")
#: a stroke row: kind, centre, radius, strength, direction
STROKE_LEN = 9


def kind_index(kind) -> int:
    """The KINDS index of *kind* (a name or an index), or -1."""
    if isinstance(kind, str):
        name = kind.strip().lower()
        return KINDS.index(name) if name in KINDS else -1
    try:
        i = int(kind)
    except (TypeError, ValueError):
        return -1
    return i if 0 <= i < len(KINDS) else -1


def _vkey(v):
    return (round(v[0], 6), round(v[1], 6), round(v[2], 6))


def _unit(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    return (v[0] / n, v[1] / n, v[2] / n) if n > 1e-12 else None


def _falloff(t: float) -> float:
    """1 at the centre, 0 at the radius, smooth in between."""
    if t >= 1.0:
        return 0.0
    if t <= 0.0:
        return 1.0
    return 1.0 - t * t * (3.0 - 2.0 * t)


class Mesh:
    """A welded mesh: vertices, faces as index triples, neighbours."""

    def __init__(self, tris):
        self.verts = []
        self.faces = []
        index = {}
        for tri in tris:
            ids = []
            for v in tri:
                k = _vkey(v)
                i = index.get(k)
                if i is None:
                    i = index[k] = len(self.verts)
                    self.verts.append([float(v[0]), float(v[1]),
                                       float(v[2])])
                ids.append(i)
            if len(set(ids)) == 3:
                self.faces.append(tuple(ids))
        self.neighbours = [set() for _ in self.verts]
        for a, b, c in self.faces:
            self.neighbours[a].update((b, c))
            self.neighbours[b].update((a, c))
            self.neighbours[c].update((a, b))

    def normals(self) -> list:
        """Area-weighted unit normal per vertex."""
        out = [[0.0, 0.0, 0.0] for _ in self.verts]
        vs = self.verts
        for a, b, c in self.faces:
            pa, pb, pc = vs[a], vs[b], vs[c]
            e1 = (pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2])
            e2 = (pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2])
            n = (e1[1] * e2[2] - e1[2] * e2[1],
                 e1[2] * e2[0] - e1[0] * e2[2],
                 e1[0] * e2[1] - e1[1] * e2[0])
            for i in (a, b, c):
                out[i][0] += n[0]
                out[i][1] += n[1]
                out[i][2] += n[2]
        return [_unit(n) or (0.0, 0.0, 1.0) for n in out]

    def triangles(self) -> list:
        vs = [tuple(v) for v in self.verts]
        return [(vs[a], vs[b], vs[c]) for a, b, c in self.faces]


def _within(mesh, centre, radius):
    """[(index, weight)] of the vertices a brush at *centre* reaches."""
    cx, cy, cz = centre
    r2 = radius * radius
    hits = []
    for i, v in enumerate(mesh.verts):
        dx, dy, dz = v[0] - cx, v[1] - cy, v[2] - cz
        d2 = dx * dx + dy * dy + dz * dz
        if d2 < r2:
            hits.append((i, _falloff(math.sqrt(d2) / radius)))
    return hits


def apply_stroke(mesh, kind: int, centre, radius: float, strength: float,
                 direction=(0.0, 0.0, 0.0)) -> int:
    """One brush dab on *mesh* (in place). Returns how many vertices it
    touched."""
    if radius <= 0.0 or strength == 0.0:
        return 0
    hits = _within(mesh, centre, radius)
    if not hits:
        return 0
    vs = mesh.verts
    name = KINDS[kind] if 0 <= kind < len(KINDS) else "grab"
    if name == "grab":
        u = _unit(direction)
        if u is None:                      # no direction: out along the
            normals = mesh.normals()       # average normal of the patch
            u = _unit([sum(normals[i][k] * w for i, w in hits)
                       for k in range(3)]) or (0.0, 0.0, 1.0)
        for i, w in hits:
            for k in range(3):
                vs[i][k] += u[k] * strength * w
    elif name == "inflate":
        normals = mesh.normals()
        for i, w in hits:
            n = normals[i]
            for k in range(3):
                vs[i][k] += n[k] * strength * w
    elif name == "smooth":
        passes = max(1, int(math.ceil(abs(strength))))
        amount = min(abs(strength) / passes, 1.0)
        for _ in range(passes):
            moved = {}
            for i, w in hits:
                nb = mesh.neighbours[i]
                if not nb:
                    continue
                m = [sum(vs[j][k] for j in nb) / len(nb) for k in range(3)]
                moved[i] = [vs[i][k] + (m[k] - vs[i][k]) * amount * w
                            for k in range(3)]
            for i, p in moved.items():
                vs[i] = p
    elif name == "flatten":
        normals = mesh.normals()
        total = sum(w for _i, w in hits) or 1.0
        n = _unit([sum(normals[i][k] * w for i, w in hits)
                   for k in range(3)]) or (0.0, 0.0, 1.0)
        c = [sum(vs[i][k] * w for i, w in hits) / total for k in range(3)]
        amount = min(abs(strength), 1.0)
        for i, w in hits:
            h = sum((vs[i][k] - c[k]) * n[k] for k in range(3))
            for k in range(3):
                vs[i][k] -= n[k] * h * amount * w
    elif name == "pinch":
        amount = max(min(strength, 1.0), -1.0)
        for i, w in hits:
            for k in range(3):
                vs[i][k] += (centre[k] - vs[i][k]) * amount * w
    return len(hits)


def _mirrored(row, axis: int):
    row = list(row)
    row[1 + axis] = -row[1 + axis]
    row[6 + axis] = -row[6 + axis]
    return row


def sculpt(tris, strokes, mirror: str = "none") -> list:
    """The triangles of *tris* after every stroke in *strokes* (rows
    ``[kind, x, y, z, radius, strength, dx, dy, dz]``), each repeated
    across the *mirror* plane through the origin when one is set."""
    mesh = Mesh(tris)
    if not mesh.faces:
        return []
    axis = MIRRORS.index(mirror) - 1 if mirror in MIRRORS else -1
    for row in strokes:
        try:
            r = [float(v) for v in row]
        except (TypeError, ValueError):
            continue
        if len(r) != STROKE_LEN:
            continue
        for use in ((r, _mirrored(r, axis)) if axis >= 0 else (r,)):
            apply_stroke(mesh, int(use[0]), use[1:4], use[4], use[5],
                         use[6:9])
    return mesh.triangles()


# ------------------------------------------------ world -> local frame

def _inverse3(m):
    (a, b, c), (d, e, f), (g, h, i) = m
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if abs(det) < 1e-12:
        return None
    inv = 1.0 / det
    return [[(e * i - f * h) * inv, (c * h - b * i) * inv, (b * f - c * e) * inv],
            [(f * g - d * i) * inv, (a * i - c * g) * inv, (c * d - a * f) * inv],
            [(d * h - e * g) * inv, (b * g - a * h) * inv, (a * e - b * d) * inv]]


def _mul(m, v):
    return [sum(m[r][k] * v[k] for k in range(3)) for r in range(3)]


def _frame(tri):
    a, b, c = tri
    e1 = [b[k] - a[k] for k in range(3)]
    e2 = [c[k] - a[k] for k in range(3)]
    n = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2],
         e1[0] * e2[1] - e1[1] * e2[0]]
    return [[e1[k], e2[k], n[k]] for k in range(3)]     # columns


def to_local(world_tris, local_tris, point, direction=None):
    """*point* (and *direction*) given in the frame *world_tris* are
    shown in, expressed in the frame of *local_tris* — the same
    tessellation in the same order, as the view shows it and as the
    sculpt computes on it. The nearest world vertex's twin locates the
    point; the linear part of the placement, read off the triangle it
    belongs to, turns the direction. ``(point, direction)``, or
    ``(None, None)`` when the meshes cannot be matched."""
    if not world_tris or len(world_tris) != len(local_tris):
        return None, None
    best, best_d = None, float("inf")
    for i, wt in enumerate(world_tris):
        for k, v in enumerate(wt):
            d = ((v[0] - point[0]) ** 2 + (v[1] - point[1]) ** 2
                 + (v[2] - point[2]) ** 2)
            if d < best_d:
                best, best_d = (i, k), d
    i, k = best
    wt, lt = world_tris[i], local_tris[i]
    lin = None
    for j in range(len(world_tris)):
        inv = _inverse3(_frame(world_tris[(i + j) % len(world_tris)]))
        if inv is not None:
            lin = [[sum(_frame(local_tris[(i + j) % len(local_tris)])[r][c]
                        * inv[c][s] for c in range(3)) for s in range(3)]
                   for r in range(3)]
            break
    if lin is None:
        return None, None
    # the exact point: its offset from the vertex, turned into local
    offset = _mul(lin, [point[c] - wt[k][c] for c in range(3)])
    local_point = [lt[k][c] + offset[c] for c in range(3)]
    local_dir = _mul(lin, list(direction)) if direction is not None else None
    return local_point, local_dir
