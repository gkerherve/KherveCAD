"""Converting between ordinary objects and Lego (Qt-free).

- **to_lego** — any part to bricks: its coloured preview mesh is
  voxelized on the Lego grid (8 mm columns; layers a brick or a plate
  high) at a chosen scale, filled solid by ray parity up each column,
  and every cell painted with the colour of the nearest surface the ray
  crossed, matched to the nearest LEGO colour. `examples_lego.Scene`
  then packs the cells into standard bricks and drops the studs another
  brick covers, so only the outside costs triangles.
- **to_solid** — the other way: any brick build (a set, a Lego Builder
  model, a legoized part) voxelized on its own grid at plate resolution
  and fused into as few boxes as possible per colour — one smooth solid
  with no studs and no seams, to print or to go on modelling. A cell
  counts when the build covers most of its height, so studs (1.8 of a
  plate's 3.2 mm) drop out, and the air inside a hollow brick is closed
  up.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from .library_lego import (BRICK_H, COLORS, PITCH, PLATE_H, TOP,
                           TRANSLUCENT)
from .model import CadNode

#: a conversion bigger than this many cells is refused (ask for fewer
#: studs): pure Python, and a few thousand bricks is already a big set
MAX_CELLS = 120000
#: a part with no colour of its own becomes this
DEFAULT_COLOUR = "Light bluish grey"
#: to_solid: the share of a cell's height the build must cover
COVER = 0.75
#: to_solid: air gaps shorter than this inside a column are the hollow
#: underside of a brick, not a real opening (one is a brick high)
HOLLOW = BRICK_H - TOP + 0.05


# --------------------------------------------------------------- colour

def _rgb(value):
    """(r, g, b) 0..255 of a "#rrggbb" / "#rgb" string, or None."""
    s = str(value).strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        return None
    try:
        return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


_PALETTE = [(name, _rgb(hexcol)) for name, hexcol in COLORS.items()]


def nearest_colour(colour):
    """The LEGO colour name nearest a preview colour tuple
    ``(colour, alpha[, material])`` (or None). See-through colours
    (alpha below 0.9) match among the clear ones only."""
    if colour is None:
        return DEFAULT_COLOUR
    rgb = _rgb(colour[0])
    if rgb is None:
        return DEFAULT_COLOUR
    clear = len(colour) > 1 and float(colour[1]) < 0.9
    best, best_d = DEFAULT_COLOUR, None
    for name, ref in _PALETTE:
        if (name in TRANSLUCENT) != clear:
            continue
        # weighted RGB distance: the eye is kindest to blue
        d = (2 * (rgb[0] - ref[0]) ** 2 + 4 * (rgb[1] - ref[1]) ** 2
             + 3 * (rgb[2] - ref[2]) ** 2)
        if best_d is None or d < best_d:
            best, best_d = name, d
    return best


# ------------------------------------------------------------ voxelizer

def column_hits(tris, colours, cell, origin):
    """For every grid column (i, j), the surfaces a vertical ray through
    its centre crosses: {(i, j): [(z, step, colour), ...]} sorted by z,
    *step* +1 where the ray enters a solid (the surface faces down) and
    -1 where it leaves. Two hits of one surface at a shared edge count
    once, but a piece's top and the bottom of the one stacked on it —
    the same height, opposite ways — both stay: dropping one broke the
    count, and a house's walls came out the colour of its baseplate."""
    sx, sy = cell[0], cell[1]
    ox, oy = origin[0], origin[1]
    cols = {}
    for tri, colour in zip(tris, colours):
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = tri
        det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(det) < 1e-12:
            continue                         # seen edge-on from below
        # the outward normal's z: CCW from outside, so up = leaving
        nz = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
        step = -1 if nz > 0 else 1
        i0 = math.ceil((min(ax, bx, cx) - ox) / sx - 0.5)
        i1 = math.floor((max(ax, bx, cx) - ox) / sx - 0.5)
        j0 = math.ceil((min(ay, by, cy) - oy) / sy - 0.5)
        j1 = math.floor((max(ay, by, cy) - oy) / sy - 0.5)
        for i in range(i0, i1 + 1):
            px = ox + (i + 0.5) * sx
            for j in range(j0, j1 + 1):
                py = oy + (j + 0.5) * sy
                w0 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / det
                w1 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / det
                w2 = 1.0 - w0 - w1
                if w0 < -1e-9 or w1 < -1e-9 or w2 < -1e-9:
                    continue
                cols.setdefault((i, j), []).append(
                    (w0 * az + w1 * bz + w2 * cz, step, colour))
    for key, hits in cols.items():
        hits.sort(key=lambda h: (h[0], h[1]))      # leave before entering
        dedup = [hits[0]]
        for hit in hits[1:]:
            last = dedup[-1]
            if hit[1] == last[1] and hit[0] - last[0] <= 1e-6:
                continue                     # one surface, a shared edge
            dedup.append(hit)
        cols[key] = dedup
    return cols


def _intervals(hits):
    """The inside of one column, [(z0, z1)] merged where they touch:
    inside wherever more solids have been entered than left. A mesh
    wound inside out (no interval that way) falls back to parity."""
    spans, depth, start = [], 0, None
    for z, step, _c in hits:
        before, depth = depth, depth + step
        if before <= 0 < depth:
            start = z
        elif depth <= 0 < before and start is not None:
            spans.append([start, z])
            start = None
    if not spans:
        spans = [[hits[n][0], hits[n + 1][0]]
                 for n in range(0, len(hits) - 1, 2)]
    merged = []
    for z0, z1 in spans:
        if merged and z0 - merged[-1][1] <= 1e-6:
            merged[-1][1] = max(merged[-1][1], z1)
        else:
            merged.append([z0, z1])
    return merged


def voxelize(tris, colours, cell, origin, cover=0.5, close_below=0.0):
    """{(i, j, k): colour} for the cells the solid fills. A cell is
    filled when the inside of its column covers at least *cover* of its
    height, and takes the colour of the last solid entered below its
    middle (colour() paints whole solids, so that is the piece it
    belongs to). Gaps inside a column shorter than *close_below* are
    closed first, and so is the air under the lowest surface down to
    the model's floor when it is that short (a hollow brick)."""
    import bisect
    sz, oz = cell[2], origin[2]
    out = {}
    for (i, j), hits in column_hits(tris, colours, cell, origin).items():
        spans = _intervals(hits)
        if not spans:
            continue
        if close_below > 0:
            closed = [spans[0]]
            for z0, z1 in spans[1:]:
                if z0 - closed[-1][1] < close_below:
                    closed[-1][1] = z1
                else:
                    closed.append([z0, z1])
            if closed[0][0] - oz < close_below:
                closed[0][0] = oz
            spans = closed
        entries = [(z, c) for z, step, c in hits if step > 0] or \
            [(z, c) for z, _s, c in hits]
        entry_z = [z for z, _c in entries]
        cover_of = {}
        for z0, z1 in spans:
            for k in range(math.floor((z0 - oz) / sz),
                           math.ceil((z1 - oz) / sz)):
                lo, hi = oz + k * sz, oz + (k + 1) * sz
                cover_of[k] = cover_of.get(k, 0.0) + max(
                    0.0, min(hi, z1) - max(lo, z0))
        for k, covered in cover_of.items():
            if covered >= cover * sz - 1e-9:
                mid = oz + (k + 0.5) * sz
                n = bisect.bisect_right(entry_z, mid) - 1
                out[(i, j, k)] = entries[max(n, 0)][1]
        if len(out) > MAX_CELLS:
            raise ValueError(
                f"more than {MAX_CELLS} cells — choose fewer studs")
    return out


def bounds(tris):
    pts = [v for t in tris for v in t]
    lo = [min(p[k] for p in pts) for k in range(3)]
    hi = [max(p[k] for p in pts) for k in range(3)]
    return lo, hi


# ---------------------------------------------------------------- Lego

def to_lego(tris, colours, studs_across=24, plates=False, colour=None,
            name="Lego"):
    """A brick model of the mesh: *studs_across* studs along its longer
    horizontal side (the height follows, a brick or a plate a layer).
    *colour* forces one LEGO colour instead of matching the part's own.
    Returns (model node, info dict)."""
    from .examples_lego import Scene
    if not tris:
        raise ValueError("nothing to convert — the part has no solid")
    lo, hi = bounds(tris)
    span = max(hi[0] - lo[0], hi[1] - lo[1], 1e-6)
    s = span / max(int(studs_across), 1)          # model mm per stud
    layer = PLATE_H if plates else BRICK_H
    cell = (s, s, s * layer / PITCH)
    cells = voxelize(tris, colours, cell, lo)
    if not cells:
        raise ValueError("the part has no inside to fill — is it a "
                         "closed solid?")
    names = {}
    voxels = {}
    for key, c in cells.items():
        if colour:
            label = colour
        else:
            if c not in names:
                names[c] = nearest_colour(c)
            label = names[c]
        voxels[key] = (label, label)
    scene = Scene(seed=7)
    scene.add_voxels(voxels, height=layer)
    node = scene.to_node(name)
    pieces = len(scene.pieces)
    i_span = max(i for i, _j, _k in cells) - min(i for i, _j, _k in cells) + 1
    j_span = max(j for _i, j, _k in cells) - min(j for _i, j, _k in cells) + 1
    k_span = max(k for _i, _j, k in cells) - min(k for _i, _j, k in cells) + 1
    return node, dict(pieces=pieces, cells=len(cells),
                      studs=(i_span, j_span),
                      size_mm=(i_span * PITCH, j_span * PITCH,
                               k_span * layer),
                      scale=PITCH / s)


# --------------------------------------------------------------- solid

def boxes(cells):
    """Greedy merge of {(i, j, k): value} into boxes of one value:
    [(i, j, k, ni, nj, nk, value)] — runs along i, then whole rows along
    j, then whole slabs along k."""
    left = dict(cells)
    out = []
    for i, j, k in sorted(cells, key=lambda c: (c[2], c[1], c[0])):
        if (i, j, k) not in left:
            continue
        v = left[(i, j, k)]
        ni = 1
        while left.get((i + ni, j, k)) == v:
            ni += 1
        nj = 1
        while all(left.get((i + a, j + nj, k)) == v for a in range(ni)):
            nj += 1
        nk = 1
        while all(left.get((i + a, j + b, k + nk)) == v
                  for a in range(ni) for b in range(nj)):
            nk += 1
        for a in range(ni):
            for b in range(nj):
                for c in range(nk):
                    del left[(i + a, j + b, k + c)]
        out.append((i, j, k, ni, nj, nk, v))
    return out


def to_solid(tris, colours, name="Solid"):
    """One stud-free, seam-free solid of a brick build: plate-resolution
    cells on the build's own grid, fused into boxes per colour (a group
    per colour). Returns (node, info)."""
    from .library_lego import colour as lego_colour
    if not tris:
        raise ValueError("nothing to fuse — the selection has no bricks")
    lo, _hi = bounds(tris)
    origin = (0.0, 0.0, lo[2])                    # the stud grid itself
    cells = voxelize(tris, colours, (PITCH, PITCH, PLATE_H), origin,
                     cover=COVER, close_below=HOLLOW)
    if not cells:
        raise ValueError("nothing solid found on the Lego grid")
    names = {}
    by_colour = {}
    for key, c in cells.items():
        if c not in names:
            names[c] = nearest_colour(c)
        by_colour.setdefault(names[c], {})[key] = names[c]
    root = CadNode("union", name)
    count = 0
    for label, group in by_colour.items():
        inner = CadNode("union", label)
        for i, j, k, ni, nj, nk, _v in boxes(group):
            inner.add(CadNode("cube", "Block", dict(
                x=i * PITCH, y=j * PITCH, z=lo[2] + k * PLATE_H,
                width=ni * PITCH, depth=nj * PITCH, height=nk * PLATE_H,
                center=False)))
            count += 1
        root.add(lego_colour(inner, label))
    return root, dict(blocks=count, cells=len(cells),
                      colours=len(by_colour))
