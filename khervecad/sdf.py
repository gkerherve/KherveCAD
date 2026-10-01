"""Signed distance fields, smooth union and surface extraction — the
smooth blend behind organic shapes.

CSG meets its parts at hard seams: a head on a neck on a torso reads
as three objects. A **smooth blend** melts them together with a
fillet of a chosen radius, the way clay sculpting (and SDF modellers
like Womp or Clayxels) join forms. Each primitive under the blend
becomes a signed distance function in its own frame; a polynomial
smooth-min merges them; the field is sampled on a grid and its zero
surface extracted with **marching tetrahedra** — no ambiguous cases,
and edge vertices shared between cells, so the result is watertight
and ready to bake into one OpenSCAD polyhedron (bake.py).

Pure geometry, Qt-free; the tree is read through mesh.py (imported
when called — mesh imports this package's registry at load).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

INF = float("inf")

#: most grid points one blend may sample; past it the cells grow. With
#: numpy the field and the tetrahedra are vectorized and a grid ten
#: times finer costs what the pure-Python one did — enough for skin
#: detail (wrinkles, pores) at about a millimetre
MAX_GRID_POINTS = 1_500_000
MAX_GRID_POINTS_NP = 16_000_000
#: grid points evaluated at once (memory: ~100 bytes a point)
SLAB_POINTS = 1_000_000

try:                                    # the fast path; pure Python without
    import numpy as _np
except Exception:                       # pragma: no cover - numpy is a dep
    _np = None

#: node types a blend can merge (see _PRIMITIVES) and the ones it walks
#: through, carrying the transform
PRIMITIVE_TYPES = ("sphere", "cube", "cylinder", "capsule", "ellipsoid",
                   "rounded_box")


class Unsupported(Exception):
    """A node under a blend that has no distance function."""

    def __init__(self, node):
        super().__init__(f"{node.name} ({node.type})")
        self.node = node


# ------------------------------------------------------------ primitives
# Each builder takes resolved params and returns (sdf(x, y, z) in the
# node's own frame, local box min, local box max).

def _sphere(p):
    cx, cy, cz, r = p["x"], p["y"], p["z"], abs(p["radius"])

    def f(x, y, z):
        return math.sqrt((x - cx) ** 2 + (y - cy) ** 2 + (z - cz) ** 2) - r
    return f, (cx - r, cy - r, cz - r), (cx + r, cy + r, cz + r)


def _box(cx, cy, cz, hx, hy, hz, rr=0.0):
    def f(x, y, z):
        qx = abs(x - cx) - hx
        qy = abs(y - cy) - hy
        qz = abs(z - cz) - hz
        out = math.sqrt(max(qx, 0.0) ** 2 + max(qy, 0.0) ** 2
                        + max(qz, 0.0) ** 2)
        return out + min(max(qx, qy, qz), 0.0) - rr
    return f


def _cube(p):
    w, d, h = abs(p["width"]), abs(p["depth"]), abs(p["height"])
    x0, y0, z0 = p["x"], p["y"], p["z"]
    if p.get("center"):
        x0, y0, z0 = x0 - w / 2, y0 - d / 2, z0 - h / 2
    f = _box(x0 + w / 2, y0 + d / 2, z0 + h / 2, w / 2, d / 2, h / 2)
    return f, (x0, y0, z0), (x0 + w, y0 + d, z0 + h)


def _rounded_box(p):
    w, d, h = abs(p["width"]), abs(p["depth"]), abs(p["height"])
    x0, y0, z0 = p["x"], p["y"], p["z"]
    if p.get("center", True):
        x0, y0, z0 = x0 - w / 2, y0 - d / 2, z0 - h / 2
    rr = max(min(p["radius"], w / 2, d / 2, h / 2), 0.0)
    f = _box(x0 + w / 2, y0 + d / 2, z0 + h / 2,
             w / 2 - rr, d / 2 - rr, h / 2 - rr, rr)
    return f, (x0, y0, z0), (x0 + w, y0 + d, z0 + h)


def _cylinder(p):
    h = abs(p["height"])
    r1, r2 = abs(p["radius_bottom"]), abs(p["radius_top"])
    cx, cy = p["x"], p["y"]
    z0 = p["z"] - (h / 2 if p.get("center") else 0.0)

    def f(x, y, z):
        t = min(max((z - z0) / h, 0.0), 1.0) if h > 0 else 0.0
        dr = math.sqrt((x - cx) ** 2 + (y - cy) ** 2) - (r1 + (r2 - r1) * t)
        dz = max(z0 - z, z - (z0 + h))
        return (math.sqrt(max(dr, 0.0) ** 2 + max(dz, 0.0) ** 2)
                + min(max(dr, dz), 0.0))
    r = max(r1, r2)
    return f, (cx - r, cy - r, z0), (cx + r, cy + r, z0 + h)


def _capsule(p):
    ax, ay, az = p["x1"], p["y1"], p["z1"]
    bx, by, bz = p["x2"], p["y2"], p["z2"]
    r = abs(p["radius"])
    ux, uy, uz = bx - ax, by - ay, bz - az
    l2 = ux * ux + uy * uy + uz * uz

    def f(x, y, z):
        px, py, pz = x - ax, y - ay, z - az
        t = 0.0 if l2 == 0 else min(max((px * ux + py * uy + pz * uz)
                                        / l2, 0.0), 1.0)
        dx, dy, dz = px - ux * t, py - uy * t, pz - uz * t
        return math.sqrt(dx * dx + dy * dy + dz * dz) - r
    return (f, (min(ax, bx) - r, min(ay, by) - r, min(az, bz) - r),
            (max(ax, bx) + r, max(ay, by) + r, max(az, bz) + r))


def _ellipsoid(p):
    cx, cy, cz = p["x"], p["y"], p["z"]
    rx, ry, rz = (max(abs(p[k]), 1e-9) for k in ("rx", "ry", "rz"))
    smallest = min(rx, ry, rz)

    def f(x, y, z):
        # Quilez's bound: exact on the surface, close off it
        qx, qy, qz = (x - cx) / rx, (y - cy) / ry, (z - cz) / rz
        k0 = math.sqrt(qx * qx + qy * qy + qz * qz)
        k1 = math.sqrt((qx / rx) ** 2 + (qy / ry) ** 2 + (qz / rz) ** 2)
        return k0 * (k0 - 1.0) / k1 if k1 > 1e-12 else -smallest
    return f, (cx - rx, cy - ry, cz - rz), (cx + rx, cy + ry, cz + rz)


_PRIMITIVES = {"sphere": _sphere, "cube": _cube, "cylinder": _cylinder,
               "capsule": _capsule, "ellipsoid": _ellipsoid,
               "rounded_box": _rounded_box}


# ------------------------------------------- the same, over numpy arrays
# Each takes resolved params and returns fv(X, Y, Z) on arrays in the
# node's own frame — the scalar builders above, line for line.

def _v_sphere(p):
    np = _np
    cx, cy, cz, r = p["x"], p["y"], p["z"], abs(p["radius"])
    return lambda x, y, z: np.sqrt((x - cx) ** 2 + (y - cy) ** 2
                                   + (z - cz) ** 2) - r


def _v_box(cx, cy, cz, hx, hy, hz, rr=0.0):
    np = _np

    def f(x, y, z):
        qx = np.abs(x - cx) - hx
        qy = np.abs(y - cy) - hy
        qz = np.abs(z - cz) - hz
        out = np.sqrt(np.maximum(qx, 0.0) ** 2 + np.maximum(qy, 0.0) ** 2
                      + np.maximum(qz, 0.0) ** 2)
        return out + np.minimum(np.maximum(np.maximum(qx, qy), qz),
                                0.0) - rr
    return f


def _v_cube(p):
    w, d, h = abs(p["width"]), abs(p["depth"]), abs(p["height"])
    x0, y0, z0 = p["x"], p["y"], p["z"]
    if p.get("center"):
        x0, y0, z0 = x0 - w / 2, y0 - d / 2, z0 - h / 2
    return _v_box(x0 + w / 2, y0 + d / 2, z0 + h / 2, w / 2, d / 2, h / 2)


def _v_rounded_box(p):
    w, d, h = abs(p["width"]), abs(p["depth"]), abs(p["height"])
    x0, y0, z0 = p["x"], p["y"], p["z"]
    if p.get("center", True):
        x0, y0, z0 = x0 - w / 2, y0 - d / 2, z0 - h / 2
    rr = max(min(p["radius"], w / 2, d / 2, h / 2), 0.0)
    return _v_box(x0 + w / 2, y0 + d / 2, z0 + h / 2,
                  w / 2 - rr, d / 2 - rr, h / 2 - rr, rr)


def _v_cylinder(p):
    np = _np
    h = abs(p["height"])
    r1, r2 = abs(p["radius_bottom"]), abs(p["radius_top"])
    cx, cy = p["x"], p["y"]
    z0 = p["z"] - (h / 2 if p.get("center") else 0.0)

    def f(x, y, z):
        t = np.clip((z - z0) / h, 0.0, 1.0) if h > 0 else 0.0
        dr = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) - (r1 + (r2 - r1) * t)
        dz = np.maximum(z0 - z, z - (z0 + h))
        return (np.sqrt(np.maximum(dr, 0.0) ** 2 + np.maximum(dz, 0.0) ** 2)
                + np.minimum(np.maximum(dr, dz), 0.0))
    return f


def _v_capsule(p):
    np = _np
    ax, ay, az = p["x1"], p["y1"], p["z1"]
    bx, by, bz = p["x2"], p["y2"], p["z2"]
    r = abs(p["radius"])
    ux, uy, uz = bx - ax, by - ay, bz - az
    l2 = ux * ux + uy * uy + uz * uz

    def f(x, y, z):
        px, py, pz = x - ax, y - ay, z - az
        t = 0.0 if l2 == 0 else np.clip((px * ux + py * uy + pz * uz) / l2,
                                        0.0, 1.0)
        dx, dy, dz = px - ux * t, py - uy * t, pz - uz * t
        return np.sqrt(dx * dx + dy * dy + dz * dz) - r
    return f


def _v_ellipsoid(p):
    np = _np
    cx, cy, cz = p["x"], p["y"], p["z"]
    rx, ry, rz = (max(abs(p[k]), 1e-9) for k in ("rx", "ry", "rz"))
    smallest = min(rx, ry, rz)

    def f(x, y, z):
        qx, qy, qz = (x - cx) / rx, (y - cy) / ry, (z - cz) / rz
        k0 = np.sqrt(qx * qx + qy * qy + qz * qz)
        k1 = np.sqrt((qx / rx) ** 2 + (qy / ry) ** 2 + (qz / rz) ** 2)
        safe = np.where(k1 > 1e-12, k1, 1.0)
        return np.where(k1 > 1e-12, k0 * (k0 - 1.0) / safe, -smallest)
    return f


_VECTOR = {"sphere": _v_sphere, "cube": _v_cube, "cylinder": _v_cylinder,
           "capsule": _v_capsule, "ellipsoid": _v_ellipsoid,
           "rounded_box": _v_rounded_box}


# -------------------------------------------------------------- the tree

class _Leaf:
    __slots__ = ("fn", "inv", "scale", "lo", "hi", "vfn")

    def __init__(self, fn, inv, scale, lo, hi, vfn=None):
        self.fn, self.inv, self.scale, self.lo, self.hi = \
            fn, inv, scale, lo, hi
        self.vfn = vfn                  # the numpy twin of fn, or None


def _inverse(m):
    (a, b, c), (d, e, f), (g, h, i) = m[0][:3], m[1][:3], m[2][:3]
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if abs(det) < 1e-18:
        return None
    r = [[(e * i - f * h) / det, (c * h - b * i) / det,
          (b * f - c * e) / det],
         [(f * g - d * i) / det, (a * i - c * g) / det,
          (c * d - a * f) / det],
         [(d * h - e * g) / det, (b * g - a * h) / det,
          (a * e - b * d) / det]]
    t = (m[0][3], m[1][3], m[2][3])
    return [r[k] + [-(r[k][0] * t[0] + r[k][1] * t[1] + r[k][2] * t[2])]
            for k in range(3)]


def _leaf(node, env, m):
    from . import mesh
    params = mesh.rp(node, env)
    fn, lo, hi = _PRIMITIVES[node.type](params)
    vfn = _VECTOR[node.type](params) if _np is not None else None
    inv = _inverse(m)
    if inv is None:                             # squashed flat: nothing
        return None
    # distances scale with the frame; the smallest axis keeps the field
    # an underestimate, which is what a sampled surface needs
    scale = min(math.sqrt(m[0][j] ** 2 + m[1][j] ** 2 + m[2][j] ** 2)
                for j in range(3))
    corners = [mesh.transform_point(m, (x, y, z)) for x in (lo[0], hi[0])
               for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    return _Leaf(fn, inv, scale,
                 tuple(min(c[i] for c in corners) for i in range(3)),
                 tuple(max(c[i] for c in corners) for i in range(3)), vfn)


def _walk_children(node, env, m, out):
    from . import mesh
    env = dict(env)
    for child in node.children:
        if child.type == "assign":
            mesh._apply_assign(child, env)
        elif child.type == "variables":
            for grandchild in child.children:
                if grandchild.type == "assign":
                    mesh._apply_assign(grandchild, env)
                else:
                    _walk(grandchild, env, m, out)
        else:
            _walk(child, env, m, out)


def _walk(node, env, m, out):
    from . import mesh
    if not node.visible:
        return
    t = node.type

    def num(key, default=0.0):
        return mesh.rv(node.params.get(key, default), env, default)
    if t == "color":
        return _walk_children(node, env, m, out)
    if t == "union":
        move = [num(k) for k in ("x", "y", "z", "rx", "ry", "rz")]
        if any(move):
            m = mesh.mat_mul(m, mesh.mat_mul(
                mesh.mat_translate(*move[:3]), mesh.mat_rotate(*move[3:])))
        return _walk_children(node, env, m, out)
    if t in ("translate", "rotate", "scale", "mirror"):
        make = dict(translate=mesh.mat_translate, rotate=mesh.mat_rotate,
                    scale=mesh.mat_scale, mirror=mesh.mat_mirror)[t]
        default = 1.0 if t == "scale" else 0.0
        xform = make(num("x", default), num("y", default), num("z", default))
        return _walk_children(node, env, mesh.mat_mul(m, xform), out)
    if t == "joint":
        px, py, pz = num("px"), num("py"), num("pz")
        xform = mesh.mat_mul(mesh.mat_translate(px, py, pz), mesh.mat_mul(
            mesh.mat_rotate(num("rx"), num("ry"), num("rz")),
            mesh.mat_translate(-px, -py, -pz)))
        return _walk_children(node, env, mesh.mat_mul(m, xform), out)
    if t == "symmetry":
        _walk_children(node, env, m, out)
        n = (num("x"), num("y"), num("z"))
        if any(abs(v) > 1e-12 for v in n):
            cx, cy, cz = num("cx"), num("cy"), num("cz")
            xform = mesh.mat_mul(mesh.mat_translate(cx, cy, cz), mesh.mat_mul(
                mesh.mat_mirror(*n), mesh.mat_translate(-cx, -cy, -cz)))
            _walk_children(node, env, mesh.mat_mul(m, xform), out)
        return
    if t in ("for_loop", "while_loop"):
        var = str(node.params.get("variable", "i")) or "i"
        for value in node.loop_values(env):
            scoped = dict(env)
            scoped[var] = value
            _walk_children(node, scoped, m, out)
        return
    if t == "if_else":
        for child in mesh._if_branch(node, env):
            _walk(child, env, m, out)
        return
    if t not in _PRIMITIVES:
        raise Unsupported(node)
    leaf = _leaf(node, env, m)
    if leaf is not None:
        out.append(leaf)


def leaves(node, env) -> list:
    """The distance-function leaves under *node* (a blend), in world
    space. Raises Unsupported for a node the blend cannot merge."""
    from . import mesh
    out = []
    _walk_children(node, dict(env or {}), mesh.mat_identity(), out)
    return out


# ----------------------------------------------------------- the field

def field(parts, k: float):
    """The smooth union of *parts* with blend radius *k*, as f(x, y, z).
    A part whose box is farther than the blend reach cannot change the
    value, so it is skipped without being evaluated."""
    def f(x, y, z):
        d = INF
        for leaf in parts:
            if d != INF:
                lo, hi = leaf.lo, leaf.hi
                gx = max(lo[0] - x, 0.0, x - hi[0])
                gy = max(lo[1] - y, 0.0, y - hi[1])
                gz = max(lo[2] - z, 0.0, z - hi[2])
                if gx * gx + gy * gy + gz * gz > (d + k) ** 2 and d + k > 0:
                    continue
            m = leaf.inv
            v = leaf.fn(m[0][0] * x + m[0][1] * y + m[0][2] * z + m[0][3],
                        m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3],
                        m[2][0] * x + m[2][1] * y + m[2][2] * z + m[2][3]
                        ) * leaf.scale
            if d == INF:
                d = v
            elif k > 0.0:
                h = max(k - abs(d - v), 0.0) / k
                d = min(d, v) - h * h * k * 0.25
            elif v < d:
                d = v
        return d
    return f


# ------------------------------------------------- marching tetrahedra

_CORNERS = ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
            (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1))
#: six tetrahedra round the cube's main diagonal (Kuhn): neighbouring
#: cubes split their shared face along the same diagonal, so the
#: surface has no cracks
_TETS = ((0, 1, 2, 6), (0, 2, 3, 6), (0, 3, 7, 6),
         (0, 7, 4, 6), (0, 4, 5, 6), (0, 5, 1, 6))


def polygonize(f, lo, hi, cell) -> list:
    """Counter-clockwise (outward) triangles of the surface f = 0 over
    the box *lo*..*hi*, sampled every *cell* mm. The box must enclose
    the surface with a margin, or the result is left open."""
    nx, ny, nz = (max(int(math.ceil((hi[i] - lo[i]) / cell)), 1) + 1
                  for i in range(3))
    xs = [lo[0] + i * cell for i in range(nx)]
    ys = [lo[1] + j * cell for j in range(ny)]
    zs = [lo[2] + k * cell for k in range(nz)]
    vals = [0.0] * (nx * ny * nz)
    for k in range(nz):
        z = zs[k]
        for j in range(ny):
            y = ys[j]
            base = nx * (j + ny * k)
            for i in range(nx):
                v = f(xs[i], y, z)
                # a sample exactly on the surface would put a vertex on
                # a grid corner and collapse faces: nudge it outside
                vals[base + i] = v if v != 0.0 else 1e-12
    return mesh_values(vals, xs, ys, zs)


def mesh_values(vals, xs, ys, zs) -> list:
    """Marching tetrahedra over sampled values: *vals* flat, x fastest
    (index i + nx * (j + ny * k)), negative inside, none exactly 0.
    Counter-clockwise (outward) triangles. remesh.py samples a grid of
    its own and meshes it here."""
    nx, ny, nz = len(xs), len(ys), len(zs)
    offsets = [dx + nx * (dy + ny * dz) for dx, dy, dz in _CORNERS]
    cache = {}
    tris = []
    for k in range(nz - 1):
        for j in range(ny - 1):
            for i in range(nx - 1):
                g0 = i + nx * (j + ny * k)
                ids = [g0 + o for o in offsets]
                vs = [vals[g] for g in ids]
                if min(vs) > 0.0 or max(vs) < 0.0:
                    continue
                pos = [(xs[i + dx], ys[j + dy], zs[k + dz])
                       for dx, dy, dz in _CORNERS]
                for tet in _TETS:
                    ins = [c for c in tet if vs[c] < 0.0]
                    if not ins or len(ins) == 4:
                        continue
                    outs = [c for c in tet if vs[c] >= 0.0]

                    def cut(a, b):
                        key = (ids[a], ids[b]) if ids[a] < ids[b] \
                            else (ids[b], ids[a])
                        point = cache.get(key)
                        if point is None:
                            t = vs[a] / (vs[a] - vs[b])
                            t = min(max(t, 1e-3), 1.0 - 1e-3)
                            pa, pb = pos[a], pos[b]
                            point = (pa[0] + (pb[0] - pa[0]) * t,
                                     pa[1] + (pb[1] - pa[1]) * t,
                                     pa[2] + (pb[2] - pa[2]) * t)
                            cache[key] = point
                        return point
                    if len(ins) == 1:
                        polys = [[cut(ins[0], o) for o in outs]]
                    elif len(ins) == 3:
                        polys = [[cut(c, outs[0]) for c in ins]]
                    else:
                        (i0, i1), (o0, o1) = ins, outs
                        q = [cut(i0, o0), cut(i0, o1), cut(i1, o1),
                             cut(i1, o0)]
                        polys = [[q[0], q[1], q[2]], [q[0], q[2], q[3]]]
                    # outward = from the inside corners to the outside
                    ci = [sum(pos[c][a] for c in ins) / len(ins)
                          for a in range(3)]
                    co = [sum(pos[c][a] for c in outs) / len(outs)
                          for a in range(3)]
                    dx, dy, dz = co[0] - ci[0], co[1] - ci[1], co[2] - ci[2]
                    for a, b, c in polys:
                        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
                        vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
                        n = (uy * vz - uz * vy, uz * vx - ux * vz,
                             ux * vy - uy * vx)
                        if n[0] * dx + n[1] * dy + n[2] * dz < 0.0:
                            b, c = c, b
                        tris.append((a, b, c))
    return tris


# ------------------------------------------------------- the numpy path

def field_values(parts, k: float, pts, reach: float):
    """The smooth union of *parts* (blend radius *k*) at the points
    *pts* (an (N, 3) array). A leaf is evaluated only within *reach* of
    its box — beyond it its distance exceeds the blend, so it cannot
    change the value; points no leaf reaches stay +1e30 (outside)."""
    np = _np
    big = 1e30
    d = np.full(len(pts), big)
    for leaf in parts:
        lo = np.asarray(leaf.lo) - reach
        hi = np.asarray(leaf.hi) + reach
        idx = np.nonzero(np.all((pts >= lo) & (pts <= hi), axis=1))[0]
        if not len(idx):
            continue
        p = pts[idx]
        m = leaf.inv
        x = m[0][0] * p[:, 0] + m[0][1] * p[:, 1] + m[0][2] * p[:, 2] + m[0][3]
        y = m[1][0] * p[:, 0] + m[1][1] * p[:, 1] + m[1][2] * p[:, 2] + m[1][3]
        z = m[2][0] * p[:, 0] + m[2][1] * p[:, 1] + m[2][2] * p[:, 2] + m[2][3]
        v = leaf.vfn(x, y, z) * leaf.scale
        dd = d[idx]
        first = dd >= big * 0.5
        if k > 0.0:
            h = np.maximum(k - np.abs(dd - v), 0.0) / k
            new = np.minimum(dd, v) - h * h * k * 0.25
        else:
            new = np.minimum(dd, v)
        d[idx] = np.where(first, v, new)
    return d


def polygonize_np(parts, k, lo, hi, cell) -> list:
    """polygonize() over the smooth union of *parts*, vectorized: the
    grid sampled a slab of z planes at a time, then meshed by
    mesh_values_np."""
    np = _np
    nx, ny, nz = (max(int(math.ceil((hi[i] - lo[i]) / cell)), 1) + 1
                  for i in range(3))
    xs = lo[0] + np.arange(nx) * cell
    ys = lo[1] + np.arange(ny) * cell
    zs = lo[2] + np.arange(nz) * cell
    vals = np.empty(nx * ny * nz)
    gx, gy = np.meshgrid(xs, ys)                  # (ny, nx), x fastest
    plane = np.stack([gx.ravel(), gy.ravel()], axis=1)
    per = max(1, SLAB_POINTS // (nx * ny))
    reach = k + 2.0 * cell
    for k0 in range(0, nz, per):
        ks = range(k0, min(nz, k0 + per))
        pts = np.concatenate([np.column_stack(
            [plane, np.full(len(plane), zs[kk])]) for kk in ks])
        v = field_values(parts, k, pts, reach)
        vals[k0 * nx * ny:(ks[-1] + 1) * nx * ny] = v
    vals[vals == 0.0] = 1e-12             # never a vertex on a grid corner
    return mesh_values_np(vals, xs, ys, zs)


def _tet_table():
    """Case (inside bits over a tetrahedron's 4 corners) -> triangles as
    three (a, b) corner pairs: the same cuts mesh_values makes."""
    table = {}
    for case in range(1, 15):
        ins = [q for q in range(4) if case >> q & 1]
        outs = [q for q in range(4) if not case >> q & 1]
        if len(ins) == 1:
            tris = [[(ins[0], o) for o in outs]]
        elif len(ins) == 3:
            tris = [[(c, outs[0]) for c in ins]]
        else:
            (i0, i1), (o0, o1) = ins, outs
            q = [(i0, o0), (i0, o1), (i1, o1), (i1, o0)]
            tris = [[q[0], q[1], q[2]], [q[0], q[2], q[3]]]
        table[case] = (ins, outs, tris)
    return table


_TET_TABLE = _tet_table()


def mesh_values_np(vals, xs, ys, zs) -> list:
    """mesh_values() vectorized: the same tetrahedra, the same cuts
    (an edge's vertex is shared by every face that crosses it, so the
    surface is closed) and the same outward winding."""
    np = _np
    vals = np.asarray(vals, dtype=float)
    xs, ys, zs = (np.asarray(a, dtype=float) for a in (xs, ys, zs))
    nx, ny, nz = len(xs), len(ys), len(zs)
    if min(nx, ny, nz) < 2:
        return []
    grid = vals.reshape(nz, ny, nx)
    inside = grid < 0.0
    count = np.zeros((nz - 1, ny - 1, nx - 1), dtype=np.int8)
    for dx, dy, dz in _CORNERS:
        count += inside[dz:nz - 1 + dz, dy:ny - 1 + dy, dx:nx - 1 + dx]
    ka, ja, ia = np.nonzero((count > 0) & (count < 8))
    if not len(ia):
        return []
    g0 = ia + nx * (ja + ny * ka)
    offsets = np.array([dx + nx * (dy + ny * dz) for dx, dy, dz in _CORNERS])
    gids = g0[:, None] + offsets[None, :]                     # (M, 8)
    cvals = vals[gids]
    cins = cvals < 0.0

    def coords(g):
        i = g % nx
        j = (g // nx) % ny
        k = g // (nx * ny)
        return np.stack([xs[i], ys[j], zs[k]], axis=-1)

    ea, eb, dirs = [], [], []
    for tet in _TETS:
        tc = np.array(tet)
        bits = (cins[:, tc[0]].astype(np.int8) | cins[:, tc[1]] << 1
                | cins[:, tc[2]] << 2 | cins[:, tc[3]] << 3)
        for case, (ins, outs, tris) in _TET_TABLE.items():
            rows = np.nonzero(bits == case)[0]
            if not len(rows):
                continue
            tg = gids[rows][:, tc]                            # (R, 4)
            ci = coords(tg[:, ins]).mean(axis=1)
            co = coords(tg[:, outs]).mean(axis=1)
            for tri in tris:
                ea.append(np.stack([tg[:, a] for a, _b in tri], axis=1))
                eb.append(np.stack([tg[:, b] for _a, b in tri], axis=1))
                dirs.append(co - ci)
    ea = np.concatenate(ea)                                   # (T, 3)
    eb = np.concatenate(eb)
    dirs = np.concatenate(dirs)
    lo_g, hi_g = np.minimum(ea, eb), np.maximum(ea, eb)
    total = np.int64(nx) * ny * nz
    keys = lo_g.astype(np.int64) * total + hi_g
    uniq, inverse = np.unique(keys.ravel(), return_inverse=True)
    ga, gb = uniq // total, uniq % total
    va, vb = vals[ga], vals[gb]
    t = np.clip(va / (va - vb), 1e-3, 1.0 - 1e-3)
    pa, pb = coords(ga), coords(gb)
    points = pa + (pb - pa) * t[:, None]
    tri_v = inverse.reshape(-1, 3)
    a, b, c = (points[tri_v[:, q]] for q in range(3))
    n = np.cross(b - a, c - a)
    flip = np.einsum("ij,ij->i", n, dirs) < 0.0
    tri_v[flip] = tri_v[flip][:, [0, 2, 1]]
    pts = [tuple(p) for p in points.tolist()]
    return [(pts[i], pts[j], pts[k]) for i, j, k in tri_v.tolist()]


def blend(node, env, radius: float, detail: int) -> list:
    """Triangles of the smooth blend of everything under *node*."""
    parts = leaves(node, env)
    if not parts:
        return []
    k = max(float(radius), 0.0)
    lo = [min(p.lo[i] for p in parts) - k for i in range(3)]
    hi = [max(p.hi[i] for p in parts) + k for i in range(3)]
    size = max(hi[i] - lo[i] for i in range(3))
    cell = size / max(int(detail), 4)
    fast = _np is not None and all(p.vfn is not None for p in parts)
    limit = MAX_GRID_POINTS_NP if fast else MAX_GRID_POINTS
    # a margin of two cells round the reach keeps the surface closed
    while True:
        counts = [(hi[i] - lo[i]) / cell + 5 for i in range(3)]
        if counts[0] * counts[1] * counts[2] <= limit:
            break
        cell *= 1.25
    lo = [v - 2 * cell for v in lo]
    hi = [v + 2 * cell for v in hi]
    if fast:
        return polygonize_np(parts, k, lo, hi, cell)
    return polygonize(field(parts, k), lo, hi, cell)
