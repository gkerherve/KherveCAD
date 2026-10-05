"""SubD — Rhino's subdivision surfaces: a coarse CAGE you edit, a smooth
surface that follows it (Qt-free).

The `subd` node wraps a polyhedron, the cage, and draws the Catmull-
Clark limit of it `levels` times: every cage face becomes quads, every
corner is pulled towards its neighbours, so eight cage points make a
round pebble and a few dozen make a car body, a shoe, a character's
head. Shape it the way Rhino does: Tab into Edit Mode, which opens the
CAGE (meshedit.find_editable looks through the SubD), drag its points
and the smooth surface follows on every move; extrude a cage face for
an arm, a nose, a handle.

Creases keep an edge sharp where the design needs one — the rim of a
cup, a panel line: list cage point pairs in `creases`, or set `sharp`
to crease every cage edge whose faces meet at more than that angle.
A cage edge with one face (an open cage) is always a crease, so an
open cage gives an open-edged sheet rather than shrinking away.

OpenSCAD gets the baked smooth polyhedron (bakedkit) and STEP the same
surface, faceted (Rhino's SubD is exact; this one is as fine as the
levels make it).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from . import bakedkit

MAX_LEVELS = 5
#: refuse past this many output faces (each level is ~4x)
MAX_FACES = 400000

_DEFAULTS = dict(levels=3, sharp=0.0, creases=[], show_cage=False)


# ============================================================ the maths

def catmull_clark(points, faces, creases=frozenset()):
    """One Catmull-Clark step over a polygon mesh (faces counter-
    clockwise from outside, any number of sides). *creases* is a set of
    frozenset({i, j}) cage edges kept sharp. Returns (points, quads,
    creases of the result)."""
    pts = [tuple(float(c) for c in p) for p in points]
    nf = len(faces)
    face_pt = []
    for f in faces:
        n = len(f)
        face_pt.append(tuple(sum(pts[i][k] for i in f) / n
                             for k in range(3)))
    edge_faces = {}
    for fi, f in enumerate(faces):
        for k in range(len(f)):
            e = frozenset((f[k], f[(k + 1) % len(f)]))
            edge_faces.setdefault(e, []).append(fi)
    sharp = {e for e, fs in edge_faces.items()
             if len(fs) != 2 or e in creases}
    edge_index = {}
    new_pts = list(pts)               # old points first, moved below
    for e, fs in edge_faces.items():
        a, b = tuple(e)
        mid = tuple((pts[a][k] + pts[b][k]) / 2 for k in range(3))
        if e in sharp:
            p = mid
        else:
            f0, f1 = face_pt[fs[0]], face_pt[fs[1]]
            p = tuple((pts[a][k] + pts[b][k] + f0[k] + f1[k]) / 4
                      for k in range(3))
        edge_index[e] = len(new_pts)
        new_pts.append(p)
    face_index = []
    for fp in face_pt:
        face_index.append(len(new_pts))
        new_pts.append(fp)
    # move the old points
    v_faces = [[] for _ in pts]
    v_edges = [[] for _ in pts]
    for fi, f in enumerate(faces):
        for i in f:
            v_faces[i].append(fi)
    for e in edge_faces:
        for i in e:
            v_edges[i].append(e)
    for i, p in enumerate(pts):
        es = v_edges[i]
        if not es:
            continue
        hard = [e for e in es if e in sharp]
        if len(hard) >= 3:
            continue                              # a corner stays
        if len(hard) == 2:
            o = [next(j for j in e if j != i) for e in hard]
            new_pts[i] = tuple(0.75 * p[k] + 0.125 * (pts[o[0]][k]
                                                      + pts[o[1]][k])
                               for k in range(3))
            continue
        n = len(v_faces[i])
        if n < 3 or len(es) != n:
            continue                              # irregular boundary
        f_avg = [sum(face_pt[fi][k] for fi in v_faces[i]) / n
                 for k in range(3)]
        r_avg = [0.0, 0.0, 0.0]
        for e in es:
            a, b = tuple(e)
            for k in range(3):
                r_avg[k] += (pts[a][k] + pts[b][k]) / 2 / len(es)
        new_pts[i] = tuple((f_avg[k] + 2 * r_avg[k] + (n - 3) * p[k]) / n
                           for k in range(3))
    quads = []
    new_creases = set()
    for fi, f in enumerate(faces):
        m = len(f)
        for k in range(m):
            v = f[k]
            e_next = edge_index[frozenset((v, f[(k + 1) % m]))]
            e_prev = edge_index[frozenset((f[(k - 1) % m], v))]
            quads.append([v, e_next, face_index[fi], e_prev])
    for e in sharp:
        a, b = tuple(e)
        mid = edge_index[e]
        new_creases.add(frozenset((a, mid)))
        new_creases.add(frozenset((mid, b)))
    return new_pts, quads, new_creases


def limit_mesh(points, faces, levels=3, creases=frozenset()):
    """(points, quads) after *levels* steps."""
    pts, fs, cr = points, faces, set(creases)
    for _ in range(max(0, min(int(levels), MAX_LEVELS))):
        if len(fs) * 4 > MAX_FACES:
            break
        pts, fs, cr = catmull_clark(pts, fs, cr)
    return pts, fs


def triangles(points, faces):
    out = []
    for f in faces:
        for k in range(1, len(f) - 1):
            out.append((tuple(points[f[0]]), tuple(points[f[k]]),
                        tuple(points[f[k + 1]])))
    return out


def angle_creases(points, faces, sharp):
    """Cage edges whose two faces meet at more than *sharp* degrees."""
    if sharp <= 0:
        return set()
    from .meshedit import face_normal
    normals = [face_normal(points, f) for f in faces]
    owners = {}
    for fi, f in enumerate(faces):
        for k in range(len(f)):
            owners.setdefault(frozenset((f[k], f[(k + 1) % len(f)])),
                              []).append(fi)
    limit = math.cos(math.radians(sharp))
    out = set()
    for e, fs in owners.items():
        if len(fs) == 2:
            a, b = normals[fs[0]], normals[fs[1]]
            if sum(x * y for x, y in zip(a, b)) < limit:
                out.add(e)
    return out


# ============================================================ the node

def cage(node, env):
    """(points, faces counter-clockwise) of the cage: the polyhedron
    inside, or any solid inside welded into polygons."""
    from . import mesh, meshedit
    poly = next((c for c in node.walk() if c is not node
                 and c.type == "polyhedron" and c.visible), None)
    if poly is not None and _only_wrappers_between(node, poly):
        pts = [tuple(mesh.rv(v, env) for v in row[:3])
               for row in poly.params.get("points") or []]
        faces = [[int(i) for i in f][::-1]
                 for f in poly.params.get("faces") or [] if len(f) >= 3]
        m = mesh.ancestor_matrix(poly, env, stop=node)
        pts = [tuple(mesh.mat_apply(m, q)) for q in pts]
        if mesh.flips_winding(m):
            faces = [f[::-1] for f in faces]
        return pts, faces
    tris = bakedkit.source_tris(node, env)
    pts, faces = meshedit.triangles_to_mesh(tris)
    pts, faces = meshedit.merge_coplanar(pts, faces)
    # meshedit keeps OpenSCAD's clockwise faces
    return [tuple(p) for p in pts], [list(f)[::-1] for f in faces]


def _only_wrappers_between(node, poly):
    from .meshedit import TRANSPARENT
    probe = poly.parent
    while probe is not None and probe is not node:
        if probe.type not in TRANSPARENT:
            return False
        probe = probe.parent
    return True


def _compute(node, env):
    pts, faces = cage(node, env)
    if not faces:
        return []
    from . import mesh
    creases = angle_creases(pts, faces,
                            mesh.rv(node.params.get("sharp", 0.0), env, 0.0))
    for row in node.params.get("creases") or []:
        if isinstance(row, list) and len(row) >= 2:
            try:
                creases.add(frozenset((int(row[0]), int(row[1]))))
            except (TypeError, ValueError):
                pass
    levels = int(mesh.rv(node.params.get("levels", 3), env, 3))
    out_pts, quads = limit_mesh(pts, faces, levels, creases)
    return triangles(out_pts, quads)


def _check(node, env):
    from . import mesh
    levels = mesh.rv(node.params.get("levels", 3), env, 3)
    if not 0 <= levels <= MAX_LEVELS:
        return f"SubD: levels from 0 to {MAX_LEVELS}"
    return None


KIT = bakedkit.make(
    "subd", "SubD (smooth cage)", "mdi.circle-box-outline", _DEFAULTS,
    [("levels", "Smoothness (levels, 1-5)", "int", 0, MAX_LEVELS),
     ("sharp", "Crease edges sharper than (°, 0 = none)", "float",
      0.0, 180.0),
     ("creases", "Creased cage edges (point pairs)", "rows", ["A", "B"],
      None),
     ("show_cage", "Show the cage too", "bool", None, None)],
    _compute, draws_children=lambda n: bool(n.params.get("show_cage")),
    check=_check)


# ===================================================== making one

def box_cage(w=40.0, d=30.0, h=20.0):
    """A cube cage (polyhedron params) centred on the origin, on z = 0."""
    x, y = w / 2, d / 2
    pts = [[-x, -y, 0], [x, -y, 0], [x, y, 0], [-x, y, 0],
           [-x, -y, h], [x, -y, h], [x, y, h], [-x, y, h]]
    # OpenSCAD's polyhedron: clockwise seen from outside
    faces = [[0, 1, 2, 3], [4, 7, 6, 5], [0, 4, 5, 1], [1, 5, 6, 2],
             [2, 6, 7, 3], [3, 7, 4, 0]]
    return dict(points=pts, faces=faces)


def insert_box(model, parent=None):
    """Insert ▸ SubD box: a SubD round a cube cage, ready to pull."""
    node = model.add_node("subd", dict(_DEFAULTS), parent=parent,
                          name="SubD")
    model.add_node("polyhedron", box_cage(), parent=node, name="Cage")
    return node


def convert(model, node, fn=None):
    """Wrap the selected solid in a SubD, its mesh becoming the cage
    (meshedit.convert makes it a polyhedron first) — one undo step."""
    from . import meshedit
    poly = meshedit.find_editable(node)
    if poly is None:
        why = meshedit.convertible(node)
        if why:
            raise ValueError(why)
        poly, why = meshedit.convert(model, node, fn)
        if poly is None:
            raise ValueError(why)
    # the SubD goes right round the cage, so a colour the conversion
    # kept stays OUTSIDE it and still paints the smooth surface
    target = poly
    parent = target.parent
    index = parent.children.index(target)
    surf = model.add_node("subd", dict(_DEFAULTS, levels=2, sharp=0.0),
                          parent=parent, name="SubD")
    model.move_node(surf, parent, index)
    model.move_node(target, surf)
    return surf
