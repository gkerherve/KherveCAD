"""Cavity shading and edge lines for the 3D preview (Qt-free) — what
Blender's Solid view calls Cavity and Outline.

The preview has no depth buffer, so screen-space effects are out; both
of these come from the mesh itself, computed once per mesh in
`analyse()` on the worker thread that also builds the BSP tree:

- **cavity** — per face, a multiplier for the finished colour: faces
  in a valley (their edge-neighbours bend towards the face normal)
  darken, faces on a ridge lighten, by an amount that grows with the
  dihedral angle; smoothed one ring so a single facet does not flash.
- **creases** — per face, the edges it shares with a neighbour at more
  than `EDGE_ANGLE` degrees: a cube's twelve edges, a cylinder's two
  rims and not its facets. Drawn as segments after the face's
  polygons are painted, so occlusion comes out right.
- **silhouette** — per frame (`silhouette()`), the shared edges where
  one face looks at the eye and the other looks away.

The tree the painter walks holds split copies of the mesh; `bsp.Tree.
parents` maps every piece back to the input face these tables are
indexed by.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

#: faces meeting at more than this (degrees) are joined by a drawn edge
EDGE_ANGLE = 25.0

#: how far the cavity term may push a face's value at full strength
CAVITY_RANGE = 0.35


def _key(v):
    return (round(v[0], 5), round(v[1], 5), round(v[2], 5))


def _normal(tri):
    a, b, c = tri
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length < 1e-15:
        return (0.0, 0.0, 0.0)
    return (nx / length, ny / length, nz / length)


class MeshInfo:
    """Per-face tables for one mesh: `normals`, `cavity` (multipliers
    around 1), `creases` ({face: [(p, q), ...]}) and `neighbours`
    ([(face_a, face_b, p, q)] over every shared edge, for the
    silhouette)."""

    __slots__ = ("normals", "cavity", "creases", "neighbours")

    def __init__(self, normals, cavity, creases, neighbours):
        self.normals = normals
        self.cavity = cavity
        self.creases = creases
        self.neighbours = neighbours


def analyse(tris, edge_angle: float = EDGE_ANGLE) -> MeshInfo:
    normals = [_normal(t) for t in tris]
    directed = {}
    for i, tri in enumerate(tris):
        keys = [_key(v) for v in tri]
        for k in range(3):
            directed[(keys[k], keys[(k + 1) % 3])] = (i, k)
    cos_edge = math.cos(math.radians(edge_angle))
    raw = [0.0] * len(tris)
    count = [0] * len(tris)
    creases = {}
    neighbours = []
    for (ka, kb), (i, k) in directed.items():
        other = directed.get((kb, ka))
        if other is None:
            # an open border or a T-junction (OpenSCAD's exact meshes
            # are full of them): the face ends here, so draw the line —
            # skipping it left the edges of many exact parts unmarked
            creases.setdefault(i, []).append((tris[i][k],
                                              tris[i][(k + 1) % 3]))
            continue
        if ka >= kb:
            continue                     # a shared edge: once is enough
        j = other[0]
        ni, nj = normals[i], normals[j]
        cos = max(-1.0, min(1.0, ni[0] * nj[0] + ni[1] * nj[1]
                             + ni[2] * nj[2]))
        angle = math.acos(cos)
        # bending: the neighbour's far vertex above this face's plane
        # (along the normal) means a valley
        a = tris[i][k]
        far = tris[j][(other[1] + 2) % 3]
        side = (ni[0] * (far[0] - a[0]) + ni[1] * (far[1] - a[1])
                + ni[2] * (far[2] - a[2]))
        signed = angle if side > 1e-9 else -angle if side < -1e-9 else 0.0
        p, q = tris[i][k], tris[i][(k + 1) % 3]
        # weighted by the edge's length: a wall's long concave foot
        # counts for more than its short convex ends
        weight = math.sqrt((q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2
                           + (q[2] - p[2]) ** 2)
        raw[i] += signed * weight
        raw[j] += signed * weight
        count[i] += weight
        count[j] += weight
        neighbours.append((i, j, p, q))
        if cos < cos_edge:
            creases.setdefault(i, []).append((p, q))
            creases.setdefault(j, []).append((p, q))
    # mean signed bend per face, then one ring of smoothing
    mean = [raw[i] / count[i] if count[i] else 0.0 for i in range(len(tris))]
    smooth = list(mean)
    ring = [0] * len(tris)
    for i, j, _p, _q in neighbours:
        smooth[i] += mean[j]
        smooth[j] += mean[i]
        ring[i] += 1
        ring[j] += 1
    cavity = []
    for i in range(len(tris)):
        value = smooth[i] / (ring[i] + 1)
        # +90° of valley -> -1, +90° of ridge -> +1
        term = max(-1.0, min(1.0, -value / (math.pi / 2)))
        cavity.append(term)
    return MeshInfo(normals, cavity, creases, neighbours)


def multiplier(term: float, strength: float) -> float:
    """The value multiplier for a face's colour."""
    return 1.0 + term * strength * CAVITY_RANGE


def piece_segments(tri, segs, eps=1e-4):
    """The parts of the input face's edge segments *segs* that lie on
    the edges of *tri*, one BSP piece of that face. The painter draws a
    piece's lines right after its polygon, so lines get the same
    occlusion as faces — drawing a face's whole crease when any piece
    of it was painted let a wall's edge run straight across the roof in
    front of it. Pieces equal faces without a tree, and every segment
    comes back whole."""
    out = []
    for p, q in segs:
        dx, dy, dz = q[0] - p[0], q[1] - p[1], q[2] - p[2]
        length2 = dx * dx + dy * dy + dz * dz
        if length2 < 1e-18:
            continue
        tol = eps * eps * length2
        on = []
        for v in tri:
            wx, wy, wz = v[0] - p[0], v[1] - p[1], v[2] - p[2]
            t = (wx * dx + wy * dy + wz * dz) / length2
            # distance² from the line, scaled by the segment's length²
            cx = wy * dz - wz * dy
            cy = wz * dx - wx * dz
            cz = wx * dy - wy * dx
            on.append(-1e-6 <= t <= 1 + 1e-6
                      and cx * cx + cy * cy + cz * cz <= tol)
        for k in range(3):
            if on[k] and on[(k + 1) % 3]:
                out.append((tri[k], tri[(k + 1) % 3]))
    return out


def silhouette(info: MeshInfo, facing) -> dict:
    """{face: [(p, q), ...]} of the edges where one owner faces the
    eye and the other does not, keyed by the front-facing owner —
    *facing* is a per-face list of booleans for this frame."""
    out = {}
    for i, j, p, q in info.neighbours:
        fi, fj = facing[i], facing[j]
        if fi == fj:
            continue
        out.setdefault(i if fi else j, []).append((p, q))
    return out
