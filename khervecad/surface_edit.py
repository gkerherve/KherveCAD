"""Editing surface BODIES — SolidWorks' Trim, Knit, Planar and Boundary
surface, Thicken, Fillet and Mirror (Qt-free, OpenCascade).

`curve_surface` (curve_surface.py) makes a surface from curves; with
`sheet` on it stays a surface. A `surface_edit` node WRAPS surfaces and
works on them, so a surface part is a tree read from the inside out,
like SolidWorks' feature list read from the first feature to the last:

    Thicken( Fillet( Knit( Trim( loft, arm, mirrored arm ), cap ) ) )

* **trim**     — the surfaces cut each other where they cross and the
                 pieces picked by `remove` (a point on each) go. Standard:
                 the FIRST child is trimmed by the others, which then
                 disappear; Mutual: every surface is trimmed by every
                 other and all stay. `keep` keeps the picked pieces
                 instead.
* **knit**     — sew the surfaces into one body (a solid when they close).
* **planar**   — a flat surface filling a closed curve, or the closed loop
                 of free edges nearest each `points` row of the first
                 child.
* **boundary** — the same, but any shape: a surface filled through the
                 loop (a patch when it is not flat).
* **thicken**  — give a surface body a wall of `thickness` mm.
* **fillet**   — round the edges nearest each `points` row by `radius`.
* **mirror**   — the surfaces and their reflection in an axis plane.

Every pick is a POINT in the node's frame — the piece, edge or loop
nearest to it — so a rebuilt surface finds its pieces again. OpenSCAD
gets the baked polyhedron (bakedkit); a STEP export gets the shape.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from . import bakedkit

OPS = ("trim", "knit", "planar", "boundary", "thicken", "fillet", "mirror")
PLANES = ("XY (Top)", "XZ (Front)", "YZ (Right)")

#: what each op needs, as the sentence the red tooltip shows
NEEDS = {
    "trim": (2, "a trim needs the surface to trim and at least one more "
                "surface to cut with"),
    "knit": (1, "knit needs the surfaces to sew together"),
    "planar": (1, "a planar surface needs a closed curve, or a surface "
                  "with an open loop of edges"),
    "boundary": (1, "a boundary surface needs a surface with an open "
                    "loop of edges (or a closed curve)"),
    "thicken": (1, "thicken needs a surface"),
    "fillet": (1, "a fillet needs a body with edges"),
    "mirror": (1, "mirror needs the surfaces to reflect"),
}

DEFLECTION = 0.002
ANGLE = 12.0
SEW_TOL = 0.05

_DEFAULTS = dict(op="trim", mutual=False, keep=False, remove=[],
                 points=[], solid=False, thickness=2.0, radius=5.0,
                 plane="YZ (Right)", offset=0.0)


# ============================================================== helpers

def _faces(shape):
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_FACE
    from . import cadexchange
    out = []
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        out.append(cadexchange._topods("Face", exp.Current()))
        exp.Next()
    return out


def _edges(shape):
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopTools import TopTools_IndexedMapOfShape
    from OCP.TopExp import TopExp
    from . import cadexchange
    m = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(shape, TopAbs_EDGE, m)
    return [cadexchange._topods("Edge", m.FindKey(i + 1))
            for i in range(m.Extent())]


def compound(shapes):
    from OCP.TopoDS import TopoDS_Compound
    from OCP.BRep import BRep_Builder
    comp, b = TopoDS_Compound(), BRep_Builder()
    b.MakeCompound(comp)
    for s in shapes:
        b.Add(comp, s)
    return comp


def _dist(point, shape):
    """Distance from an (x, y, z) point to an OCC shape."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.gp import gp_Pnt
    v = BRepBuilderAPI_MakeVertex(gp_Pnt(*point)).Vertex()
    d = BRepExtrema_DistShapeShape(v, shape)
    return d.Value() if d.IsDone() else 1e30


def _nearest(point, shapes):
    best, best_d = None, 1e30
    for i, s in enumerate(shapes):
        d = _dist(point, s)
        if d < best_d:
            best, best_d = i, d
    return best


def _point(row):
    vals = [float(v) for v in list(row)[:3]]
    return tuple(vals + [0.0] * (3 - len(vals)))


def child_shapes(node, env):
    """The OCC shape of every visible child, in order."""
    from . import curve3d
    out = []
    for c in node.children:
        if not c.visible:
            continue
        if c.type == "curve_surface":
            shape = _sheet(c, env)
        elif c.type == "surface_edit":
            shape = shape_of(c, env)
        elif c.type == "curve":
            wire = curve3d.wire_of(c, env)
            if wire is None:
                raise ValueError(f"{c.name}: this curve cannot be built")
            shape = wire
        else:
            continue
        out.append(shape)
    return out


def _sheet(node, env):
    """A curve_surface child as a surface (never thickened here)."""
    from . import curve_surface
    saved = node.params.get("sheet")
    node.params["sheet"] = True
    try:
        return curve_surface.shape(node, env)
    finally:
        if saved is None:
            node.params.pop("sheet", None)
        else:
            node.params["sheet"] = saved


# =============================================================== the ops

def trim(shapes, mutual, picks, keep):
    """Split the surfaces where they cross and drop (or keep) the pieces
    nearest the *picks*."""
    from OCP.BOPAlgo import BOPAlgo_Builder
    builder = BOPAlgo_Builder()
    for s in shapes:
        builder.AddArgument(s)
    builder.Perform()
    if builder.HasErrors():
        raise ValueError("the surfaces could not be cut by each other — "
                         "check that they really cross")
    if mutual:
        pieces = _faces(builder.Shape())
    else:
        pieces = []
        for f in _faces(shapes[0]):
            mods = builder.Modified(f)
            got = [m for m in mods]
            if got:
                for m in got:
                    pieces.extend(_faces(m))
            elif not builder.IsDeleted(f):
                pieces.append(f)
    if not pieces:
        raise ValueError("nothing is left after the trim")
    chosen = set()
    for p in picks:
        i = _nearest(_point(p), pieces)
        if i is not None:
            chosen.add(i)
    kept = [pc for i, pc in enumerate(pieces)
            if (i in chosen) == bool(keep)]
    if not kept:
        raise ValueError("the trim would remove every piece")
    return compound(kept)


def pieces_of(shapes, mutual=True):
    """The pieces a trim of *shapes* would leave to choose from (for the
    window to number them): list of OCC faces."""
    from OCP.BOPAlgo import BOPAlgo_Builder
    builder = BOPAlgo_Builder()
    for s in shapes:
        builder.AddArgument(s)
    builder.Perform()
    return _faces(builder.Shape())


def knit(shapes, solid=False, tol=SEW_TOL):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing
    sew = BRepBuilderAPI_Sewing(tol)
    for s in shapes:
        for f in _faces(s):
            sew.Add(f)
    sew.Perform()
    out = sew.SewedShape()
    if solid:
        out = _solid_of(out) or out
    return out


def _solid_of(shape):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeSolid
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_SHELL
    from OCP.ShapeFix import ShapeFix_Solid
    from . import cadexchange
    exp = TopExp_Explorer(shape, TopAbs_SHELL)
    if not exp.More():
        return None
    mk = BRepBuilderAPI_MakeSolid(cadexchange._topods("Shell", exp.Current()))
    if not mk.IsDone():
        return None
    fix = ShapeFix_Solid(mk.Solid())
    fix.Perform()
    return fix.Solid()


def free_loops(shape):
    """The closed wires made of the free (one-face) edges of *shape*."""
    from OCP.ShapeAnalysis import ShapeAnalysis_FreeBounds
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_WIRE
    from . import cadexchange
    fb = ShapeAnalysis_FreeBounds(shape, SEW_TOL, False, False)
    out = []
    for comp in (fb.GetClosedWires(), fb.GetOpenWires()):
        exp = TopExp_Explorer(comp, TopAbs_WIRE)
        while exp.More():
            out.append(cadexchange._topods("Wire", exp.Current()))
            exp.Next()
    return out


def fill(wire, planar_only=False):
    """A face filling the closed *wire* (flat when it is flat)."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    mk = BRepBuilderAPI_MakeFace(wire, True)
    if mk.IsDone():
        return mk.Face()
    if planar_only:
        raise ValueError("this loop is not flat — use Boundary surface")
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeFilling
    from OCP.GeomAbs import GeomAbs_C0
    op = BRepOffsetAPI_MakeFilling()
    for e in _edges(wire):
        op.Add(e, GeomAbs_C0, True)
    op.Build()
    if not op.IsDone():
        raise ValueError("could not fill this loop")
    return op.Shape()


def caps(shapes, picks, planar_only):
    """Faces closing the open loops of the first shape nearest *picks*
    (or every closed curve among *shapes*)."""
    from OCP.TopAbs import TopAbs_WIRE
    out = []
    loops = []
    base = None
    for s in shapes:
        if s.ShapeType() == TopAbs_WIRE:
            out.append(fill(s, planar_only))
        elif base is None:
            base = s
    if base is not None:
        loops = free_loops(base)
        if not loops:
            raise ValueError("this surface has no open loop of edges")
        chosen = []
        for p in picks:
            i = _nearest(_point(p), loops)
            if i is not None and i not in chosen:
                chosen.append(i)
        if not picks:
            chosen = list(range(len(loops)))
        out.extend(fill(loops[i], planar_only) for i in chosen)
    if not out:
        raise ValueError("nothing to fill — pick an open loop of edges")
    return compound(out)


def thicken(shape, thick):
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeThickSolid
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_SOLID
    if TopExp_Explorer(shape, TopAbs_SOLID).More():
        return shape
    op = BRepOffsetAPI_MakeThickSolid()
    op.MakeThickSolidBySimple(shape, thick)
    op.Build()
    if op.IsDone() and not op.Shape().IsNull():
        return op.Shape()
    raise ValueError(f"could not thicken by {thick:g} mm — try a thinner "
                     "wall or round the sharp edges first")


def fillet(shape, radius, picks):
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
    edges = _edges(shape)
    mk = BRepFilletAPI_MakeFillet(shape)
    added = 0
    seen = []
    for p in picks:
        i = _nearest(_point(p), edges)
        if i is None or i in seen:
            continue
        seen.append(i)
        mk.Add(radius, edges[i])
        added += 1
    if not added:
        raise ValueError("pick the edges to round")
    mk.Build()
    if not mk.IsDone():
        raise ValueError(f"a fillet of {radius:g} mm does not fit here")
    return mk.Shape()


def mirror(shapes, plane, offset):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Trsf, gp_Ax2, gp_Pnt, gp_Dir
    normal = {"XY (Top)": (0, 0, 1), "XZ (Front)": (0, 1, 0),
              "YZ (Right)": (1, 0, 0)}.get(plane, (1, 0, 0))
    o = gp_Pnt(*(normal[i] * offset for i in range(3)))
    t = gp_Trsf()
    t.SetMirror(gp_Ax2(o, gp_Dir(*normal)))
    out = list(shapes)
    for s in shapes:
        out.append(BRepBuilderAPI_Transform(s, t, True).Shape())
    return compound(out)


# ============================================================ the node

def shape_of(node, env):
    """The OCC shape a `surface_edit` node makes, or ValueError."""
    from . import mesh
    op = str(node.params.get("op", "trim"))
    shapes = child_shapes(node, env)
    least, why = NEEDS.get(op, (1, ""))
    if len(shapes) < least:
        raise ValueError(why)
    p = node.params
    if op == "trim":
        return trim(shapes, bool(p.get("mutual")), p.get("remove") or [],
                    bool(p.get("keep")))
    if op == "knit":
        return knit(shapes, bool(p.get("solid")))
    if op in ("planar", "boundary"):
        return caps(shapes, p.get("points") or [], op == "planar")
    if op == "thicken":
        return thicken(knit(shapes) if len(shapes) > 1 else shapes[0],
                       mesh.rv(p.get("thickness", 2.0), env, 2.0))
    if op == "fillet":
        return fillet(knit(shapes) if len(shapes) > 1 else shapes[0],
                      mesh.rv(p.get("radius", 5.0), env, 5.0),
                      p.get("points") or [])
    if op == "mirror":
        return mirror(shapes, str(p.get("plane", "YZ (Right)")),
                      mesh.rv(p.get("offset", 0.0), env, 0.0))
    raise ValueError(f"unknown surface operation {op}")


def _compute(node, env):
    from . import cadexchange
    return cadexchange._mesh_shape_rel(shape_of(node, env), DEFLECTION,
                                       ANGLE)


def _check(node, env):
    from . import cadexchange
    if not cadexchange.occ_available():
        return cadexchange.missing(".step").replace(
            "STEP", "Surface editing")
    try:
        shape_of(node, env)
    except ValueError as exc:
        return str(exc)
    except Exception as exc:                       # pragma: no cover
        return f"surface: {exc}"
    return None


KIT = bakedkit.make(
    "surface_edit", "Surface edit", "mdi.layers-triple-outline",
    _DEFAULTS,
    [("op", "Operation", "choice", list(OPS), None),
     ("mutual", "Trim: mutual (every surface trims every other)", "bool",
      None, None),
     ("keep", "Trim: keep the picked pieces (else remove them)", "bool",
      None, None),
     ("remove", "Trim: pieces to remove (a point on each)", "rows",
      ["X", "Y", "Z"], None),
     ("points", "Edges / loops picked (a point on each)", "rows",
      ["X", "Y", "Z"], None),
     ("solid", "Knit: make a solid when closed", "bool", None, None),
     ("thickness", "Thicken: wall (mm)", "float", -1e4, 1e4),
     ("radius", "Fillet: radius (mm)", "float", 0.0, 1e4),
     ("plane", "Mirror: plane", "choice", list(PLANES), None),
     ("offset", "Mirror: plane offset (mm)", "float", -1e5, 1e5)],
    _compute, choices={"op": OPS, "plane": PLANES},
    check=_check, inexact_ok=True)
