"""Organic modelling nodes: capsule, ellipsoid, rounded box, live
symmetry and posable joints.

Characters are soft, symmetric and posable — nothing a cube and a
difference() hand you. Before these, a limb was a hand-written chain
of ``hull() { scaled sphere; scaled sphere }`` blocks, a mirrored half
had to be kept in step by hand, and bending an elbow meant recomputing
every coordinate below it.

- **capsule** — a rod with round ends between two points (limbs,
  fingers, handles);
- **ellipsoid** — a sphere with three radii (heads, bodies, eyes);
- **rounded box** — a box with a fillet radius on every edge;
- **symmetry** — its children plus their mirror image across a plane,
  so one edited half updates both;
- **joint** — rotates its children about a pivot. Joints nest (a hand
  in a forearm in an upper arm), so the tree *is* the armature, and a
  pose is a handful of angles (`set_pose`).

Each compiles to one call of a small ``kcad_*`` helper module, and a
program that uses one starts with that module's definition — so an
exported .scad is still plain, standalone OpenSCAD, and the importer,
which knows the ``kcad_*`` names, rebuilds the very same node: a
lossless round trip with no pattern guessing.

No package imports at module level: model.py imports this from its
bottom to register the types, so whatever needs the tree, the
tessellator or the parser is imported when called. It also aggregates
bake.py (polyhedron and the baked-mesh nodes), which keeps the same
rule, so model, mesh and the parser each hook in exactly once.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from . import bake
from . import pattern

#: model.SHAPE_3D / model.OPERATION (not imported: see the docstring)
SHAPE_3D = "3d"
OPERATION = "op"


def _xyz(prefix="", label=""):
    return [(f"{prefix}{a}", f"{label}{a.upper()}", "float", -1e6, 1e6)
            for a in "xyz"]


NODE_TYPES = {
    "capsule": dict(
        label="Capsule", category=SHAPE_3D, icon="mdi.pill",
        params=dict(x1=0.0, y1=0.0, z1=0.0, x2=0.0, y2=0.0, z2=30.0,
                    radius=6.0, segments=32),
        schema=[("x1", "Start X", "float", -1e6, 1e6),
                ("y1", "Start Y", "float", -1e6, 1e6),
                ("z1", "Start Z", "float", -1e6, 1e6),
                ("x2", "End X", "float", -1e6, 1e6),
                ("y2", "End Y", "float", -1e6, 1e6),
                ("z2", "End Z", "float", -1e6, 1e6),
                ("radius", "Radius", "float", 0.01, 1e6),
                ("segments", "Segments ($fn)", "int", 4, 512)]),
    "ellipsoid": dict(
        label="Ellipsoid", category=SHAPE_3D, icon="mdi.egg-outline",
        params=dict(x=0.0, y=0.0, z=0.0, rx=15.0, ry=10.0, rz=8.0,
                    segments=48),
        schema=_xyz(label="Centre ")
        + [("rx", "Radius X", "float", 0.01, 1e6),
           ("ry", "Radius Y", "float", 0.01, 1e6),
           ("rz", "Radius Z", "float", 0.01, 1e6),
           ("segments", "Segments ($fn)", "int", 4, 512)]),
    "rounded_box": dict(
        label="Rounded box", category=SHAPE_3D,
        icon="mdi.dice-6-outline",
        params=dict(x=0.0, y=0.0, z=0.0, width=30.0, depth=20.0,
                    height=10.0, radius=3.0, center=True, segments=32),
        schema=_xyz()
        + [("width", "Width (X)", "float", 0.01, 1e6),
           ("depth", "Depth (Y)", "float", 0.01, 1e6),
           ("height", "Height (Z)", "float", 0.01, 1e6),
           ("radius", "Edge radius", "float", 0.0, 1e6),
           ("center", "Center", "bool", None, None),
           ("segments", "Segments ($fn)", "int", 4, 512)]),
    "symmetry": dict(
        label="Symmetry (mirror copy)", category=OPERATION,
        icon="mdi.mirror",
        params=dict(x=1.0, y=0.0, z=0.0, cx=0.0, cy=0.0, cz=0.0),
        schema=[("x", "Plane normal X", "float", -1.0, 1.0),
                ("y", "Plane normal Y", "float", -1.0, 1.0),
                ("z", "Plane normal Z", "float", -1.0, 1.0)]
        + _xyz("c", "Plane point ")),
    "joint": dict(
        label="Joint (pivot)", category=OPERATION, icon="mdi.axis-arrow",
        params=dict(px=0.0, py=0.0, pz=0.0, rx=0.0, ry=0.0, rz=0.0,
                    min_angle=-180.0, max_angle=180.0),
        schema=_xyz("p", "Pivot ")
        + [("rx", "Bend X°", "float", -360.0, 360.0),
           ("ry", "Bend Y°", "float", -360.0, 360.0),
           ("rz", "Bend Z°", "float", -360.0, 360.0),
           ("min_angle", "Min angle°", "float", -360.0, 360.0),
           ("max_angle", "Max angle°", "float", -360.0, 360.0)]),
}

#: this module's own types; bake.py's join the registry below
_OWN = frozenset(NODE_TYPES)
NODE_TYPES.update(bake.NODE_TYPES)
NODE_TYPES.update(pattern.NODE_TYPES)
TYPES = frozenset(NODE_TYPES)
LEAVES = frozenset({"capsule", "ellipsoid", "rounded_box"}) | bake.LEAVES
WRAPPERS = frozenset({"symmetry", "joint"}) | bake.WRAPPERS
WRAPPERS = WRAPPERS | pattern.WRAPPERS

#: helper module per type, emitted in this order above the program
_ORDER = ("capsule", "ellipsoid", "rounded_box", "symmetry", "joint")
HELPERS = {
    "capsule": """\
module kcad_capsule(a = [0, 0, 0], b = [0, 0, 1], r = 1) {
    hull() {
        translate(a) sphere(r = r);
        translate(b) sphere(r = r);
    }
}""",
    "ellipsoid": """\
module kcad_ellipsoid(c = [0, 0, 0], r = [1, 1, 1]) {
    translate(c) scale(r) sphere(r = 1);
}""",
    "rounded_box": """\
module kcad_rounded_box(p = [0, 0, 0], size = [1, 1, 1], r = 0,
                        center = false) {
    rr = max(min(r, size[0] / 2, size[1] / 2, size[2] / 2), 0);
    translate(center ? p - size / 2 : p)
        if (rr <= 0) cube(size);
        else hull() for (i = [0, 1], j = [0, 1], k = [0, 1])
            translate([rr + i * (size[0] - 2 * rr),
                       rr + j * (size[1] - 2 * rr),
                       rr + k * (size[2] - 2 * rr)])
                sphere(r = rr);
}""",
    "symmetry": """\
module kcad_symmetry(n = [1, 0, 0], c = [0, 0, 0]) {
    children();
    translate(c) mirror(n) translate(-c) children();
}""",
    "joint": """\
module kcad_joint(pivot = [0, 0, 0], a = [0, 0, 0], limits = [-180, 180]) {
    translate(pivot) rotate(a) translate(-pivot) children();
}""",
    # OpenSCAD has no materials: this renders its children unchanged
    # and exists so a colour's material survives export and import
    "material": """\
module kcad_material(name = "") {
    children();
}""",
}


def register(node_types: dict, container_types: set):
    """Add the organic types to model's registry (called once, from the
    bottom of model.py). *container_types* is updated in place because
    other modules hold a reference to that very set."""
    node_types.update(NODE_TYPES)
    container_types.update(WRAPPERS)


def preamble(root) -> list:
    """Source lines defining the helper modules *root*'s tree uses."""
    used = {n.type for n in root.walk() if n.type in _OWN}
    lines = []
    for t in _ORDER:
        if t in used:
            lines.extend(HELPERS[t].split("\n"))
    if any(n.type == "color" and
           str(n.params.get("material") or "Default") != "Default"
           for n in root.walk()):
        lines.extend(HELPERS["material"].split("\n"))
    lines.extend(bake.preamble(root))
    lines.extend(pattern.preamble(root))
    if not lines:
        return []
    return (["// KherveCAD helper modules (organic and mesh nodes)"]
            + lines + [""])


# ---------------------------------------------------------------- codegen

def statement(node, fmt, fn) -> str:
    """The node's one OpenSCAD statement (head only, for wrappers).
    *fmt* and *fn* are model's formatter and effective-$fn helpers."""
    if node.type in bake.TYPES:
        return bake.statement(node, fmt, fn)
    if node.type in pattern.TYPES:
        return pattern.statement(node, fmt, fn)
    p = node.params
    t = node.type

    def vec(*keys):
        return "[" + ", ".join(fmt(p[k]) for k in keys) + "]"
    if t == "capsule":
        return (f"kcad_capsule(a = {vec('x1', 'y1', 'z1')}, "
                f"b = {vec('x2', 'y2', 'z2')}, r = {fmt(p['radius'])}, "
                f"$fn = {fmt(fn(p))})")
    if t == "ellipsoid":
        return (f"kcad_ellipsoid(c = {vec('x', 'y', 'z')}, "
                f"r = {vec('rx', 'ry', 'rz')}, $fn = {fmt(fn(p))})")
    if t == "rounded_box":
        return (f"kcad_rounded_box(p = {vec('x', 'y', 'z')}, "
                f"size = {vec('width', 'depth', 'height')}, "
                f"r = {fmt(p['radius'])}, "
                f"center = {fmt(bool(p.get('center', True)))}, "
                f"$fn = {fmt(fn(p))})")
    if t == "symmetry":
        return (f"kcad_symmetry(n = {vec('x', 'y', 'z')}, "
                f"c = {vec('cx', 'cy', 'cz')})")
    if t == "joint":
        return (f"kcad_joint(pivot = {vec('px', 'py', 'pz')}, "
                f"a = {vec('rx', 'ry', 'rz')}, "
                f"limits = [{fmt(p['min_angle'])}, "
                f"{fmt(p['max_angle'])}])")
    raise ValueError(f"not an organic type: {t}")   # pragma: no cover


# ------------------------------------------------------------ import

def _vec3(value, default):
    from .scadparse import _num
    if not isinstance(value, list):
        if value is None:
            return list(default)
        value = [value] * 3                  # a scalar means all three
    value = list(value) + list(default[len(value):])
    return [_num(v, d) for v, d in zip(value[:3], default)]


def _segments(named, default):
    from .scadparse import _num
    try:
        return max(int(_num(named.get("$fn", default), default)), 3)
    except (TypeError, ValueError):
        return default


def _b_capsule(parser, positional, named):
    from .model import CadNode
    from .scadparse import _num
    a = _vec3(named.get("a"), (0.0, 0.0, 0.0))
    b = _vec3(named.get("b"), (0.0, 0.0, 30.0))
    return CadNode("capsule", "Capsule", dict(
        x1=a[0], y1=a[1], z1=a[2], x2=b[0], y2=b[1], z2=b[2],
        radius=_num(named.get("r", 6.0), 6.0),
        segments=_segments(named, 32)))


def _b_ellipsoid(parser, positional, named):
    from .model import CadNode
    c = _vec3(named.get("c"), (0.0, 0.0, 0.0))
    r = _vec3(named.get("r"), (15.0, 10.0, 8.0))
    return CadNode("ellipsoid", "Ellipsoid", dict(
        x=c[0], y=c[1], z=c[2], rx=r[0], ry=r[1], rz=r[2],
        segments=_segments(named, 48)))


def _b_rounded_box(parser, positional, named):
    from .model import CadNode
    from .scadparse import _num
    at = _vec3(named.get("p"), (0.0, 0.0, 0.0))
    size = _vec3(named.get("size"), (30.0, 20.0, 10.0))
    return CadNode("rounded_box", "Rounded box", dict(
        x=at[0], y=at[1], z=at[2],
        width=size[0], depth=size[1], height=size[2],
        radius=_num(named.get("r", 3.0), 3.0),
        center=bool(named.get("center", False)),
        segments=_segments(named, 32)))


def _b_symmetry(parser, positional, named):
    from .model import CadNode
    n = _vec3(named.get("n"), (1.0, 0.0, 0.0))
    c = _vec3(named.get("c"), (0.0, 0.0, 0.0))
    return CadNode("symmetry", "Symmetry", dict(
        x=n[0], y=n[1], z=n[2], cx=c[0], cy=c[1], cz=c[2]))


def _b_joint(parser, positional, named):
    from .model import CadNode
    from .scadparse import _num
    pivot = _vec3(named.get("pivot"), (0.0, 0.0, 0.0))
    a = _vec3(named.get("a"), (0.0, 0.0, 0.0))
    limits = named.get("limits")
    lo, hi = (limits + [180.0])[:2] if isinstance(limits, list) \
        else (-180.0, 180.0)
    return CadNode("joint", "Joint", dict(
        px=pivot[0], py=pivot[1], pz=pivot[2], rx=a[0], ry=a[1], rz=a[2],
        min_angle=_num(lo, -180.0), max_angle=_num(hi, 180.0)))


#: parser builders, merged into scadparse._BUILDERS
BUILDERS = {
    "kcad_capsule": _b_capsule, "kcad_ellipsoid": _b_ellipsoid,
    "kcad_rounded_box": _b_rounded_box, "kcad_symmetry": _b_symmetry,
    "kcad_joint": _b_joint,
}
BUILDERS.update(bake.BUILDERS)
BUILDERS.update(pattern.BUILDERS)


def _b_material(parser, positional, named):
    """kcad_material("Metal") color(...) { ... } parses as a colour
    wrapper around the colour node; fold_material merges the two."""
    from .model import MATERIALS, CadNode
    name = str(named.get("name", positional[0] if positional
                         else "Default"))
    if name not in MATERIALS:
        parser.warn(f"unknown material {name!r} — kept as Default")
        name = "Default"
    node = CadNode("color", "Color", dict(color="#c8c8c8", alpha=1.0,
                                          material=name))
    node._kcad_material = True        # this parse only; not persisted
    return node


BUILDERS["kcad_material"] = _b_material


def fold_material(node):
    """Fold a parsed kcad_material wrapper into the colour node it
    holds (scadparse._fold_container calls this first). Only the
    wrapper the builder made is folded, so genuinely nested colours
    stay two nodes."""
    if not getattr(node, "_kcad_material", False):
        return None
    if len(node.children) == 1 and node.children[0].type == "color":
        child = node.children[0]
        child.params["material"] = node.params.get("material", "Default")
        node.remove(child)
        child.visible = node.visible and child.visible
        return child
    return None


# -------------------------------------------------------- validation

def check(node, env):
    """An error message for a broken organic node, else None."""
    from . import expr
    if node.type in bake.TYPES:
        return bake.check(node, env)
    if node.type in pattern.TYPES:
        return pattern.check(node, env)
    p = node.params

    def val(key, default=0.0):
        try:
            return float(expr.resolve(p.get(key, default), env, default))
        except Exception:
            return default
    if node.type == "symmetry":
        if all(abs(val(k)) < 1e-12 for k in ("x", "y", "z")):
            return "the mirror plane's normal is zero — set x, y or z"
    elif node.type == "joint":
        lo, hi = val("min_angle", -180.0), val("max_angle", 180.0)
        if lo > hi:
            return f"min angle {lo:g}° is above max angle {hi:g}°"
        for key in ("rx", "ry", "rz"):
            angle = val(key)
            if not lo - 1e-9 <= angle <= hi + 1e-9:
                return (f"{key} = {angle:g}° is past the joint's limits "
                        f"({lo:g}° to {hi:g}°)")
    return None


# ------------------------------------------------------ tessellation

def _ball(radius, segments):
    """The distinct vertices of a built-in sphere at the origin."""
    from . import mesh
    tris = mesh.sphere_mesh(dict(x=0.0, y=0.0, z=0.0, radius=radius,
                                 segments=segments))
    return list({v for tri in tris for v in tri})


def tess(node, env, color, sel, selected):
    """The built-in tessellation of an organic node, as mesh._tess
    returns it: a list of (triangle, colour, selected)."""
    from . import geom3d, mesh
    if node.type in bake.TYPES:
        return bake.tess(node, env, color, sel, selected)
    if node.type in pattern.TYPES:
        return pattern.tess(node, env, color, sel, selected)
    t = node.type
    p = mesh.rp(node, env)
    if t in WRAPPERS:
        kids = mesh._children_mesh(node, env, color, sel, selected)
        if t == "joint":
            px, py, pz = p["px"], p["py"], p["pz"]
            m = mesh.mat_mul(mesh.mat_translate(px, py, pz),
                             mesh.mat_mul(mesh.mat_rotate(p["rx"], p["ry"],
                                                          p["rz"]),
                                          mesh.mat_translate(-px, -py,
                                                             -pz)))
            return mesh._transform_colored(m, kids)
        if all(abs(p[k]) < 1e-12 for k in ("x", "y", "z")):
            return kids
        cx, cy, cz = p["cx"], p["cy"], p["cz"]
        m = mesh.mat_mul(mesh.mat_translate(cx, cy, cz),
                         mesh.mat_mul(mesh.mat_mirror(p["x"], p["y"],
                                                      p["z"]),
                                      mesh.mat_translate(-cx, -cy, -cz)))
        # mirroring turns faces inside out; _transform_colored
        # reverses their winding, so the copy stays outward
        return kids + mesh._transform_colored(m, kids)
    n = max(mesh._cap(p["segments"]), 4)
    if t == "ellipsoid":
        unit = mesh.sphere_mesh(dict(x=0.0, y=0.0, z=0.0, radius=1.0,
                                     segments=n))
        cx, cy, cz = p["x"], p["y"], p["z"]
        rx, ry, rz = abs(p["rx"]), abs(p["ry"]), abs(p["rz"])
        tris = [tuple((cx + rx * v[0], cy + ry * v[1], cz + rz * v[2])
                      for v in tri) for tri in unit]
        return mesh._emit(tris, color, selected)
    if t == "capsule":
        r = p["radius"]
        if r <= 0:
            return []
        ball = _ball(r, n)
        pts = [(p["x1"] + x, p["y1"] + y, p["z1"] + z) for x, y, z in ball]
        pts += [(p["x2"] + x, p["y2"] + y, p["z2"] + z) for x, y, z in ball]
        return mesh._emit(geom3d.convex_hull(pts), color, selected)
    if t == "rounded_box":
        w, d, h = abs(p["width"]), abs(p["depth"]), abs(p["height"])
        x0, y0, z0 = p["x"], p["y"], p["z"]
        if p.get("center", True):
            x0, y0, z0 = x0 - w / 2, y0 - d / 2, z0 - h / 2
        r = max(min(p["radius"], w / 2, d / 2, h / 2), 0.0)
        if r <= 1e-9:
            return mesh._emit(mesh.cube_mesh(dict(
                x=x0, y=y0, z=z0, width=w, depth=d, height=h,
                center=False)), color, selected)
        ball = _ball(r, n)
        pts = []
        for cx in (x0 + r, x0 + w - r):
            for cy in (y0 + r, y0 + d - r):
                for cz in (z0 + r, z0 + h - r):
                    pts.extend((cx + x, cy + y, cz + z) for x, y, z in ball)
        return mesh._emit(geom3d.convex_hull(pts), color, selected)
    return []                                     # pragma: no cover
