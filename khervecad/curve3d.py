"""3D curves — a smooth or straight line through points in space (Qt-free).

Rhino's whole way of working starts from curves; KherveCAD's started
from solids, and a cable, a handrail, a wire frame or a bent rod had to
be faked with hulls of spheres. The `curve` node is that missing piece:

* **points** — the rows [X, Y, Z] the curve passes through, in order;
* **style** — "smooth" (a Catmull-Rom curve through every point, the
  same one Sweep uses) or "straight" (a polyline with sharp corners);
* **closed** — joins the end back to the start (a ring, a loop);
* **thickness** — the curve is drawn as a round wire this many mm
  across, so it is a real solid that prints, renders and booleans. A
  curve meant only as a guide can be made thin and hidden.

In OpenSCAD the wire is a chain of hulled spheres (`kcad_curve`, real
OpenSCAD with the same Catmull-Rom formula); in the preview it is the
same chain as a tube with round joints; in a STEP export (cadexchange)
it is an EXACT B-spline swept by a circle — a pipe any CAD reads as
true surfaces.

"Make a pipe along it" is one more step: a Sweep node reads the same
points (`sweep_from_curve`), so the curve is the rail for any profile.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

SHAPE_3D = "3d"
STYLES = ["smooth", "straight"]

NODE_TYPES = {
    "curve": dict(
        label="3D curve", category=SHAPE_3D, icon="mdi.vector-curve",
        params=dict(points=[[0.0, 0.0, 0.0], [20.0, 10.0, 10.0],
                            [40.0, 0.0, 20.0], [60.0, 10.0, 10.0]],
                    style="smooth", closed=False, thickness=2.0,
                    smooth=8),
        schema=[("points", "Points the curve passes through", "rows",
                 ["X", "Y", "Z"], None),
                ("style", "Style", "choice", STYLES, None),
                ("closed", "Closed loop", "bool", None, None),
                ("thickness", "Wire thickness (mm)", "float", 0.01, 1e5),
                ("smooth", "Smoothness (steps between points)", "int",
                 1, 64)]),
}
TYPES = frozenset(NODE_TYPES)
LEAVES = frozenset(NODE_TYPES)
TEXT_PARAMS = frozenset({"style"})


# ------------------------------------------------------------- geometry

def control_points(node, env=None):
    from . import mesh
    out = []
    for row in node.params.get("points") or []:
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            vals = [mesh.rv(v, env) for v in list(row)[:3]]
            vals += [0.0] * (3 - len(vals))
            out.append(tuple(vals))
    return out


def polyline(points, style="smooth", closed=False, smooth=8):
    """The points the drawn curve runs through: the controls themselves
    for a straight curve, a Catmull-Rom densification for a smooth one
    (every control stays on the curve). A closed curve repeats its first
    point at the end."""
    from .sweep import densify
    if len(points) < 2:
        return list(points)
    if style == "straight":
        pts = list(points)
    else:
        pts = densify(points, max(int(smooth), 1), closed)
    if closed and len(pts) > 2:
        pts = pts + [pts[0]]
    return pts


def length(points) -> float:
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def _resolved(node, env):
    from . import mesh
    style = str(node.params.get("style", "smooth"))
    closed = bool(node.params.get("closed", False))
    smooth = int(mesh.rv(node.params.get("smooth", 8), env, 8))
    thick = mesh.rv(node.params.get("thickness", 2.0), env, 2.0)
    return style, closed, smooth, thick


def wire_mesh(node, env=None, sides=12):
    """The preview: one tube per span with a ball at every point, which
    is exactly what the OpenSCAD chain of hulled spheres looks like."""
    from . import mesh
    style, closed, smooth, thick = _resolved(node, env)
    pts = polyline(control_points(node, env), style, closed, smooth)
    r = thick / 2.0
    if r <= 0 or len(pts) < 2:
        return []
    n = max(6, min(int(sides), 32))
    tris = []
    for a, b in zip(pts, pts[1:]):
        tris.extend(_tube(a, b, r, n))
    ball = dict(radius=r, segments=n, x=0.0, y=0.0, z=0.0)
    joints = pts[:-1] if closed else pts
    for p in joints:
        ball.update(x=p[0], y=p[1], z=p[2])
        tris.extend(mesh.sphere_mesh(ball))
    return tris


def _tube(a, b, r, n):
    d = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ln = math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2)
    if ln < 1e-9:
        return []
    w = (d[0] / ln, d[1] / ln, d[2] / ln)
    up = (0.0, 0.0, 1.0) if abs(w[2]) < 0.9 else (1.0, 0.0, 0.0)
    u = _norm(_cross(up, w))
    v = _cross(w, u)
    ring = []
    for i in range(n):
        t = 2 * math.pi * i / n
        c, s = math.cos(t) * r, math.sin(t) * r
        ring.append((c * u[0] + s * v[0], c * u[1] + s * v[1],
                     c * u[2] + s * v[2]))
    out = []
    for i in range(n):
        j = (i + 1) % n
        p0 = _add(a, ring[i])
        p1 = _add(a, ring[j])
        q0 = _add(b, ring[i])
        q1 = _add(b, ring[j])
        out.append((p0, p1, q1))
        out.append((p0, q1, q0))
    return out


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _norm(a):
    ln = math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2) or 1.0
    return (a[0] / ln, a[1] / ln, a[2] / ln)


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


# ---------------------------------------------------------------- code

HELPER = """\
function kcad_cr(p0, p1, p2, p3, t) =
    0.5 * ((2 * p1) + (p2 - p0) * t
           + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
           + (3 * p1 - p0 - 3 * p2 + p3) * t * t * t);
function kcad_curve_points(p, smooth, closed, straight) =
    let (n = len(p))
    straight || n < 2 ? concat(p, closed && n > 2 ? [p[0]] : [])
    : let (spans = closed ? n : n - 1,
           at = function (i) closed ? p[(i + n) % n]
                : (i < 0 ? 2 * p[0] - p[1]
                   : i >= n ? 2 * p[n - 1] - p[n - 2] : p[i]))
      concat([for (k = [0 : spans - 1]) for (j = [0 : smooth])
              kcad_cr(at(k - 1), at(k), at(k + 1), at(k + 2),
                      j / (smooth + 1))],
             [closed ? p[0] : p[n - 1]]);
module kcad_curve(points = [], style = "smooth", closed = false,
                  thickness = 2, smooth = 8) {
    q = kcad_curve_points(points, max(round(smooth), 1), closed,
                          style == "straight");
    for (i = [0 : len(q) - 2])
        hull() {
            translate(q[i]) sphere(d = thickness);
            translate(q[i + 1]) sphere(d = thickness);
        }
}"""


def preamble(root) -> list:
    if any(n.type in TYPES for n in root.walk()):
        return HELPER.split("\n")
    return []


def statement(node, fmt, fn) -> str:
    from .model import scad_str
    p = node.params
    rows = "[" + ", ".join(
        "[" + ", ".join(fmt(v) for v in (list(r) + [0, 0, 0])[:3]) + "]"
        for r in p.get("points") or [] if isinstance(r, (list, tuple))) + "]"
    return (f"kcad_curve(points = {rows}, style = "
            f"{scad_str(str(p.get('style', 'smooth')))}, closed = "
            f"{'true' if p.get('closed') else 'false'}, thickness = "
            f"{fmt(p.get('thickness', 2.0))}, smooth = "
            f"{fmt(p.get('smooth', 8))})")


def _b_curve(parser, positional, named):
    from .model import CadNode
    from .scadparse import _num
    from .curves2d import _read_rows
    d = NODE_TYPES["curve"]["params"]
    style = str(named.get("style", "smooth")).strip('"')
    closed = named.get("closed", False)
    return CadNode("curve", "3D curve", dict(
        points=_read_rows(named.get("points", positional[0] if positional
                                    else []), 3, parser),
        style=style if style in STYLES else "smooth",
        closed=closed is True or str(closed).lower() == "true",
        thickness=_num(named.get("thickness", d["thickness"]),
                       d["thickness"]),
        smooth=_int(_num(named.get("smooth", d["smooth"]), d["smooth"]))))


def _int(v):
    return v if isinstance(v, str) else max(int(round(v)), 1)


BUILDERS = {"kcad_curve": _b_curve}


def check(node, env):
    from . import mesh
    pts = control_points(node, env)
    if len(pts) < 2:
        return "3D curve: give it at least two points"
    if node.params.get("closed") and len(pts) < 3:
        return "3D curve: a closed loop needs at least three points"
    if mesh.rv(node.params.get("thickness", 2.0), env, 2.0) <= 0:
        return "3D curve: the wire thickness must be more than 0"
    return None


def tess(node, env, color, sel, selected):
    from . import mesh
    return mesh._emit(wire_mesh(node, env), color, selected)


# --------------------------------------------------------- exact (OCC)

def exact_shape(node, env):
    """The wire as an exact pipe: a B-spline (or a polyline of lines)
    through the points, a circle of the thickness swept along it. None
    when OpenCascade cannot build it."""
    from OCP.gp import gp_Pnt, gp_Circ, gp_Ax2, gp_Dir
    from OCP.GeomAPI import GeomAPI_Interpolate
    from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakeEdge,
                                    BRepBuilderAPI_MakeWire)
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell
    style, closed, smooth, thick = _resolved(node, env)
    pts = control_points(node, env)
    if len(pts) < 2 or thick <= 0:
        return None
    if style == "straight":
        return _straight_exact(polyline(pts, style, closed), thick / 2.0)
    dense = polyline(pts, style, closed, smooth)
    periodic = bool(closed and len(pts) > 2)
    curve = bspline(pts, closed, smooth)
    if curve is None:
        return None
    spine = BRepBuilderAPI_MakeWire(
        BRepBuilderAPI_MakeEdge(curve).Edge()).Wire()
    start = curve.Value(curve.FirstParameter())
    tangent = curve.DN(curve.FirstParameter(), 1)
    circ = gp_Circ(gp_Ax2(start, gp_Dir(tangent)), thick / 2.0)
    profile = BRepBuilderAPI_MakeWire(
        BRepBuilderAPI_MakeEdge(circ).Edge()).Wire()
    pipe = BRepOffsetAPI_MakePipeShell(spine)
    pipe.SetMode(False)                  # corrected Frenet: no twist
    pipe.Add(profile)
    pipe.Build()
    if not pipe.IsDone():
        return None
    pipe.MakeSolid()
    if periodic:
        return pipe.Shape()
    # round ends, as the chain of balls has on screen
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeSphere
    from OCP.TopoDS import TopoDS_Compound
    from OCP.BRep import BRep_Builder
    comp, bld = TopoDS_Compound(), BRep_Builder()
    bld.MakeCompound(comp)
    bld.Add(comp, pipe.Shape())
    for p in (dense[0], dense[-1]):
        bld.Add(comp, BRepPrimAPI_MakeSphere(gp_Pnt(*p), thick / 2.0).Shape())
    return comp


def bspline(points, closed=False, smooth=8):
    """The exact B-spline through the SAME Catmull-Rom points the
    preview and OpenSCAD draw (so the exact curve IS the one on screen,
    only smooth), or None."""
    from OCP.gp import gp_Pnt
    from OCP.GeomAPI import GeomAPI_Interpolate
    pts = list(points)
    if len(pts) < 2:
        return None
    dense = polyline(pts, "smooth", closed, smooth)
    periodic = bool(closed and len(pts) > 2)
    if periodic:
        dense = dense[:-1]
    arr = _pnt_array(len(dense))
    for i, p in enumerate(dense, 1):
        arr.SetValue(i, gp_Pnt(*p))
    interp = GeomAPI_Interpolate(arr, periodic, 1e-7)
    interp.Perform()
    return interp.Curve() if interp.IsDone() else None


def wire_of(node, env=None):
    """A curve node as an exact OCC wire: B-spline when smooth, lines
    when straight. None when it cannot be built."""
    from OCP.gp import gp_Pnt
    from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakeEdge,
                                    BRepBuilderAPI_MakeWire,
                                    BRepBuilderAPI_MakePolygon)
    style, closed, smooth, _thick = _resolved(node, env or {})
    pts = control_points(node, env)
    if len(pts) < 2:
        return None
    if style == "straight":
        poly = BRepBuilderAPI_MakePolygon()
        for p in pts:
            poly.Add(gp_Pnt(*p))
        if closed and len(pts) > 2:
            poly.Close()
        return poly.Wire() if poly.IsDone() else None
    curve = bspline(pts, closed, smooth)
    if curve is None:
        return None
    return BRepBuilderAPI_MakeWire(
        BRepBuilderAPI_MakeEdge(curve).Edge()).Wire()


def _straight_exact(pts, r):
    """A straight curve exactly: a cylinder per span and a ball at each
    corner — the shape on screen, with true round faces."""
    from OCP.gp import gp_Pnt, gp_Ax2, gp_Dir
    from OCP.BRepPrimAPI import (BRepPrimAPI_MakeCylinder,
                                 BRepPrimAPI_MakeSphere)
    from OCP.TopoDS import TopoDS_Compound
    from OCP.BRep import BRep_Builder
    comp, b = TopoDS_Compound(), BRep_Builder()
    b.MakeCompound(comp)
    for p, q in zip(pts, pts[1:]):
        d = (q[0] - p[0], q[1] - p[1], q[2] - p[2])
        ln = math.sqrt(sum(c * c for c in d))
        if ln < 1e-9:
            continue
        b.Add(comp, BRepPrimAPI_MakeCylinder(
            gp_Ax2(gp_Pnt(*p), gp_Dir(*d)), r, ln).Shape())
    for p in pts:
        b.Add(comp, BRepPrimAPI_MakeSphere(gp_Pnt(*p), r).Shape())
    return comp


def _pnt_array(n):
    try:
        from OCP.TColgp import TColgp_HArray1OfPnt
        return TColgp_HArray1OfPnt(1, n)
    except ImportError:                     # OCP 7.8+: generic arrays
        from OCP.collections import HArray1_gp_Pnt
        return HArray1_gp_Pnt(1, n)


def sweep_from_curve(model, curve_node):
    """Replace a curve by a Sweep along the same points with a circle
    profile of the curve's thickness — the start of a pipe, a handrail,
    a moulding: change the profile to change the section."""
    style, closed, smooth, thick = _resolved(curve_node, {})
    parent = curve_node.parent
    index = parent.children.index(curve_node)
    sweep = model.add_node("sweep", dict(
        path=[list(p) for p in control_points(curve_node)],
        smooth=0 if style == "straight" else min(max(smooth // 2, 1), 12),
        closed=bool(closed)), parent=parent,
        name="Sweep along " + (curve_node.name or "curve"))
    model.move_node(sweep, parent, index)
    model.add_node("circle", dict(radius=max(thick, 0.1) * 2.0),
                   parent=sweep, name="Profile")
    model.remove_node(curve_node)
    return sweep
