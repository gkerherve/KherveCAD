"""Exact parts — an imported STEP / IGES part kept as its TRUE surfaces,
and edited as them (Qt-free, OpenCascade).

A part opened from STEP arrives as a mesh (cadexchange_ui), which is
right for viewing, placing and printing but cannot be filleted the way
the supplier's CAD would: the mesh's facets are not the edges. Right-
click it ▸ Make Exact (Edit as B-rep) turns it into a `brep` node that
holds the file and the part's index, rebuilt from the exact shape every
time, and two operations done ON that shape:

* **fillets** — rows [x, y, z, radius]: the edge nearest the point is
  rounded by OpenCascade's own rolling-ball fillet (BRepFilletAPI), so
  a filleted bore is a true torus where it meets the face;
* **chamfers** — rows [x, y, z, size]: the edge nearest the point is
  cut back by that distance.

Edges are remembered by a POINT on them (a picked edge's middle), so a
row keeps finding its edge however the part is placed; a point that no
longer finds one is a red validation message, never a guess. Placement
is the node's own x / y / z / rx / ry / rz / scale, like an imported
mesh. OpenSCAD gets the baked polyhedron; STEP export (cadexchange)
the exact filleted shape.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from . import bakedkit

#: a fillet / chamfer point must be this close (mm) to an edge
REACH = 2.0
DEFLECTION = 0.0015
ANGLE = 12.0

_DEFAULTS = dict(source="", part=0, x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0,
                 rz=0.0, scale=1.0, fillets=[], chamfers=[])


def base_shape(node, env=None):
    """The part's exact shape as the file has it, or raises ValueError."""
    from . import cadexchange, mesh
    src = str(node.params.get("source", "")).strip()
    if not src:
        raise ValueError("exact part: no file")
    shapes = cadexchange.exact_shapes(src)
    if shapes is None:
        raise ValueError(f"exact part: cannot read {src} — is the file "
                         "still there?")
    try:
        return shapes[int(mesh.rv(node.params.get("part", 0), env, 0))]
    except (IndexError, ValueError, TypeError):
        raise ValueError(f"exact part: {src} has no part "
                         f"{node.params.get('part')}")


def _edges(shape):
    """Every edge of *shape* once (an edge shared by two faces is met
    twice by the explorer)."""
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_EDGE
    from . import cadexchange
    out = []
    exp = TopExp_Explorer(shape, TopAbs_EDGE)
    while exp.More():
        e = cadexchange._topods("Edge", exp.Current())
        if not any(e.IsSame(o) for o in out):
            out.append(e)
        exp.Next()
    return out


def edge_distance(edge, point):
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.gp import gp_Pnt
    v = BRepBuilderAPI_MakeVertex(gp_Pnt(*point)).Vertex()
    d = BRepExtrema_DistShapeShape(edge, v)
    return d.Value() if d.IsDone() else float("inf")


def nearest_edge(shape, point, reach=REACH):
    best = None
    for e in _edges(shape):
        d = edge_distance(e, point)
        if best is None or d < best[0]:
            best = (d, e)
    if best is None or best[0] > reach:
        return None
    return best[1]


def _rows(node, key, env):
    from . import mesh
    out = []
    for row in node.params.get(key) or []:
        if isinstance(row, list) and len(row) >= 4:
            out.append([mesh.rv(v, env, 0.0) for v in row[:4]])
    return out


def shape(node, env=None, placed=True):
    """The exact part with its fillets and chamfers, in the node's frame
    (its placement applied unless *placed* is False)."""
    from . import mesh
    env = env or {}
    s = base_shape(node, env)
    fillets = _rows(node, "fillets", env)
    if fillets:
        from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
        op = BRepFilletAPI_MakeFillet(s)
        for x, y, z, r in fillets:
            e = nearest_edge(s, (x, y, z))
            if e is None:
                raise ValueError(f"exact part: no edge near ({x:g}, {y:g}, "
                                 f"{z:g}) to fillet any more")
            op.Add(float(r), e)
        op.Build()
        if not op.IsDone():
            raise ValueError("exact part: the fillets do not fit — try a "
                             "smaller radius")
        s = op.Shape()
    chamfers = _rows(node, "chamfers", env)
    if chamfers:
        from OCP.BRepFilletAPI import BRepFilletAPI_MakeChamfer
        op = BRepFilletAPI_MakeChamfer(s)
        for x, y, z, d in chamfers:
            e = nearest_edge(s, (x, y, z))
            if e is None:
                raise ValueError(f"exact part: no edge near ({x:g}, {y:g}, "
                                 f"{z:g}) to chamfer any more")
            op.Add(float(d), e)
        op.Build()
        if not op.IsDone():
            raise ValueError("exact part: the chamfers do not fit — try a "
                             "smaller size")
        s = op.Shape()
    if not placed:
        return s
    from .cadexchange import Compiler
    return Compiler(None)._apply(s, placement(node, env))


def placement(node, env=None):
    from . import mesh
    p = mesh.rp(node, env or {})
    sc = p.get("scale", 1.0)
    return mesh.mat_mul(mesh.mat_translate(p["x"], p["y"], p["z"]),
                        mesh.mat_mul(mesh.mat_rotate(p["rx"], p["ry"],
                                                     p["rz"]),
                                     mesh.mat_scale(sc, sc, sc)))


def _compute(node, env):
    from . import cadexchange
    return cadexchange._mesh_shape_rel(shape(node, env), DEFLECTION, ANGLE)


def _check(node, env):
    from . import cadexchange
    if not cadexchange.occ_available():
        return cadexchange.missing(".step")
    try:
        shape(node, env)
    except ValueError as exc:
        return str(exc)
    except Exception as exc:                        # pragma: no cover
        return f"exact part: {exc}"
    return None


KIT = bakedkit.make(
    "brep", "Exact part (B-rep)", "mdi.cube-scan", _DEFAULTS,
    [("source", "File (STEP / IGES / BREP)", "str", None, None),
     ("part", "Part in the file", "int", 0, 100000),
     ("x", "X", "float", -1e6, 1e6), ("y", "Y", "float", -1e6, 1e6),
     ("z", "Z", "float", -1e6, 1e6),
     ("rx", "Rotate X°", "float", -360.0, 360.0),
     ("ry", "Rotate Y°", "float", -360.0, 360.0),
     ("rz", "Rotate Z°", "float", -360.0, 360.0),
     ("scale", "Scale", "float", 1e-6, 1e6),
     ("fillets", "Fillets (a point on the edge, radius)", "rows",
      ["X", "Y", "Z", "Radius"], None),
     ("chamfers", "Chamfers (a point on the edge, size)", "rows",
      ["X", "Y", "Z", "Size"], None)],
    _compute, leaf=True, text=("source",), check=_check)


# ======================================================== making one

def convertible(node):
    """The `stl_import` node to turn exact, or None."""
    probe = node
    while probe is not None:
        if probe.type == "stl_import" and \
                str(probe.params.get("cad_source", "")).strip():
            return probe
        kids = [c for c in probe.children if c.visible]
        if len(kids) != 1:
            return None
        probe = kids[0]
    return None


def make_exact(model, node):
    """Replace an imported STEP mesh by its exact part — same place,
    same name, one undo step. Returns the brep node."""
    from . import cadexchange
    mesh_node = convertible(node)
    if mesh_node is None:
        raise ValueError("this is not a part imported from a STEP / IGES "
                         "file")
    if not cadexchange.occ_available():
        raise ValueError(cadexchange.missing(".step"))
    p = mesh_node.params
    params = dict(_DEFAULTS, source=str(p.get("cad_source")),
                  part=int(p.get("cad_part", 0)), fillets=[], chamfers=[])
    for k in ("x", "y", "z", "rx", "ry", "rz", "scale"):
        params[k] = p.get(k, _DEFAULTS[k])
    # the mesh was written in the document's unit; the file is in mm
    from . import units
    k = units.to_mm(getattr(model, "unit", "mm")) or 1.0
    if abs(k - 1.0) > 1e-12:
        params["scale"] = float(params["scale"]) / k
    parent = mesh_node.parent
    index = parent.children.index(mesh_node)
    exact = model.add_node("brep", params, parent=parent,
                           name=mesh_node.name)
    model.move_node(exact, parent, index)
    model.remove_node(mesh_node)
    return exact


def to_local(node, world_point, env=None):
    """A world point (a picked edge's middle) in the part's own file
    frame — what the fillet rows hold."""
    from . import mesh, physics
    m = mesh.mat_mul(mesh.ancestor_matrix(node, env),
                     placement(node, env))
    return [round(v, 4) for v in mesh.mat_apply(physics._invert(m),
                                                world_point)]
