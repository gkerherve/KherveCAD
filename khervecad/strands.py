"""The `hair_strands` wrapper (Qt-free): real strands grown from a
surface — Blender's hair particles, combed and clumped. A troll's mane,
a beard, fur tufts, a lion's ruff, whiskers.

``count`` roots are darted over the children's surface (``within`` a
region, never on faces looking within ``clear_angle`` of ``clear`` — the
face), each strand a tapered tube of ``segments`` pieces and ``sides``
sides, ``length`` mm (± ``length_jitter``), from ``root_radius`` to a
point. It leaves along the surface normal, bent towards the ``comb``
direction by ``comb_strength``, droops under ``gravity`` (0..1),
corkscrews ``curl`` mm round its own path (``curl_turns`` turns), and
gathers into ``clumps`` locks — each strand pulled towards its lock's
strand by ``clump_strength`` towards the tip — so a mane reads as locks,
not a brush. The strands are coloured ``color`` (with ``material``, e.g.
Fur); the children are drawn as they are.

Baked through bakedkit: ``kcad_hair_strands(..., points, faces) {
children }`` — OpenSCAD draws the strands as one polyhedron (every
strand its own closed tube) and the children unchanged.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from . import bakedkit

CLEARS = ("none", "-y", "+y", "-x", "+x", "+z", "-z")
_CLEAR_VEC = {"-y": (0, -1, 0), "+y": (0, 1, 0), "-x": (-1, 0, 0),
              "+x": (1, 0, 0), "+z": (0, 0, 1), "-z": (0, 0, -1)}
#: no more strands than this (each is ~50 triangles)
MAX_STRANDS = 20000


def _roots(tris, count, within, clear, clear_angle, seed):
    import numpy as np
    from .scatter import surface_points
    t = np.asarray(tris, dtype=float).reshape(-1, 3, 3)
    keep = np.ones(len(t), dtype=bool)
    n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    length = np.linalg.norm(n, axis=1)
    keep &= length > 1e-12
    if clear in _CLEAR_VEC:
        c = np.asarray(_CLEAR_VEC[clear], dtype=float)
        cos = (n @ c) / np.maximum(length, 1e-12)
        keep &= cos < math.cos(math.radians(clear_angle))
    src = [tris[i] for i in np.nonzero(keep)[0].tolist()]
    box = within if within and len(within) == 2 else None
    return surface_points(src, count, 0.0, None, 90.0, box, seed)


def strand_paths(roots, params):
    """(N, S + 1, 3) points of every strand's centre line."""
    import numpy as np
    rng = np.random.default_rng(int(params["seed"]) + 17)
    N = len(roots)
    S = max(1, int(params["segments"]))
    if not N:
        return np.zeros((0, S + 1, 3))
    p0 = np.asarray([r[0] for r in roots], dtype=float)
    nrm = np.asarray([r[1] for r in roots], dtype=float)
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
    comb = np.asarray([params["comb_x"], params["comb_y"],
                       params["comb_z"]], dtype=float)
    if np.linalg.norm(comb) > 1e-9:
        comb = comb / np.linalg.norm(comb)
    lengths = params["length"] * (1.0 + params["length_jitter"]
                                  * rng.uniform(-1, 1, N))
    step = (lengths / S)[:, None]
    d = nrm + params["comb_strength"] * comb[None, :]
    d /= np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-12)
    pts = np.zeros((N, S + 1, 3))
    pos = p0.copy()
    # the root sinks into the skin so no gap shows round it
    pts[:, 0] = pos - nrm * min(params["root_radius"], 1.0)
    down = np.array([0.0, 0.0, -1.0])
    for k in range(1, S + 1):
        # gravity bends the direction more the further out it is
        g = params["gravity"] * (k / S)
        d = d + g * down[None, :] * 0.6
        d /= np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-12)
        pos = pos + d * step
        pts[:, k] = pos
    if params["curl"] > 0:
        # a corkscrew round each strand's own line
        ref = np.where(np.abs(nrm[:, 2:3]) < 0.9, [[0.0, 0.0, 1.0]],
                       [[1.0, 0.0, 0.0]])
        a = np.cross(nrm, ref)
        a /= np.maximum(np.linalg.norm(a, axis=1, keepdims=True), 1e-12)
        b = np.cross(nrm, a)
        phase = rng.uniform(0, 2 * math.pi, N)
        for k in range(1, S + 1):
            ang = phase + 2 * math.pi * params["curl_turns"] * k / S
            r = params["curl"] * min(1.0, 2.0 * k / S)
            pts[:, k] += (np.cos(ang)[:, None] * a
                          + np.sin(ang)[:, None] * b) * r
    clumps = int(params["clumps"])
    if clumps > 0 and N > 1:
        clumps = min(clumps, N)
        guides = rng.choice(N, clumps, replace=False)
        roots_g = p0[guides]
        owner = np.argmin(((p0[:, None, :] - roots_g[None]) ** 2).sum(-1),
                          axis=1)
        lead = pts[guides[owner]]
        offset = (p0 - roots_g[owner])[:, None, :]
        t = (np.arange(S + 1) / S)[None, :, None]
        target = lead + offset * (1.0 - t)
        w = params["clump_strength"] * t ** 1.2
        pts = pts * (1.0 - w) + target * w
    return pts


def tubes(paths, root_radius, tip_radius, sides):
    """Closed tapered tubes along *paths* (N, S + 1, 3): counter-
    clockwise triangles, every strand its own closed solid."""
    import numpy as np
    N, P, _ = paths.shape
    if not N:
        return []
    sides = max(3, int(sides))
    tang = np.zeros_like(paths)
    tang[:, 1:-1] = paths[:, 2:] - paths[:, :-2]
    tang[:, 0] = paths[:, 1] - paths[:, 0]
    tang[:, -1] = paths[:, -1] - paths[:, -2]
    tang /= np.maximum(np.linalg.norm(tang, axis=2, keepdims=True), 1e-12)
    # parallel transport of one normal along each strand
    ref = np.where(np.abs(tang[:, 0, 2:3]) < 0.9, [[0.0, 0.0, 1.0]],
                   [[1.0, 0.0, 0.0]])
    nrm = np.zeros_like(paths)
    n = np.cross(tang[:, 0], ref)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    nrm[:, 0] = n
    for k in range(1, P):
        n = n - (n * tang[:, k]).sum(1, keepdims=True) * tang[:, k]
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        nrm[:, k] = n
    bin_ = np.cross(tang, nrm)
    radius = root_radius + (tip_radius - root_radius) * \
        (np.arange(P) / (P - 1))
    radius[-1] = 0.0                      # the tip closes to a point
    ang = 2 * math.pi * np.arange(sides) / sides
    ring = (np.cos(ang)[None, None, :, None] * nrm[:, :, None, :]
            + np.sin(ang)[None, None, :, None] * bin_[:, :, None, :])
    verts = paths[:, :, None, :] + ring * radius[None, :, None, None]
    out = []
    for i in range(N):
        v = verts[i]
        base = paths[i, 0]
        for s in range(sides):
            t = (s + 1) % sides
            out.append((tuple(base), tuple(v[0, t]), tuple(v[0, s])))
        for k in range(P - 2):
            for s in range(sides):
                t = (s + 1) % sides
                a, b = v[k, s], v[k, t]
                c, d = v[k + 1, t], v[k + 1, s]
                out.append((tuple(a), tuple(b), tuple(c)))
                out.append((tuple(a), tuple(c), tuple(d)))
        tip = tuple(paths[i, -1])
        for s in range(sides):
            t = (s + 1) % sides
            out.append((tuple(v[P - 2, s]), tuple(v[P - 2, t]), tip))
    return out


def grow(tris, params):
    count = int(min(max(params["count"], 0), MAX_STRANDS))
    roots = _roots(tris, count, params["within"], params["clear"],
                   params["clear_angle"], params["seed"])
    return tubes(strand_paths(roots, params), params["root_radius"],
                 params["tip_radius"], params["sides"])


# ------------------------------------------------------------- the node

_DEFAULTS = dict(count=600, length=30.0, length_jitter=0.3,
                 root_radius=0.5, tip_radius=0.1, segments=6, sides=4,
                 gravity=0.4, curl=0.0, curl_turns=2.0, clumps=40,
                 clump_strength=0.6, comb_x=0.0, comb_y=0.0, comb_z=0.0,
                 comb_strength=0.0, within=[], clear="-y",
                 clear_angle=60.0, seed=1, color="#3b2a1a",
                 material="Default")
_TEXT = ("clear", "color", "material")


def _resolved(node, env):
    out = {}
    for k, d in _DEFAULTS.items():
        if isinstance(d, str):
            out[k] = str(node.params.get(k, d))
        elif isinstance(d, list):
            out[k] = bakedkit.rows(node, env, k, 3)
        else:
            out[k] = bakedkit.num(node, env, k, d)
    return out


def _compute(node, env):
    return grow(bakedkit.source_tris(node, env), _resolved(node, env))


def _colour(node):
    material = str(node.params.get("material", "Default"))
    colour = str(node.params.get("color", "#3b2a1a"))
    return (colour, 1.0, material) if material != "Default" \
        else (colour, 1.0)


def _check(node, env):
    p = node.params
    count = bakedkit.num(node, env, "count", 600)
    if not 1 <= count <= MAX_STRANDS:
        return f"hair strands: count must be 1 to {MAX_STRANDS}"
    if bakedkit.num(node, env, "length", 30.0) <= 0:
        return "hair strands: the length must be more than 0"
    if bakedkit.num(node, env, "root_radius", 0.5) <= 0:
        return "hair strands: the root radius must be more than 0"
    within = p.get("within") or []
    if within and (len(within) != 2 or any(
            not isinstance(r, list) or len(r) != 3 for r in within)):
        return "hair strands: 'within' is two corners [x, y, z], or empty"
    from .model import MATERIALS
    if str(p.get("material", "Default")) not in MATERIALS:
        return "hair strands: unknown material"
    return None


KIT = bakedkit.make(
    "hair_strands", "Hair strands (fur, manes, beards)", "mdi.grass",
    _DEFAULTS,
    [("count", "Strands", "int", 1, MAX_STRANDS),
     ("length", "Length (mm)", "float", 0.01, 1e5),
     ("length_jitter", "Length varies by (0-1)", "float", 0.0, 1.0),
     ("root_radius", "Root radius (mm)", "float", 0.001, 1e3),
     ("tip_radius", "Tip radius (mm)", "float", 0.0, 1e3),
     ("segments", "Segments a strand", "int", 1, 64),
     ("sides", "Sides", "int", 3, 12),
     ("gravity", "Gravity (0-1, droop)", "float", -2.0, 2.0),
     ("curl", "Curl radius (mm)", "float", 0.0, 1e3),
     ("curl_turns", "Curl turns", "float", 0.0, 100.0),
     ("clumps", "Locks (0 = none)", "int", 0, 5000),
     ("clump_strength", "Gathered into locks (0-1)", "float", 0.0, 1.0),
     ("comb_x", "Comb towards X", "float", -1.0, 1.0),
     ("comb_y", "Comb towards Y", "float", -1.0, 1.0),
     ("comb_z", "Comb towards Z", "float", -1.0, 1.0),
     ("comb_strength", "Combed by (0 = along the normal)", "float",
      0.0, 10.0),
     ("within", "Only inside (two corners, mm)", "rows", ["X", "Y", "Z"],
      None),
     ("clear", "Keep clear the faces looking", "choice", list(CLEARS),
      None),
     ("clear_angle", "... within (°)", "float", 1.0, 179.0),
     ("seed", "Seed", "int", 0, 1000000),
     ("color", "Strand colour", "color", None, None),
     ("material", "Strand material", "str", None, None)],
    _compute, choices={"clear": CLEARS}, text=_TEXT,
    draws_children=lambda node: True, check=_check, colour=_colour,
    helper_body=("    color(color) polyhedron(points = points, faces = "
                 "faces, convexity = 10);\n    children();"))
