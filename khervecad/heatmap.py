"""Heat maps on the part — the print check painted where it applies.

The print check says "walls down to 0.4 mm" or "18 % overhangs"; a heat
map shows WHERE, on the model, in the 3D view and in every picture
render_view takes (Blender's 3D-Print Toolbox and mesh-analysis
overlay). Each face gets a colour for its value:

* ``thickness`` — the wall behind the face: a ray from its centre
  straight into the part, to the first surface it meets. Red below the
  minimum wall, orange to twice it, then yellow → green → blue as the
  wall thickens; grey where the ray never meets the far side (an open
  mesh).
* ``overhang`` — how far the face looks down: green up to the limit
  minus 10°, yellow to the limit, red beyond it (needs support); faces
  lying on the build plate are blue.

Rays are Manifold's (4 µs each, every face measured) when csg.py has it,
else the print check's grid, sampled. Qt-free.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

KINDS = ("off", "thickness", "overhang")

RED, ORANGE, YELLOW = "#e53935", "#fb8c00", "#fdd835"
GREEN, TEAL, BLUE, GREY = "#43a047", "#00897b", "#1e88e5", "#9e9e9e"
#: faces measured without Manifold (the rest take their nearest's)
SAMPLES = 6000


def _normal_centroid(tri):
    a, b, c = tri
    u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
         u[0] * v[1] - u[1] * v[0])
    length = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
    if length < 1e-18:
        return None, None, 0.0
    n = (n[0] / length, n[1] / length, n[2] / length)
    cen = ((a[0] + b[0] + c[0]) / 3, (a[1] + b[1] + c[1]) / 3,
           (a[2] + b[2] + c[2]) / 3)
    return n, cen, length / 2


def thickness(tris, reach: float) -> list:
    """Per face: the wall thickness behind it (mm), None past *reach*
    or where the ray never comes out."""
    from . import csg
    tris = list(tris)
    solid = None
    if csg.available():
        solid = csg.to_manifold([(t, None, False) for t in tris], {})
    out = []
    if solid is not None:
        eps = 1e-6
        for tri in tris:
            n, cen, _a = _normal_centroid(tri)
            if n is None:
                out.append(None)
                continue
            start = (cen[0] - n[0] * eps, cen[1] - n[1] * eps,
                     cen[2] - n[2] * eps)
            end = (cen[0] - n[0] * reach, cen[1] - n[1] * reach,
                   cen[2] - n[2] * reach)
            hits = solid.ray_cast(start, end)
            out.append(hits[0].distance * reach if hits else None)
        return out
    from . import analysis
    grid = analysis._Grid(tris)
    stride = max(1, len(tris) // SAMPLES)
    measured = {}
    for i in range(0, len(tris), stride):
        n, cen, _a = _normal_centroid(tris[i])
        if n is None:
            continue
        d = (-n[0], -n[1], -n[2])
        far = tuple(cen[k] + d[k] * reach for k in range(3))
        best = None
        for j in grid.near(cen, far):
            if j == i:
                continue
            hit = analysis._ray_hit(cen, d, tris[j])
            if hit is not None and hit <= reach and (best is None
                                                     or hit < best):
                best = hit
        measured[i] = best
    for i in range(len(tris)):
        out.append(measured.get(i - i % stride))
    return out


def thickness_colour(t, min_wall: float) -> str:
    if t is None:
        return GREY
    if t < min_wall:
        return RED
    if t < 2 * min_wall:
        return ORANGE
    if t < 3 * min_wall:
        return YELLOW
    if t < 5 * min_wall:
        return GREEN
    if t < 10 * min_wall:
        return TEAL
    return BLUE


def overhang_colours(tris, limit: float):
    """(colours, fraction of the surface past the limit)."""
    if not tris:
        return [], 0.0
    floor = min(v[2] for t in tris for v in t)
    sin_limit = math.sin(math.radians(limit))
    sin_warn = math.sin(math.radians(max(limit - 10.0, 0.0)))
    out, over, total = [], 0.0, 0.0
    for tri in tris:
        n, _c, area = _normal_centroid(tri)
        total += area
        if n is None:
            out.append(GREY)
            continue
        down = -n[2]
        if down > 0.5 and all(v[2] - floor <= 0.1 for v in tri):
            out.append(BLUE)                    # on the build plate
        elif down > sin_limit:
            out.append(RED)
            over += area
        elif down > sin_warn:
            out.append(YELLOW)
        else:
            out.append(GREEN)
    return out, (over / total if total else 0.0)


def colours(tris, kind: str, min_wall: float = 0.8,
            overhang: float = 45.0):
    """(per-face preview colours, stats dict) for heat map *kind*."""
    tris = list(tris)
    if kind == "thickness":
        reach = max(min_wall * 12, 1e-3)
        values = thickness(tris, reach)
        cols = [thickness_colour(t, min_wall) for t in values]
        known = [t for t in values if t is not None]
        area_thin = total = 0.0
        for tri, t in zip(tris, values):
            _n, _c, a = _normal_centroid(tri)
            total += a
            if t is not None and t < min_wall:
                area_thin += a
        stats = dict(kind=kind, min_wall=min_wall,
                     thinnest=min(known) if known else None,
                     thin_fraction=area_thin / total if total else 0.0,
                     legend=f"red < {min_wall:g}, orange < "
                            f"{2 * min_wall:g}, yellow < {3 * min_wall:g},"
                            f" green < {5 * min_wall:g}, teal < "
                            f"{10 * min_wall:g}, blue thicker, grey open")
    elif kind == "overhang":
        cols, frac = overhang_colours(tris, overhang)
        stats = dict(kind=kind, overhang_limit=overhang,
                     overhang_fraction=frac,
                     legend=f"red steeper than {overhang:g}° (needs "
                            f"support), yellow within 10° of it, green "
                            "fine, blue on the plate")
    else:
        return None, {}
    return [(c, 1.0, "Matte") for c in cols], stats
