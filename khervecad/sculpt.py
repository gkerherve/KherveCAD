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

Two more brushes draw LINES rather than dabs — the detail that makes
skin read as old: ``crease`` carves a groove ``strength`` mm deep from
the point to point + (dx, dy, dz), ``radius`` mm either side of it
(wrinkles, crow's feet, a frown, the fold of a knuckle), ``ridge``
raises one (a vein, a tendon, a scar). Their profile is a soft bell that
tapers at both ends, so a run of short strokes reads as one wrinkle.
And ``noise`` (mm) roughens the whole surface along its normals with a
seeded fractal of ``noise_scale`` mm — pores, lumpy old skin, a cast
texture — after the strokes, so a smooth stroke cannot wipe it.

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

KINDS = ("grab", "inflate", "smooth", "flatten", "pinch", "crease",
         "ridge", "snake_hook", "draw", "clay_strips", "layer",
         "elastic_grab", "pose", "mask")
#: brushes that run along a segment (point -> point + direction)
LINES = frozenset({"crease", "ridge"})

try:                                    # the fast path
    import numpy as _np
except Exception:                       # pragma: no cover - numpy is a dep
    _np = None
MIRRORS = ("none", "x", "y", "z")
#: a stroke row: kind, centre, radius, strength, direction
STROKE_LEN = 9
#: a pose row adds a point on the part that moves (the limb's tip)
POSE_LEN = 12
ROW_LENS = (STROKE_LEN, POSE_LEN)
#: the creature brushes (sculpt_brushes.py; numpy only)
CREATURE = frozenset({"snake_hook", "draw", "clay_strips", "layer",
                      "elastic_grab", "pose", "mask"})


def kind_index(kind) -> int:
    """The KINDS index of *kind* (a name or an index), or -1."""
    if isinstance(kind, str):
        name = kind.strip().lower().replace(" ", "_").replace("-", "_")
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
    if 0 <= kind < len(KINDS) and KINDS[kind] in LINES:
        return _apply_line(mesh, kind, centre, radius, strength, direction)
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


def _apply_line(mesh, kind, centre, radius, strength, direction):
    return _line_stroke(mesh, -1.0 if KINDS[kind] == "crease" else 1.0,
                        centre, radius, strength, direction)


def _mirrored(row, axis: int):
    row = list(row)
    row[1 + axis] = -row[1 + axis]
    if 0 <= int(row[0]) < len(KINDS) and KINDS[int(row[0])] == "pose":
        # a rotation axis is a pseudo-vector: across a mirror the other
        # two components turn round (and the turn keeps its angle)
        for k in range(3):
            if k != axis:
                row[6 + k] = -row[6 + k]
    else:
        row[6 + axis] = -row[6 + axis]
    if len(row) >= POSE_LEN:
        row[9 + axis] = -row[9 + axis]
    return row


def line_weight(t, along, length, radius):
    """The crease / ridge profile: a bell across the line (*t* = distance
    / radius, 1 at the edge) that tapers over a radius at either end
    (*along* = position on the segment, 0..*length*). Works on floats
    and on numpy arrays."""
    if _np is not None and not isinstance(t, float):
        np = _np
        across = np.clip(1.0 - t * t, 0.0, 1.0) ** 3
        ends = np.clip(np.minimum(along, length - along) / max(radius, 1e-9)
                       + 0.35, 0.0, 1.0)
        return across * ends * ends * (3.0 - 2.0 * ends)
    across = max(0.0, 1.0 - t * t) ** 3
    e = min(max(min(along, length - along) / max(radius, 1e-9) + 0.35,
                0.0), 1.0)
    return across * e * e * (3.0 - 2.0 * e)


def _segment(p, centre, direction):
    """(distance to the segment, position along it, its length) for the
    point *p* — the line brushes' geometry."""
    d = direction
    length = math.sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2])
    rel = (p[0] - centre[0], p[1] - centre[1], p[2] - centre[2])
    if length < 1e-9:
        return math.sqrt(rel[0] ** 2 + rel[1] ** 2 + rel[2] ** 2), 0.0, 0.0
    u = (d[0] / length, d[1] / length, d[2] / length)
    along = min(max(rel[0] * u[0] + rel[1] * u[1] + rel[2] * u[2], 0.0),
                length)
    q = (rel[0] - u[0] * along, rel[1] - u[1] * along, rel[2] - u[2] * along)
    return math.sqrt(q[0] ** 2 + q[1] ** 2 + q[2] ** 2), along, length


def _line_stroke(mesh, sign, centre, radius, strength, direction):
    normals = mesh.normals()
    vs = mesh.verts
    touched = 0
    for i, v in enumerate(vs):
        dist, along, length = _segment(v, centre, direction)
        if dist >= radius:
            continue
        w = line_weight(dist / radius, along, length, radius)
        if w <= 0.0:
            continue
        touched += 1
        n = normals[i]
        for k in range(3):
            v[k] += n[k] * sign * strength * w
    return touched


# --------------------------------------------------------------- noise

def _hash(ix, iy, iz, seed):
    """A repeatable pseudo-random value in [-1, 1] per lattice point
    (integer arrays in, float array out)."""
    np = _np
    h = (ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791) ^ (seed * 2654435761)
    h = (h ^ (h >> 13)) * 1274126177
    h = h ^ (h >> 16)
    return (h & 0xFFFFFF).astype(np.float64) / 0x7FFFFF - 1.0


def value_noise(points, scale: float, seed: int = 1, octaves: int = 3):
    """Smooth fractal value noise in about [-1, 1] at the (N, 3) array
    *points*, features *scale* mm across — the same everywhere the same
    point is asked (no state), so a re-bake is identical."""
    np = _np
    out = np.zeros(len(points))
    amp, total = 1.0, 0.0
    freq = 1.0 / max(scale, 1e-6)
    for octave in range(octaves):
        q = points * freq + octave * 17.31
        base = np.floor(q).astype(np.int64)
        f = q - base
        f = f * f * (3.0 - 2.0 * f)                         # smoothstep
        acc = np.zeros(len(points))
        for dx in (0, 1):
            wx = f[:, 0] if dx else 1.0 - f[:, 0]
            for dy in (0, 1):
                wy = f[:, 1] if dy else 1.0 - f[:, 1]
                for dz in (0, 1):
                    wz = f[:, 2] if dz else 1.0 - f[:, 2]
                    acc += wx * wy * wz * _hash(base[:, 0] + dx,
                                                base[:, 1] + dy,
                                                base[:, 2] + dz,
                                                int(seed) + octave)
        out += acc * amp
        total += amp
        amp *= 0.5
        freq *= 2.0
    return out / total


# ----------------------------------------------------------- numpy path

def weld(arr, digits: int = 6):
    """``(unique points, inverse)`` of the (N, 3) array *arr* after
    rounding to *digits* — np.unique(axis=0) without its slow row
    comparison: integer keys, one lexsort, a diff."""
    np = _np
    keys = np.round(arr * 10.0 ** digits).astype(np.int64)
    order = np.lexsort((keys[:, 2], keys[:, 1], keys[:, 0]))
    ordered = keys[order]
    new = np.ones(len(ordered), dtype=bool)
    if len(ordered) > 1:
        new[1:] = np.any(ordered[1:] != ordered[:-1], axis=1)
    group = np.cumsum(new) - 1
    inverse = np.empty(len(arr), dtype=np.int64)
    inverse[order] = group
    uniq = ordered[new].astype(np.float64) / 10.0 ** digits
    return uniq, inverse


class _Fast:
    """The welded mesh as numpy arrays: what the Python Mesh is, with
    every brush applied to all vertices at once."""

    def __init__(self, tris):
        np = _np
        arr = np.asarray(tris, dtype=np.float64).reshape(-1, 3)
        uniq, inverse = weld(arr)
        faces = inverse.reshape(-1, 3)
        ok = ((faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2])
              & (faces[:, 0] != faces[:, 2]))
        self.faces = faces[ok]
        self.verts = uniq.copy()
        edges = np.concatenate([self.faces[:, [0, 1]], self.faces[:, [1, 2]],
                                self.faces[:, [2, 0]]])
        edges = np.sort(edges, axis=1)
        n = max(len(self.verts), 1)
        key = np.unique(edges[:, 0].astype(np.int64) * n + edges[:, 1])
        edges = np.stack([key // n, key % n], axis=1)
        self.edges = edges
        self.degree = np.bincount(edges.ravel(), minlength=len(self.verts))
        self._normals = None
        self.stale = False

    def normals(self):
        np = _np
        if self._normals is None:
            v, f = self.verts, self.faces
            n = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
            out = np.zeros_like(v)
            for k in range(3):
                np.add.at(out, f[:, k], n)
            length = np.linalg.norm(out, axis=1)
            out[length < 1e-12] = (0.0, 0.0, 1.0)
            length[length < 1e-12] = 1.0
            self._normals = out / length[:, None]
        return self._normals

    def moved(self):
        self._normals = None
        self.stale = False

    def neighbour_mean(self):
        np = _np
        acc = np.zeros_like(self.verts)
        a, b = self.edges[:, 0], self.edges[:, 1]
        np.add.at(acc, a, self.verts[b])
        np.add.at(acc, b, self.verts[a])
        deg = np.maximum(self.degree, 1)[:, None]
        return acc / deg

    def triangles(self):
        vs = [tuple(v) for v in self.verts.tolist()]
        return [(vs[a], vs[b], vs[c]) for a, b, c in self.faces.tolist()]


def _fast_stroke(mesh, kind, centre, radius, strength, direction,
                 extra=None):
    """One stroke on the _Fast *mesh*. Returns the mesh to carry on
    with (a snake hook refines the skin it stretched into a new one)."""
    np = _np
    name = KINDS[kind] if 0 <= kind < len(KINDS) else "grab"
    if name in CREATURE:
        from . import sculpt_brushes
        return sculpt_brushes.apply(mesh, name, centre, radius, strength,
                                    direction, extra)
    if radius <= 0.0 or strength == 0.0:
        return mesh
    vs = mesh.verts
    c = np.asarray(centre, dtype=np.float64)
    free = getattr(mesh, "mask", None)
    if name in LINES:
        d = np.asarray(direction, dtype=np.float64)
        length = float(np.linalg.norm(d))
        rel = vs - c
        if length < 1e-9:
            dist, along = np.linalg.norm(rel, axis=1), np.zeros(len(vs))
        else:
            u = d / length
            along = np.clip(rel @ u, 0.0, length)
            dist = np.linalg.norm(rel - along[:, None] * u, axis=1)
        idx = np.nonzero(dist < radius)[0]
        if not len(idx):
            return mesh
        w = line_weight(dist[idx] / radius, along[idx], length, radius)
        if free is not None:
            w = w * (1.0 - free[idx])
        sign = -1.0 if name == "crease" else 1.0
        vs[idx] += mesh.normals()[idx] * (sign * strength * w)[:, None]
        # a line moves the surface a hair: the next line may keep these
        # normals (hundreds of wrinkles would re-measure 200k faces each),
        # any other brush measures afresh
        mesh.stale = True
        return mesh
    if mesh.stale:
        mesh.moved()
    d2 = np.einsum("ij,ij->i", vs - c, vs - c)
    idx = np.nonzero(d2 < radius * radius)[0]
    if not len(idx):
        return mesh
    t = np.sqrt(d2[idx]) / radius
    w = 1.0 - t * t * (3.0 - 2.0 * t)
    if free is not None:
        w = w * (1.0 - free[idx])
    if name == "grab":
        u = _unit(direction)
        if u is None:
            n = (mesh.normals()[idx] * w[:, None]).sum(axis=0)
            u = _unit(n) or (0.0, 0.0, 1.0)
        vs[idx] += np.asarray(u) * (strength * w)[:, None]
    elif name == "inflate":
        vs[idx] += mesh.normals()[idx] * (strength * w)[:, None]
    elif name == "smooth":
        passes = max(1, int(math.ceil(abs(strength))))
        amount = min(abs(strength) / passes, 1.0)
        for _ in range(passes):
            m = mesh.neighbour_mean()[idx]
            has = mesh.degree[idx] > 0
            step = (m - vs[idx]) * (amount * w)[:, None]
            vs[idx] += np.where(has[:, None], step, 0.0)
    elif name == "flatten":
        total = w.sum() or 1.0
        n = _unit((mesh.normals()[idx] * w[:, None]).sum(axis=0)) \
            or (0.0, 0.0, 1.0)
        n = np.asarray(n)
        cen = (vs[idx] * w[:, None]).sum(axis=0) / total
        h = (vs[idx] - cen) @ n
        vs[idx] -= n[None, :] * (h * min(abs(strength), 1.0) * w)[:, None]
    elif name == "pinch":
        amount = max(min(strength, 1.0), -1.0)
        vs[idx] += (c - vs[idx]) * (amount * w)[:, None]
    mesh.moved()
    return mesh


def _rows(strokes, axis):
    for row in strokes:
        try:
            r = [float(v) for v in row]
        except (TypeError, ValueError):
            continue
        if len(r) not in ROW_LENS:
            continue
        yield from ((r, _mirrored(r, axis)) if axis >= 0 else (r,))


def sculpt(tris, strokes, mirror: str = "none", noise: float = 0.0,
           noise_scale: float = 4.0, seed: int = 1) -> list:
    """The triangles of *tris* after every stroke in *strokes* (rows
    ``[kind, x, y, z, radius, strength, dx, dy, dz]``), each repeated
    across the *mirror* plane through the origin when one is set, then
    roughened by *noise* mm of fractal noise *noise_scale* mm across."""
    axis = MIRRORS.index(mirror) - 1 if mirror in MIRRORS else -1
    if _np is not None:
        fast = _Fast(tris)
        if not len(fast.faces):
            return []
        for use in _rows(strokes, axis):
            fast = _fast_stroke(fast, int(use[0]), use[1:4], use[4],
                                use[5], use[6:9],
                                use[9:12] if len(use) >= POSE_LEN else None)
        if noise:
            fast.moved()
            n = value_noise(fast.verts, noise_scale, int(seed))
            fast.verts += fast.normals() * (n * noise)[:, None]
        return fast.triangles()
    mesh = Mesh(tris)
    if not mesh.faces:
        return []
    for use in _rows(strokes, axis):
        if KINDS[int(use[0])] in CREATURE:
            continue                    # the creature brushes need numpy
        apply_stroke(mesh, int(use[0]), use[1:4], use[4], use[5], use[6:9])
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


_WORLD = [None, None]                   # (the list it came from, its array)


def _world_array(world_tris):
    """The world triangles' vertices as an (N * 3, 3) array, kept for
    the list it was made from (a batch of strokes maps through one)."""
    if _WORLD[0] is not world_tris:
        _WORLD[0] = world_tris
        _WORLD[1] = _np.asarray(world_tris, dtype=float).reshape(-1, 3)
    return _WORLD[1]


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
    if _np is not None:
        flat = _world_array(world_tris)
        d = ((flat - _np.asarray(point, dtype=float)) ** 2).sum(axis=1)
        j = int(d.argmin())
        i, k = j // 3, j % 3
    else:
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
