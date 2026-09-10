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

import json

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
    "loft": dict(
        label="Loft (tube through sections)", category=SHAPE_3D,
        icon="mdi.vector-curve",
        params=dict(sections=[[0.0, 0.0, 0.0, 6.0, 6.0],
                              [0.0, 0.0, 30.0, 4.0, 4.0],
                              [12.0, 0.0, 50.0, 3.0, 3.0]],
                    sides=24, smooth=3, caps="round"),
        schema=[("sections", "Sections (centre, radii)", "rows",
                 ["X", "Y", "Z", "Width r", "Height r"], None),
                ("sides", "Sides", "int", 3, 256),
                ("smooth", "Smoothing steps", "int", 0, 12),
                ("caps", "Ends", "choice", ["round", "flat"], None)]),
    "blend": dict(
        label="Smooth blend", category=OPERATION, icon="mdi.blur-radial",
        params=dict(radius=4.0, detail=40),
        schema=[("radius", "Blend radius", "float", 0.0, 1e4),
                ("detail", "Detail (cells across)", "int", 8, 160)]),
    "bend": dict(
        label="Bend", category=OPERATION, icon="mdi.arrow-u-right-top",
        params=dict(axis="z", toward="x", angle=45.0, detail=2.0),
        schema=[("axis", "Length axis", "choice", ["x", "y", "z"], None),
                ("toward", "Bend toward", "choice", ["x", "y", "z"], None),
                ("angle", "Angle°", "float", -720.0, 720.0),
                ("detail", "Max edge (mm)", "float", 0.05, 1e4)]),
    "twist": dict(
        label="Twist", category=OPERATION, icon="mdi.rotate-3d",
        params=dict(axis="z", angle=90.0, detail=2.0),
        schema=[("axis", "Axis", "choice", ["x", "y", "z"], None),
                ("angle", "Angle° (over the length)", "float",
                 -3600.0, 3600.0),
                ("detail", "Max edge (mm)", "float", 0.05, 1e4)]),
    "taper": dict(
        label="Taper", category=OPERATION, icon="mdi.triangle-outline",
        params=dict(axis="z", factor=0.5, detail=5.0),
        schema=[("axis", "Axis", "choice", ["x", "y", "z"], None),
                ("factor", "Scale at the far end", "float", 0.01, 100.0),
                ("detail", "Max edge (mm)", "float", 0.05, 1e4)]),
    "lattice": dict(
        label="Lattice (free-form)", category=OPERATION, icon="mdi.grid",
        params=dict(offsets=[[0.0, 0.0, 0.0] for _ in range(8)],
                    detail=2.0),
        schema=[("offsets", "Corner offsets (x fastest, then y, z)",
                 "rows", ["dX", "dY", "dZ"], None),
                ("detail", "Max edge (mm)", "float", 0.05, 1e4)]),
    "subdivide": dict(
        label="Subdivide (smooth)", category=OPERATION,
        icon="mdi.circle-multiple-outline",
        params=dict(levels=2),
        schema=[("levels", "Levels", "int", 1, 4)]),
}

TYPES = frozenset(NODE_TYPES)
LEAVES = frozenset({"polyhedron", "loft"})
WRAPPERS = frozenset({"blend", "bend", "twist", "taper", "lattice",
                      "subdivide"})

#: wrappers whose surface is computed here and baked into the program,
#: with their helper module's parameters (besides points and faces)
_BAKED = {
    "blend": [("radius", 0), ("detail", 40)],
    "bend": [("axis", "z"), ("toward", "x"), ("angle", 0), ("detail", 2)],
    "twist": [("axis", "z"), ("angle", 0), ("detail", 2)],
    "taper": [("axis", "z"), ("factor", 1), ("detail", 5)],
    "lattice": [("offsets", []), ("detail", 2)],
    "subdivide": [("levels", 1)],
}
#: parameters written as quoted OpenSCAD strings
_CHOICES = {"axis", "toward"}
#: what a deformer cannot take from the preview mesh: booleans and the
#: rest are only approximated there, so baking them would bake a wrong
#: shape into the program
_INEXACT = {"difference", "intersection", "minkowski", "offset",
            "projection", "scad_raw"}

#: set while generating code for reading rather than rendering
#: (get_code): baked point/face arrays are summarised, not written out.
#: The importer ignores those arrays anyway — it rebuilds the node from
#: its parameters and children — so an elided program still round-trips.
ELIDE = False

#: OpenSCAD for kcad_loft: the tube computed from the sections at
#: render time — the same formulas as loft.py (keep them in step), so
#: expressions and loop variables in the sections just work.
HELPERS = {
    "loft": """\
function kcad_unit(v) = let(l = norm(v)) l > 1e-12 ? v / l : [0, 0, 1];
function kcad_cr(p0, p1, p2, p3, t) =
    0.5 * (2 * p1 + (p2 - p0) * t
           + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
           + (3 * p1 - p0 - 3 * p2 + p3) * t * t * t);
function kcad_loft_path(s, smooth) =
    let(n = len(s))
    smooth <= 0 || n < 2 ? s :
    let(ext = concat([2 * s[0] - s[1]], s, [2 * s[n - 1] - s[n - 2]]))
    concat([for (k = [0 : n - 2], j = [0 : smooth])
                kcad_cr(ext[k], ext[k + 1], ext[k + 2], ext[k + 3],
                        j / (smooth + 1))],
           [s[n - 1]]);
function kcad_rmf(c, t, i, acc) =
    i >= len(c) - 1 ? acc :
    let(nrm = acc[len(acc) - 1],
        v1 = c[i + 1] - c[i], c1 = v1 * v1,
        rl = c1 < 1e-18 ? nrm : nrm - (2 / c1) * (v1 * nrm) * v1,
        tl = c1 < 1e-18 ? t[i] : t[i] - (2 / c1) * (v1 * t[i]) * v1,
        v2 = t[i + 1] - tl, c2 = v2 * v2,
        nn = c2 < 1e-18 ? rl : rl - (2 / c2) * (v2 * rl) * v2)
    kcad_rmf(c, t, i + 1, concat(acc, [nn]));
module kcad_loft(sections = [], sides = 24, smooth = 3, caps = "round") {
    s = kcad_loft_path(sections, smooth);
    n = len(s);
    if (n >= 2) {
        S = max(floor(sides + 0.5), 3);
        c = [for (row = s) [row[0], row[1], row[2]]];
        t = [for (i = [0 : n - 1])
                kcad_unit(c[min(i + 1, n - 1)] - c[max(i - 1, 0)])];
        ref = abs(t[0][2]) > 0.99 ? [1, 0, 0] : [0, 0, 1];
        nrm = kcad_rmf(c, t, 0, [kcad_unit(ref - (ref * t[0]) * t[0])]);
        bin = [for (i = [0 : n - 1]) cross(t[i], nrm[i])];
        rad = [for (row = s) [max(row[3], 0.001), max(row[4], 0.001)]];
        domed = caps != "flat";
        m = max(2, floor(S / 4 + 0.5));
        d0 = (rad[0][0] + rad[0][1]) / 2;
        d1 = (rad[n - 1][0] + rad[n - 1][1]) / 2;
        head = domed ? [for (j = [m - 1 : -1 : 1]) let(phi = 90 * j / m)
            [c[0] - t[0] * d0 * sin(phi), nrm[0], bin[0],
             rad[0][0] * cos(phi), rad[0][1] * cos(phi)]] : [];
        body = [for (i = [0 : n - 1])
            [c[i], nrm[i], bin[i], rad[i][0], rad[i][1]]];
        tail = domed ? [for (j = [1 : m - 1]) let(phi = 90 * j / m)
            [c[n - 1] + t[n - 1] * d1 * sin(phi), nrm[n - 1], bin[n - 1],
             rad[n - 1][0] * cos(phi), rad[n - 1][1] * cos(phi)]] : [];
        rings = concat(head, body, tail);
        R = len(rings);
        pts = concat([domed ? c[0] - t[0] * d0 : c[0]],
            [for (r = rings, k = [0 : S - 1]) let(a = 360 * k / S)
                r[0] + r[3] * cos(a) * r[2] + r[4] * sin(a) * r[1]],
            [domed ? c[n - 1] + t[n - 1] * d1 : c[n - 1]]);
        last = len(pts) - 1;
        faces = concat(
            [for (r = [0 : R - 2], k = [0 : S - 1], f = [0, 1])
                let(a0 = 1 + r * S, b0 = 1 + (r + 1) * S, k1 = (k + 1) % S)
                f == 0 ? [a0 + k, a0 + k1, b0 + k1]
                       : [a0 + k, b0 + k1, b0 + k]],
            [for (k = [0 : S - 1], f = [0, 1]) let(k1 = (k + 1) % S)
                f == 0 ? [0, 1 + k1, 1 + k]
                       : [last, 1 + (R - 1) * S + k, 1 + (R - 1) * S + k1]]);
        polyhedron(points = pts, faces = faces, convexity = 10);
    }
}""",
}


def _literal(value) -> str:
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, list):
        return "[]"
    return str(value)


# A baked node's surface is computed in Python and written into its
# call; the children stay in the call's block so the node round-trips,
# and the module simply never instantiates them.
for _t, _args in _BAKED.items():
    HELPERS[_t] = (
        f"module kcad_{_t}("
        + ", ".join(f"{k} = {_literal(v)}" for k, v in _args)
        + ", points = [], faces = []) {\n"
        "    polyhedron(points = points, faces = faces, convexity = 10);\n}")


def preamble(root) -> list:
    """Helper-module source lines this module's nodes need."""
    used = {n.type for n in root.walk()}
    lines = []
    for t in ("loft",) + tuple(_BAKED):
        if t in used:
            lines.extend(HELPERS[t].split("\n"))
    return lines


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


def _rows_wrapped(rows, fmt, per_line: int = 8) -> str:
    """Like _rows, over several lines (a baked mesh is thousands of
    rows, and one physical line of it would choke the code editor)."""
    if not rows:
        return "[]"
    if ELIDE:
        return f"[/* {len(rows)} baked rows */]"
    chunks = [", ".join("[" + ", ".join(fmt(v) for v in row) + "]"
                        for row in rows[i:i + per_line])
              for i in range(0, len(rows), per_line)]
    return "[\n        " + ",\n        ".join(chunks) + "\n    ]"


# ------------------------------------------------ baked-mesh cache

#: {content key: (points, faces, triangles)} — baking a blend samples a
#: grid, far too slow to repeat on every regeneration of the program
_CACHE = {}
_CACHE_SIZE = 16


def _codegen_env(node) -> dict:
    """The variables in scope at *node*: every assignment in each
    enclosing container, outermost first (what the tessellator has in
    hand when it reaches the node)."""
    from . import mesh
    chain = []
    parent = node.parent
    while parent is not None:
        chain.append(parent)
        parent = parent.parent
    env = {}
    for container in reversed(chain):
        for child in container.children:
            if child.type == "assign":
                mesh._apply_assign(child, env)
            elif child.type == "variables":
                for grandchild in child.children:
                    if grandchild.type == "assign":
                        mesh._apply_assign(grandchild, env)
    return env


def _compute(node, env) -> list:
    """The triangles of a baked node, from scratch."""
    from . import deform, mesh, sdf
    p = node.params

    def num(key, default):
        return mesh.rv(p.get(key, default), env, default)
    t = node.type
    if t == "blend":
        return sdf.blend(node, env, num("radius", 4.0),
                         int(num("detail", 40.0)))
    src = [tri for tri, _c, _s in
           mesh._children_mesh(node, env, None, frozenset(), False)]
    if t == "subdivide":
        return deform.loop_subdivide(src, int(num("levels", 1.0)))
    src = deform.split_long_edges(src, num("detail", 2.0))
    axis = str(p.get("axis", "z"))
    if t == "bend":
        return deform.bend(src, axis, str(p.get("toward", "x")),
                           num("angle", 0.0))
    if t == "twist":
        return deform.twist(src, axis, num("angle", 0.0))
    if t == "taper":
        return deform.taper(src, axis, num("factor", 1.0))
    if t == "lattice":
        rows = [[mesh.rv(v, env) for v in row]
                for row in p.get("offsets") or []]
        return deform.lattice(src, rows)
    return src                                     # pragma: no cover


def baked(node, env):
    """(points, faces, triangles) of a baked node, cached by content."""
    from . import document
    key = json.dumps([document.node_to_dict(node),
                      sorted((k, repr(v)) for k, v in env.items())],
                     sort_keys=True, default=str)
    hit = _CACHE.get(key)
    if hit is None:
        tris = _compute(node, env)
        points, faces = to_polyhedron(tris)
        hit = _CACHE[key] = (points, faces, tris)
        while len(_CACHE) > _CACHE_SIZE:
            _CACHE.pop(next(iter(_CACHE)))
    return hit


# ----------------------------------------------------------- codegen

def statement(node, fmt, fn) -> str:
    p = node.params
    if node.type == "polyhedron":
        return (f"polyhedron(points = {_rows(p['points'], fmt)}, "
                f"faces = {_rows(p['faces'], fmt)}, convexity = 10)")
    if node.type in _BAKED:
        try:
            points, faces, _tris = baked(node, _codegen_env(node))
        except Exception:
            points, faces = [], []          # validation has flagged it

        def arg(key, default):
            value = p.get(key, default)
            if key in _CHOICES:
                return f'"{value}"'
            if isinstance(value, list):
                return _rows(value, fmt)
            return fmt(value)
        args = ", ".join(f"{k} = {arg(k, d)}" for k, d in _BAKED[node.type])
        return (f"kcad_{node.type}({args},\n"
                f"    points = {_rows_wrapped(points, fmt)},\n"
                f"    faces = {_rows_wrapped(faces, fmt)})")
    if node.type == "loft":
        caps = "flat" if str(p.get("caps", "round")) == "flat" else "round"
        return (f"kcad_loft(sections = {_rows(p['sections'], fmt)}, "
                f"sides = {fmt(p['sides'])}, smooth = {fmt(p['smooth'])}, "
                f'caps = "{caps}")')
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


def _b_loft(parser, positional, named):
    from .model import CadNode
    from .scadparse import _num
    sections = named.get("sections",
                         positional[0] if positional else None)
    if not isinstance(sections, list):
        parser.warn("kcad_loft without sections skipped")
        return None
    rows = [[_num(v) for v in row] for row in sections
            if isinstance(row, list)]

    def whole(key, default):
        try:
            return int(_num(named.get(key, default), default))
        except (TypeError, ValueError):
            return default
    caps = named.get("caps", "round")
    return CadNode("loft", "Loft", dict(
        sections=rows, sides=whole("sides", 24), smooth=whole("smooth", 3),
        caps="flat" if caps == "flat" else "round"))


def _b_baked(kind):
    """Builder for kcad_<kind>: the parameters come back; the baked
    points/faces are ignored, since the surface is recomputed from the
    children that follow in the call's block."""
    def build(parser, positional, named):
        from .model import CadNode
        from .scadparse import _num
        defaults = NODE_TYPES[kind]["params"]
        params = {}
        for key, _default in _BAKED[kind]:
            value = named.get(key, defaults[key])
            if key in _CHOICES:
                params[key] = value if value in ("x", "y", "z") \
                    else defaults[key]
            elif key == "offsets":
                params[key] = ([[_num(v) for v in row] for row in value
                                if isinstance(row, list)]
                               if isinstance(value, list)
                               else [list(r) for r in defaults[key]])
            elif (kind, key) in (("blend", "detail"),
                                 ("subdivide", "levels")):
                try:
                    params[key] = int(_num(value, defaults[key]))
                except (TypeError, ValueError):
                    params[key] = defaults[key]
            else:
                params[key] = _num(value, defaults[key])
        return CadNode(kind, NODE_TYPES[kind]["label"], params)
    return build


BUILDERS = {"polyhedron": _b_polyhedron, "kcad_loft": _b_loft}
BUILDERS.update({f"kcad_{t}": _b_baked(t) for t in _BAKED})


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


def _check_loft(p, env):
    from . import expr
    rows = p.get("sections") or []
    if len(rows) < 2:
        return "a loft needs at least 2 sections"
    for number, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != 5:
            return (f"section {number} needs 5 values: x, y, z, width "
                    "radius, height radius")
        for value in row:
            if isinstance(value, str):
                try:
                    expr.evaluate(value, env)
                except expr.ExprError as exc:
                    return f"section {number}: {exc}"
    if str(p.get("caps", "round")) not in ("round", "flat"):
        return "ends must be 'round' or 'flat'"
    return None


def check(node, env):
    if node.type == "polyhedron":
        return _check_polyhedron(node.params)
    if node.type == "loft":
        return _check_loft(node.params, env)
    if node.type in _BAKED:
        return _check_baked(node, env)
    return None


def _check_baked(node, env):
    from . import sdf
    t = node.type
    word = "blend" if t == "blend" else t
    parent = node.parent
    while parent is not None:
        if parent.type in ("for_loop", "while_loop", "if_else"):
            kind = parent.type.replace("_", " ").replace(" loop", "")
            return (f"a {word} is baked into one mesh, so it can't sit "
                    f"inside a {kind} — put the {kind} inside the {word}")
        parent = parent.parent
    if t == "blend":
        try:
            sdf.leaves(node, env)
        except sdf.Unsupported as exc:
            return ("a blend merges spheres, cubes, cylinders, capsules, "
                    "ellipsoids and rounded boxes (and the transforms, "
                    f"groups, loops and joints around them) — {exc} is "
                    "not one")
        return None
    bad = next((n for n in node.walk() if n is not node and n.visible
                and n.type in _INEXACT), None)
    if bad is not None:
        return (f"a {word} reshapes the preview mesh, which cannot cut "
                f"booleans — {bad.name} ({bad.type}) would be baked "
                "wrong. Deform primitives, extrusions, lofts and groups")
    p = node.params
    if t == "bend" and p.get("axis") == p.get("toward"):
        return "bend: the length axis and the bend direction must differ"
    if t == "lattice":
        rows = p.get("offsets") or []
        if len(rows) != 8 or any(not isinstance(r, list) or len(r) != 3
                                 for r in rows):
            return ("lattice: give 8 corner offsets [dx, dy, dz] — x "
                    "fastest, then y, then z")
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
    if node.type in _BAKED:
        try:
            _points, _faces, tris = baked(node, env)
        except Exception:                  # validation has flagged it
            tris = []
        out = mesh._emit(tris, color, selected)
        if sel and not selected:
            # a selected primitive inside still glows on its own
            out.extend(item for item in mesh._children_mesh(
                node, env, color, sel, selected) if item[2])
        return out
    if node.type == "loft":
        from . import loft
        p = node.params
        rows = [[mesh.rv(v, env) for v in row]
                for row in p.get("sections") or []
                if isinstance(row, list) and len(row) == 5]
        points, faces = loft.loft(
            rows, sides=mesh.rv(p.get("sides", 24), env, 24.0),
            smooth=int(mesh.rv(p.get("smooth", 3), env, 3.0)),
            caps=str(p.get("caps", "round")))
        return mesh._emit(loft.triangles(points, faces), color, selected)
    return []                                     # pragma: no cover
