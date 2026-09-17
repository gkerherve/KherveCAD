"""Surface patterns for printed parts: the knurled grip and the
honeycomb wall (the knurled-surface library, BOSL2's walls.scad).

- **knurl** — a cylinder covered in diamond knurling: two sets of
  helical V grooves turning opposite ways, their intersection leaving
  pyramids. ``count`` diamonds round, ``depth`` of the grooves,
  ``angle`` of the helix. In OpenSCAD it is the intersection of two
  twisted extrusions of a toothed circle; the preview builds the same
  surface directly (the radius at each point is the lower of the two
  toothed sections), so it is exact without a boolean;
- **honeycomb** — a 2D rectangle perforated with hexagonal cells (across
  flats ``cell``, ``wall`` between them, a solid ``margin`` round the
  edge; only whole cells are cut). Extrude it for a light, stiff panel.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

SHAPE_2D = "2d"
SHAPE_3D = "3d"

NODE_TYPES = {
    "knurl": dict(
        label="Knurled cylinder", category=SHAPE_3D, icon="mdi.grid",
        params=dict(diameter=20.0, length=15.0, count=24, depth=0.8,
                    angle=30.0),
        schema=[("diameter", "Outer diameter (mm)", "float", 0.5, 1e5),
                ("length", "Length (mm)", "float", 0.1, 1e5),
                ("count", "Diamonds round", "int", 3, 400),
                ("depth", "Groove depth (mm)", "float", 0.01, 100.0),
                ("angle", "Helix angle°", "float", 5.0, 75.0)]),
    "honeycomb": dict(
        label="Honeycomb panel (2D)", category=SHAPE_2D,
        icon="mdi.hexagon-multiple",
        params=dict(x=0.0, y=0.0, width=60.0, height=40.0, cell=8.0,
                    wall=1.2, margin=3.0),
        schema=[("x", "X", "float", -1e6, 1e6),
                ("y", "Y", "float", -1e6, 1e6),
                ("width", "Width (mm)", "float", 0.1, 1e6),
                ("height", "Height (mm)", "float", 0.1, 1e6),
                ("cell", "Cell across flats (mm)", "float", 0.1, 1e5),
                ("wall", "Wall between cells (mm)", "float", 0.05, 1e5),
                ("margin", "Solid margin (mm)", "float", 0.0, 1e5)]),
}
TYPES = frozenset(NODE_TYPES)
LEAVES = frozenset(NODE_TYPES)
#: 2D shapes whose inner loops are holes
NESTED_2D = frozenset({"honeycomb"})


def knurl_twist(diameter, length, angle):
    """Degrees one groove set turns over the length."""
    return length * math.tan(math.radians(angle)) / (diameter / 2) \
        * 180 / math.pi


def _tooth_radius(phi, count, r, depth):
    """Radius of the toothed section at angle *phi*° (crests at multiples
    of 360 / count, straight flanks between, as the polygon draws it)."""
    period = 360.0 / count
    u = (phi % period) / period                       # 0..1 across a tooth
    frac = abs(u * 2 - 1)                              # 1 at crests, 0 root
    crest, root = r, r - depth
    # the polygon's straight chord between crest and root, at angle phi
    a0 = math.radians(0.0)
    half = math.radians(period / 2)
    t = 1 - frac
    # chord from (crest, 0) to (root, half) in polar, intersected at t*half
    x0, y0 = crest * math.cos(a0), crest * math.sin(a0)
    x1, y1 = root * math.cos(half), root * math.sin(half)
    ang = t * half
    dx, dy = x1 - x0, y1 - y0
    denom = dx * math.sin(ang) - dy * math.cos(ang)
    if abs(denom) < 1e-12:
        return crest
    s = (y0 * math.cos(ang) - x0 * math.sin(ang)) / denom
    return math.hypot(x0 + s * dx, y0 + s * dy)


def knurl_mesh(diameter, length, count, depth, angle, around=None,
               slices=None):
    """The knurl as a closed mesh: r(θ, z) = min of the two turning
    toothed sections."""
    count = max(int(count), 3)
    r = diameter / 2
    twist = knurl_twist(diameter, length, angle)
    around = around or count * 8
    slices = slices or max(int(abs(twist) / (180.0 / count)) * 2, 8)
    rings = []
    for k in range(slices + 1):
        z = length * k / slices
        turn = twist * k / slices
        ring = []
        for i in range(around):
            th = 360.0 * i / around
            rad = min(_tooth_radius(th + turn, count, r, depth),
                      _tooth_radius(th - turn, count, r, depth))
            ring.append((rad * math.cos(math.radians(th)),
                         rad * math.sin(math.radians(th)), z))
        rings.append(ring)
    tris = []
    for lower, upper in zip(rings, rings[1:]):
        for i in range(around):
            j = (i + 1) % around
            tris.append((lower[i], lower[j], upper[j]))
            tris.append((lower[i], upper[j], upper[i]))
    c0, c1 = (0.0, 0.0, 0.0), (0.0, 0.0, length)
    for i in range(around):
        j = (i + 1) % around
        tris.append((c0, rings[0][j], rings[0][i]))
        tris.append((c1, rings[-1][i], rings[-1][j]))
    return tris


def honeycomb_centres(width, height, cell, wall, margin):
    """Centres of the whole hexagonal cells inside the margin (the
    helper's kcad_honeycomb_centres)."""
    R = cell / math.sqrt(3)
    sx = cell + wall
    sy = sx * math.sqrt(3) / 2
    out = []
    rows = int((height - 2 * margin) / sy) + 2
    cols = int((width - 2 * margin) / sx) + 2
    for row in range(rows):
        for col in range(cols):
            cx = margin + cell / 2 + col * sx + (row % 2) * sx / 2
            cy = margin + R + row * sy
            if cx + cell / 2 <= width - margin + 1e-9 and \
                    cy + R <= height - margin + 1e-9:
                out.append((cx, cy))
    return out


def _hexagon(cx, cy, cell):
    R = cell / math.sqrt(3)
    return [(cx + R * math.cos(math.radians(90 + 60 * i)),
             cy + R * math.sin(math.radians(90 + 60 * i))) for i in range(6)]


HELPER = """\
function kcad_honeycomb_centres(w, h, cell, wall, margin) =
    let (R = cell / sqrt(3), sx = cell + wall, sy = sx * sqrt(3) / 2,
         rows = floor((h - 2 * margin) / sy) + 2,
         cols = floor((w - 2 * margin) / sx) + 2)
    [for (row = [0 : rows - 1], col = [0 : cols - 1])
     let (cx = margin + cell / 2 + col * sx + (row % 2) * sx / 2,
          cy = margin + R + row * sy)
     if (cx + cell / 2 <= w - margin + 1e-9 && cy + R <= h - margin + 1e-9)
     [cx, cy]];
module kcad_honeycomb(size = [60, 40], cell = 8, wall = 1.2, margin = 3,
                      center = [0, 0]) {
    translate(center) difference() {
        square(size);
        for (c = kcad_honeycomb_centres(size[0], size[1], cell, wall, margin))
            translate(c) rotate(90) circle(r = cell / sqrt(3), $fn = 6);
    }
}
function kcad_knurl_section(n, r, depth) =
    [for (i = [0 : 2 * n - 1]) (i % 2 == 0 ? r : r - depth)
     * [cos(180 * i / n), sin(180 * i / n)]];
module kcad_knurl(diameter = 20, length = 15, count = 24, depth = 0.8,
                  angle = 30) {
    n = max(round(count), 3);
    tw = length * tan(angle) / (diameter / 2) * 180 / PI;
    sl = max(floor(abs(tw) / (180 / n)) * 2, 8);
    intersection() {
        linear_extrude(height = length, twist = tw, slices = sl)
            polygon(kcad_knurl_section(n, diameter / 2, depth));
        linear_extrude(height = length, twist = -tw, slices = sl)
            polygon(kcad_knurl_section(n, diameter / 2, depth));
    }
}"""


def preamble(root) -> list:
    if any(n.type in TYPES for n in root.walk()):
        return HELPER.split("\n")
    return []


def statement(node, fmt, fn) -> str:
    p = node.params
    if node.type == "knurl":
        return (f"kcad_knurl(diameter = {fmt(p['diameter'])}, length = "
                f"{fmt(p['length'])}, count = {fmt(p['count'])}, depth = "
                f"{fmt(p['depth'])}, angle = {fmt(p['angle'])})")
    return (f"kcad_honeycomb(size = [{fmt(p['width'])}, "
            f"{fmt(p['height'])}], cell = {fmt(p['cell'])}, wall = "
            f"{fmt(p['wall'])}, margin = {fmt(p['margin'])}, center = "
            f"[{fmt(p['x'])}, {fmt(p['y'])}])")


def _b_knurl(parser, positional, named):
    from .model import CadNode
    from .scadparse import _num
    d = NODE_TYPES["knurl"]["params"]
    params = {k: _num(named.get(k, v), v) for k, v in d.items()}
    if not isinstance(params["count"], str):
        params["count"] = max(int(params["count"]), 3)
    return CadNode("knurl", "Knurl", params)


def _b_honeycomb(parser, positional, named):
    from .model import CadNode
    from .scadparse import _num
    d = NODE_TYPES["honeycomb"]["params"]
    size = named.get("size")
    centre = named.get("center")
    w, h = (size + [d["height"]])[:2] if isinstance(size, list) \
        else (d["width"], d["height"])
    cx, cy = (centre + [0.0])[:2] if isinstance(centre, list) else (0.0, 0.0)
    return CadNode("honeycomb", "Honeycomb", dict(
        x=_num(cx, 0.0), y=_num(cy, 0.0), width=_num(w, d["width"]),
        height=_num(h, d["height"]),
        cell=_num(named.get("cell", d["cell"]), d["cell"]),
        wall=_num(named.get("wall", d["wall"]), d["wall"]),
        margin=_num(named.get("margin", d["margin"]), d["margin"])))


BUILDERS = {"kcad_knurl": _b_knurl, "kcad_honeycomb": _b_honeycomb}


def check(node, env):
    from . import mesh
    p = mesh.rp(node, env)
    if node.type == "knurl":
        if p["depth"] >= p["diameter"] / 2:
            return "knurl: the grooves are deeper than the radius"
        return None
    if p["cell"] <= 0 or p["wall"] <= 0:
        return "honeycomb: cell and wall must be above 0"
    if not honeycomb_centres(p["width"], p["height"], p["cell"], p["wall"],
                             p["margin"]):
        return "honeycomb: no whole cell fits — widen it or shrink the cell"
    return None


def outlines(node, env):
    from . import mesh
    p = mesh.rp(node, env)
    x, y = p["x"], p["y"]
    out = [[(x, y), (x + p["width"], y), (x + p["width"], y + p["height"]),
            (x, y + p["height"])]]
    for cx, cy in honeycomb_centres(p["width"], p["height"], p["cell"],
                                    p["wall"], p["margin"]):
        out.append(_hexagon(cx + x, cy + y, p["cell"]))
    return out


def tess(node, env, color, sel, selected):
    from . import mesh
    if node.type == "honeycomb":
        loops = mesh._oriented(node, mesh.node_outlines(node, env))
        tris = []
        for solid, holes in mesh.outline_regions(loops):
            tris.extend(((a[0], a[1], 0.0), (b[0], b[1], 0.0),
                         (c[0], c[1], 0.0))
                        for a, b, c in mesh._caps(solid, holes))
        return mesh._emit(tris, color, selected)
    p = mesh.rp(node, env)
    return mesh._emit(knurl_mesh(p["diameter"], p["length"], p["count"],
                                 p["depth"], p["angle"]), color, selected)
