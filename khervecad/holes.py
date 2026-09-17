"""Holes for printed and machined parts — the `hole` node (Catch'n'Hole,
MCAD's teardrop and polyholes, the hole wizard of a CAD program): the
solid to SUBTRACT, placed with its top at z = 0 going down, so it drops
into a difference() against a face.

- **plain** — a bolt clearance hole;
- **counterbore** — plus a wider, shallow bore for a socket head;
- **countersink** — plus a cone for a flat head (angle 90° metric, 82°
  imperial);
- **nut_trap** — plus a hexagonal pocket a nut presses into;
- **heat_insert** — a hole for a brass insert, with a lead-in cone;
- **slot** — a hole stretched along X by ``length`` (adjustment);
- **teardrop** — a HORIZONTAL hole along X, its top pointed at 45° so it
  prints without support (the point is up, +Z).

``extra`` extends the tool above z = 0 so the cut never leaves a skin
on a coincident face. Every hole is a union of cylinders, cones and
prisms, compiled to ONE ``kcad_hole(...)`` call; the preview draws the
same pieces.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

SHAPE_3D = "3d"

KINDS = ("plain", "counterbore", "countersink", "nut_trap", "heat_insert",
         "slot", "teardrop")

NODE_TYPES = {
    "hole": dict(
        label="Hole (counterbore, countersink, nut trap…)",
        category=SHAPE_3D, icon="mdi.circle-slice-8",
        params=dict(kind="counterbore", diameter=3.2, depth=10.0,
                    head_diameter=6.0, head_depth=3.2,
                    countersink_angle=90.0, nut_width=5.5, nut_height=2.4,
                    length=6.0, extra=1.0, segments=32),
        schema=[("kind", "Kind", "choice", list(KINDS), None),
                ("diameter", "Hole diameter (mm)", "float", 0.1, 1e5),
                ("depth", "Depth / teardrop length (mm)", "float", 0.1, 1e5),
                ("head_diameter", "Head / insert lead-in diameter (mm)",
                 "float", 0.1, 1e5),
                ("head_depth", "Counterbore depth (mm)", "float", 0.0, 1e5),
                ("countersink_angle", "Countersink angle°", "float", 30.0,
                 150.0),
                ("nut_width", "Nut across flats (mm)", "float", 0.1, 1e5),
                ("nut_height", "Nut pocket depth (mm)", "float", 0.0, 1e5),
                ("length", "Slot length (mm)", "float", 0.0, 1e5),
                ("extra", "Extends above the face (mm)", "float", 0.0, 1e3),
                ("segments", "Segments ($fn)", "int", 3, 256)]),
}
TYPES = frozenset(NODE_TYPES)
LEAVES = frozenset(NODE_TYPES)
TEXT_PARAMS = frozenset({"kind"})

HELPER = """\
module kcad_hole(kind = "counterbore", diameter = 3.2, depth = 10,
                 head_diameter = 6, head_depth = 3.2, countersink_angle = 90,
                 nut_width = 5.5, nut_height = 2.4, length = 6, extra = 1,
                 segments = 32) {
    d = diameter;
    if (kind == "teardrop") {
        rotate([0, 90, 0]) translate([0, 0, -depth / 2]) {
            cylinder(h = depth, d = d, $fn = segments);
            rotate([0, 0, 45]) cube([d / 2, d / 2, depth]);
        }
    } else if (kind == "slot") {
        translate([0, 0, -depth]) hull() {
            cylinder(h = depth + extra, d = d, $fn = segments);
            translate([length, 0, 0])
                cylinder(h = depth + extra, d = d, $fn = segments);
        }
    } else {
        translate([0, 0, -depth]) cylinder(h = depth + extra, d = d,
                                           $fn = segments);
        if (kind == "counterbore")
            translate([0, 0, -head_depth])
                cylinder(h = head_depth + extra, d = head_diameter,
                         $fn = segments);
        if (kind == "countersink") {
            cone = (head_diameter - d) / 2 / tan(countersink_angle / 2);
            translate([0, 0, -cone])
                cylinder(h = cone, d1 = d, d2 = head_diameter,
                         $fn = segments);
            cylinder(h = extra, d = head_diameter, $fn = segments);
        }
        if (kind == "nut_trap")
            translate([0, 0, -nut_height])
                cylinder(h = nut_height + extra,
                         r = nut_width / 2 / cos(30), $fn = 6);
        if (kind == "heat_insert") {
            lead = (head_diameter - d) / 2;
            translate([0, 0, -lead])
                cylinder(h = lead, d1 = d, d2 = head_diameter,
                         $fn = segments);
            cylinder(h = extra, d = head_diameter, $fn = segments);
        }
    }
}"""


def preamble(root) -> list:
    if any(n.type == "hole" for n in root.walk()):
        return HELPER.split("\n")
    return []


def _cyl(z, h, r1, r2, n):
    from . import mesh
    return mesh.cylinder_mesh(dict(x=0.0, y=0.0, z=z, height=h,
                                   radius_bottom=r1, radius_top=r2,
                                   segments=n, center=False))


def pieces(p):
    """The hole's solids, as triangle lists (the helper's union)."""
    from . import geom3d, mesh
    kind, d = p["kind"], p["diameter"]
    n = max(int(p.get("segments", 32)), 3)
    extra, depth = p["extra"], p["depth"]
    if kind == "teardrop":
        body = _cyl(-depth / 2, depth, d / 2, d / 2, n)
        # the pointed roof: a square prism turned 45° about the axis
        s = d / 2
        roof = mesh.cube_mesh(dict(x=0.0, y=0.0, z=-depth / 2, width=s,
                                   depth=s, height=depth, center=False))
        roof = mesh.transform_mesh(mesh.mat_rotate(0, 0, 45), roof)
        turn = mesh.mat_rotate(0, 90, 0)
        return [mesh.transform_mesh(turn, body),
                mesh.transform_mesh(turn, roof)]
    if kind == "slot":
        pts = [v for tri in _cyl(-depth, depth + extra, d / 2, d / 2, n)
               for v in tri]
        pts += [(x + p["length"], y, z) for x, y, z in pts]
        return [geom3d.convex_hull(pts)]
    out = [_cyl(-depth, depth + extra, d / 2, d / 2, n)]
    head = p["head_diameter"]
    if kind == "counterbore":
        out.append(_cyl(-p["head_depth"], p["head_depth"] + extra, head / 2,
                        head / 2, n))
    elif kind == "countersink":
        cone = (head - d) / 2 / math.tan(math.radians(
            p["countersink_angle"] / 2))
        out.append(_cyl(-cone, cone, d / 2, head / 2, n))
        out.append(_cyl(0.0, extra, head / 2, head / 2, n))
    elif kind == "nut_trap":
        r = p["nut_width"] / 2 / math.cos(math.radians(30))
        out.append(_cyl(-p["nut_height"], p["nut_height"] + extra, r, r, 6))
    elif kind == "heat_insert":
        lead = (head - d) / 2
        out.append(_cyl(-lead, lead, d / 2, head / 2, n))
        out.append(_cyl(0.0, extra, head / 2, head / 2, n))
    return out


def _params(node, env):
    from . import mesh
    p = mesh.rp(node, env)
    p["kind"] = str(node.params.get("kind", "plain"))
    return p


def statement(node, fmt, fn) -> str:
    from .model import scad_str
    p = node.params
    d = NODE_TYPES["hole"]["params"]
    args = [f"kind = {scad_str(str(p.get('kind', 'plain')))}"]
    for key in d:
        if key != "kind":
            args.append(f"{key} = {fmt(p.get(key, d[key]))}")
    return f"kcad_hole({', '.join(args)})"


def build(parser, positional, named):
    from .model import CadNode
    from .scadparse import _num
    d = NODE_TYPES["hole"]["params"]
    params = dict(d)
    kind = str(named.get("kind", d["kind"]))
    if kind not in KINDS:
        parser.warn(f"unknown hole kind {kind!r} — kept as plain")
        kind = "plain"
    params["kind"] = kind
    for key, default in d.items():
        if key != "kind" and key in named:
            value = _num(named[key], default)
            if isinstance(default, int) and not isinstance(value, str):
                value = int(math.floor(value + 0.5))
            params[key] = value
    return CadNode("hole", f"Hole ({kind})", params)


BUILDERS = {"kcad_hole": build}


def check(node, env):
    from . import expr
    try:
        p = _params(node, env)
    except expr.ExprError as exc:
        return f"hole: {exc}"
    if p["kind"] not in KINDS:
        return f"hole kind must be one of {', '.join(KINDS)}"
    if p["diameter"] <= 0 or p["depth"] <= 0:
        return "hole: diameter and depth must be above 0"
    if p["kind"] in ("counterbore", "countersink", "heat_insert") and \
            p["head_diameter"] <= p["diameter"]:
        return "hole: the head diameter must be wider than the hole"
    if p["kind"] == "nut_trap" and \
            p["nut_width"] / math.cos(math.radians(30)) <= p["diameter"]:
        return "hole: the nut is narrower than the hole"
    return None


def tess(node, env, color, sel, selected):
    from . import mesh
    tris = [t for piece in pieces(_params(node, env)) for t in piece]
    return mesh._emit(tris, color, selected)
