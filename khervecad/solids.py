"""Regular solids and regular 2D shapes — BOSL2's polyhedra.scad and
MCAD's regular_shapes.scad as two nodes:

- **polyhedron_solid** — the five Platonic solids and the common
  Archimedean ones (cuboctahedron, truncated tetrahedron / cube /
  octahedron / icosahedron — the football —, rhombicuboctahedron,
  icosidodecahedron), sized by circumradius. Each is the convex hull of
  its vertices (standard coordinates: permutations of a few numbers and
  the golden ratio), so the helper needs no face table;
- **star** — a regular polygon (``inner_radius`` 0) or a star of
  ``points`` tips between two radii, turned by ``angle``.

Both compile to one ``kcad_*`` call whose helper computes the same
points in OpenSCAD.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import itertools
import math

SHAPE_2D = "2d"
SHAPE_3D = "3d"

PHI = (1 + math.sqrt(5)) / 2

SOLIDS = ("tetrahedron", "cube", "octahedron", "dodecahedron",
          "icosahedron", "cuboctahedron", "truncated_tetrahedron",
          "truncated_cube", "truncated_octahedron", "truncated_icosahedron",
          "rhombicuboctahedron", "icosidodecahedron")

NODE_TYPES = {
    "polyhedron_solid": dict(
        label="Regular polyhedron", category=SHAPE_3D,
        icon="mdi.hexagon-multiple-outline",
        params=dict(kind="icosahedron", radius=10.0, x=0.0, y=0.0, z=0.0),
        schema=[("kind", "Solid", "choice", list(SOLIDS), None),
                ("radius", "Circumradius (mm)", "float", 0.01, 1e6),
                ("x", "Centre X", "float", -1e6, 1e6),
                ("y", "Centre Y", "float", -1e6, 1e6),
                ("z", "Centre Z", "float", -1e6, 1e6)]),
    "star": dict(
        label="Regular polygon / star", category=SHAPE_2D,
        icon="mdi.star-outline",
        params=dict(points=5, radius=10.0, inner_radius=4.0, angle=90.0,
                    x=0.0, y=0.0),
        schema=[("points", "Sides / tips", "int", 3, 1000),
                ("radius", "Outer radius (mm)", "float", 0.01, 1e6),
                ("inner_radius", "Inner radius (0 = regular polygon)",
                 "float", 0.0, 1e6),
                ("angle", "Turn° (first tip)", "float", -360.0, 360.0),
                ("x", "Centre X", "float", -1e6, 1e6),
                ("y", "Centre Y", "float", -1e6, 1e6)]),
}
TYPES = frozenset(NODE_TYPES)
LEAVES = frozenset(NODE_TYPES)
TEXT_PARAMS = frozenset({"kind"})


# ------------------------------------------------------------- vertices

def _signs(v):
    """Every sign combination of *v* (zeros stay single)."""
    choices = [(c,) if c == 0 else (c, -c) for c in v]
    return [tuple(p) for p in itertools.product(*choices)]


def _cyclic(v):
    return [v, (v[1], v[2], v[0]), (v[2], v[0], v[1])]


def _all_perms(v):
    return sorted(set(itertools.permutations(v)))


def raw_vertices(kind):
    """Unscaled vertex coordinates of a solid."""
    p = PHI
    pts = []
    if kind == "tetrahedron":
        pts = [(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)]
    elif kind == "cube":
        pts = _signs((1, 1, 1))
    elif kind == "octahedron":
        for v in _cyclic((1, 0, 0)):
            pts += _signs(v)
    elif kind == "dodecahedron":
        pts = _signs((1, 1, 1))
        for v in _cyclic((0, 1 / p, p)):
            pts += _signs(v)
    elif kind == "icosahedron":
        for v in _cyclic((0, 1, p)):
            pts += _signs(v)
    elif kind == "cuboctahedron":
        for v in _cyclic((1, 1, 0)):
            pts += _signs(v)
    elif kind == "truncated_tetrahedron":
        for v in _all_perms((3, 1, 1)):
            pts += [s for s in _signs(v)
                    if sum(1 for c in s if c < 0) % 2 == 0]
    elif kind == "truncated_cube":
        xi = math.sqrt(2) - 1
        for v in _cyclic((xi, 1, 1)):
            pts += _signs(v)
    elif kind == "truncated_octahedron":
        for v in _all_perms((0, 1, 2)):
            pts += _signs(v)
    elif kind == "truncated_icosahedron":
        for base in ((0, 1, 3 * p), (1, 2 + p, 2 * p), (p, 2, p ** 3)):
            for v in _cyclic(base):
                pts += _signs(v)
    elif kind == "rhombicuboctahedron":
        for v in _cyclic((1, 1, 1 + math.sqrt(2))):
            pts += _signs(v)
    elif kind == "icosidodecahedron":
        for v in _cyclic((0, 0, p)):
            pts += _signs(v)
        for v in _cyclic((0.5, p / 2, p * p / 2)):
            pts += _signs(v)
    return sorted(set((float(a), float(b), float(c)) for a, b, c in pts))


def vertices(kind, radius):
    raw = raw_vertices(kind)
    far = max(math.sqrt(a * a + b * b + c * c) for a, b, c in raw)
    k = radius / far
    return [(a * k, b * k, c * k) for a, b, c in raw]


def star_outline(points, radius, inner, angle):
    n = max(int(points), 3)
    out = []
    if inner <= 0:
        for i in range(n):
            a = math.radians(angle + 360.0 * i / n)
            out.append((radius * math.cos(a), radius * math.sin(a)))
        return out
    for i in range(2 * n):
        r = radius if i % 2 == 0 else inner
        a = math.radians(angle + 180.0 * i / n)
        out.append((r * math.cos(a), r * math.sin(a)))
    return out


HELPER = """\
function kcad_phi() = (1 + sqrt(5)) / 2;
function kcad_signs(v) = [for (a = v[0] == 0 ? [0] : [v[0], -v[0]],
                              b = v[1] == 0 ? [0] : [v[1], -v[1]],
                              c = v[2] == 0 ? [0] : [v[2], -v[2]]) [a, b, c]];
function kcad_cyclic(v) = [v, [v[1], v[2], v[0]], [v[2], v[0], v[1]]];
function kcad_perms(v) = [v, [v[0], v[2], v[1]], [v[1], v[0], v[2]],
                          [v[1], v[2], v[0]], [v[2], v[0], v[1]],
                          [v[2], v[1], v[0]]];
function kcad_from(bases, perm = false) =
    [for (b = bases) for (v = perm ? kcad_perms(b) : kcad_cyclic(b))
     for (s = kcad_signs(v)) s];
function kcad_solid_raw(kind) = let (p = kcad_phi())
    kind == "tetrahedron" ? [[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]]
  : kind == "cube" ? kcad_signs([1, 1, 1])
  : kind == "octahedron" ? kcad_from([[1, 0, 0]])
  : kind == "dodecahedron" ? concat(kcad_signs([1, 1, 1]),
                                    kcad_from([[0, 1 / p, p]]))
  : kind == "icosahedron" ? kcad_from([[0, 1, p]])
  : kind == "cuboctahedron" ? kcad_from([[1, 1, 0]])
  : kind == "truncated_tetrahedron" ?
        [for (s = kcad_from([[3, 1, 1]], true))
         if (len([for (c = s) if (c < 0) 1]) % 2 == 0) s]
  : kind == "truncated_cube" ? kcad_from([[sqrt(2) - 1, 1, 1]])
  : kind == "truncated_octahedron" ? kcad_from([[0, 1, 2]], true)
  : kind == "truncated_icosahedron" ?
        kcad_from([[0, 1, 3 * p], [1, 2 + p, 2 * p], [p, 2, p * p * p]])
  : kind == "rhombicuboctahedron" ? kcad_from([[1, 1, 1 + sqrt(2)]])
  : kind == "icosidodecahedron" ?
        concat(kcad_from([[0, 0, p]]), kcad_from([[0.5, p / 2, p * p / 2]]))
  : [];
module kcad_polyhedron(kind = "icosahedron", radius = 10, center = [0, 0, 0]) {
    raw = kcad_solid_raw(kind);
    far = max([for (v = raw) norm(v)]);
    translate(center) hull() for (v = raw)
        translate(v * radius / far) cube(0.001, center = true);
}
function kcad_star_points(n, r, ri, a) = ri <= 0
    ? [for (i = [0 : n - 1]) r * [cos(a + 360 * i / n), sin(a + 360 * i / n)]]
    : [for (i = [0 : 2 * n - 1]) (i % 2 == 0 ? r : ri)
       * [cos(a + 180 * i / n), sin(a + 180 * i / n)]];
module kcad_star(points = 5, radius = 10, inner_radius = 4, angle = 90,
                 center = [0, 0]) {
    translate(center)
        polygon(kcad_star_points(max(round(points), 3), radius, inner_radius,
                                 angle));
}"""


def preamble(root) -> list:
    if any(n.type in TYPES for n in root.walk()):
        return HELPER.split("\n")
    return []


# ---------------------------------------------------------------- codegen

def statement(node, fmt, fn) -> str:
    from .model import scad_str
    p = node.params
    if node.type == "polyhedron_solid":
        return (f"kcad_polyhedron(kind = {scad_str(str(p.get('kind')))}, "
                f"radius = {fmt(p['radius'])}, center = [{fmt(p['x'])}, "
                f"{fmt(p['y'])}, {fmt(p['z'])}])")
    return (f"kcad_star(points = {fmt(p['points'])}, radius = "
            f"{fmt(p['radius'])}, inner_radius = {fmt(p['inner_radius'])}, "
            f"angle = {fmt(p['angle'])}, center = [{fmt(p['x'])}, "
            f"{fmt(p['y'])}])")


def _vec(value, n, parser_num):
    if isinstance(value, list):
        return [parser_num(v, 0.0) for v in (list(value) + [0.0] * n)[:n]]
    return [0.0] * n


def _b_polyhedron(parser, positional, named):
    from .model import CadNode
    from .scadparse import _num
    kind = str(named.get("kind", "icosahedron"))
    if kind not in SOLIDS:
        parser.warn(f"unknown solid {kind!r} — kept as icosahedron")
        kind = "icosahedron"
    c = _vec(named.get("center"), 3, _num)
    return CadNode("polyhedron_solid", kind.replace("_", " ").capitalize(),
                   dict(kind=kind, radius=_num(named.get("radius", 10.0),
                                               10.0),
                        x=c[0], y=c[1], z=c[2]))


def _b_star(parser, positional, named):
    from .model import CadNode
    from .scadparse import _num
    c = _vec(named.get("center"), 2, _num)
    n = _num(named.get("points", 5), 5.0)
    return CadNode("star", "Star", dict(
        points=n if isinstance(n, str) else max(int(n), 3),
        radius=_num(named.get("radius", 10.0), 10.0),
        inner_radius=_num(named.get("inner_radius", 4.0), 4.0),
        angle=_num(named.get("angle", 90.0), 90.0), x=c[0], y=c[1]))


BUILDERS = {"kcad_polyhedron": _b_polyhedron, "kcad_star": _b_star}


def check(node, env):
    from . import mesh
    p = mesh.rp(node, env)
    if node.type == "polyhedron_solid":
        if str(node.params.get("kind")) not in SOLIDS:
            return f"solid must be one of {', '.join(SOLIDS)}"
        if p["radius"] <= 0:
            return "the radius must be above 0"
        return None
    if p["radius"] <= 0 or p["inner_radius"] < 0:
        return "the radii must be above 0"
    if p["inner_radius"] >= p["radius"]:
        return "the inner radius must be smaller than the outer"
    return None


def outlines(node, env):
    from . import mesh
    p = mesh.rp(node, env)
    pts = star_outline(p["points"], p["radius"], p["inner_radius"],
                       p["angle"])
    return [[(x + p["x"], y + p["y"]) for x, y in pts]]


def tess(node, env, color, sel, selected):
    from . import geom3d, mesh
    if node.type == "star":
        return mesh._emit(mesh.flat_mesh(node, env), color, selected)
    p = mesh.rp(node, env)
    pts = [(x + p["x"], y + p["y"], z + p["z"])
           for x, y, z in vertices(str(node.params.get("kind")),
                                   p["radius"])]
    return mesh._emit(geom3d.convex_hull(pts), color, selected)
