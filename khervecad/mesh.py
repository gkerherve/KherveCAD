"""Built-in tessellator — triangle meshes for the 3D preview.

OpenSCAD is the real engine: when its binary is available the 3D view
shows the exact mesh OpenSCAD renders. This module is the fallback
(and the instant preview): it turns the object tree into triangles in
pure Python, evaluating expressions and unrolling loops/conditionals
like OpenSCAD would. CSG-heavy ops are approximated (difference/
intersection/minkowski show their first operand, 3D hull unions) —
the OpenSCAD engine renders them exactly.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
from pathlib import Path

from . import expr
from .model import SHAPE_2D, CadNode
from . import organic

#: a mesh is a list of triangles; a triangle is 3 (x, y, z) tuples.

#: params that stay strings (never resolved to numbers).
_TEXT_PARAMS = {"text", "path", "variable", "condition", "update",
                "values", "value"}

#: ops the fallback can only approximate (engine renders exactly).
APPROXIMATED = {"difference", "intersection", "minkowski", "hull",
                "offset"}

_stl_cache = {}

#: when set (int), primitive/revolve segment counts and extrude slices
#: are capped to this — used for the fast, low-detail 2D silhouette.
_DETAIL = None


def _cap(n) -> int:
    return min(int(n), _DETAIL) if _DETAIL else int(n)


def rv(value, env=None, default=0.0) -> float:
    """Resolve a param that may be a number or an expression."""
    return expr.resolve(value, env, default)


#: round object types whose segment count the document-wide $fn
#: override replaces (linear_extrude's "segments" means slices, so it
#: is deliberately excluded).
_FN_TYPES = {"circle", "cylinder", "sphere", "rotate_extrude",
             "capsule", "ellipsoid", "rounded_box"}
_FN_OVERRIDE = None

#: {str(node id): node} for Linked-copy references + cycle-guard stack;
#: set by the tessellate entry points.
_REF_INDEX = None
_REF_STACK = set()


def rp(node: CadNode, env=None) -> dict:
    """Node params with every numeric/expression value resolved."""
    out = {}
    for key, value in node.params.items():
        if key in _TEXT_PARAMS:
            out[key] = value
        elif isinstance(value, bool):
            out[key] = value
        elif isinstance(value, list):
            # a list param is normally polygon points — but not always
            # (an Object's "anchors" is a list of dicts), and unpacking
            # one of those raised ValueError straight through a Qt slot,
            # which PyQt turns into abort(): the whole app died
            if all(isinstance(pt, (list, tuple)) and len(pt) == 2
                   for pt in value):
                out[key] = [[rv(x, env), rv(y, env)] for x, y in value]
            else:
                out[key] = value
        else:
            out[key] = rv(value, env)
    if _FN_OVERRIDE is not None and node.type in _FN_TYPES:
        out["segments"] = _FN_OVERRIDE
    return out


# ------------------------------------------------------------- matrices

def mat_identity():
    return [[1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]


def mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)]
            for i in range(4)]


def mat_translate(x, y, z):
    m = mat_identity()
    m[0][3], m[1][3], m[2][3] = x, y, z
    return m


def mat_scale(x, y, z):
    m = mat_identity()
    m[0][0], m[1][1], m[2][2] = x, y, z
    return m


def mat_rotate(ax, ay, az):
    """Rotation like OpenSCAD rotate([ax, ay, az]) — X then Y then Z."""
    rx, ry, rz = (math.radians(v) for v in (ax, ay, az))
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    mx = [[1, 0, 0, 0], [0, cx, -sx, 0], [0, sx, cx, 0], [0, 0, 0, 1]]
    my = [[cy, 0, sy, 0], [0, 1, 0, 0], [-sy, 0, cy, 0], [0, 0, 0, 1]]
    mz = [[cz, -sz, 0, 0], [sz, cz, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    return mat_mul(mz, mat_mul(my, mx))


def mat_mirror(nx, ny, nz):
    length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    nx, ny, nz = nx / length, ny / length, nz / length
    m = mat_identity()
    axes = (nx, ny, nz)
    for i in range(3):
        for j in range(3):
            m[i][j] = (1.0 if i == j else 0.0) - 2 * axes[i] * axes[j]
    return m


def transform_point(m, p):
    x, y, z = p
    return (m[0][0] * x + m[0][1] * y + m[0][2] * z + m[0][3],
            m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3],
            m[2][0] * x + m[2][1] * y + m[2][2] * z + m[2][3])


def transform_mesh(m, mesh):
    out = [tuple(transform_point(m, v) for v in tri) for tri in mesh]
    # A mirroring transform flips winding; fix it so normals stay outward.
    det = (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
           - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
           + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))
    if det < 0:
        out = [(a, c, b) for a, b, c in out]
    return out


# --------------------------------------------------------- 2D outlines

def polygon_area(points) -> float:
    total = 0.0
    for i, (x1, y1) in enumerate(points):
        x2, y2 = points[(i + 1) % len(points)]
        total += x1 * y2 - x2 * y1
    return total / 2.0


def ensure_ccw(points):
    return points if polygon_area(points) >= 0 else points[::-1]


def triangulate(points):
    """Ear-clipping triangulation of a simple polygon (2D)."""
    pts = ensure_ccw([tuple(p) for p in points])
    if len(pts) < 3:
        return []
    indices = list(range(len(pts)))
    triangles = []
    guard = 0
    while len(indices) > 3 and guard < 10000:
        guard += 1
        ear_found = False
        for k in range(len(indices)):
            i0 = indices[k - 1]
            i1 = indices[k]
            i2 = indices[(k + 1) % len(indices)]
            a, b, c = pts[i0], pts[i1], pts[i2]
            cross = ((b[0] - a[0]) * (c[1] - a[1])
                     - (b[1] - a[1]) * (c[0] - a[0]))
            if cross <= 1e-12:
                continue                     # reflex corner
            if any(_point_in_tri(pts[j], a, b, c)
                   for j in indices
                   if j not in (i0, i1, i2)):
                continue
            triangles.append((i0, i1, i2))
            del indices[k]
            ear_found = True
            break
        if not ear_found:                    # degenerate: fan fallback
            break
    if len(indices) == 3:
        triangles.append(tuple(indices))
    elif len(indices) > 3:                   # non-simple polygon: fan
        for k in range(1, len(indices) - 1):
            triangles.append((indices[0], indices[k], indices[k + 1]))
    return [(pts[i], pts[j], pts[k]) for i, j, k in triangles]


def _point_in_tri(p, a, b, c):
    def sign(p1, p2, p3):
        return ((p1[0] - p3[0]) * (p2[1] - p3[1])
                - (p2[0] - p3[0]) * (p1[1] - p3[1]))
    d1, d2, d3 = sign(p, a, b), sign(p, b, c), sign(p, c, a)
    has_neg = min(d1, d2, d3) < -1e-12
    has_pos = max(d1, d2, d3) > 1e-12
    return not (has_neg and has_pos)


def convex_hull_2d(points):
    """Andrew's monotone chain — hull of 2D points, CCW."""
    pts = sorted(set((round(x, 9), round(y, 9)) for x, y in points))
    if len(pts) <= 2:
        return list(pts)

    def cross(o, a, b):
        return ((a[0] - o[0]) * (b[1] - o[1])
                - (a[1] - o[1]) * (b[0] - o[0]))
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def offset_outline(points, r):
    """Naive polygon offset for the preview: push each vertex along
    its angle-bisector normal. OpenSCAD's offset() is exact."""
    pts = ensure_ccw(points)
    n = len(pts)
    if n < 3 or not r:
        return list(pts)
    out = []
    for i in range(n):
        px, py = pts[i - 1]
        cx, cy = pts[i]
        nx_, ny_ = pts[(i + 1) % n]
        # edge normals (outward for CCW)
        e1 = (cy - py, px - cx)
        e2 = (ny_ - cy, cx - nx_)
        l1 = math.hypot(*e1) or 1.0
        l2 = math.hypot(*e2) or 1.0
        bx = e1[0] / l1 + e2[0] / l2
        by = e1[1] / l1 + e2[1] / l2
        lb = math.hypot(bx, by)
        if lb < 1e-9:
            out.append((cx, cy))
            continue
        # scale so edges shift by exactly r
        dot = (e1[0] / l1 * bx + e1[1] / l1 * by) / lb
        scale = r / max(dot, 0.1)
        out.append((cx + bx / lb * scale, cy + by / lb * scale))
    return out


def node_outlines(node: CadNode, env=None):
    """Closed CCW outlines (lists of (x, y)) for a 2D shape node."""
    p = rp(node, env)
    if node.type == "rect":
        x, y, w, h = p["x"], p["y"], p["width"], p["height"]
        return [[(x, y), (x + w, y), (x + w, y + h), (x, y + h)]]
    if node.type == "circle":
        angle = p.get("angle", 360.0)
        arc = [(p["x"] + ax, p["y"] + ay)
               for ax, ay in node.arc_points(env)]
        if angle >= 360.0:
            return [arc[:-1]]                # closed ring, drop repeat
        return [[(p["x"], p["y"])] + arc]    # pie slice with centre
    if node.type == "polygon":
        return [[(p["x"] + x, p["y"] + y) for x, y in p["points"]]]
    if node.type == "line":
        return [_capsule(p["x1"], p["y1"], p["x2"], p["y2"],
                         p["width"] / 2.0)]
    if node.type == "text":
        return _text_outlines(p)
    return []


def _capsule(x1, y1, x2, y2, r):
    """Rounded-cap stroke outline, matching the hull-of-circles codegen."""
    angle = math.atan2(y2 - y1, x2 - x1)
    steps = 12
    points = []
    for i in range(steps + 1):               # cap around p2
        a = angle - math.pi / 2 + math.pi * i / steps
        points.append((x2 + r * math.cos(a), y2 + r * math.sin(a)))
    for i in range(steps + 1):               # cap around p1
        a = angle + math.pi / 2 + math.pi * i / steps
        points.append((x1 + r * math.cos(a), y1 + r * math.sin(a)))
    return points


def _text_outlines(p):
    """Glyph outlines via Qt (preview only; OpenSCAD renders exactly)."""
    try:
        from PyQt5.QtGui import QFont, QPainterPath
    except ImportError:                      # pragma: no cover
        return []
    font = QFont("DejaVu Sans")
    font.setPointSizeF(max(float(p["size"]), 0.5))
    path = QPainterPath()
    path.addText(0, 0, font, str(p["text"]))
    outlines = []
    for poly in path.simplified().toSubpathPolygons():
        pts = [(p["x"] + pt.x(), p["y"] - pt.y()) for pt in poly]
        if len(pts) >= 3:
            outlines.append(pts)
    return outlines


def collect_outlines(node: CadNode, env=None):
    """All outlines of the visible 2D content in *node*'s subtree,
    with loops unrolled, conditionals evaluated and offset/hull
    applied (approximately)."""
    env = dict(env or {})
    outlines = []
    if not node.visible:
        return outlines
    if node.category == SHAPE_2D:
        outlines.extend(node_outlines(node, env))
    if node.type == "offset":
        child_outlines = _children_outlines(node, env)
        r = rv(node.params["radius"], env)
        return [offset_outline(o, r) for o in child_outlines]
    if node.type == "hull":
        pts = [pt for o in _children_outlines(node, env) for pt in o]
        hull = convex_hull_2d(pts)
        return [hull] if len(hull) >= 3 else []
    if node.type in ("for_loop", "while_loop"):
        var = str(node.params.get("variable", "i")) or "i"
        for value in node.loop_values(env):
            scoped = dict(env)
            scoped[var] = value
            outlines.extend(_children_outlines(node, scoped))
        return outlines
    if node.type == "if_else":
        branch = _if_branch(node, env)
        for child in branch:
            outlines.extend(collect_outlines(child, env))
        return outlines
    outlines.extend(_children_outlines(node, env))
    return outlines


def _children_outlines(node, env):
    outlines = []
    env = dict(env)
    for child in node.children:
        if child.type == "assign":
            _apply_assign(child, env)
        else:
            outlines.extend(collect_outlines(child, env))
    return outlines


def _apply_assign(node, env):
    var = str(node.params.get("variable", "")).strip()
    if var:
        try:
            env[var] = expr.evaluate(node.params.get("value", 0), env)
        except expr.ExprError:
            pass


def _if_branch(node, env):
    """Children of the branch an if/else takes under *env*."""
    else_node = next((c for c in node.children
                      if c.type == "union"
                      and c.name.lower().startswith("else")), None)
    then_nodes = [c for c in node.children if c is not else_node]
    try:
        take_then = bool(expr.evaluate(node.params["condition"], env))
    except expr.ExprError:
        take_then = True
    if take_then:
        return then_nodes
    return list(else_node.children) if else_node is not None else []


# ----------------------------------------------------------- primitives

def cube_mesh(p):
    w, d, h = p["width"], p["depth"], p["height"]
    ox = -w / 2 if p["center"] else 0.0
    oy = -d / 2 if p["center"] else 0.0
    oz = -h / 2 if p["center"] else 0.0
    x0, y0, z0 = p["x"] + ox, p["y"] + oy, p["z"] + oz
    x1, y1, z1 = x0 + w, y0 + d, z0 + h
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    mesh = []
    for a, b, c, d_ in quads:
        mesh.append((v[a], v[b], v[c]))
        mesh.append((v[a], v[c], v[d_]))
    return mesh


def sphere_mesh(p):
    r = p["radius"]
    n = max(_cap(p["segments"]), 4)
    rings = max(n // 2, 3)
    cx, cy, cz = p["x"], p["y"], p["z"]

    def vert(i, j):
        theta = math.pi * i / rings
        phi = 2 * math.pi * j / n
        return (cx + r * math.sin(theta) * math.cos(phi),
                cy + r * math.sin(theta) * math.sin(phi),
                cz + r * math.cos(theta))
    mesh = []
    for i in range(rings):
        for j in range(n):
            a = vert(i, j)
            b = vert(i + 1, j)
            c = vert(i + 1, j + 1)
            d = vert(i, j + 1)
            if i > 0:
                mesh.append((a, b, d))
            if i < rings - 1:
                mesh.append((b, c, d))
    return mesh


def cylinder_mesh(p):
    n = max(_cap(p["segments"]), 3)
    h = p["height"]
    r1, r2 = p["radius_bottom"], p["radius_top"]
    cx, cy = p["x"], p["y"]
    z0 = p["z"] - (h / 2 if p["center"] else 0.0)
    z1 = z0 + h
    bottom = [(cx + r1 * math.cos(2 * math.pi * i / n),
               cy + r1 * math.sin(2 * math.pi * i / n), z0)
              for i in range(n)]
    top = [(cx + r2 * math.cos(2 * math.pi * i / n),
            cy + r2 * math.sin(2 * math.pi * i / n), z1)
           for i in range(n)]
    mesh = []
    for i in range(n):
        j = (i + 1) % n
        mesh.append((bottom[i], bottom[j], top[j]))
        mesh.append((bottom[i], top[j], top[i]))
    center_b = (cx, cy, z0)
    center_t = (cx, cy, z1)
    for i in range(n):
        j = (i + 1) % n
        if r1 > 0:
            mesh.append((center_b, bottom[j], bottom[i]))
        if r2 > 0:
            mesh.append((center_t, top[i], top[j]))
    return mesh


def stl_mesh(p):
    """Triangles of an imported mesh (STL/OBJ/OFF/3MF), cached by path
    + mtime."""
    path = str(p.get("path", "")).strip()
    if not path or not Path(path).exists():
        return []
    try:
        key = (path, Path(path).stat().st_mtime)
        if key not in _stl_cache:
            from .engine import parse_mesh
            _stl_cache.clear()               # keep only the latest
            _stl_cache[key] = parse_mesh(path)
        mesh = _stl_cache[key]
    except Exception:
        return []
    m = mat_translate(p["x"], p["y"], p["z"])
    return transform_mesh(m, mesh)


# ----------------------------------------------------------- extrusions

def linear_extrude_mesh(node: CadNode, env=None):
    p = rp(node, env)
    height = p["height"]
    twist = p.get("twist", 0.0)
    scale_top = p.get("scale", 1.0)
    z0 = -height / 2 if p.get("center") else 0.0
    slices = max(int(p.get("segments") or 0), 1)
    if twist and slices == 1:
        slices = max(int(abs(twist) / 6), 8)
    # keep the instant preview light for heavy twists (threads);
    # the OpenSCAD engine renders the exact slice count.
    slices = min(slices, 120)
    if _DETAIL:
        slices = min(slices, _DETAIL)
    mesh = []
    for outline in collect_outlines(node, env):
        if len(outline) < 3:
            continue
        outline = ensure_ccw(outline)
        cx = sum(x for x, _ in outline) / len(outline)
        cy = sum(y for _, y in outline) / len(outline)

        def ring(f):
            """Outline at fraction f of the height (twist about origin,
            scale about the outline centroid, like OpenSCAD)."""
            angle = -math.radians(twist) * f
            s = 1.0 + (scale_top - 1.0) * f
            cos_a, sin_a = math.cos(angle), math.sin(angle)
            pts = []
            for x, y in outline:
                sx = cx + (x - cx) * s
                sy = cy + (y - cy) * s
                pts.append((sx * cos_a - sy * sin_a,
                            sx * sin_a + sy * cos_a,
                            z0 + height * f))
            return pts
        rings = [ring(i / slices) for i in range(slices + 1)]
        n = len(outline)
        for k in range(slices):
            lower, upper = rings[k], rings[k + 1]
            for i in range(n):
                j = (i + 1) % n
                mesh.append((lower[i], lower[j], upper[j]))
                mesh.append((lower[i], upper[j], upper[i]))
        bottom = triangulate(outline)
        for a, b, c in bottom:               # bottom cap faces down
            mesh.append(((a[0], a[1], z0), (c[0], c[1], z0),
                         (b[0], b[1], z0)))
        if scale_top > 0:
            top_ring = rings[-1]
            top2d = [(x, y) for x, y, _ in top_ring]
            for a, b, c in triangulate(top2d):
                z = z0 + height
                mesh.append(((a[0], a[1], z), (b[0], b[1], z),
                             (c[0], c[1], z)))
    return mesh


def rotate_extrude_mesh(node: CadNode, env=None):
    p = rp(node, env)
    angle = min(max(p.get("angle", 360.0), 0.01), 360.0)
    n = max(_cap(p.get("segments", 96)), 3)
    steps = max(int(n * angle / 360.0), 2)
    full = angle >= 360.0
    mesh = []
    for outline in collect_outlines(node, env):
        if len(outline) < 3:
            continue
        profile = [(max(x, 0.0), y) for x, y in ensure_ccw(outline)]

        def ring(step):
            a = math.radians(angle) * step / steps
            cos_a, sin_a = math.cos(a), math.sin(a)
            return [(x * cos_a, x * sin_a, y) for x, y in profile]
        rings = [ring(s) for s in range(steps + 1)]
        m = len(profile)
        for s in range(steps):
            r0, r1 = rings[s], rings[s + 1]
            for i in range(m):
                j = (i + 1) % m
                mesh.append((r0[i], r1[i], r1[j]))
                mesh.append((r0[i], r1[j], r0[j]))
        if not full:                          # end caps
            for a, b, c in triangulate(profile):
                mesh.append(((a[0], 0.0, a[1]), (c[0], 0.0, c[1]),
                             (b[0], 0.0, b[1])))
            last = math.radians(angle)
            cos_a, sin_a = math.cos(last), math.sin(last)
            for a, b, c in triangulate(profile):
                mesh.append(((a[0] * cos_a, a[0] * sin_a, a[1]),
                             (b[0] * cos_a, b[0] * sin_a, b[1]),
                             (c[0] * cos_a, c[0] * sin_a, c[1])))
    return mesh


def flat_mesh(node: CadNode, env=None):
    """Un-extruded 2D shape shown as a flat face at z = 0."""
    mesh = []
    for outline in node_outlines(node, env):
        mesh.extend((
            (a[0], a[1], 0.0), (b[0], b[1], 0.0), (c[0], c[1], 0.0))
            for a, b, c in triangulate(outline))
    return mesh


# ------------------------------------------------- per-Object mesh cache

#: {component node id: (content key, local [(tri, color, False)])} —
#: an Object's tessellation in its LOCAL frame, reused as long as its
#: contents are unchanged. Moving/rotating/recolouring an Object (or
#: anything else in the assembly) then costs one matrix transform
#: instead of a full re-tessellation, which is what keeps assembly
#: drags snappy.
_COMP_CACHE = {}
_COMP_CACHE_MAX = 128

#: cache hit/miss counters (tests and profiling).
CACHE_STATS = {"hits": 0, "misses": 0}

#: the Object's own params that do NOT affect its local mesh.
_PLACEMENT_KEYS = ("x", "y", "z", "rx", "ry", "rz", "color", "alpha",
                   "mate", "anchors")


#: {content key: triangles} — OpenSCAD's EXACT local mesh for a part,
#: rendered one part at a time in the background. An assembly is parts
#: placed next to each other, not booleaned together, so each part can
#: be rendered on its own and the assembly assembled from the results:
#: booleans are really cut (bolt holes appear), per-part colours
#: survive (an STL of the whole document could only carry one), and a
#: part is re-rendered only when its own contents change — moving,
#: snapping or colouring it costs nothing.
_EXACT = {}
_EXACT_MAX = 64


def clear_component_cache():
    _COMP_CACHE.clear()


def exact_key(node, env=None, fn=None):
    """The content key an exact mesh for *node* would be stored under,
    or None when the subtree cannot be keyed (it pulls in a Linked copy
    whose master lives outside it).

    *fn* must be the same segment count the preview tessellates with —
    it is part of the key, so computing it outside a tessellation
    (where the global override is unset) would produce a key the
    lookup never matches, and every part would render for nothing."""
    global _DETAIL
    saved_detail = _DETAIL
    _DETAIL = None
    _set_fn(fn)
    try:
        return _component_key(node, dict(env or {}))
    finally:
        _set_fn(None)
        _DETAIL = saved_detail


def set_exact_mesh(key, tris):
    """Store OpenSCAD's exact mesh for one part. A late result is
    harmless: the key is the part's *content*, so a mesh for an old
    version simply lands under a key nothing asks for."""
    if not key:
        return
    if len(_EXACT) >= _EXACT_MAX:
        _EXACT.clear()
    _EXACT[key] = tris
    # the local (approximate) tessellation of that part is now stale
    for node_id, cached in list(_COMP_CACHE.items()):
        if cached[0] == key:
            del _COMP_CACHE[node_id]


def has_exact_mesh(key) -> bool:
    return bool(key) and key in _EXACT


def clear_exact_meshes():
    _EXACT.clear()
    _COMP_CACHE.clear()


def _component_key(node, env):
    """Content key of an Object's subtree: anything that could change
    the local mesh — child types/params/visibility, the environment,
    the $fn override, the detail cap, mesh-file mtimes. Returns None
    when the subtree cannot be cached (it pulls in a Linked copy whose
    master lives outside the subtree)."""
    parts = []
    walk = [node]
    while walk:
        n = walk.pop()
        if n.type == "reference":
            return None                     # master may change unseen
        parts.append(n.type)
        # the Object's own visibility is not content: _tess gates on it
        # before the cache, and the isolated view force-shows hidden
        # Objects — either way the local mesh is the same
        parts.append("1" if (n.visible or n is node) else "0")
        for key in sorted(n.params):
            if n is node and key in _PLACEMENT_KEYS:
                continue
            parts.append(f"{key}={n.params[key]!r}")
        if n.type == "stl_import":
            from pathlib import Path
            try:
                parts.append(str(Path(str(n.params.get(
                    "path", ""))).stat().st_mtime_ns))
            except OSError:
                parts.append("?")
        parts.append(";")
        walk.extend(n.children)
    parts.append(repr(sorted(env.items(), key=lambda kv: kv[0]))
                 if env else "")
    parts.append(str(_FN_OVERRIDE))
    parts.append(str(_DETAIL))
    return "\x00".join(parts)


def _component_mesh(node, env, color, sel, selected):
    """The component branch of _tess with a two-level cache:

    1. the LOCAL mesh, invalidated only when the Object's contents
       change (placement and colour are excluded from the key);
    2. the PLACED mesh (local × placement, colours applied), reused
       while the placement/colour stay put — so re-tessellating the
       assembly after a drag re-transforms only the dragged Object
       and every other one is a dictionary lookup.

    Selection passes bypass the cache (per-triangle flags)."""
    group_color = color
    col = str(node.params.get("color", "")).strip()
    if col:
        group_color = (col, rv(node.params.get("alpha", 1.0), env, 1.0))
    rx = rv(node.params.get("rx", 0), env, 0.0)
    ry = rv(node.params.get("ry", 0), env, 0.0)
    rz = rv(node.params.get("rz", 0), env, 0.0)
    tx = rv(node.params.get("x", 0), env, 0.0)
    ty = rv(node.params.get("y", 0), env, 0.0)
    tz = rv(node.params.get("z", 0), env, 0.0)
    moved = any((rx, ry, rz, tx, ty, tz))

    if sel:
        # highlight pass: rare, needs true per-triangle selection flags
        out = _children_mesh(node, env, group_color, sel, selected)
        if moved:
            out = _transform_colored(
                mat_mul(mat_translate(tx, ty, tz),
                        mat_rotate(rx, ry, rz)), out)
        return out

    key = _component_key(node, env)
    placed_key = (key, (tx, ty, tz, rx, ry, rz), group_color)
    cached = _COMP_CACHE.get(node.id) if key is not None else None
    if cached is not None and cached[0] == key:
        CACHE_STATS["hits"] += 1
        local = cached[1]
        if cached[2] == placed_key:            # nothing moved: free
            return cached[3]
    elif key is not None and key in _EXACT:
        CACHE_STATS["misses"] += 1
        # OpenSCAD has rendered this exact part: use its mesh (holes
        # really cut) instead of the approximate tessellation, still
        # colour-neutral so the part's own colour applies below
        local = [(tri, None, False) for tri in _EXACT[key]]
    else:
        CACHE_STATS["misses"] += 1
        # children tessellated colour-neutral, so the Object's own
        # colour can change without invalidating the local cache
        local = _children_mesh(node, env, None, frozenset(), False)
    out = [(tri, c if c is not None else group_color, False)
           for tri, c, _s in local]
    if moved:
        out = _transform_colored(
            mat_mul(mat_translate(tx, ty, tz),
                    mat_rotate(rx, ry, rz)), out)
    if key is not None:
        if len(_COMP_CACHE) >= _COMP_CACHE_MAX:
            _COMP_CACHE.clear()
        _COMP_CACHE[node.id] = (key, local, placed_key, out)
    return out


# ----------------------------------------------------------- tree walk

def _set_fn(fn):
    global _FN_OVERRIDE
    _FN_OVERRIDE = int(fn) if fn else None


def _set_refs(node):
    """Index nodes by name so Linked copies can resolve their master.
    The index is built from the *document* root (the top of the node's
    parent chain), so tessellating one instance alone — the Snap
    tool's per-part pick meshes, a part outline in the 2D assembly —
    still resolves the Object definition it references."""
    global _REF_INDEX
    _REF_INDEX = {}
    top = node
    while top.parent is not None:
        top = top.parent
    for n in top.walk():
        _REF_INDEX.setdefault(n.name, n)
    _REF_STACK.clear()


def _clear_refs():
    global _REF_INDEX
    _REF_INDEX = None
    _REF_STACK.clear()


def tessellate(node: CadNode, env=None, fn=None, detail=None):
    """Triangle mesh for *node*'s subtree (fallback semantics). *fn*
    overrides the segment count of every round object when given;
    *detail* caps it, for the low-resolution 2D outlines."""
    global _DETAIL
    _DETAIL = detail
    _set_fn(fn)
    _set_refs(node)
    try:
        return [tri for tri, _c, _s in
                _tess(node, dict(env or {}), None, frozenset(), False)]
    finally:
        _DETAIL = None
        _set_fn(None)
        _clear_refs()


def tessellate_colored(node: CadNode, env=None, fn=None):
    """Like tessellate but returns [(triangle, (color, alpha) | None)]
    with per-face colours from color() nodes — the built-in preview
    shows them (STL from the engine is geometry-only)."""
    _set_fn(fn)
    _set_refs(node)
    try:
        return [(t, c) for t, c, _s in
                _tess(node, dict(env or {}), None, frozenset(), False)]
    finally:
        _set_fn(None)
        _clear_refs()


def selected_world_tris(node: CadNode, sel_ids, env=None, detail=None,
                        fn=None):
    """World-space triangles belonging to any node whose id is in
    *sel_ids* — used to highlight the selected object in both views.
    Ancestor transforms are already applied, so the triangles land
    where the object actually sits in the assembly. *detail* caps
    segment counts for the fast, low-resolution 2D silhouette."""
    global _DETAIL
    sel = frozenset(sel_ids)
    if not sel:
        return []
    _DETAIL = detail
    _set_fn(fn)
    _set_refs(node)
    try:
        out = [t for t, _c, s in
               _tess(node, dict(env or {}), None, sel, False) if s]
        if not out:
            # the selection may live in a non-rendering store (a master),
            # which _tess skips — so it never appears in the scene walk.
            # Tessellate each selected node's own subtree directly so it
            # can still be highlighted in both views.
            by_id = {n.id: n for n in node.walk()}
            for nid in sel:
                target = by_id.get(nid)
                if target is not None and target is not node:
                    out += [t for t, _c, _s in
                            _tess(target, dict(env or {}), None,
                                  frozenset({nid}), True)]
        return out
    finally:
        _DETAIL = None
        _set_fn(None)
        _clear_refs()


def _emit(tris, color, selected):
    return [(tri, color, selected) for tri in tris]


def _tess(node, env, color, sel, selected):
    if not node.visible:
        return []
    selected = selected or (node.id in sel)
    t = node.type
    if t == "color":
        color = (str(node.params.get("color", "#4a90d9")),
                 rv(node.params.get("alpha", 1.0), env, 1.0))
        return _children_mesh(node, env, color, sel, selected)
    if t == "masters":
        # definitions store: masters render only through Linked copies,
        # so the group contributes no geometry of its own.
        return []
    if t == "scad_raw":
        # verbatim OpenSCAD — only the OpenSCAD engine can render it;
        # the built-in tessellator has no model for it.
        return []
    if t == "projection":
        # flattens 3D to a 2D outline — a 2D result the mesh preview
        # can't represent; the OpenSCAD engine renders it.
        return []
    if t in ("root", "variables"):
        # "variables" only holds assignments, so it adds no geometry.
        return _children_mesh(node, env, color, sel, selected)
    if t == "hull":
        return _hull_mesh(node, env, color, sel, selected)
    if t == "reference":
        # a Linked copy renders its master's geometry, moved/rotated.
        # When the master is an **Object**, this is an assembly
        # instance: it renders the Object's LOCAL geometry (the module
        # body — placement zeroed, definition visibility ignored, as a
        # hidden Object is a pure definition) under its own placement.
        target = (_REF_INDEX or {}).get(
            str(node.params.get("ref", "")).strip())
        if target is None or node.id in _REF_STACK:
            return []
        col = str(node.params.get("color", "")).strip()
        if col:
            # the instance's own colour: two copies of one Object can
            # wear different colours (a colour inside the master still
            # wins, as OpenSCAD's innermost color() does)
            color = (col, rv(node.params.get("alpha", 1.0), env, 1.0))
        _REF_STACK.add(node.id)
        try:
            if target.type == "component":
                saved = {k: target.params.get(k, 0.0)
                         for k in ("x", "y", "z", "rx", "ry", "rz")}
                saved_visible = target.visible
                try:
                    for k in saved:
                        target.params[k] = 0.0
                    target.visible = True
                    out = _tess(target, env, color, sel, selected)
                finally:
                    target.params.update(saved)
                    target.visible = saved_visible
            else:
                out = _tess(target, env, color, sel, selected)
        finally:
            _REF_STACK.discard(node.id)
        rx = rv(node.params.get("rx", 0), env, 0.0)
        ry = rv(node.params.get("ry", 0), env, 0.0)
        rz = rv(node.params.get("rz", 0), env, 0.0)
        tx = rv(node.params.get("x", 0), env, 0.0)
        ty = rv(node.params.get("y", 0), env, 0.0)
        tz = rv(node.params.get("z", 0), env, 0.0)
        if any((rx, ry, rz, tx, ty, tz)):
            matrix = mat_mul(mat_translate(tx, ty, tz),
                             mat_rotate(rx, ry, rz))
            out = _transform_colored(matrix, out)
        return out
    if t == "component":
        # like a group, but the local mesh is cached (see
        # _component_mesh) so assembly edits stay snappy
        return _component_mesh(node, env, color, sel, selected)
    if t == "union":
        # a group is a part: apply its own colour, then its rotate and
        # translate (matching the color()/translate()/rotate() codegen)
        group_color = color
        col = str(node.params.get("color", "")).strip()
        if col:
            group_color = (col, rv(node.params.get("alpha", 1.0), env,
                                   1.0))
        out = _children_mesh(node, env, group_color, sel, selected)
        rx = rv(node.params.get("rx", 0), env, 0.0)
        ry = rv(node.params.get("ry", 0), env, 0.0)
        rz = rv(node.params.get("rz", 0), env, 0.0)
        tx = rv(node.params.get("x", 0), env, 0.0)
        ty = rv(node.params.get("y", 0), env, 0.0)
        tz = rv(node.params.get("z", 0), env, 0.0)
        if any((rx, ry, rz, tx, ty, tz)):
            matrix = mat_mul(mat_translate(tx, ty, tz),
                             mat_rotate(rx, ry, rz))
            out = _transform_colored(matrix, out)
        return out
    if t in ("difference", "intersection", "minkowski"):
        # Approximation: show the first operand; the OpenSCAD engine
        # renders the true CSG result.
        ops = [c for c in node.children if c.type != "assign"]
        if not ops:
            return []
        mesh = _tess(ops[0], env, color, sel, selected)
        # a selected object hiding in a subtracted / later operand (e.g.
        # a bore removed from a body) still needs its own geometry so it
        # can be shown when *it* is picked — but selecting the whole
        # difference must not draw the removed tools as solid, so only
        # pull in an operand that actually contains a selected node.
        if sel:
            for child in ops[1:]:
                if any(n.id in sel for n in child.walk()):
                    mesh.extend(_tess(child, env, color, sel, selected))
        return mesh
    if t in ("for_loop", "while_loop"):
        var = str(node.params.get("variable", "i")) or "i"
        mesh = []
        for value in node.loop_values(env):
            scoped = dict(env)
            scoped[var] = value
            mesh.extend(_children_mesh(node, scoped, color, sel,
                                       selected))
        return mesh
    if t == "if_else":
        mesh = []
        for child in _if_branch(node, env):
            mesh.extend(_tess(child, env, color, sel, selected))
        return mesh
    if t == "assign":
        return []
    if t == "linear_extrude":
        return _emit(linear_extrude_mesh(node, env), color, selected)
    if t == "rotate_extrude":
        return _emit(rotate_extrude_mesh(node, env), color, selected)
    if t in ("translate", "rotate", "scale", "mirror"):
        p = rp(node, env)
        matrix = dict(translate=mat_translate, rotate=mat_rotate,
                      scale=mat_scale,
                      mirror=mat_mirror)[t](p["x"], p["y"], p["z"])
        return _transform_colored(
            matrix, _children_mesh(node, env, color, sel, selected))
    if t == "offset":
        # 2D-only op: preview its (offset) outlines flat at z = 0.
        mesh = []
        for outline in collect_outlines(node, env):
            mesh.extend((
                (a[0], a[1], 0.0), (b[0], b[1], 0.0),
                (c[0], c[1], 0.0)) for a, b, c in triangulate(outline))
        return _emit(mesh, color, selected)
    if t == "cube":
        return _emit(cube_mesh(rp(node, env)), color, selected)
    if t == "sphere":
        return _emit(sphere_mesh(rp(node, env)), color, selected)
    if t == "cylinder":
        return _emit(cylinder_mesh(rp(node, env)), color, selected)
    if t == "stl_import":
        return _emit(stl_mesh(rp(node, env)), color, selected)
    if t in organic.TYPES:
        return organic.tess(node, env, color, sel, selected)
    if node.category == SHAPE_2D:
        return _emit(flat_mesh(node, env), color, selected)
    return []                                 # pragma: no cover


#: past this many points a hull previews as the union of its children
#: rather than stall the GUI thread (the exact render is still exact)
HULL_POINT_LIMIT = 60000


def _hull_mesh(node, env, color, sel, selected):
    """A 3D hull is the convex hull of its children (geom3d) — a chain
    of hulled spheres previews as the capsule it is, not as a string of
    beads. A flat (2D) hull has no volume to hull and keeps the union
    of its children, as before."""
    from . import geom3d
    parts = _children_mesh(node, env, color, sel, selected)
    pts = [v for tri, _c, _s in parts for v in tri]
    if not 4 <= len(pts) <= HULL_POINT_LIMIT:
        return parts
    tris = geom3d.convex_hull(pts)
    if not tris:
        return parts                            # coplanar: a 2D hull
    own = color if color is not None else next(
        (c for _t, c, _s in parts if c is not None), None)
    out = _emit(tris, own, selected)
    if sel and not selected:
        # a selected operand still needs its own triangles to glow
        out.extend(item for item in parts if item[2])
    return out


def _transform_colored(matrix, marked):
    plain = transform_mesh(matrix, [tri for tri, _c, _s in marked])
    return [(p, c, s) for p, (_t, c, s) in zip(plain, marked)]


def _children_mesh(node, env, color, sel, selected):
    mesh = []
    env = dict(env)
    for child in node.children:
        if child.type == "assign":
            _apply_assign(child, env)
        elif child.type == "variables":
            # transparent group: its assignments belong to this scope so
            # sibling geometry can use them
            for grandchild in child.children:
                if grandchild.type == "assign":
                    _apply_assign(grandchild, env)
                else:
                    mesh.extend(_tess(grandchild, env, color, sel,
                                      selected))
        else:
            mesh.extend(_tess(child, env, color, sel, selected))
    return mesh


def uses_booleans(node: CadNode) -> bool:
    """True if the subtree contains ops the fallback preview can only
    approximate (booleans, minkowski, hull, offset)."""
    return any(n.type in APPROXIMATED
               for n in node.walk() if n.visible)
