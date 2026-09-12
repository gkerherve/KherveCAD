"""Sheet metal: a plate with bent flanges, and its flat pattern.

A ``sheet_metal`` node is a base plate (``width`` along X, ``depth``
along Y, ``thickness`` up) with a flange on any of its four edges —
north (+Y), east (+X), south (-Y), west (-X) — each a *length* (the
flat leg beyond the bend, measured on the outside) bent *up* by an
*angle*, round an inside bend ``radius``. Like the organic nodes it
compiles to ONE call of a ``kcad_sheet`` helper module (real OpenSCAD:
the bend profile is a polygon of arcs, extruded along the edge), so
every number may be an expression, and the importer rebuilds the node
from the call.

`flat_pattern()` unfolds it: the base, then each flange laid out flat
beyond its edge, the bend zone as wide as the **bend allowance**
``(radius + K * thickness) * angle`` (K-factor, where the neutral
fibre lies through the thickness — 0.44 for most steel and aluminium
bends), with the bend lines marked. `flat_dxf()` writes it for a laser
or a press brake.

Kept simple on purpose: one bend per edge, no reliefs, no hems; a box,
a bracket, a tray, a channel or a U come out of it.

No package imports at module level (see organic.py).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

SHAPE_3D = "3d"

#: the four edges, in the order the helper's `flanges` list takes them:
#: (key, outward direction (dx, dy), the axis the edge runs along)
EDGES = (("n", (0, 1), "x"), ("e", (1, 0), "y"), ("s", (0, -1), "x"),
         ("w", (-1, 0), "y"))

NODE_TYPES = {
    "sheet_metal": dict(
        label="Sheet metal part", category=SHAPE_3D,
        icon="mdi.file-document-outline",
        params=dict(width=80.0, depth=60.0, thickness=1.5, radius=1.5,
                    kfactor=0.44,
                    n_length=20.0, n_angle=90.0, e_length=0.0,
                    e_angle=90.0, s_length=20.0, s_angle=90.0,
                    w_length=0.0, w_angle=90.0),
        schema=[("width", "Base width X (mm)", "float", 0.1, 1e6),
                ("depth", "Base depth Y (mm)", "float", 0.1, 1e6),
                ("thickness", "Thickness (mm)", "float", 0.05, 100.0),
                ("radius", "Inside bend radius (mm)", "float", 0.0, 1e4),
                ("kfactor", "K-factor (neutral fibre)", "float", 0.0, 1.0),
                ("n_length", "North flange (+Y) length", "float", 0.0,
                 1e6),
                ("n_angle", "North bend angle°", "float", -180.0, 180.0),
                ("e_length", "East flange (+X) length", "float", 0.0,
                 1e6),
                ("e_angle", "East bend angle°", "float", -180.0, 180.0),
                ("s_length", "South flange (-Y) length", "float", 0.0,
                 1e6),
                ("s_angle", "South bend angle°", "float", -180.0, 180.0),
                ("w_length", "West flange (-X) length", "float", 0.0,
                 1e6),
                ("w_angle", "West bend angle°", "float", -180.0, 180.0)]),
}
TYPES = frozenset(NODE_TYPES)
LEAVES = frozenset(NODE_TYPES)

#: the helper module — the same profile as bend_profile() below, run by
#: OpenSCAD at render time (keep the two in step)
HELPER = """\
module kcad_sheet(size = [80, 60], t = 1.5, r = 1.5, k = 0.44,
                  flanges = [[0, 90], [0, 90], [0, 90], [0, 90]]) {
    function arc(rad, a, n) = [for (i = [0 : n]) let (b = a * i / n)
        [rad * sin(b), t + r - rad * cos(b)]];
    function leg(len, a, rad) = [rad * sin(a) + len * cos(a),
                                 t + r - rad * cos(a) + len * sin(a)];
    // the bend's profile in the (outward, up) plane, extruded along
    // the edge over y in [-along, 0]; a negative angle hangs it below
    // the plate (z -> t - z)
    module bend(len, a, along) {
        n = max(4, floor(($fn > 0 ? $fn : 32) * abs(a) / 360 + 0.5));
        pts = a == 0
            ? [[0, 0], [len, 0], [len, t], [0, t]]
            : concat(arc(r + t, abs(a), n), [leg(len, abs(a), r + t)],
                     [leg(len, abs(a), r)],
                     [for (i = [n : -1 : 0]) arc(r, abs(a), n)[i]]);
        if (a < 0) translate([0, 0, t]) mirror([0, 0, 1])
            rotate([90, 0, 0]) linear_extrude(height = along) polygon(pts);
        else rotate([90, 0, 0]) linear_extrude(height = along) polygon(pts);
    }
    cube([size[0], size[1], t]);
    if (flanges[0][0] > 0) translate([0, size[1], 0]) rotate([0, 0, 90])
        bend(flanges[0][0], flanges[0][1], size[0]);          // north
    if (flanges[1][0] > 0) translate([size[0], size[1], 0])
        bend(flanges[1][0], flanges[1][1], size[1]);          // east
    if (flanges[2][0] > 0) translate([size[0], 0, 0]) rotate([0, 0, -90])
        bend(flanges[2][0], flanges[2][1], size[0]);          // south
    if (flanges[3][0] > 0) rotate([0, 0, 180])
        bend(flanges[3][0], flanges[3][1], size[1]);          // west
}"""


def preamble(root) -> list:
    if any(n.type == "sheet_metal" for n in root.walk()):
        return HELPER.split("\n")
    return []


# ---------------------------------------------------------------- codegen

def statement(node, fmt, fn) -> str:
    p = node.params
    flanges = ", ".join(
        f"[{fmt(p[f'{k}_length'])}, {fmt(p[f'{k}_angle'])}]"
        for k, _d, _a in EDGES)
    return (f"kcad_sheet(size = [{fmt(p['width'])}, {fmt(p['depth'])}], "
            f"t = {fmt(p['thickness'])}, r = {fmt(p['radius'])}, "
            f"k = {fmt(p['kfactor'])}, flanges = [{flanges}])")


def build(parser, positional, named):
    """kcad_sheet(...) -> the node."""
    from .model import CadNode
    from .scadparse import _num
    d = NODE_TYPES["sheet_metal"]["params"]
    size = named.get("size", positional[0] if positional else None)
    params = dict(d)
    if isinstance(size, list) and len(size) >= 2:
        params["width"], params["depth"] = (_num(size[0], d["width"]),
                                            _num(size[1], d["depth"]))
    for key, name in (("thickness", "t"), ("radius", "r"),
                      ("kfactor", "k")):
        if name in named:
            params[key] = _num(named[name], d[key])
    flanges = named.get("flanges")
    if isinstance(flanges, list):
        for (key, _dir, _axis), entry in zip(EDGES, flanges):
            if isinstance(entry, list) and len(entry) >= 2:
                params[f"{key}_length"] = _num(entry[0], 0.0)
                params[f"{key}_angle"] = _num(entry[1], 90.0)
    return CadNode("sheet_metal", "Sheet metal part", params)


BUILDERS = {"kcad_sheet": build}


# ------------------------------------------------------------- validation

def check(node, env):
    from . import expr
    p = node.params

    def val(key, default=0.0):
        value = p.get(key, default)
        if isinstance(value, str):
            value = expr.evaluate(value, env)
        return float(value)
    try:
        t, r = val("thickness", 1.0), val("radius", 0.0)
        if t <= 0:
            return "thickness must be above 0"
        if r < 0:
            return "the bend radius cannot be negative"
        if val("width", 1.0) <= 0 or val("depth", 1.0) <= 0:
            return "the base plate needs a width and a depth"
        for key, _d, _a in EDGES:
            if val(f"{key}_length") < 0:
                return f"{key}_length cannot be negative"
            if not -180.0 <= val(f"{key}_angle", 90.0) <= 180.0:
                return f"{key}_angle must be within -180° and 180°"
        k = val("kfactor", 0.44)
        if not 0.0 <= k <= 1.0:
            return "the K-factor lies between 0 and 1"
    except expr.ExprError as exc:
        return f"{exc}"
    return None


# ----------------------------------------------------------- tessellation

def bend_profile(length, angle, t, r, n):
    """The bend's cross-section in the (outward u, up z) plane, the
    base plate ending at u = 0 with its top at z = t: outer arc, leg,
    inner arc — the helper's polygon (angle in degrees, > 0)."""
    a = math.radians(abs(angle))
    if a < 1e-9:
        return [(0.0, 0.0), (length, 0.0), (length, t), (0.0, t)]

    def arc(rad, reverse=False):
        pts = [(rad * math.sin(a * i / n), t + r - rad * math.cos(a * i / n))
               for i in range(n + 1)]
        return pts[::-1] if reverse else pts

    def leg(rad):
        return (rad * math.sin(a) + length * math.cos(a),
                t + r - rad * math.cos(a) + length * math.sin(a))
    return arc(r + t) + [leg(r + t), leg(r)] + arc(r, reverse=True)


def _prism(profile, along, t):
    """Triangles of the profile extruded from y = -along to y = 0, in
    the frame (u -> x, z -> z), with the plate's top at z = t."""
    from . import mesh
    outline = [(u, z) for u, z in profile]
    tris2d = mesh.triangulate(outline)
    out = []
    for tri in tris2d:
        (u0, z0), (u1, z1), (u2, z2) = tri
        out.append(((u0, 0.0, z0), (u1, 0.0, z1), (u2, 0.0, z2)))
        out.append(((u0, -along, z0), (u2, -along, z2), (u1, -along, z1)))
    n = len(outline)
    for i in range(n):
        (u0, z0), (u1, z1) = outline[i], outline[(i + 1) % n]
        out.append(((u0, 0.0, z0), (u0, -along, z0), (u1, -along, z1)))
        out.append(((u0, 0.0, z0), (u1, -along, z1), (u1, 0.0, z1)))
    return out


def tess(node, env, color, sel, selected):
    """The preview: the plate and each flange as its own solid, the
    bend profile extruded along the edge and placed like the helper."""
    from . import mesh
    p = mesh.rp(node, env)
    w, d, t, r = p["width"], p["depth"], p["thickness"], p["radius"]
    seg = mesh._cap(mesh._FN_OVERRIDE or 32)
    tris = list(mesh.cube_mesh(dict(x=0.0, y=0.0, z=0.0, width=w, depth=d,
                                    height=t, center=False)))
    for key, (dx, dy), axis in EDGES:
        length, angle = p[f"{key}_length"], p[f"{key}_angle"]
        if length <= 0:
            continue
        n = max(4, int(math.floor(seg * abs(angle) / 360.0 + 0.5)))
        profile = bend_profile(length, angle, t, r, n)
        along = w if axis == "x" else d
        prism = _prism(profile, along, t)
        if angle < 0:                 # bent down: mirror through the plate
            # z -> t - z: the plate maps onto itself, the bend hangs below
            prism = mesh.transform_mesh(
                mesh.mat_mul(mesh.mat_translate(0, 0, t),
                             mesh.mat_mirror(0, 0, 1)), prism)
        # the prism runs u along +X from the edge at x = 0 and spans
        # y in [-along, 0]; turn it to face outward from its edge
        if key == "e":
            m = mesh.mat_translate(w, d, 0)
        elif key == "w":
            m = mesh.mat_mul(mesh.mat_translate(0, 0, 0),
                             mesh.mat_rotate(0, 0, 180))
        elif key == "n":
            m = mesh.mat_mul(mesh.mat_translate(0, d, 0),
                             mesh.mat_rotate(0, 0, 90))
        else:                          # south
            m = mesh.mat_mul(mesh.mat_translate(w, 0, 0),
                             mesh.mat_rotate(0, 0, -90))
        tris.extend(mesh.transform_mesh(m, prism))
    tris = [tuple(tuple(float(c) for c in v) for v in tri) for tri in tris]
    return mesh._emit(tris, color, selected)


# ------------------------------------------------------------ unfolding

def bend_allowance(t, r, k, angle):
    """Length of the neutral fibre through the bend (mm)."""
    return (r + k * t) * math.radians(abs(angle))


def flat_pattern(params, env=None):
    """The unfolded blank: {"outline": [(x, y)], "bend_lines":
    [((x, y), (x, y))], "width", "height", "flanges": [...]} in mm,
    the base plate at the origin, each flange laid out beyond its
    edge over BA + length (the leg's inside length is what folds
    flat: length - (r + t) * tan(a/2) for a right angle)."""
    from . import mesh
    d0 = NODE_TYPES["sheet_metal"]["params"]
    p = {key: mesh.rv(params.get(key, default), env, default)
         for key, default in d0.items()}
    w, d = float(p["width"]), float(p["depth"])
    t, r, k = (float(p["thickness"]), float(p["radius"]),
               float(p["kfactor"]))
    outline = [(0.0, 0.0), (w, 0.0), (w, d), (0.0, d)]
    flanges, bend_lines = [], []
    for key, (dx, dy), axis in EDGES:
        length = float(p.get(f"{key}_length", 0.0))
        angle = float(p.get(f"{key}_angle", 90.0))
        if length <= 0:
            continue
        ba = bend_allowance(t, r, k, angle)
        # the flat leg: the outer length less the outer setback
        setback = (r + t) * math.tan(math.radians(abs(angle)) / 2.0)
        leg = max(length - setback, 0.0)
        reach = ba + leg
        flanges.append(dict(edge=key, allowance=ba, leg=leg, reach=reach,
                            angle=angle))
        if key == "n":
            box = [(0.0, d), (w, d), (w, d + reach), (0.0, d + reach)]
            lines = [((0.0, d), (w, d)), ((0.0, d + ba), (w, d + ba))]
        elif key == "s":
            box = [(0.0, -reach), (w, -reach), (w, 0.0), (0.0, 0.0)]
            lines = [((0.0, 0.0), (w, 0.0)), ((0.0, -ba), (w, -ba))]
        elif key == "e":
            box = [(w, 0.0), (w + reach, 0.0), (w + reach, d), (w, d)]
            lines = [((w, 0.0), (w, d)), ((w + ba, 0.0), (w + ba, d))]
        else:
            box = [(-reach, 0.0), (0.0, 0.0), (0.0, d), (-reach, d)]
            lines = [((0.0, 0.0), (0.0, d)), ((-ba, 0.0), (-ba, d))]
        flanges[-1]["box"] = box
        bend_lines.extend(lines)
    # one outline: the base with each flange's rectangle merged on
    pts = _union_boxes(outline, [f["box"] for f in flanges])
    xs = [q[0] for q in pts]
    ys = [q[1] for q in pts]
    return dict(outline=pts, bend_lines=bend_lines, flanges=flanges,
                width=max(xs) - min(xs), height=max(ys) - min(ys),
                thickness=t)


def _union_boxes(base, boxes):
    """The cross-shaped outline of the base with rectangles on its
    edges (they never overlap one another: one per edge)."""
    x0, y0 = base[0]
    x1, y1 = base[2]
    n = e = s = w = 0.0
    for b in boxes:
        bx = [q[0] for q in b]
        by = [q[1] for q in b]
        if min(by) >= y1 - 1e-9:
            n = max(by) - y1
        elif max(by) <= y0 + 1e-9:
            s = y0 - min(by)
        elif min(bx) >= x1 - 1e-9:
            e = max(bx) - x1
        else:
            w = x0 - min(bx)
    pts = [(x0, y0)]
    if s:
        pts += [(x0, y0 - s), (x1, y0 - s)]
    pts.append((x1, y0))
    if e:
        pts += [(x1 + e, y0), (x1 + e, y1)]
    pts.append((x1, y1))
    if n:
        pts += [(x1, y1 + n), (x0, y1 + n)]
    pts.append((x0, y1))
    if w:
        pts += [(x0 - w, y1), (x0 - w, y0)]
    return pts


def flat_dxf(pattern, path):
    """The flat pattern as DXF R12: the outline on layer CUT, the bend
    lines on layer BEND, in millimetres."""
    out = ["0", "SECTION", "2", "ENTITIES"]

    def line(a, b, layer):
        out.extend(["0", "LINE", "8", layer, "10", f"{a[0]:.4f}", "20",
                    f"{a[1]:.4f}", "30", "0", "11", f"{b[0]:.4f}", "21",
                    f"{b[1]:.4f}", "31", "0"])
    pts = pattern["outline"]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        line(a, b, "CUT")
    for a, b in pattern["bend_lines"]:
        line(a, b, "BEND")
    out.extend(["0", "ENDSEC", "0", "EOF"])
    with open(path, "w", encoding="ascii") as fh:
        fh.write("\n".join(out) + "\n")
    return str(path)


def unfold_node(node, env=None):
    """A 2D polygon node of the flat pattern (the blank as sketch
    geometry — extrude it by the thickness for a flat solid)."""
    from .model import CadNode
    pat = flat_pattern(node.params, env)
    poly = CadNode("polygon", f"{node.name} flat pattern", dict(
        x=0.0, y=0.0, points=[[round(x, 4), round(y, 4)]
                              for x, y in pat["outline"]]))
    return poly, pat
