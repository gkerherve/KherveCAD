"""Reference geometry (Qt-free), 2026-10-27 — SolidWorks' Reference
Geometry: planes, axes and points that stay in the tree, are drawn in the
3D view and are sketched on.

The user: "selecting an origin or a plane on the side of a thing, and we
need to see it in the 3D view ... select a plane in 3D and it stays there
if we wish to, and then make a rectangle."

Three nodes, construction only — they draw nothing in the model:

- ``ref_plane``  origin x, y, z + normal nx, ny, nz + ``size`` (the
  square drawn, mm);
- ``ref_axis``   a point x, y, z + direction dx, dy, dz + ``length``;
- ``ref_point``  x, y, z.

Each compiles to a ``kcad_ref_*`` call whose helper module is EMPTY, so
the OpenSCAD program renders nothing for it and re-imports it as the same
node (GUI and code stay one). Every number may be an expression.

The constructions SolidWorks offers, as plain functions over world
points: `offset_plane` (a face + distance), `plane_three_points`,
`plane_at_angle` (through an edge, turned from a face), `plane_from_axis`
(through an axis, square to a plane), `axis_two_points`,
`axis_of_planes` (where two planes meet), `axis_of_cylinder` (a round
face's triangles), `frame` (the plane's right / up / normal, the same
axes Sketch on Face uses, so a sketch on a plane is a face sketch).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

CONTROL = "ctl"

NODE_TYPES = {
    "ref_plane": dict(
        label="Plane", category=CONTROL, icon="mdi.square-outline",
        params=dict(x=0.0, y=0.0, z=0.0, nx=0.0, ny=0.0, nz=1.0,
                    size=100.0),
        schema=[("x", "Origin X", "float", -1e9, 1e9),
                ("y", "Origin Y", "float", -1e9, 1e9),
                ("z", "Origin Z", "float", -1e9, 1e9),
                ("nx", "Normal X", "float", -1.0, 1.0),
                ("ny", "Normal Y", "float", -1.0, 1.0),
                ("nz", "Normal Z", "float", -1.0, 1.0),
                ("size", "Drawn size (mm)", "float", 0.1, 1e7)]),
    "ref_axis": dict(
        label="Axis", category=CONTROL, icon="mdi.axis-arrow",
        params=dict(x=0.0, y=0.0, z=0.0, dx=0.0, dy=0.0, dz=1.0,
                    length=100.0),
        schema=[("x", "Point X", "float", -1e9, 1e9),
                ("y", "Point Y", "float", -1e9, 1e9),
                ("z", "Point Z", "float", -1e9, 1e9),
                ("dx", "Direction X", "float", -1.0, 1.0),
                ("dy", "Direction Y", "float", -1.0, 1.0),
                ("dz", "Direction Z", "float", -1.0, 1.0),
                ("length", "Drawn length (mm)", "float", 0.1, 1e7)]),
    "ref_point": dict(
        label="Point", category=CONTROL, icon="mdi.circle-small",
        params=dict(x=0.0, y=0.0, z=0.0),
        schema=[("x", "X", "float", -1e9, 1e9),
                ("y", "Y", "float", -1e9, 1e9),
                ("z", "Z", "float", -1e9, 1e9)]),
}
TYPES = frozenset(NODE_TYPES)
LEAVES = frozenset(NODE_TYPES)

HELPER = """\
// reference geometry: construction only, renders nothing
module kcad_ref_plane(origin = [0, 0, 0], normal = [0, 0, 1],
                      size = 100) {}
module kcad_ref_axis(point = [0, 0, 0], direction = [0, 0, 1],
                     length = 100) {}
module kcad_ref_point(at = [0, 0, 0]) {}"""


# --------------------------------------------------------------- vectors

def _sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def _add(a, b):
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def _mul(a, k):
    return [a[0] * k, a[1] * k, a[2] * k]


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]]


def _len(a):
    return math.sqrt(_dot(a, a))


def unit(a):
    n = _len(a)
    if n < 1e-12:
        raise ValueError("a direction of zero length")
    return [a[0] / n, a[1] / n, a[2] / n]


def _rot(v, axis, deg):
    """*v* turned *deg* about the unit *axis* (Rodrigues)."""
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    k = axis
    return _add(_add(_mul(v, c), _mul(_cross(k, v), s)),
                _mul(k, _dot(k, v) * (1 - c)))


def _tidy(v, digits=6):
    return [round(float(c), digits) + 0.0 for c in v]


# ---------------------------------------------------------- constructions

def offset_plane(point, normal, distance=0.0):
    """(origin, normal) of the plane *distance* off a face."""
    n = unit(normal)
    return _tidy(_add(point, _mul(n, distance))), _tidy(n)


def plane_three_points(a, b, c):
    n = _cross(_sub(b, a), _sub(c, a))
    if _len(n) < 1e-9:
        raise ValueError("The three points lie on one line.")
    centre = _mul(_add(_add(a, b), c), 1.0 / 3.0)
    return _tidy(centre), _tidy(unit(n))


def plane_at_angle(edge_a, edge_b, face_normal, angle):
    """The plane through the edge a-b, turned *angle* degrees from the
    face it bounds (normal *face_normal*) about that edge."""
    axis = unit(_sub(edge_b, edge_a))
    n = _sub(face_normal, _mul(axis, _dot(face_normal, axis)))
    n = _rot(unit(n), axis, angle)
    mid = _mul(_add(edge_a, edge_b), 0.5)
    return _tidy(mid), _tidy(unit(n))


def plane_from_axis(point, direction, plane_normal):
    """Through an axis and square to a plane (the axis lies in it)."""
    d = unit(direction)
    n = _cross(d, plane_normal)
    if _len(n) < 1e-9:
        raise ValueError("The axis is square to that plane — any plane "
                         "through it would do; pick another plane.")
    return _tidy(point), _tidy(unit(n))


def axis_two_points(a, b):
    return _tidy(a), _tidy(unit(_sub(b, a)))


def axis_of_planes(o1, n1, o2, n2):
    """Where two planes meet."""
    d = _cross(n1, n2)
    if _len(d) < 1e-9:
        raise ValueError("The planes are parallel; they never meet.")
    d = unit(d)
    # the point of the line nearest the first plane's origin
    h1, h2 = _dot(n1, o1), _dot(n2, o2)
    n12 = _dot(n1, n2)
    det = 1 - n12 * n12
    c1 = (h1 - h2 * n12) / det
    c2 = (h2 - h1 * n12) / det
    p = _add(_mul(n1, c1), _mul(n2, c2))
    # slide it along the line next to the first origin
    p = _add(p, _mul(d, _dot(_sub(o1, p), d)))
    return _tidy(p), _tidy(d)


def axis_of_cylinder(tris):
    """(point, direction) of a round face from its triangles: the axis
    is square to every normal (least eigenvector of Σ n nᵀ), the point
    the least-squares centre of the face's vertices in the cross-plane."""
    import numpy as np
    if not tris:
        raise ValueError("No face to find the axis of.")
    t = np.asarray(tris, float).reshape(-1, 3, 3)
    n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    ln = np.linalg.norm(n, axis=1)
    n = n[ln > 1e-12] / ln[ln > 1e-12][:, None]
    if len(n) < 2:
        raise ValueError("That face is flat — pick a round one.")
    w, v = np.linalg.eigh(n.T @ n)
    d = v[:, 0]
    if w[1] < 1e-6 * max(w[2], 1e-12):
        raise ValueError("That face is flat — pick a round one.")
    pts = t.reshape(-1, 3)
    # cross-plane coordinates
    e1 = np.cross(d, [1.0, 0.0, 0.0])
    if np.linalg.norm(e1) < 0.1:
        e1 = np.cross(d, [0.0, 1.0, 0.0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(d, e1)
    u, vv = pts @ e1, pts @ e2
    # circle fit: u² + v² + a u + b v + c = 0
    a = np.column_stack([u, vv, np.ones_like(u)])
    rhs = -(u * u + vv * vv)
    sol, *_ = np.linalg.lstsq(a, rhs, rcond=None)
    cu, cv = -sol[0] / 2, -sol[1] / 2
    along = float(np.mean(pts @ d))
    p = cu * e1 + cv * e2 + along * d
    if d[int(np.argmax(np.abs(d)))] < 0:
        d = -d
    return _tidy(p), _tidy(d)


def frame(origin, normal):
    """(origin, right, up, normal) of a plane — the axes a face sketch
    on it gets (face_sketch.frame_for)."""
    from .face_sketch import frame_for
    r, u, n = frame_for(normal)
    return list(origin), r, u, n


#: the three main planes, as (name, view2d plane, origin, normal)
MAIN_PLANES = (("Front", "Front (XZ)", (0.0, 0.0, 0.0), (0.0, -1.0, 0.0)),
               ("Top", "Top (XY)", (0.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
               ("Right", "Side (YZ)", (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)))


def plane_of(node, env=None):
    """(origin, normal) of a ref_plane, its numbers resolved."""
    from . import mesh
    p = mesh.rp(node, env)
    return ([float(p["x"]), float(p["y"]), float(p["z"])],
            unit([float(p["nx"]), float(p["ny"]), float(p["nz"])]))


def axis_of(node, env=None):
    from . import mesh
    p = mesh.rp(node, env)
    return ([float(p["x"]), float(p["y"]), float(p["z"])],
            unit([float(p["dx"]), float(p["dy"]), float(p["dz"])]))


def ray_plane(origin, d, po, pn):
    """The point a ray meets a plane, or None (parallel / behind)."""
    den = _dot(d, pn)
    if abs(den) < 1e-12:
        return None
    t = _dot(_sub(po, origin), pn) / den
    if t < 0:
        return None
    return _add(origin, _mul(d, t))


# ---------------------------------------------------------------- code

def preamble(root) -> list:
    if any(n.type in TYPES for n in root.walk()):
        return HELPER.split("\n")
    return []


def statement(node, fmt, fn) -> str:
    p = node.params

    def vec(*keys):
        return "[" + ", ".join(fmt(p.get(k, 0.0)) for k in keys) + "]"
    if node.type == "ref_plane":
        return (f"kcad_ref_plane(origin = {vec('x', 'y', 'z')}, normal = "
                f"{vec('nx', 'ny', 'nz')}, size = "
                f"{fmt(p.get('size', 100.0))})")
    if node.type == "ref_axis":
        return (f"kcad_ref_axis(point = {vec('x', 'y', 'z')}, direction = "
                f"{vec('dx', 'dy', 'dz')}, length = "
                f"{fmt(p.get('length', 100.0))})")
    return f"kcad_ref_point(at = {vec('x', 'y', 'z')})"


def _vec(parser, value, default):
    from .curves2d import _read_rows
    rows = _read_rows([value] if value is not None else [default], 3,
                      parser)
    return (list(rows[0]) + list(default))[:3] if rows else list(default)


def _b_plane(parser, positional, named):
    from .model import CadNode
    from .scadparse import _num
    o = _vec(parser, named.get("origin"), [0.0, 0.0, 0.0])
    n = _vec(parser, named.get("normal"), [0.0, 0.0, 1.0])
    return CadNode("ref_plane", "Plane", dict(
        x=o[0], y=o[1], z=o[2], nx=n[0], ny=n[1], nz=n[2],
        size=_num(named.get("size", 100.0), 100.0)))


def _b_axis(parser, positional, named):
    from .model import CadNode
    from .scadparse import _num
    o = _vec(parser, named.get("point"), [0.0, 0.0, 0.0])
    d = _vec(parser, named.get("direction"), [0.0, 0.0, 1.0])
    return CadNode("ref_axis", "Axis", dict(
        x=o[0], y=o[1], z=o[2], dx=d[0], dy=d[1], dz=d[2],
        length=_num(named.get("length", 100.0), 100.0)))


def _b_point(parser, positional, named):
    from .model import CadNode
    o = _vec(parser, named.get("at", positional[0] if positional
                               else None), [0.0, 0.0, 0.0])
    return CadNode("ref_point", "Point", dict(x=o[0], y=o[1], z=o[2]))


BUILDERS = {"kcad_ref_plane": _b_plane, "kcad_ref_axis": _b_axis,
            "kcad_ref_point": _b_point}


def check(node, env):
    from . import mesh
    try:
        p = mesh.rp(node, env)
    except Exception as exc:                       # pragma: no cover
        return str(exc)
    if node.type == "ref_plane":
        if math.hypot(p["nx"], p["ny"], p["nz"]) < 1e-9:
            return "Plane: the normal has no direction"
    if node.type == "ref_axis":
        if math.hypot(p["dx"], p["dy"], p["dz"]) < 1e-9:
            return "Axis: the direction has no length"
    return None


def tess(node, env, color, sel, selected):
    return []                         # construction: draws nothing


def outlines(node, env):
    return []
