"""The `scatter` wrapper (Qt-free): copies of one piece over a surface —
Blender's particle instancing / Distribute Points on Faces + Instance
on Points.

Spikes down a spine, warts, scales, barnacles, rows of teeth, eye
clusters, rivets, studs, pebbles in a path: the FIRST child is the
piece, modelled at the origin standing up along +Z (its base at z = 0);
the other children are the surface it is scattered over (drawn too, as
Blender leaves the target in the scene, unless ``show_target`` is off).

* ``mode`` ``surface``: ``count`` points darted over the surface by
  area, at least ``spacing`` mm apart (0 = an even spread), seeded;
  ``facing`` + ``max_angle`` keep only faces looking that way (the top
  of a back, the underside of a jaw) and ``within`` (two corners) keeps
  a region. ``mode`` ``path``: ``count`` copies evenly along the
  polyline ``path`` (rows x, y, z — a spine, a jaw line, a brow),
  each dropped onto the nearest point of the surface — a row of spikes
  or teeth exactly where you drew it.
* Each copy stands on its point along the surface normal (``align``
  ``normal``), or upright (``up``), or between the two (``blend``,
  ``align_blend`` 0..1); ``sink`` mm pushes it into the surface so no
  gap shows; ``spin_jitter`` turns it at random about its own axis,
  ``tilt_jitter`` leans it; ``scale`` × (1 ± ``scale_jitter``) sizes
  it, and ``taper`` shrinks copies towards the path's ends (a spine's
  spikes smaller at the tail).

The placements are computed here and written into the call as
4 × 3 matrices — ``kcad_scatter(..., placements = [[...], ...]) {
piece; surface... }`` — whose helper is real OpenSCAD: a ``for`` over
them with ``multmatrix`` round ``children(0)``. So OpenSCAD renders the
real piece at every spot, and the importer rebuilds the node from its
parameters (the placements are recomputed from the children).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import hashlib
import json
import math

MODES = ("surface", "path")
ALIGNS = ("normal", "up", "blend")
FACINGS = ("any", "+z", "-z", "+x", "-x", "+y", "-y")
_FACING_VEC = {"+z": (0, 0, 1), "-z": (0, 0, -1), "+x": (1, 0, 0),
               "-x": (-1, 0, 0), "+y": (0, 1, 0), "-y": (0, -1, 0)}
#: no more copies than this (the program writes a matrix per copy)
MAX_COPIES = 5000

NODE_TYPES = {
    "scatter": dict(
        label="Scatter on surface", category="operation",
        icon="mdi.dots-hexagon",
        params=dict(mode="surface", count=40, spacing=0.0, seed=1,
                    scale=1.0, scale_jitter=0.2, spin_jitter=180.0,
                    tilt_jitter=0.0, align="normal", align_blend=0.5,
                    sink=0.0, facing="any", max_angle=90.0, within=[],
                    path=[], taper=0.0, show_target=True),
        schema=[("mode", "Where", "choice", list(MODES), None),
                ("count", "Copies", "int", 1, MAX_COPIES),
                ("spacing", "At least this far apart (mm, 0 = even)",
                 "float", 0.0, 1e6),
                ("seed", "Seed", "int", 0, 1000000),
                ("scale", "Size", "float", 0.0001, 1e4),
                ("scale_jitter", "Size varies by (0-1)", "float", 0.0, 1.0),
                ("spin_jitter", "Spin at random up to (°)", "float",
                 0.0, 360.0),
                ("tilt_jitter", "Lean at random up to (°)", "float",
                 0.0, 90.0),
                ("align", "Stand along", "choice", list(ALIGNS), None),
                ("align_blend", "... normal share when blended (0-1)",
                 "float", 0.0, 1.0),
                ("sink", "Sink into the surface (mm)", "float", -1e4, 1e4),
                ("facing", "Only faces looking", "choice", list(FACINGS),
                 None),
                ("max_angle", "... within (°)", "float", 0.0, 180.0),
                ("within", "Only inside (two corners, mm)", "rows",
                 ["X", "Y", "Z"], None),
                ("path", "Path (mode path: points, mm)", "rows",
                 ["X", "Y", "Z"], None),
                ("taper", "Smaller towards the path's ends (0-1)", "float",
                 0.0, 1.0),
                ("show_target", "Draw the surface too", "bool",
                 None, None)]),
}
TYPES = frozenset(NODE_TYPES)
LEAVES = frozenset()
WRAPPERS = frozenset(NODE_TYPES)
#: never cached by parameters alone (the placements read the children)
COLORED = frozenset(NODE_TYPES)
TEXT_PARAMS = frozenset()
_NUMBERS = ("count", "spacing", "seed", "scale", "scale_jitter",
            "spin_jitter", "tilt_jitter", "align_blend", "sink",
            "max_angle", "taper")
_CHOICE = {"mode": MODES, "align": ALIGNS, "facing": FACINGS}

HELPER = """\
module kcad_scatter(mode = "surface", count = 40, spacing = 0, seed = 1,
                    scale = 1, scale_jitter = 0.2, spin_jitter = 180,
                    tilt_jitter = 0, align = "normal", align_blend = 0.5,
                    sink = 0, facing = "any", max_angle = 90, within = [],
                    path = [], taper = 0, show_target = true,
                    placements = []) {
    for (m = placements)
        multmatrix([[m[0], m[1], m[2], m[3]], [m[4], m[5], m[6], m[7]],
                    [m[8], m[9], m[10], m[11]], [0, 0, 0, 1]])
            children(0);
    if (show_target && $children > 1) children([1 : $children - 1]);
}"""


# ------------------------------------------------------------ the maths

def _unit(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    return (v[0] / n, v[1] / n, v[2] / n) if n > 1e-12 else None


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _frame(z):
    """A right-handed frame (x, y, z) with the given unit z."""
    ref = (1.0, 0.0, 0.0) if abs(z[0]) < 0.9 else (0.0, 1.0, 0.0)
    x = _unit(_cross(ref, z))
    return x, _cross(z, x), z


def _rot(axis, angle):
    """3x3 rotation about a unit axis (rows)."""
    x, y, z = axis
    c, s = math.cos(angle), math.sin(angle)
    t = 1.0 - c
    return [[t * x * x + c, t * x * y - s * z, t * x * z + s * y],
            [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
            [t * x * z - s * y, t * y * z + s * x, t * z * z + c]]


def _mat_mul(a, b):
    return [[sum(a[r][k] * b[k][c] for k in range(3)) for c in range(3)]
            for r in range(3)]


def surface_points(tris, count, spacing=0.0, facing=None, max_angle=90.0,
                   within=None, seed=1):
    """``[(point, normal)]``: *count* darts over *tris* by area, kept
    *spacing* apart (0 = an even spread) — numpy, with a hash grid for
    the spacing test so thousands of copies stay quick."""
    import numpy as np
    if not tris or count <= 0:
        return []
    t = np.asarray(tris, dtype=np.float64).reshape(-1, 3, 3)
    n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    area = np.linalg.norm(n, axis=1) / 2.0
    keep = area > 1e-12
    unit = np.zeros_like(n)
    unit[keep] = n[keep] / (2.0 * area[keep, None])
    if facing is not None:
        f = np.asarray(facing, dtype=np.float64)
        f = f / np.linalg.norm(f)
        keep &= unit @ f >= math.cos(math.radians(max_angle)) - 1e-9
    if within is not None:
        lo, hi = np.asarray(within[0]), np.asarray(within[1])
        lo, hi = np.minimum(lo, hi), np.maximum(lo, hi)
        c = t.mean(axis=1)
        keep &= np.all((c >= lo) & (c <= hi), axis=1)
    idx = np.nonzero(keep)[0]
    if not len(idx):
        return []
    total = float(area[idx].sum())
    gap = float(spacing) if spacing > 0 else \
        0.8 * math.sqrt(total / (count * math.pi))
    rng = np.random.default_rng(int(seed))
    tries = int(count) * 30
    pick = idx[np.searchsorted(np.cumsum(area[idx]) / total,
                               rng.random(tries), side="right")
               .clip(0, len(idx) - 1)]
    r1, r2 = rng.random(tries), rng.random(tries)
    flip = r1 + r2 > 1.0
    r1[flip], r2[flip] = 1.0 - r1[flip], 1.0 - r2[flip]
    pts = t[pick, 0] + (t[pick, 1] - t[pick, 0]) * r1[:, None] \
        + (t[pick, 2] - t[pick, 0]) * r2[:, None]
    grid, out = {}, []
    g2 = gap * gap
    for p, k in zip(pts.tolist(), pick.tolist()):
        if len(out) >= count:
            break
        cell = (int(math.floor(p[0] / gap)), int(math.floor(p[1] / gap)),
                int(math.floor(p[2] / gap))) if gap > 0 else (0, 0, 0)
        if gap > 0:
            near = False
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        for q in grid.get((cell[0] + dx, cell[1] + dy,
                                           cell[2] + dz), ()):
                            if (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + \
                                    (p[2] - q[2]) ** 2 < g2:
                                near = True
                                break
                        if near:
                            break
                    if near:
                        break
            if near:
                continue
            grid.setdefault(cell, []).append(p)
        out.append((p, unit[k].tolist()))
    return out


def path_points(tris, path, count):
    """``[(point, normal, s)]``: *count* points evenly along the
    polyline *path*, each dropped onto the nearest point of *tris*
    (s = 0..1 along the path)."""
    import numpy as np
    from .shrinkwrap import Target
    if len(path) < 2 or not tris or count <= 0:
        return []
    p = np.asarray(path, dtype=np.float64)
    seg = np.linalg.norm(p[1:] - p[:-1], axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    length = cum[-1]
    if length <= 0:
        return []
    s = np.linspace(0.0, 1.0, int(count)) if count > 1 else np.array([0.5])
    at = s * length
    k = np.clip(np.searchsorted(cum, at, side="right") - 1, 0, len(seg) - 1)
    f = ((at - cum[k]) / np.where(seg[k] > 0, seg[k], 1.0))[:, None]
    pts = p[k] + (p[k + 1] - p[k]) * f
    target = Target(tris)
    q, ti = target.nearest(pts)
    return [(q[i].tolist(), target.n[ti[i]].tolist(), float(s[i]))
            for i in range(len(pts))]


def placements(tris, params):
    """The 4 x 3 matrices (rows flattened, 12 numbers) of every copy."""
    import random
    mode = params["mode"]
    count = int(min(max(params["count"], 0), MAX_COPIES))
    if mode == "path":
        spots = path_points(tris, params["path"], count)
    else:
        facing = _FACING_VEC.get(params["facing"])
        within = params["within"] if len(params["within"]) == 2 else None
        spots = [(pt, nm, None) for pt, nm in surface_points(
            tris, count, params["spacing"], facing, params["max_angle"],
            within, params["seed"])]
    rng = random.Random(int(params["seed"]) * 7919 + 13)
    out = []
    for point, normal, s in spots:
        n = _unit(normal) or (0.0, 0.0, 1.0)
        if params["align"] == "up":
            z = (0.0, 0.0, 1.0)
        elif params["align"] == "blend":
            b = params["align_blend"]
            z = _unit([n[k] * b + (k == 2) * (1.0 - b) for k in range(3)]) \
                or n
        else:
            z = n
        x, y, z = _frame(z)
        frame = [[x[0], y[0], z[0]], [x[1], y[1], z[1]], [x[2], y[2], z[2]]]
        spin = math.radians(rng.uniform(-0.5, 0.5)
                            * params["spin_jitter"]) \
            if params["spin_jitter"] else 0.0
        tilt = math.radians(rng.uniform(0.0, params["tilt_jitter"])) \
            if params["tilt_jitter"] else 0.0
        lean_dir = rng.uniform(0.0, 2.0 * math.pi)
        local = _rot((0.0, 0.0, 1.0), spin)
        if tilt:
            local = _mat_mul(_rot((math.cos(lean_dir), math.sin(lean_dir),
                                   0.0), tilt), local)
        size = params["scale"] * (1.0 + params["scale_jitter"]
                                  * rng.uniform(-1.0, 1.0))
        if s is not None and params["taper"]:
            # full size in the middle of the path, smaller at its ends
            size *= 1.0 - params["taper"] * abs(2.0 * s - 1.0)
        r = _mat_mul(frame, local)
        sink = params["sink"]
        origin = [point[k] - n[k] * sink for k in range(3)]
        out.append([round(r[0][0] * size, 6), round(r[0][1] * size, 6),
                    round(r[0][2] * size, 6), round(origin[0], 4),
                    round(r[1][0] * size, 6), round(r[1][1] * size, 6),
                    round(r[1][2] * size, 6), round(origin[1], 4),
                    round(r[2][0] * size, 6), round(r[2][1] * size, 6),
                    round(r[2][2] * size, 6), round(origin[2], 4)])
    return out


# ------------------------------------------------------------- contract

def preamble(root) -> list:
    if any(n.type in TYPES for n in root.walk()):
        return HELPER.split("\n")
    return []


def _resolved(node, env):
    from . import mesh
    d = NODE_TYPES["scatter"]["params"]
    p = node.params
    out = {k: mesh.rv(p.get(k, d[k]), env, d[k]) for k in _NUMBERS}
    for k in _CHOICE:
        out[k] = str(p.get(k, d[k]))
    for k in ("within", "path"):
        out[k] = [[mesh.rv(v, env) for v in row] for row in p.get(k) or []
                  if isinstance(row, list) and len(row) == 3]
    return out


#: placements by content (the surface's mesh + the parameters)
_CACHE = {}
CACHE_SIZE = 16


def _target(node, env):
    from . import mesh
    ops = mesh._operands(node, env)
    tris = [tri for child, scope in ops[1:] for tri, _c, _s in
            mesh._tess(child, scope, None, frozenset(), False)]
    return ops, tris


def compute(node, env):
    """(operands, placements) of a scatter node, cached by content."""
    ops, tris = _target(node, env)
    params = _resolved(node, env)
    import numpy as np
    h = hashlib.sha1(json.dumps(params, sort_keys=True).encode())
    if tris:
        h.update(np.asarray(tris, dtype=np.float64).tobytes())
    key = h.hexdigest()
    mats = _CACHE.get(key)
    if mats is None:
        mats = placements(tris, params)
        _CACHE[key] = mats
        while len(_CACHE) > CACHE_SIZE:
            _CACHE.pop(next(iter(_CACHE)))
    return ops, mats


def statement(node, fmt, fn) -> str:
    from . import bake
    from .model import scad_str
    p = node.params
    d = NODE_TYPES["scatter"]["params"]
    try:
        _ops, mats = compute(node, bake._codegen_env(node))
    except Exception:
        mats = []                       # validation has flagged it
    parts = []
    for k in d:
        v = p.get(k, d[k])
        if k in _CHOICE:
            parts.append(f"{k} = {scad_str(str(v))}")
        elif k == "show_target":
            parts.append(f"{k} = {'true' if v else 'false'}")
        elif k in ("within", "path"):
            parts.append(f"{k} = {bake._rows(v or [], fmt)}")
        else:
            parts.append(f"{k} = {fmt(v)}")
    return (f"kcad_scatter({', '.join(parts)},\n"
            f"    placements = {bake._rows_wrapped(mats, fmt, 2)})")


def _b_scatter(parser, positional, named):
    from .model import CadNode
    from .scadparse import _num
    d = NODE_TYPES["scatter"]["params"]
    params = {}
    for k, default in d.items():
        v = named.get(k, default)
        if k in _CHOICE:
            v = str(v).strip('"')
            params[k] = v if v in _CHOICE[k] else default
        elif k == "show_target":
            params[k] = v is True or v == "true"
        elif k in ("within", "path"):
            params[k] = [[_num(c) for c in row] for row in v
                         if isinstance(row, list)] \
                if isinstance(v, list) else []
        elif k in ("count", "seed"):
            try:
                params[k] = int(_num(v, default))
            except (TypeError, ValueError):
                params[k] = v if isinstance(v, str) else default
        else:
            params[k] = _num(v, default)
    return CadNode("scatter", NODE_TYPES["scatter"]["label"], params)


BUILDERS = {"kcad_scatter": _b_scatter}


def check(node, env):
    from . import bake, mesh
    parent = node.parent
    while parent is not None:
        if parent.type in ("for_loop", "while_loop", "if_else"):
            what = parent.type.replace("_", " ").replace(" loop", "")
            return (f"a scatter bakes its spots into the program, so it "
                    f"can't sit inside a {what} — put the {what} inside it")
        parent = parent.parent
    p = node.params
    for k, allowed in _CHOICE.items():
        if str(p.get(k, NODE_TYPES["scatter"]["params"][k])) not in allowed:
            return f"scatter: {k} must be one of {', '.join(allowed)}"
    ops = mesh._operands(node, env)
    if len(ops) < 2:
        return ("scatter: the first child is the piece, the others the "
                "surface it goes on — put both inside")
    bad = next((n for child, _s in ops[1:] for n in child.walk()
                if n.visible and bake._inexact(n)), None)
    if bad is not None:
        return (f"scatter: the surface is read from the preview, which "
                f"cannot cut {bad.name} ({bad.type}) right")
    try:
        count = mesh.rv(p.get("count", 40), env, 40)
    except Exception as exc:
        return f"scatter: {exc}"
    if not 1 <= count <= MAX_COPIES:
        return f"scatter: copies must be 1 to {MAX_COPIES}"
    if str(p.get("mode")) == "path" and len([
            r for r in p.get("path") or []
            if isinstance(r, list) and len(r) == 3]) < 2:
        return "scatter: a path needs at least two points [x, y, z]"
    within = p.get("within") or []
    if within and (len(within) != 2 or any(
            not isinstance(r, list) or len(r) != 3 for r in within)):
        return "scatter: 'within' is two corners [x, y, z], or empty"
    return None


def tess(node, env, color, sel, selected):
    from . import mesh
    try:
        ops, mats = compute(node, env)
    except Exception:
        ops, mats = mesh._operands(node, env), []
    if not ops:
        return []
    piece, scope = ops[0]
    items = mesh._tess(piece, scope, color, sel, selected)
    out = []
    for m in mats:
        mat = [[m[0], m[1], m[2], m[3]], [m[4], m[5], m[6], m[7]],
               [m[8], m[9], m[10], m[11]], [0.0, 0.0, 0.0, 1.0]]
        out.extend(mesh._transform_colored(mat, items))
    if node.params.get("show_target", True):
        for child, sc in ops[1:]:
            out.extend(mesh._tess(child, sc, color, sel, selected))
    return out
