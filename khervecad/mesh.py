"""Built-in tessellator — triangle meshes for the 3D preview.

OpenSCAD is the real engine: when its binary is available the 3D view
shows the exact mesh OpenSCAD renders. This module is the fallback
(and the instant preview): it turns the object tree into triangles in
pure Python. Booleans are approximated (difference/intersection show
their first operand) — the OpenSCAD engine renders them exactly.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from .model import SHAPE_2D, SHAPE_3D, CadNode

#: a mesh is a list of triangles; a triangle is 3 (x, y, z) tuples.


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


def node_outlines(node: CadNode):
    """Closed CCW outlines (lists of (x, y)) for a 2D shape node."""
    p = node.params
    if node.type == "rect":
        x, y, w, h = p["x"], p["y"], p["width"], p["height"]
        return [[(x, y), (x + w, y), (x + w, y + h), (x, y + h)]]
    if node.type == "circle":
        n = max(int(p["segments"]), 3)
        return [[(p["x"] + p["radius"] * math.cos(2 * math.pi * i / n),
                  p["y"] + p["radius"] * math.sin(2 * math.pi * i / n))
                 for i in range(n)]]
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


def collect_outlines(node: CadNode):
    """All outlines of the visible 2D shapes in *node*'s subtree."""
    outlines = []
    if not node.visible:
        return outlines
    if node.category == SHAPE_2D:
        outlines.extend(node_outlines(node))
    for child in node.children:
        outlines.extend(collect_outlines(child))
    return outlines


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
    n = max(int(p["segments"]), 4)
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
    n = max(int(p["segments"]), 3)
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


# ----------------------------------------------------------- extrusions

def linear_extrude_mesh(node: CadNode):
    p = node.params
    height = p["height"]
    twist = p.get("twist", 0.0)
    scale_top = p.get("scale", 1.0)
    z0 = -height / 2 if p.get("center") else 0.0
    slices = max(int(p.get("segments") or 0), 1)
    if twist and slices == 1:
        slices = max(int(abs(twist) / 6), 8)
    mesh = []
    for outline in collect_outlines(node):
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


def rotate_extrude_mesh(node: CadNode):
    p = node.params
    angle = min(max(p.get("angle", 360.0), 0.01), 360.0)
    n = max(int(p.get("segments", 96)), 3)
    steps = max(int(n * angle / 360.0), 2)
    full = angle >= 360.0
    mesh = []
    for outline in collect_outlines(node):
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


def flat_mesh(node: CadNode):
    """Un-extruded 2D shape shown as a flat face at z = 0."""
    mesh = []
    for outline in node_outlines(node):
        mesh.extend((
            (a[0], a[1], 0.0), (b[0], b[1], 0.0), (c[0], c[1], 0.0))
            for a, b, c in triangulate(outline))
    return mesh


# ----------------------------------------------------------- tree walk

def tessellate(node: CadNode):
    """Triangle mesh for *node*'s subtree (fallback semantics)."""
    if not node.visible:
        return []
    t = node.type
    if t == "root" or t == "union":
        mesh = []
        for child in node.children:
            mesh.extend(tessellate(child))
        return mesh
    if t in ("difference", "intersection"):
        # Approximation: show the first operand; the OpenSCAD engine
        # renders the true boolean.
        return tessellate(node.children[0]) if node.children else []
    if t == "linear_extrude":
        return linear_extrude_mesh(node)
    if t == "rotate_extrude":
        return rotate_extrude_mesh(node)
    if t == "translate":
        m = mat_translate(node.params["x"], node.params["y"],
                          node.params["z"])
        return transform_mesh(m, _children_mesh(node))
    if t == "rotate":
        m = mat_rotate(node.params["x"], node.params["y"],
                       node.params["z"])
        return transform_mesh(m, _children_mesh(node))
    if t == "scale":
        m = mat_scale(node.params["x"], node.params["y"],
                      node.params["z"])
        return transform_mesh(m, _children_mesh(node))
    if t == "mirror":
        m = mat_mirror(node.params["x"], node.params["y"],
                       node.params["z"])
        return transform_mesh(m, _children_mesh(node))
    if t == "cube":
        return cube_mesh(node.params)
    if t == "sphere":
        return sphere_mesh(node.params)
    if t == "cylinder":
        return cylinder_mesh(node.params)
    if node.category == SHAPE_2D:
        return flat_mesh(node)
    return []                                 # pragma: no cover


def _children_mesh(node):
    mesh = []
    for child in node.children:
        mesh.extend(tessellate(child))
    return mesh


def uses_booleans(node: CadNode) -> bool:
    """True if the subtree contains difference/intersection (the
    fallback preview approximates those)."""
    return any(n.type in ("difference", "intersection")
               for n in node.walk() if n.visible)
