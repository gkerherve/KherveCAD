"""Textured surfaces — BOSL2's textures (``texture = "diamonds"`` on a
cylinder or a cuboid): a cylinder or a flat panel whose surface carries
a relief pattern.

Patterns, each a height 0..1 over the surface (u around / across, v
along / up, both in mm): **ribs**, **waves**, **diamonds** (pyramids,
a knurl), **bricks** (mortar lines), **hexes** (hexagonal tiles),
**dimples** (round hollows) and **checkers**. The relief is ``depth``
deep; the cylinder's period is rounded so the pattern closes seamlessly
round it.

It compiles to one ``kcad_textured(...)`` call whose helper builds the
same polyhedron (grid points, then faces) in OpenSCAD — no boolean, and
the preview is the same surface.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

SHAPE_3D = "3d"

SHAPES = ("cylinder", "panel")
PATTERNS = ("ribs", "waves", "diamonds", "bricks", "hexes", "dimples",
            "checkers")

NODE_TYPES = {
    "textured": dict(
        label="Textured cylinder / panel", category=SHAPE_3D,
        icon="mdi.texture-box",
        params=dict(shape="cylinder", pattern="diamonds", diameter=30.0,
                    width=60.0, depth=40.0, height=30.0, period=4.0,
                    relief=0.8, detail=6),
        schema=[("shape", "Shape", "choice", list(SHAPES), None),
                ("pattern", "Pattern", "choice", list(PATTERNS), None),
                ("diameter", "Cylinder diameter (mm)", "float", 1.0, 1e5),
                ("width", "Panel width X (mm)", "float", 1.0, 1e5),
                ("depth", "Panel depth Y (mm)", "float", 1.0, 1e5),
                ("height", "Height / panel thickness (mm)", "float", 0.1,
                 1e5),
                ("period", "Pattern size (mm)", "float", 0.2, 1e4),
                ("relief", "Relief depth (mm)", "float", 0.01, 100.0),
                ("detail", "Samples per pattern", "int", 2, 32)]),
}
TYPES = frozenset(NODE_TYPES)
LEAVES = frozenset(NODE_TYPES)
TEXT_PARAMS = frozenset({"shape", "pattern"})


def _tri(t):
    """Triangle wave 0..1..0 over a period of 1."""
    f = t - math.floor(t)
    return 1 - abs(2 * f - 1)


def height(pattern, u, v, p):
    """The texture's height 0..1 at (u, v) mm for period *p* (the
    helper's kcad_texture_h)."""
    a, b = u / p, v / p
    if pattern == "ribs":
        return 0.5 + 0.5 * math.cos(2 * math.pi * a)
    if pattern == "waves":
        return 0.5 + 0.5 * math.sin(2 * math.pi * (a + 0.25 * math.sin(
            2 * math.pi * b)))
    if pattern == "diamonds":
        return min(_tri(a + b), _tri(a - b))
    if pattern == "bricks":
        row = math.floor(2 * b)
        fb = 2 * b - row
        fa = a + 0.5 * (row % 2) - math.floor(a + 0.5 * (row % 2))
        return 0.0 if fb < 0.12 or fa < 0.06 else 1.0
    if pattern == "hexes":
        # distance to the nearest centre of a hexagonal lattice, scaled
        # so the tile border (half the spacing) is 0
        best = 9.0
        rows = (math.floor(b / 0.866) - 1, math.floor(b / 0.866),
                math.floor(b / 0.866) + 1)
        for r in rows:
            cy = r * 0.866
            off = 0.5 * (r % 2)
            for c in (math.floor(a - off) - 1, math.floor(a - off),
                      math.floor(a - off) + 1):
                best = min(best, math.hypot(a - (c + off), b - cy))
        return 1.0 if best < 0.42 else max(0.0, 1 - (best - 0.42) / 0.08)
    if pattern == "dimples":
        fa, fb = a - math.floor(a), b - math.floor(b)
        d = math.hypot(fa - 0.5, fb - 0.5)
        return 1.0 if d > 0.35 else math.sqrt(max(0.0, 1 - (1 - d / 0.35)
                                                  ** 2))
    if pattern == "checkers":
        return float((math.floor(a) + math.floor(b)) % 2)
    return 0.0


def grid(p):
    """(columns, rows, the effective period across, along) of a textured
    node's resolved params."""
    detail = max(int(p["detail"]), 2)
    if p["shape"] == "cylinder":
        circumference = math.pi * p["diameter"]
        repeats = max(int(round(circumference / p["period"])), 3)
        cols = repeats * detail
        period_u = circumference / repeats
        rows = max(int(math.ceil(p["height"] / p["period"] * detail)), 1)
        return cols, rows, period_u
    cols = max(int(math.ceil(p["width"] / p["period"] * detail)), 1)
    rows = max(int(math.ceil(p["depth"] / p["period"] * detail)), 1)
    return cols, rows, p["period"]


def solid(p):
    """Triangles of the textured solid (outward, counter-clockwise)."""
    cols, rows, pu = grid(p)
    relief, pat = p["relief"], p["pattern"]
    tris = []
    if p["shape"] == "cylinder":
        R = p["diameter"] / 2
        H = p["height"]
        ring = []
        for k in range(rows + 1):
            z = H * k / rows
            row = []
            for i in range(cols):
                th = 2 * math.pi * i / cols
                u = R * th
                r = R - relief + relief * height(pat, u, z, pu)
                row.append((r * math.cos(th), r * math.sin(th), z))
            ring.append(row)
        for k in range(rows):
            for i in range(cols):
                j = (i + 1) % cols
                a, b = ring[k][i], ring[k][j]
                c, d = ring[k + 1][j], ring[k + 1][i]
                tris += [(a, b, c), (a, c, d)]
        bottom, top = (0.0, 0.0, 0.0), (0.0, 0.0, H)
        for i in range(cols):
            j = (i + 1) % cols
            tris.append((bottom, ring[0][j], ring[0][i]))
            tris.append((top, ring[rows][i], ring[rows][j]))
        return tris
    W, D, T = p["width"], p["depth"], p["height"]
    pts = [[(W * i / cols, D * k / rows,
             T - relief + relief * height(pat, W * i / cols, D * k / rows,
                                          pu))
            for i in range(cols + 1)] for k in range(rows + 1)]
    for k in range(rows):
        for i in range(cols):
            a, b = pts[k][i], pts[k][i + 1]
            c, d = pts[k + 1][i + 1], pts[k + 1][i]
            tris += [(a, b, c), (a, c, d)]
    edges = [[pts[0][i] for i in range(cols + 1)],
             [pts[k][cols] for k in range(rows + 1)],
             [pts[rows][i] for i in range(cols, -1, -1)],
             [pts[k][0] for k in range(rows, -1, -1)]]
    centre = (W / 2, D / 2, 0.0)
    for line in edges:
        for s, e in zip(line, line[1:]):
            s0, e0 = (s[0], s[1], 0.0), (e[0], e[1], 0.0)
            tris += [(s0, e0, e), (s0, e, s)]
            tris.append((centre, e0, s0))      # the base, fanned so every
    return tris                                 # edge meets its wall


HELPER = """\
function kcad_tri(t) = 1 - abs(2 * (t - floor(t)) - 1);
function kcad_texture_h(pat, u, v, p) =
    let (a = u / p, b = v / p)
    pat == "ribs" ? 0.5 + 0.5 * cos(360 * a)
  : pat == "waves" ? 0.5 + 0.5 * sin(360 * (a + 0.25 * sin(360 * b)))
  : pat == "diamonds" ? min(kcad_tri(a + b), kcad_tri(a - b))
  : pat == "bricks" ?
      let (row = floor(2 * b), fb = 2 * b - row,
           sh = a + 0.5 * (row % 2), fa = sh - floor(sh))
      (fb < 0.12 || fa < 0.06 ? 0 : 1)
  : pat == "hexes" ?
      let (best = min([for (r = [floor(b / 0.866) - 1 : floor(b / 0.866) + 1])
                       let (cy = r * 0.866, off = 0.5 * (r % 2))
                       for (c = [floor(a - off) - 1 : floor(a - off) + 1])
                       norm([a - (c + off), b - cy])]))
      (best < 0.42 ? 1 : max(0, 1 - (best - 0.42) / 0.08))
  : pat == "dimples" ?
      let (fa = a - floor(a), fb = b - floor(b),
           d = norm([fa - 0.5, fb - 0.5]))
      (d > 0.35 ? 1 : sqrt(max(0, 1 - pow(1 - d / 0.35, 2))))
  : pat == "checkers" ? (floor(a) + floor(b)) % 2
  : 0;
module kcad_textured(shape = "cylinder", pattern = "diamonds", diameter = 30,
                     width = 60, depth = 40, height = 30, period = 4,
                     relief = 0.8, detail = 6) {
    det = max(round(detail), 2);
    if (shape == "cylinder") {
        R = diameter / 2;
        reps = max(round(PI * diameter / period), 3);
        cols = reps * det;
        pu = PI * diameter / reps;
        rows = max(ceil(height / period * det), 1);
        pts = concat(
            [for (k = [0 : rows], i = [0 : cols - 1])
             let (th = 360 * i / cols, z = height * k / rows,
                  u = R * th * PI / 180,
                  r = R - relief + relief * kcad_texture_h(pattern, u, z, pu))
             [r * cos(th), r * sin(th), z]],
            [[0, 0, 0], [0, 0, height]]);
        n = (rows + 1) * cols;
        faces = concat(
            [for (k = [0 : rows - 1], i = [0 : cols - 1])
             let (j = (i + 1) % cols)
             each [[k * cols + i, (k + 1) * cols + j, k * cols + j],
                   [k * cols + i, (k + 1) * cols + i, (k + 1) * cols + j]]],
            [for (i = [0 : cols - 1]) [n, i, (i + 1) % cols]],
            [for (i = [0 : cols - 1])
             [n + 1, rows * cols + (i + 1) % cols, rows * cols + i]]);
        polyhedron(points = pts, faces = faces);
    } else {
        cols = max(ceil(width / period * det), 1);
        rows = max(ceil(depth / period * det), 1);
        top = [for (k = [0 : rows], i = [0 : cols])
               let (x = width * i / cols, y = depth * k / rows)
               [x, y, height - relief
                      + relief * kcad_texture_h(pattern, x, y, period)]];
        w1 = cols + 1;
        bottom = [[0, 0, 0], [width, 0, 0], [width, depth, 0],
                  [0, depth, 0]];
        base = len(top);
        south = [for (i = [0 : cols]) i];
        east = [for (k = [0 : rows]) k * w1 + cols];
        north = [for (i = [cols : -1 : 0]) rows * w1 + i];
        west = [for (k = [rows : -1 : 0]) k * w1];
        faces = concat(
            [for (k = [0 : rows - 1], i = [0 : cols - 1])
             each [[k * w1 + i, (k + 1) * w1 + i + 1, k * w1 + i + 1],
                   [k * w1 + i, (k + 1) * w1 + i, (k + 1) * w1 + i + 1]]],
            [[base, base + 1, base + 2], [base, base + 2, base + 3]],
            [concat(south, [base + 1, base])],
            [concat(east, [base + 2, base + 1])],
            [concat(north, [base + 3, base + 2])],
            [concat(west, [base, base + 3])]);
        polyhedron(points = concat(top, bottom), faces = faces);
    }
}"""


def preamble(root) -> list:
    if any(n.type in TYPES for n in root.walk()):
        return HELPER.split("\n")
    return []


def _params(node, env):
    from . import mesh
    p = mesh.rp(node, env)
    p["shape"] = str(node.params.get("shape", "cylinder"))
    p["pattern"] = str(node.params.get("pattern", "diamonds"))
    return p


def statement(node, fmt, fn) -> str:
    from .model import scad_str
    p = node.params
    d = NODE_TYPES["textured"]["params"]
    args = [f"shape = {scad_str(str(p.get('shape', 'cylinder')))}",
            f"pattern = {scad_str(str(p.get('pattern', 'diamonds')))}"]
    for key in ("diameter", "width", "depth", "height", "period", "relief",
                "detail"):
        args.append(f"{key} = {fmt(p.get(key, d[key]))}")
    return f"kcad_textured({', '.join(args)})"


def build(parser, positional, named):
    from .model import CadNode
    from .scadparse import _num
    d = NODE_TYPES["textured"]["params"]
    params = dict(d)
    for key in ("shape", "pattern"):
        value = str(named.get(key, d[key]))
        allowed = SHAPES if key == "shape" else PATTERNS
        if value not in allowed:
            parser.warn(f"unknown texture {key} {value!r}")
            value = d[key]
        params[key] = value
    for key, default in d.items():
        if key not in ("shape", "pattern") and key in named:
            value = _num(named[key], default)
            if isinstance(default, int) and not isinstance(value, str):
                value = max(int(math.floor(value + 0.5)), 2)
            params[key] = value
    return CadNode("textured", f"Textured {params['shape']}", params)


BUILDERS = {"kcad_textured": build}


def check(node, env):
    p = _params(node, env)
    if p["shape"] not in SHAPES or p["pattern"] not in PATTERNS:
        return "textured: unknown shape or pattern"
    if p["shape"] == "cylinder" and p["relief"] >= p["diameter"] / 2:
        return "textured: the relief is deeper than the radius"
    if p["shape"] == "panel" and p["relief"] >= p["height"]:
        return "textured: the relief is deeper than the panel"
    cols, rows, _pu = grid(p)
    if cols * rows > 400000:
        return "textured: too fine — raise the pattern size or lower detail"
    return None


def tess(node, env, color, sel, selected):
    from . import mesh
    return mesh._emit(solid(_params(node, env)), color, selected)
