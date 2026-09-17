"""Curved 2D outlines — Round-Anything's polyRound and BOSL2's beziers as
two 2D shape nodes:

- **rounded_polygon** — a polygon whose rows are ``[x, y, radius]``:
  each corner gets a tangent arc of its own radius (0 keeps it sharp),
  shrunk where two arcs would overlap on a short edge — a bracket's
  outline with a different fillet at every corner in one shape;
- **svg_path** — a shape typed as an SVG path string (Pathbuilder's
  idea): ``M 0 0 L 40 0 A 10 10 0 0 1 40 20 … Z``, every command,
  relative or absolute, several subpaths (an inner one is a hole). y
  runs UP as in OpenSCAD, not down as in an SVG file. OpenSCAD cannot
  parse the string, so the call carries the flattened points as well —
  the importer rebuilds from ``d`` and ignores them;
- **bezier_shape** — a closed outline of cubic Bézier curves: rows are
  the on-curve point, then its two control points toward the next
  on-curve point, repeated (``3 n`` rows for ``n`` curves) — a logo, a
  cam, a guitar body.

Both compile to one ``kcad_*`` call whose helper computes the same
points in OpenSCAD; ``segments`` is the points per arc / per curve.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

SHAPE_2D = "2d"

NODE_TYPES = {
    "rounded_polygon": dict(
        label="Rounded polygon (radius per corner)", category=SHAPE_2D,
        icon="mdi.vector-polygon-variant",
        params=dict(x=0.0, y=0.0, segments=8,
                    corners=[[0.0, 0.0, 2.0], [40.0, 0.0, 6.0],
                             [40.0, 25.0, 2.0], [0.0, 25.0, 10.0]]),
        schema=[("x", "X", "float", -1e6, 1e6),
                ("y", "Y", "float", -1e6, 1e6),
                ("corners", "Corners", "rows", ["X", "Y", "Radius"], None),
                ("segments", "Points per arc", "int", 1, 128)]),
    "bezier_shape": dict(
        label="Bézier shape (closed)", category=SHAPE_2D,
        icon="mdi.vector-bezier",
        params=dict(x=0.0, y=0.0, segments=16,
                    controls=[[0.0, 0.0], [10.0, -10.0], [30.0, -10.0],
                              [40.0, 0.0], [50.0, 10.0], [50.0, 30.0],
                              [20.0, 30.0], [-10.0, 30.0],
                              [-10.0, 10.0]]),
        schema=[("x", "X", "float", -1e6, 1e6),
                ("y", "Y", "float", -1e6, 1e6),
                ("controls", "Point, control, control, point… (3 per "
                 "curve)", "rows", ["X", "Y"], None),
                ("segments", "Points per curve", "int", 2, 256)]),
}
NODE_TYPES["svg_path"] = dict(
    label="SVG path shape", category=SHAPE_2D, icon="mdi.draw",
    params=dict(x=0.0, y=0.0, segments=32,
                d="M 0 0 L 40 0 A 10 10 0 0 1 40 20 L 0 20 Z "
                  "M 8 6 h 8 v 8 h -8 z"),
    schema=[("x", "X", "float", -1e6, 1e6),
            ("y", "Y", "float", -1e6, 1e6),
            ("d", "Path (SVG syntax, y up)", "str", None, None),
            ("segments", "Points per curve / turn", "int", 4, 512)])
TYPES = frozenset(NODE_TYPES)
LEAVES = frozenset(NODE_TYPES)
#: 2D shapes whose inner loops are holes
NESTED_2D = frozenset({"svg_path"})


def rounded_outline(corners, segments=8):
    """The rounded polygon's outline (the helper's kcad_round_points)."""
    rows = [r for r in corners if len(r) >= 2]
    n = len(rows)
    out = []
    seg = max(int(segments), 1)
    for i in range(n):
        px, py = rows[i][0], rows[i][1]
        r = rows[i][2] if len(rows[i]) > 2 else 0.0
        ax, ay = rows[i - 1][0], rows[i - 1][1]
        bx, by = rows[(i + 1) % n][0], rows[(i + 1) % n][1]
        la, lb = math.hypot(ax - px, ay - py), math.hypot(bx - px, by - py)
        if r <= 0 or la < 1e-9 or lb < 1e-9:
            out.append((px, py))
            continue
        u1 = ((ax - px) / la, (ay - py) / la)
        u2 = ((bx - px) / lb, (by - py) / lb)
        cos_t = max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1]))
        theta = math.acos(cos_t)
        if theta < 1e-6 or abs(theta - math.pi) < 1e-6:
            out.append((px, py))
            continue
        t = min(r / math.tan(theta / 2), la / 2, lb / 2)
        radius = t * math.tan(theta / 2)
        bis = (u1[0] + u2[0], u1[1] + u2[1])
        bl = math.hypot(*bis)
        d = radius / math.sin(theta / 2)
        cx, cy = px + bis[0] / bl * d, py + bis[1] / bl * d
        a1 = math.atan2(py + u1[1] * t - cy, px + u1[0] * t - cx)
        a2 = math.atan2(py + u2[1] * t - cy, px + u2[0] * t - cx)
        delta = math.atan2(math.sin(a2 - a1), math.cos(a2 - a1))
        for k in range(seg + 1):
            a = a1 + delta * k / seg
            out.append((cx + radius * math.cos(a), cy + radius * math.sin(a)))
    return out


def bezier_outline(controls, segments=16):
    """The closed Bézier outline (the helper's kcad_bezier_points)."""
    rows = [(r[0], r[1]) for r in controls if len(r) >= 2]
    count = len(rows) // 3
    seg = max(int(segments), 2)
    out = []
    for c in range(count):
        p0, c1, c2 = rows[3 * c], rows[3 * c + 1], rows[3 * c + 2]
        p3 = rows[(3 * c + 3) % (3 * count)]
        for k in range(seg):
            t = k / seg
            s = 1 - t
            out.append((s ** 3 * p0[0] + 3 * s * s * t * c1[0]
                        + 3 * s * t * t * c2[0] + t ** 3 * p3[0],
                        s ** 3 * p0[1] + 3 * s * s * t * c1[1]
                        + 3 * s * t * t * c2[1] + t ** 3 * p3[1]))
    return out


HELPER = """\
function kcad_round_corner(pts, i, seg) =
    let (n = len(pts), p = pts[i], a = pts[(i + n - 1) % n],
         b = pts[(i + 1) % n], r = len(p) > 2 ? p[2] : 0,
         la = norm([a[0] - p[0], a[1] - p[1]]),
         lb = norm([b[0] - p[0], b[1] - p[1]]))
    r <= 0 || la < 1e-9 || lb < 1e-9 ? [[p[0], p[1]]]
    : let (u1 = [a[0] - p[0], a[1] - p[1]] / la,
           u2 = [b[0] - p[0], b[1] - p[1]] / lb,
           th = acos(max(-1, min(1, u1 * u2))))
      th < 1e-4 || abs(th - 180) < 1e-4 ? [[p[0], p[1]]]
    : let (t = min(r / tan(th / 2), la / 2, lb / 2),
           rad = t * tan(th / 2), bis = u1 + u2,
           c = [p[0], p[1]] + bis / norm(bis) * rad / sin(th / 2),
           t1 = [p[0], p[1]] + u1 * t - c, t2 = [p[0], p[1]] + u2 * t - c,
           a1 = atan2(t1[1], t1[0]), a2 = atan2(t2[1], t2[0]),
           d = atan2(sin(a2 - a1), cos(a2 - a1)))
      [for (k = [0 : seg]) c + rad * [cos(a1 + d * k / seg),
                                     sin(a1 + d * k / seg)]];
function kcad_round_points(pts, seg) =
    [for (i = [0 : len(pts) - 1]) for (q = kcad_round_corner(pts, i, seg)) q];
module kcad_rounded_polygon(corners = [], segments = 8, center = [0, 0]) {
    translate(center)
        polygon(kcad_round_points(corners, max(round(segments), 1)));
}
function kcad_bezier_points(c, seg) =
    let (n = floor(len(c) / 3))
    [for (i = [0 : n - 1]) for (k = [0 : seg - 1])
     let (t = k / seg, s = 1 - t, p0 = c[3 * i], c1 = c[3 * i + 1],
          c2 = c[3 * i + 2], p3 = c[(3 * i + 3) % (3 * n)])
     pow(s, 3) * p0 + 3 * s * s * t * c1 + 3 * s * t * t * c2 + pow(t, 3) * p3];
module kcad_svg_path(d = "", segments = 32, center = [0, 0], points = [],
                     paths = []) {
    // OpenSCAD cannot read the path string: KherveCAD writes the
    // flattened outline beside it (the importer rebuilds from d)
    translate(center) polygon(points = points, paths = paths);
}
module kcad_bezier_shape(controls = [], segments = 16, center = [0, 0]) {
    translate(center)
        polygon(kcad_bezier_points(controls, max(round(segments), 2)));
}"""


def preamble(root) -> list:
    if any(n.type in TYPES for n in root.walk()):
        return HELPER.split("\n")
    return []


def _rows(rows, fmt):
    return "[" + ", ".join("[" + ", ".join(fmt(v) for v in r) + "]"
                           for r in rows if isinstance(r, list)) + "]"


def svg_loops(d, segments=32):
    """The path's outlines, y up."""
    from .svgdxf import parse_path
    return [loop for loop in parse_path(str(d or ""), max(int(segments), 4))
            if len(loop) >= 3]


def statement(node, fmt, fn) -> str:
    p = node.params
    centre = f"center = [{fmt(p.get('x', 0.0))}, {fmt(p.get('y', 0.0))}]"
    if node.type == "svg_path":
        from .model import scad_str
        from . import mesh
        seg = mesh.rv(p.get("segments", 32), None, 32)
        points, paths = [], []
        for loop in svg_loops(p.get("d"), seg):
            start = len(points)
            points.extend(loop)
            paths.append(list(range(start, len(points))))
        pts = "[" + ", ".join(f"[{fmt(round(x, 4))}, {fmt(round(y, 4))}]"
                              for x, y in points) + "]"
        idx = "[" + ", ".join("[" + ", ".join(str(i) for i in path) + "]"
                              for path in paths) + "]"
        return (f"kcad_svg_path(d = {scad_str(str(p.get('d', '')))}, "
                f"segments = {fmt(p.get('segments', 32))}, {centre},\n"
                f"    points = {pts},\n    paths = {idx})")
    if node.type == "rounded_polygon":
        return (f"kcad_rounded_polygon(corners = "
                f"{_rows(p.get('corners') or [], fmt)}, segments = "
                f"{fmt(p.get('segments', 8))}, {centre})")
    return (f"kcad_bezier_shape(controls = "
            f"{_rows(p.get('controls') or [], fmt)}, segments = "
            f"{fmt(p.get('segments', 16))}, {centre})")


def _read_rows(value, width, parser):
    from .scadparse import _num
    if isinstance(value, str):
        from . import expr
        try:
            value = expr.evaluate(value, parser.scope)
        except Exception:
            parser.warn("points could not be resolved")
            return []
    rows = []
    for row in value or []:
        if isinstance(row, list) and len(row) >= 2:
            rows.append([_num(v, 0.0) for v in (list(row) + [0.0] * width)
                         [:width]])
    return rows


def _build(type_, key, width, name):
    def build(parser, positional, named):
        from .model import CadNode
        from .scadparse import _num
        d = NODE_TYPES[type_]["params"]
        centre = named.get("center")
        cx, cy = (centre + [0.0, 0.0])[:2] if isinstance(centre, list) \
            else (0.0, 0.0)
        seg = _num(named.get("segments", d["segments"]), d["segments"])
        return CadNode(type_, name, {
            "x": _num(cx, 0.0), "y": _num(cy, 0.0),
            "segments": seg if isinstance(seg, str) else max(int(seg), 1),
            key: _read_rows(named.get(key, positional[0] if positional
                                      else []), width, parser)})
    return build


def _b_svg_path(parser, positional, named):
    from .model import CadNode
    from .scadparse import _num
    centre = named.get("center")
    cx, cy = (centre + [0.0, 0.0])[:2] if isinstance(centre, list) \
        else (0.0, 0.0)
    seg = _num(named.get("segments", 32), 32.0)
    return CadNode("svg_path", "SVG path", dict(
        x=_num(cx, 0.0), y=_num(cy, 0.0),
        segments=seg if isinstance(seg, str) else max(int(seg), 4),
        d=str(named.get("d", positional[0] if positional else ""))))


BUILDERS = {
    "kcad_svg_path": _b_svg_path,
    "kcad_rounded_polygon": _build("rounded_polygon", "corners", 3,
                                   "Rounded polygon"),
    "kcad_bezier_shape": _build("bezier_shape", "controls", 2,
                                "Bézier shape"),
}


def _resolved_rows(node, env, key):
    from . import mesh
    return [[mesh.rv(v, env) for v in row]
            for row in node.params.get(key) or [] if isinstance(row, list)]


def outlines(node, env):
    from . import mesh
    x = mesh.rv(node.params.get("x", 0.0), env)
    y = mesh.rv(node.params.get("y", 0.0), env)
    seg = mesh.rv(node.params.get("segments", 8), env, 8)
    if node.type == "svg_path":
        return [[(px + x, py + y) for px, py in loop]
                for loop in svg_loops(node.params.get("d"), seg)]
    if node.type == "rounded_polygon":
        pts = rounded_outline(_resolved_rows(node, env, "corners"), seg)
    else:
        pts = bezier_outline(_resolved_rows(node, env, "controls"), seg)
    return [[(px + x, py + y) for px, py in pts]] if len(pts) >= 3 else []


def check(node, env):
    if node.type == "svg_path":
        if not svg_loops(node.params.get("d")):
            return ("SVG path: no closed shape — write it like "
                    "M 0 0 L 20 0 L 10 15 Z")
        return None
    if node.type == "rounded_polygon":
        rows = node.params.get("corners") or []
        if len(rows) < 3:
            return "rounded polygon: at least 3 corners"
        return None
    rows = node.params.get("controls") or []
    if len(rows) < 6 or len(rows) % 3:
        return ("Bézier shape: rows come in threes — a point then its two "
                "controls — and at least two curves")
    return None


def tess(node, env, color, sel, selected):
    from . import mesh
    if node.type == "svg_path":
        loops = mesh._oriented(node, mesh.node_outlines(node, env))
        tris = []
        for solid, holes in mesh.outline_regions(loops):
            tris.extend(((a[0], a[1], 0.0), (b[0], b[1], 0.0),
                         (c[0], c[1], 0.0))
                        for a, b, c in mesh._caps(solid, holes))
        return mesh._emit(tris, color, selected)
    return mesh._emit(mesh.flat_mesh(node, env), color, selected)
