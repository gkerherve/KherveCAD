"""Surfaces from curves — Rhino's loft, sweep, patch, revolve and extrude
(Qt-free, OpenCascade).

The `curve_surface` node holds 3D curves (`curve` nodes, curve3d.py) as
its children and makes an EXACT surface from them:

* **loft**    — a skin through the curves, in order (a hull, a vase, a
                wing through its sections). `ruled` gives straight
                lines between them instead of a smooth skin.
* **sweep**   — the first curve is the RAIL, the rest are PROFILES
                carried along it (a moulding, a handle, a bent beam).
* **sweep2**  — two RAILS and the profiles between them; the section
                stretches to stay on both rails (a boat side, a slide).
* **patch**   — a surface filled inside a closed boundary, every other
                curve pulling the surface through it (a bump, a cushion,
                a car panel through its feature lines).
* **revolve** — the first curve turned about the Z axis by `angle`.
* **extrude** — the first curve pushed straight up by `height`.

A surface is not a solid, and a 3D printer and OpenSCAD both want one,
so an open result is THICKENED by `thickness` (mm). A loft of closed
curves is capped into a solid on its own unless `capped` is off — then
it is an open tube (a vase, a lampshade) thickened into a wall. OpenSCAD gets the baked polyhedron
(bakedkit); a STEP export (cadexchange) gets the exact surface itself.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from . import bakedkit

KINDS = ("loft", "sweep", "sweep2", "patch", "revolve", "extrude")

#: what each kind needs, in words the user reads in the red tooltip
NEEDS = {
    "loft": (2, "a loft needs at least two curves — its sections, in "
                "order"),
    "sweep": (2, "a sweep needs a rail (the first curve) and at least "
                 "one profile"),
    "sweep2": (3, "a two-rail sweep needs two rails (the first two "
                  "curves) and at least one profile"),
    "patch": (1, "a patch needs a closed boundary curve first"),
    "revolve": (1, "a revolve needs one curve, the profile to turn"),
    "extrude": (1, "an extrude needs one curve"),
}

#: tessellation of the exact surface for the preview / OpenSCAD:
#: deflection as a fraction of the size, angle in degrees
DEFLECTION = 0.002
ANGLE = 12.0

_DEFAULTS = dict(kind="loft", thickness=1.0, ruled=False, capped=True,
                 angle=360.0,
                 height=20.0, show_curves=False)


def curves(node, env=None):
    """The curve children, in order (hidden ones skipped)."""
    return [c for c in node.children if c.visible and c.type == "curve"]


def occ_ok():
    from . import cadexchange
    return cadexchange.occ_available()


# ================================================================ build

def shape(node, env=None):
    """The exact OCC shape of the node (solid when possible), or raises
    ValueError with a sentence for the user."""
    from . import curve3d
    env = env or {}
    kind = str(node.params.get("kind", "loft"))
    cs = curves(node, env)
    least, why = NEEDS.get(kind, (1, ""))
    if len(cs) < least:
        raise ValueError(why)
    wires = []
    for c in cs:
        w = curve3d.wire_of(c, env)
        if w is None:
            raise ValueError(f"{c.name}: this curve cannot be built")
        wires.append(w)
    p = node.params
    from . import mesh
    thick = mesh.rv(p.get("thickness", 1.0), env, 1.0)
    if kind == "loft":
        out = _loft(wires, [_closed(c) and bool(p.get("capped", True))
                            for c in cs], bool(p.get("ruled", False)))
    elif kind == "sweep":
        out = _sweep(wires[0], wires[1:], None)
    elif kind == "sweep2":
        out = _sweep(wires[0], wires[2:], wires[1])
    elif kind == "patch":
        if not _closed(cs[0]):
            raise ValueError("a patch's first curve is its boundary — "
                             "tick Closed loop on it")
        out = _patch(wires[0], wires[1:])
    elif kind == "revolve":
        out = _revolve(wires[0], mesh.rv(p.get("angle", 360.0), env, 360.0))
    else:
        out = _extrude(wires[0], mesh.rv(p.get("height", 20.0), env, 20.0),
                       _closed(cs[0]))
    if out is None:
        raise ValueError(f"OpenCascade could not make this {kind} — try "
                         "curves that do not cross, all running the same "
                         "way")
    return _finish(out, thick)


def _closed(c):
    return bool(c.params.get("closed")) and len(c.params.get("points")
                                                or []) > 2


def _loft(wires, closed, ruled):
    from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
    solid = all(closed)
    op = BRepOffsetAPI_ThruSections(solid, ruled, 1e-6)
    for w in wires:
        op.AddWire(w)
    op.CheckCompatibility(True)
    op.Build()
    return op.Shape() if op.IsDone() else None


def _sweep(rail, profiles, rail2):
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell
    op = BRepOffsetAPI_MakePipeShell(rail)
    if rail2 is not None:
        op.SetMode(rail2, True)             # auxiliary spine: two rails
    else:
        op.SetMode(False)                   # corrected Frenet, no twist
    for w in profiles:
        op.Add(w, False, False)
    op.Build()
    if not op.IsDone():
        return None
    try:
        op.MakeSolid()
    except Exception:
        pass
    return op.Shape()


def _patch(boundary, inner):
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeFilling
    from OCP.GeomAbs import GeomAbs_C0
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_EDGE
    from . import cadexchange
    op = BRepOffsetAPI_MakeFilling()
    exp = TopExp_Explorer(boundary, TopAbs_EDGE)
    while exp.More():
        op.Add(cadexchange._topods("Edge", exp.Current()), GeomAbs_C0, True)
        exp.Next()
    for w in inner:
        exp = TopExp_Explorer(w, TopAbs_EDGE)
        while exp.More():
            op.Add(cadexchange._topods("Edge", exp.Current()), GeomAbs_C0,
                   False)
            exp.Next()
    op.Build()
    return op.Shape() if op.IsDone() else None


def _revolve(wire, angle):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeRevol
    from OCP.gp import gp_Ax1, gp_Pnt, gp_Dir
    axis = gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))
    if abs(angle) >= 360.0:
        return BRepPrimAPI_MakeRevol(wire, axis).Shape()
    return BRepPrimAPI_MakeRevol(wire, axis, math.radians(angle)).Shape()


def _extrude(wire, height, closed):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.gp import gp_Vec
    base = wire
    if closed:
        face = BRepBuilderAPI_MakeFace(wire, False)
        if face.IsDone():
            base = face.Face()           # a closed curve extrudes solid
    return BRepPrimAPI_MakePrism(base, gp_Vec(0, 0, height)).Shape()


def is_solid(shape):
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_SOLID
    return TopExp_Explorer(shape, TopAbs_SOLID).More()


def _finish(shape, thick):
    """A solid stays as it is (or is hollowed when thickness > 0 asks);
    a sheet is thickened into one."""
    if is_solid(shape):
        return shape
    if thick <= 0:
        raise ValueError("this surface is open, so it needs a thickness "
                         "above 0 to be a solid you can print and render")
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeThickSolid
    op = BRepOffsetAPI_MakeThickSolid()
    try:
        op.MakeThickSolidBySimple(shape, -thick)
        op.Build()
        if op.IsDone() and not op.Shape().IsNull():
            return op.Shape()
    except Exception:
        pass
    raise ValueError(f"could not thicken this surface by {thick:g} mm — "
                     "try a thinner wall, or curves that bend less "
                     "sharply")


# ========================================================== the node

def _compute(node, env):
    from . import cadexchange
    s = shape(node, env)
    return cadexchange._mesh_shape_rel(s, DEFLECTION, ANGLE)


def _check(node, env):
    if not occ_ok():
        from . import cadexchange
        return cadexchange.missing(".step").replace(
            "STEP", "Surfaces from curves")
    try:
        shape(node, env)
    except ValueError as exc:
        return str(exc)
    except Exception as exc:                       # pragma: no cover
        return f"surface: {exc}"
    return None


KIT = bakedkit.make(
    "curve_surface", "Surface from curves", "mdi.vector-curve",
    _DEFAULTS,
    [("kind", "Make", "choice", list(KINDS), None),
     ("thickness", "Wall thickness (mm; open surfaces need one)",
      "float", 0.0, 1e4),
     ("ruled", "Loft: straight between sections", "bool", None, None),
     ("capped", "Loft: close the ends (closed curves)", "bool", None,
      None),
     ("angle", "Revolve: angle (°, about Z)", "float", -360.0, 360.0),
     ("height", "Extrude: height (mm)", "float", -1e5, 1e5),
     ("show_curves", "Show the curves too", "bool", None, None)],
    _compute, choices={"kind": KINDS},
    draws_children=lambda node: bool(node.params.get("show_curves")),
    check=_check, inexact_ok=True)


# ===================================================== making one

KIND_LABELS = [
    ("loft", "Loft — a skin through the curves, in order"),
    ("sweep", "Sweep — first curve is the rail, the rest are profiles"),
    ("sweep2", "Sweep along two rails — first two curves are rails"),
    ("patch", "Patch — fill inside the first (closed) curve"),
    ("revolve", "Revolve — turn the curve about the Z axis"),
    ("extrude", "Extrude — push the curve straight up"),
]


def gather_curves(nodes):
    """The curves the user means: a selected curve itself, or every
    curve inside a selected Object or group (a curve drawn in Main
    arrives in an Object of its own). In selection order."""
    out = []
    for n in nodes:
        found = [n] if n.type == "curve" else \
            [c for c in n.walk() if c.type == "curve"]
        for c in found:
            if c not in out:
                out.append(c)
    return out


def make_surface(model, nodes, kind="loft"):
    """Wrap the curves in a new `curve_surface` of *kind* where the first
    of them stood — one undo step, returns the node. Curves from other
    Objects are brought over WHERE THEY ARE (their points mapped into
    the first one's frame), and an Object left empty is removed."""
    from . import mesh
    curves_ = gather_curves(nodes)
    if not curves_:
        raise ValueError("select one or more 3D curves first")
    first = curves_[0]
    parent = first.parent
    index = parent.children.index(first)
    names = {"loft": "Loft", "sweep": "Sweep", "sweep2": "Two-rail sweep",
             "patch": "Patch", "revolve": "Revolve", "extrude": "Extrude"}
    surf = model.add_node("curve_surface", dict(_DEFAULTS, kind=kind),
                          parent=parent, name=names.get(kind, kind))
    model.move_node(surf, parent, index)
    to_dest = _inverse(mesh.ancestor_matrix(surf))
    emptied = []
    for c in curves_:
        old = c.parent
        if old is not parent:
            m = mesh.mat_mul(to_dest, mesh.ancestor_matrix(c))
            c.params["points"] = [
                [round(v, 6) for v in mesh.mat_apply(m, _xyz(p))]
                for p in c.params.get("points") or []]
            emptied.append(old)
        model.move_node(c, surf)
    for old in emptied:
        top = old
        while top.parent is not None and top.parent is not model.root:
            top = top.parent
        holds_surface = any(n is surf for n in top.walk())
        has_geometry = any(not n.children for n in top.walk()
                           if n is not top)
        if top.parent is not None and not holds_surface and \
                not has_geometry:
            model.remove_node(top)
    return surf


def _xyz(p):
    vals = [float(v) for v in list(p)[:3]]
    return vals + [0.0] * (3 - len(vals))


def _inverse(m):
    import numpy as np
    return np.linalg.inv(np.asarray(m, dtype=float)).tolist()
