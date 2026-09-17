"""Involute gears — the `gear` node (MCAD's involute_gears, BOSL2's
gears.scad): spur, helical, herringbone, internal (ring), rack, bevel
and worm, by module, tooth count and pressure angle.

A tooth is two involute flanks off the base circle (rb = r cos α), cut
to the addendum (r + m) and the dedendum (r − (1 + c) m), its half
angle at the base circle π / 2z + inv α − backlash / 2r; a tip that
would cross itself (few teeth) is trimmed where the flanks meet. The
rest is extrusion: helical twists by thickness · tan β / r, herringbone
is two mirrored halves, bevel scales toward the cone apex (a pair's
pitch angle from ``mate_teeth``), internal is the profile — addendum
and dedendum swapped — cut from a ring, a rack straightens the pitch
circle, and a worm is its section swept round (a trapezoid thread of
axial pitch π m per start).

Compiles to ONE ``kcad_gear(kind = …, m = …, teeth = …)`` call whose
helper module computes the same points in OpenSCAD (keep `outline`
and HELPER in step — the engine parity test compares them), so every
number may be an expression and the importer rebuilds the node.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

SHAPE_3D = "3d"

KINDS = ("spur", "helical", "herringbone", "internal", "rack", "bevel",
         "worm")

NODE_TYPES = {
    "gear": dict(
        label="Gear (involute)", category=SHAPE_3D, icon="mdi.cog-outline",
        params=dict(kind="spur", m=2.0, teeth=20, pressure_angle=20.0,
                    thickness=6.0, helix=20.0, bore=5.0, backlash=0.1,
                    clearance=0.25, rim=5.0, mate_teeth=20, length=40.0,
                    worm_diameter=20.0, detail=6),
        schema=[("kind", "Kind", "choice", list(KINDS), None),
                ("m", "Module (tooth size, mm)", "float", 0.05, 100.0),
                ("teeth", "Teeth (worm: starts)", "int", 1, 1000),
                ("pressure_angle", "Pressure angle°", "float", 10.0, 35.0),
                ("thickness", "Thickness / face width (mm)", "float", 0.01,
                 1e5),
                ("helix", "Helix angle° (helical, herringbone)", "float",
                 -60.0, 60.0),
                ("bore", "Bore diameter (0 = none)", "float", 0.0, 1e5),
                ("backlash", "Backlash (mm at the pitch circle)", "float",
                 0.0, 10.0),
                ("clearance", "Root clearance (× module)", "float", 0.0,
                 1.0),
                ("rim", "Rim: internal ring / rack base (mm)", "float",
                 0.1, 1e5),
                ("mate_teeth", "Mating gear teeth (bevel)", "int", 1, 1000),
                ("length", "Length: rack / worm (mm)", "float", 0.1, 1e5),
                ("worm_diameter", "Worm pitch diameter (mm)", "float", 1.0,
                 1e5),
                ("detail", "Points per flank", "int", 2, 40)]),
}
TYPES = frozenset(NODE_TYPES)
LEAVES = frozenset(NODE_TYPES)
TEXT_PARAMS = frozenset({"kind"})

#: bisection steps trimming a pointed tooth (Python and OpenSCAD alike)
_TIP_STEPS = 24

HELPER = """\
function kcad_gear_phi(t) = t - atan(t) * PI / 180;
function kcad_gear_tip(b, lo, hi, n) = n <= 0 ? lo
    : let (mid = (lo + hi) / 2)
      kcad_gear_phi(mid) <= b ? kcad_gear_tip(b, mid, hi, n - 1)
                              : kcad_gear_tip(b, lo, mid, n - 1);
function kcad_gear_rot(p, a) = [p[0] * cos(a) - p[1] * sin(a),
                                p[0] * sin(a) + p[1] * cos(a)];
// one gear outline: z teeth, pitch radius r, the given addendum and
// dedendum radii (swapped for the hole of an internal gear)
function kcad_gear_outline(m, z, pa, ra, rf, backlash, detail) =
    let (r = m * z / 2, rb = r * cos(pa),
         beta = PI / (2 * z) + tan(pa) - pa * PI / 180 - backlash / (2 * r),
         ts = rf > rb ? sqrt(pow(rf / rb, 2) - 1) : 0,
         te0 = sqrt(pow(ra / rb, 2) - 1),
         te = kcad_gear_phi(te0) > beta ? kcad_gear_tip(beta, ts, te0, 24)
                                         : te0,
         n = max(detail, 2),
         lower = [for (i = [0 : n]) let (t = ts + (te - ts) * i / n)
                  kcad_gear_rot(rb * [cos(t * 180 / PI) + t * sin(t * 180 / PI),
                                      sin(t * 180 / PI) - t * cos(t * 180 / PI)],
                                -beta * 180 / PI)],
         upper = [for (i = [n : -1 : 0]) [lower[i][0], -lower[i][1]]],
         tooth = concat(rf < rb ? [rf * [cos(-beta * 180 / PI),
                                         sin(-beta * 180 / PI)]] : [],
                        lower, upper,
                        rf < rb ? [rf * [cos(beta * 180 / PI),
                                         sin(beta * 180 / PI)]] : []))
    [for (k = [0 : z - 1]) for (p = tooth) kcad_gear_rot(p, 360 * k / z)];
function kcad_gear_circle(r, n) = [for (i = [0 : n - 1])
    r * [cos(360 * i / n), sin(360 * i / n)]];
function kcad_gear_worm(m, starts, pa, rp, c, backlash, n) =
    let (p = PI * m, tn = tan(pa))
    [for (i = [0 : n - 1]) let (th = 360 * i / n,
         u = (th * starts / 360 * p) % p,
         d = abs(u - p / 2),
         y = min(m, max(-(1 + c) * m, (p / 4 - backlash / 4 - d) / tn)))
     (rp + y) * [cos(th), sin(th)]];
module kcad_gear_body(pts, paths, h, twist, sc) {
    linear_extrude(height = h, twist = twist, scale = sc,
                   slices = max(1, ceil(abs(twist) / 5)))
        polygon(points = pts, paths = paths);
}
module kcad_gear(kind = "spur", m = 2, teeth = 20, pressure_angle = 20,
                 thickness = 6, helix = 20, bore = 5, backlash = 0.1,
                 clearance = 0.25, rim = 5, mate_teeth = 20, length = 40,
                 worm_diameter = 20, detail = 6) {
    z = max(round(teeth), 1);
    r = m * z / 2;
    pa = pressure_angle;
    bore_pts = bore > 0 ? kcad_gear_circle(bore / 2, 48) : [];
    if (kind == "rack") {
        p = PI * m;
        tn = tan(pa);
        wt = p / 4 - backlash / 4 - m * tn;
        wr = p / 4 - backlash / 4 + (1 + clearance) * m * tn;
        yr = -(1 + clearance) * m;
        n = max(round(length / p), 1);
        pts = concat([[0, yr - rim], [0, yr]],
                     [for (k = [0 : n - 1]) let (xc = (k + 0.5) * p)
                      for (q = [[xc - wr, yr], [xc - wt, m], [xc + wt, m],
                                [xc + wr, yr]]) q],
                     [[n * p, yr], [n * p, yr - rim]]);
        linear_extrude(height = thickness) polygon(pts);
    } else if (kind == "worm") {
        rp = worm_diameter / 2;
        lead = PI * m * z;
        linear_extrude(height = length, twist = -360 * length / lead,
                       slices = max(1, ceil(360 * length / lead / 5)))
            difference() {
                polygon(kcad_gear_worm(m, z, pa, rp, clearance, backlash,
                                       96));
                if (bore > 0) circle(d = bore, $fn = 48);
            }
    } else if (kind == "internal") {
        hole = kcad_gear_outline(m, z, pa, r + (1 + clearance) * m, r - m,
                                 -backlash, detail);
        outer = kcad_gear_circle(r + (1 + clearance) * m + rim, 4 * z);
        kcad_gear_body(concat(outer, hole),
                       [[for (i = [0 : len(outer) - 1]) i],
                        [for (i = [0 : len(hole) - 1]) len(outer) + i]],
                       thickness, 0, 1);
    } else {
        prof = kcad_gear_outline(m, z, pa, r + m, r - (1 + clearance) * m,
                                 backlash, detail);
        pts = concat(prof, bore_pts);
        paths = bore > 0 ? [[for (i = [0 : len(prof) - 1]) i],
                            [for (i = [0 : len(bore_pts) - 1])
                             len(prof) + i]]
                         : [[for (i = [0 : len(prof) - 1]) i]];
        tw = thickness * tan(helix) / r * 180 / PI;
        if (kind == "helical")
            kcad_gear_body(pts, paths, thickness, tw, 1);
        else if (kind == "herringbone") {
            kcad_gear_body(pts, paths, thickness / 2, tw / 2, 1);
            translate([0, 0, thickness]) mirror([0, 0, 1])
                kcad_gear_body(pts, paths, thickness / 2, tw / 2, 1);
        } else if (kind == "bevel") {
            delta = atan2(z, max(mate_teeth, 1));
            cone = r / sin(delta);
            kcad_gear_body(pts, paths, thickness, 0,
                           max((cone - thickness) / cone, 0.05));
        } else
            kcad_gear_body(pts, paths, thickness, 0, 1);
    }
}"""


def preamble(root) -> list:
    if any(n.type == "gear" for n in root.walk()):
        return HELPER.split("\n")
    return []


# --------------------------------------------------------------- geometry

def _phi(t):
    return t - math.atan(t)


def outline(m, z, pa, ra, rf, backlash, detail):
    """The gear outline (the helper's kcad_gear_outline): *z* teeth of
    pitch radius m z / 2 between radii *ra* and *rf*."""
    z = max(int(math.floor(z + 0.5)), 1)
    r = m * z / 2.0
    pa_r = math.radians(pa)
    rb = r * math.cos(pa_r)
    beta = math.pi / (2 * z) + math.tan(pa_r) - pa_r - backlash / (2 * r)
    ts = math.sqrt((rf / rb) ** 2 - 1) if rf > rb else 0.0
    te = math.sqrt(max((ra / rb) ** 2 - 1, 0.0))
    if _phi(te) > beta:
        lo, hi = ts, te
        for _ in range(_TIP_STEPS):
            mid = (lo + hi) / 2
            if _phi(mid) <= beta:
                lo = mid
            else:
                hi = mid
        te = lo
    n = max(int(detail), 2)
    cb, sb = math.cos(-beta), math.sin(-beta)
    lower = []
    for i in range(n + 1):
        t = ts + (te - ts) * i / n
        x = rb * (math.cos(t) + t * math.sin(t))
        y = rb * (math.sin(t) - t * math.cos(t))
        lower.append((x * cb - y * sb, x * sb + y * cb))
    upper = [(x, -y) for x, y in reversed(lower)]
    tooth = []
    if rf < rb:
        tooth.append((rf * math.cos(-beta), rf * math.sin(-beta)))
    tooth += lower + upper
    if rf < rb:
        tooth.append((rf * math.cos(beta), rf * math.sin(beta)))
    out = []
    for k in range(z):
        a = 2 * math.pi * k / z
        ca, sa = math.cos(a), math.sin(a)
        out.extend((x * ca - y * sa, x * sa + y * ca) for x, y in tooth)
    return out


def _circle(r, n):
    return [(r * math.cos(2 * math.pi * i / n),
             r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def rack_outline(m, pa, backlash, clearance, rim, length):
    p = math.pi * m
    tn = math.tan(math.radians(pa))
    wt = p / 4 - backlash / 4 - m * tn
    wr = p / 4 - backlash / 4 + (1 + clearance) * m * tn
    yr = -(1 + clearance) * m
    n = max(int(math.floor(length / p + 0.5)), 1)
    pts = [(0.0, yr - rim), (0.0, yr)]
    for k in range(n):
        xc = (k + 0.5) * p
        pts += [(xc - wr, yr), (xc - wt, m), (xc + wt, m), (xc + wr, yr)]
    pts += [(n * p, yr), (n * p, yr - rim)]
    return pts


def worm_section(m, starts, pa, rp, clearance, backlash, n=96):
    p = math.pi * m
    tn = math.tan(math.radians(pa))
    out = []
    for i in range(n):
        th = 360.0 * i / n
        u = math.fmod(th * starts / 360.0 * p, p)
        d = abs(u - p / 2)
        y = min(m, max(-(1 + clearance) * m, (p / 4 - backlash / 4 - d) / tn))
        out.append(((rp + y) * math.cos(math.radians(th)),
                    (rp + y) * math.sin(math.radians(th))))
    return out


def _params(node, env):
    from . import mesh
    p = mesh.rp(node, env)
    p["kind"] = str(node.params.get("kind", "spur"))
    p["z"] = max(int(math.floor(p.get("teeth", 20) + 0.5)), 1)
    return p


def pitch_radius(node, env=None):
    p = _params(node, env)
    return p["m"] * p["z"] / 2.0


# ---------------------------------------------------------------- codegen

def statement(node, fmt, fn) -> str:
    from .model import scad_str
    p = node.params
    d = NODE_TYPES["gear"]["params"]
    kind = str(p.get("kind", "spur"))
    args = [f"kind = {scad_str(kind)}"]
    for key in ("m", "teeth", "pressure_angle", "thickness", "helix", "bore",
                "backlash", "clearance", "rim", "mate_teeth", "length",
                "worm_diameter", "detail"):
        args.append(f"{key} = {fmt(p.get(key, d[key]))}")
    return f"kcad_gear({', '.join(args)})"


def build(parser, positional, named):
    from .model import CadNode
    from .scadparse import _num
    d = NODE_TYPES["gear"]["params"]
    params = dict(d)
    kind = str(named.get("kind", d["kind"]))
    if kind not in KINDS:
        parser.warn(f"unknown gear kind {kind!r} — kept as spur")
        kind = "spur"
    params["kind"] = kind
    for key, default in d.items():
        if key != "kind" and key in named:
            value = _num(named[key], default)
            if isinstance(default, int) and not isinstance(value, str):
                value = int(math.floor(value + 0.5))
            params[key] = value
    return CadNode("gear", f"Gear ({kind})", params)


BUILDERS = {"kcad_gear": build}


# ------------------------------------------------------------- validation

def check(node, env):
    from . import expr
    try:
        p = _params(node, env)
    except expr.ExprError as exc:
        return f"gear: {exc}"
    if p["kind"] not in KINDS:
        return f"gear kind must be one of {', '.join(KINDS)}"
    if p["m"] <= 0:
        return "gear: the module must be above 0"
    if p["kind"] in ("rack", "worm"):
        return None
    if p["z"] < 4:
        return "gear: at least 4 teeth"
    r = p["m"] * p["z"] / 2
    if r - (1 + p["clearance"]) * p["m"] <= 0:
        return "gear: too few teeth for the dedendum — add teeth"
    if p["bore"] > 0 and p["kind"] != "internal" and \
            p["bore"] / 2 >= r - (1 + p["clearance"]) * p["m"]:
        return "gear: the bore is wider than the root circle"
    return None


# ----------------------------------------------------------- tessellation

def solid(node, env=None):
    """The preview triangles of a gear node (the helper's geometry)."""
    from . import features, mesh
    p = _params(node, env)
    kind, m, z, pa = p["kind"], p["m"], p["z"], p["pressure_angle"]
    r = m * z / 2.0
    c, bl, h = p["clearance"], p["backlash"], p["thickness"]
    bore = [_circle(p["bore"] / 2, 48)] if p["bore"] > 0 else []
    if kind == "rack":
        return features.extrude([rack_outline(m, pa, bl, c, p["rim"],
                                              p["length"])], h)
    if kind == "worm":
        lead = math.pi * m * z
        twist = -360.0 * p["length"] / lead
        return features.extrude(
            [worm_section(m, z, pa, p["worm_diameter"] / 2, c, bl)] + bore,
            p["length"], twist, 1.0, max(1, math.ceil(abs(twist) / 5)))
    if kind == "internal":
        hole = outline(m, z, pa, r + (1 + c) * m, r - m, -bl, p["detail"])
        outer = _circle(r + (1 + c) * m + p["rim"], 4 * z)
        return features.extrude([outer, hole], h)
    prof = outline(m, z, pa, r + m, r - (1 + c) * m, bl, p["detail"])
    loops = [prof] + bore
    tw = h * math.tan(math.radians(p["helix"])) / r * 180 / math.pi
    if kind == "helical":
        return features.extrude(loops, h, tw, 1.0,
                                max(1, math.ceil(abs(tw) / 5)))
    if kind == "herringbone":
        # one wall that twists up and back, not two halves cap to cap
        n = max(1, math.ceil(abs(tw / 2) / 5))
        up = [(h / 2 * i / n, tw / 2 * i / n, 1.0) for i in range(n + 1)]
        down = [(h - z, t, s) for z, t, s in reversed(up[:-1])]
        return features.stations_solid(loops, up + down)
    if kind == "bevel":
        delta = math.atan2(z, max(p.get("mate_teeth", 20), 1))
        cone = r / math.sin(delta)
        return features.extrude(loops, h, 0.0, max((cone - h) / cone, 0.05))
    return features.extrude(loops, h)


def tess(node, env, color, sel, selected):
    from . import mesh
    return mesh._emit(solid(node, env), color, selected)
