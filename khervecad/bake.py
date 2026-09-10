"""Mesh nodes: geometry given — or computed — as a polyhedron.

``polyhedron`` is OpenSCAD's own: points plus faces, typed in or
imported (and a coarse cage for ``subdivide`` to smooth). The nodes
built on it compute their surface in Python — a loft, a smooth blend,
a deformation — and *bake* it into the program as one polyhedron, so
an exported .scad is still standalone OpenSCAD and the exact render is
exactly the preview.

Like organic.py (which aggregates this module into the registry),
nothing from the package is imported at module level.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

SHAPE_3D = "3d"
OPERATION = "op"

#: a tetrahedron; faces run clockwise seen from outside (OpenSCAD's rule)
_TETRA_POINTS = [[0.0, 0.0, 0.0], [20.0, 0.0, 0.0], [0.0, 20.0, 0.0],
                 [0.0, 0.0, 20.0]]
_TETRA_FACES = [[0, 1, 2], [0, 3, 1], [0, 2, 3], [1, 3, 2]]

NODE_TYPES = {
    "polyhedron": dict(
        label="Polyhedron", category=SHAPE_3D,
        icon="mdi.hexagon-multiple-outline",
        params=dict(points=_TETRA_POINTS, faces=_TETRA_FACES),
        schema=[("points", "Points", "rows", ["X", "Y", "Z"], None),
                ("faces", "Faces (point indices, clockwise from "
                          "outside)", "rows", None, None)]),
}

TYPES = frozenset(NODE_TYPES)
LEAVES = frozenset({"polyhedron"})
WRAPPERS = frozenset()


def preamble(root) -> list:
    """Helper-module source lines this module's nodes need."""
    return []


# ------------------------------------------------------------ baking

def to_polyhedron(tris, digits: int = 4):
    """``(points, faces)`` for OpenSCAD from counter-clockwise
    triangles: shared vertices welded (after rounding to *digits*, the
    precision the program is written with), faces turned to OpenSCAD's
    clockwise-from-outside order, collapsed faces dropped."""
    index, points, faces = {}, [], []
    for tri in tris:
        ids = []
        for v in tri:
            key = (round(v[0], digits), round(v[1], digits),
                   round(v[2], digits))
            i = index.get(key)
            if i is None:
                i = index[key] = len(points)
                points.append([key[0], key[1], key[2]])
            ids.append(i)
        if len(set(ids)) == 3:
            faces.append([ids[0], ids[2], ids[1]])
    return points, faces


def _rows(rows, fmt) -> str:
    return "[" + ", ".join("[" + ", ".join(fmt(v) for v in row) + "]"
                           for row in rows) + "]"


# ----------------------------------------------------------- codegen

def statement(node, fmt, fn) -> str:
    p = node.params
    if node.type == "polyhedron":
        return (f"polyhedron(points = {_rows(p['points'], fmt)}, "
                f"faces = {_rows(p['faces'], fmt)}, convexity = 10)")
    raise ValueError(f"not a mesh node: {node.type}")  # pragma: no cover


# ------------------------------------------------------------ import

def _b_polyhedron(parser, positional, named):
    from .model import CadNode
    from .scadparse import _num
    points = named.get("points",
                       positional[0] if positional else None)
    faces = named.get("faces", named.get(
        "triangles", positional[1] if len(positional) > 1 else None))
    if not isinstance(points, list) or not isinstance(faces, list):
        parser.warn("polyhedron without points and faces skipped")
        return None
    pts = [[_num(v) for v in (list(row) + [0.0, 0.0, 0.0])[:3]]
           for row in points if isinstance(row, list)]
    fcs = [[int(v) if isinstance(v, (int, float)) else v for v in row]
           for row in faces if isinstance(row, list)]
    return CadNode("polyhedron", "Polyhedron", dict(points=pts, faces=fcs))


BUILDERS = {"polyhedron": _b_polyhedron}


# -------------------------------------------------------- validation

def _check_polyhedron(p):
    points, faces = p.get("points") or [], p.get("faces") or []
    if len(points) < 4:
        return "a polyhedron needs at least 4 points"
    if len(faces) < 4:
        return "a polyhedron needs at least 4 faces"
    count = len(points)
    edges = {}
    for number, face in enumerate(faces):
        try:
            idx = [int(v) for v in face]
        except (TypeError, ValueError):
            return f"face {number}: point indices must be whole numbers"
        if len(idx) < 3:
            return f"face {number} has fewer than 3 points"
        bad = [i for i in idx if not 0 <= i < count]
        if bad:
            return (f"face {number} uses point {bad[0]}, but there are "
                    f"only {count} points")
        for a, b in zip(idx, idx[1:] + idx[:1]):
            edges[(a, b)] = edges.get((a, b), 0) + 1
    for (a, b), used in edges.items():
        if used > 1:
            return (f"edge {a}-{b} runs the same way in two faces — one "
                    "of them is wound the wrong way")
        if (b, a) not in edges:
            return (f"edge {a}-{b} belongs to one face only — the "
                    "surface is not closed")
    return None


def check(node, env):
    if node.type == "polyhedron":
        return _check_polyhedron(node.params)
    return None


# ------------------------------------------------------ tessellation

def tess(node, env, color, sel, selected):
    from . import mesh
    if node.type == "polyhedron":
        pts = [tuple(mesh.rv(v, env)
                     for v in (list(row) + [0.0, 0.0, 0.0])[:3])
               for row in node.params.get("points") or []]
        tris = []
        for face in node.params.get("faces") or []:
            try:
                idx = [int(v) for v in face]
            except (TypeError, ValueError):
                continue
            if len(idx) < 3 or any(not 0 <= i < len(pts) for i in idx):
                continue
            ring = idx[::-1]      # clockwise from outside -> our CCW
            for k in range(1, len(ring) - 1):
                tris.append((pts[ring[0]], pts[ring[k]], pts[ring[k + 1]]))
        return mesh._emit(tris, color, selected)
    return []                                     # pragma: no cover
