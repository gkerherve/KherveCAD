"""Screw threads — the `thread` node (threads.scad, BOSL2's threading
and bottle caps): ISO metric, trapezoidal (ACME-like 30°), square,
buttress, tapered pipe (NPT-like 1:16) and a bottle-neck thread, male
or as the clearance "tap" to cut a nut or a threaded hole, any number
of starts, right or left hand.

Every kind is one idea: the cross-section at z = 0 is a circle whose
radius at angle θ follows the thread's axial profile at u = θ · lead /
360 (a trapezoid between the minor and major radius, possibly
asymmetric), and linear_extrude twists that section by 360° per lead —
the helicoid is exact, needs no boolean, and previews as what it is.
A pipe thread also scales toward the tip (its taper).

Compiles to ONE ``kcad_thread(...)`` call; its helper builds the same
section in OpenSCAD (keep `section` and HELPER in step).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

SHAPE_3D = "3d"

KINDS = ("metric", "trapezoidal", "square", "buttress", "pipe", "bottle")

#: sample points round the section
SECTION_POINTS = 72
#: most slices the built-in preview draws along a thread
PREVIEW_SLICES = 360

NODE_TYPES = {
    "thread": dict(
        label="Thread (screw thread)", category=SHAPE_3D,
        icon="mdi.screw-machine-flat-top",
        params=dict(kind="metric", diameter=8.0, pitch=1.25, length=16.0,
                    starts=1, left_hand=False, internal=False,
                    clearance=0.2, bore=0.0),
        schema=[("kind", "Profile", "choice", list(KINDS), None),
                ("diameter", "Major diameter (mm)", "float", 0.5, 1e5),
                ("pitch", "Pitch (mm)", "float", 0.05, 1e4),
                ("length", "Length (mm)", "float", 0.1, 1e5),
                ("starts", "Starts", "int", 1, 12),
                ("left_hand", "Left-hand", "bool", None, None),
                ("internal", "Internal: the tap that cuts a nut", "bool",
                 None, None),
                ("clearance", "Clearance for internal (mm)", "float", 0.0,
                 5.0),
                ("bore", "Hollow bore diameter (0 = solid)", "float", 0.0,
                 1e5)]),
}
TYPES = frozenset(NODE_TYPES)
LEAVES = frozenset(NODE_TYPES)
TEXT_PARAMS = frozenset({"kind"})


def profile(kind, pitch):
    """(depth, crest half-width at the major radius, load flank angle°,
    trailing flank angle°) of an axial profile."""
    p = pitch
    if kind == "trapezoidal":
        h = p / 2
        return h, p / 4 - h / 2 * math.tan(math.radians(15)), 15.0, 15.0
    if kind == "square":
        return p / 2, p / 4, 0.0, 0.0
    if kind == "buttress":
        return 0.6 * p, p / 16, 7.0, 45.0
    if kind == "pipe":
        return 0.8 * p, p * 0.033, 30.0, 30.0
    if kind == "bottle":
        return 0.45 * p, p / 6, 30.0, 30.0
    return 0.5413 * p, p / 16, 30.0, 30.0                   # ISO metric


def _radius(u, pitch, r_major, depth, crest, a_load, a_trail):
    """Radius where the section meets axial offset *u* (0..pitch): the
    tooth crest centred at pitch / 2, flanks down to the root."""
    d = u - pitch / 2
    half = crest + (depth * math.tan(math.radians(a_load if d < 0
                                                   else a_trail)))
    dist = abs(d)
    if dist <= crest:
        return r_major
    if dist >= half:
        return r_major - depth
    return r_major - depth * (dist - crest) / (half - crest)


def section(kind, diameter, pitch, starts=1, internal=False,
            clearance=0.2, n=SECTION_POINTS):
    """The thread's cross-section at z = 0 (the helper's
    kcad_thread_section)."""
    depth, crest, a_load, a_trail = profile(kind, pitch)
    r_major = diameter / 2 + (clearance if internal else 0.0)
    lead = pitch * max(int(starts), 1)
    out = []
    for i in range(n):
        th = 360.0 * i / n
        u = math.fmod(th / 360.0 * lead, pitch)
        r = _radius(u, pitch, r_major, depth, crest, a_load, a_trail)
        out.append((r * math.cos(math.radians(th)),
                    r * math.sin(math.radians(th))))
    return out


HELPER = """\
function kcad_thread_profile(kind, p) =
    kind == "trapezoidal" ? [p / 2, p / 4 - p / 4 * tan(15), 15, 15]
  : kind == "square" ? [p / 2, p / 4, 0, 0]
  : kind == "buttress" ? [0.6 * p, p / 16, 7, 45]
  : kind == "pipe" ? [0.8 * p, p * 0.033, 30, 30]
  : kind == "bottle" ? [0.45 * p, p / 6, 30, 30]
  : [0.5413 * p, p / 16, 30, 30];
function kcad_thread_r(u, p, R, prof) =
    let (d = u - p / 2, dist = abs(d),
         half = prof[1] + prof[0] * tan(d < 0 ? prof[2] : prof[3]))
    dist <= prof[1] ? R
  : dist >= half ? R - prof[0]
  : R - prof[0] * (dist - prof[1]) / (half - prof[1]);
function kcad_thread_section(kind, dia, p, starts, internal, clearance,
                             n = 72) =
    let (prof = kcad_thread_profile(kind, p),
         R = dia / 2 + (internal ? clearance : 0),
         lead = p * max(round(starts), 1))
    [for (i = [0 : n - 1]) let (th = 360 * i / n,
         u = (th / 360 * lead) % p)
     kcad_thread_r(u, p, R, prof) * [cos(th), sin(th)]];
module kcad_thread(kind = "metric", diameter = 8, pitch = 1.25, length = 16,
                   starts = 1, left_hand = false, internal = false,
                   clearance = 0.2, bore = 0) {
    lead = pitch * max(round(starts), 1);
    turns = length / lead;
    taper = kind == "pipe" ? max((diameter - length / 16) / diameter, 0.05)
                           : 1;
    linear_extrude(height = length,
                   twist = (left_hand ? 360 : -360) * turns,
                   slices = max(1, ceil(abs(turns) * 36)), scale = taper)
        difference() {
            polygon(kcad_thread_section(kind, diameter, pitch, starts,
                                        internal, clearance));
            if (bore > 0) circle(d = bore, $fn = 48);
        }
}"""


def preamble(root) -> list:
    if any(n.type == "thread" for n in root.walk()):
        return HELPER.split("\n")
    return []


def _params(node, env):
    from . import mesh
    p = mesh.rp(node, env)
    p["kind"] = str(node.params.get("kind", "metric"))
    p["starts"] = max(int(math.floor(p.get("starts", 1) + 0.5)), 1)
    return p


# ---------------------------------------------------------------- codegen

def statement(node, fmt, fn) -> str:
    from .model import scad_str
    p = node.params
    d = NODE_TYPES["thread"]["params"]
    args = [f"kind = {scad_str(str(p.get('kind', 'metric')))}"]
    for key in ("diameter", "pitch", "length", "starts", "left_hand",
                "internal", "clearance", "bore"):
        args.append(f"{key} = {fmt(p.get(key, d[key]))}")
    return f"kcad_thread({', '.join(args)})"


def build(parser, positional, named):
    from .model import CadNode
    from .scadparse import _num
    d = NODE_TYPES["thread"]["params"]
    params = dict(d)
    kind = str(named.get("kind", d["kind"]))
    if kind not in KINDS:
        parser.warn(f"unknown thread kind {kind!r} — kept as metric")
        kind = "metric"
    params["kind"] = kind
    for key, default in d.items():
        if key == "kind" or key not in named:
            continue
        if isinstance(default, bool):
            params[key] = bool(named[key])
        else:
            value = _num(named[key], default)
            if isinstance(default, int) and not isinstance(value, str):
                value = int(math.floor(value + 0.5))
            params[key] = value
    return CadNode("thread", f"Thread ({kind})", params)


BUILDERS = {"kcad_thread": build}


def check(node, env):
    from . import expr
    try:
        p = _params(node, env)
    except expr.ExprError as exc:
        return f"thread: {exc}"
    if p["kind"] not in KINDS:
        return f"thread kind must be one of {', '.join(KINDS)}"
    if p["diameter"] <= 0 or p["pitch"] <= 0 or p["length"] <= 0:
        return "thread: diameter, pitch and length must be above 0"
    depth = profile(p["kind"], p["pitch"])[0]
    if depth >= p["diameter"] / 2:
        return "thread: the pitch is too coarse for this diameter"
    if p["bore"] > 0 and p["bore"] / 2 >= p["diameter"] / 2 - depth:
        return "thread: the bore is wider than the root"
    return None


def solid(node, env=None):
    from . import features
    p = _params(node, env)
    lead = p["pitch"] * p["starts"]
    turns = p["length"] / lead
    twist = (360.0 if p["left_hand"] else -360.0) * turns
    scale = max((p["diameter"] - p["length"] / 16) / p["diameter"], 0.05) \
        if p["kind"] == "pipe" else 1.0
    loops = [section(p["kind"], p["diameter"], p["pitch"], p["starts"],
                     bool(p["internal"]), p["clearance"])]
    if p["bore"] > 0:
        loops.append([(p["bore"] / 2 * math.cos(2 * math.pi * i / 48),
                       p["bore"] / 2 * math.sin(2 * math.pi * i / 48))
                      for i in range(48)])
    slices = max(1, math.ceil(abs(turns) * 36))
    # the exact render keeps 36 slices a turn; the preview is capped
    slices = min(slices, PREVIEW_SLICES)
    return features.stations_solid(
        loops, [(p["length"] * k / slices, twist * k / slices,
                 1.0 + (scale - 1.0) * k / slices)
                for k in range(slices + 1)])


def tess(node, env, color, sel, selected):
    from . import mesh
    return mesh._emit(solid(node, env), color, selected)
