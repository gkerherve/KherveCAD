"""The **Bridges** library: famous bridges modelled from their published
dimensions, at true size (or a model scale), mm, water level z = 0,
running along X and centred.

- Golden Gate (San Francisco, 1937): main span 1280 m, side spans
  343 m, 2737 m long; art-deco towers 227 m above the water with four
  portal struts over the deck and stepped setbacks; deck 67 m above the
  water, 27 m wide, on a 7.6 m Warren stiffening truss; two 0.92 m main
  cables hung in parabolas, suspenders every 15.24 m; concrete tower
  piers, anchorage blocks and the approach viaducts; International
  Orange.
- Tower Bridge (London, 1894): two 65 m Gothic stone towers with corner
  turrets and spires, bascules over the 61 m opening, the two high-level
  lattice walkways at 42 m, and the suspension side spans hung from
  chain-like girders to the shore towers; stone and pale blue steel.
- Brooklyn Bridge (New York, 1883): main span 486 m, granite towers 84 m
  above the water pierced by two pointed Gothic arches, deck 41 m up,
  four main cables with the diagonal stays fanning from the towers.
- Sydney Harbour Bridge (1932): a 503 m two-hinged steel through-arch
  rising 134 m, the deck hung at 49 m, granite pylons 89 m tall at both
  ends of the arch, approach trusses.

Everything repeated (hangers, truss members, stays) is written into one
closed polyhedron per colour with `landmark_kit.Kit`, so a bridge is a
few nodes of real geometry.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from .landmark_kit import Kit, _f, lerp
from .model import CadNode

CATEGORY = "Bridges"

ORANGE = "#c0362c"
CONCRETE = "#b9b4aa"
ASPHALT = "#3d3f43"
WATER = "#2f6f8f"
STONE = "#c9b48c"
GRANITE = "#b3a58c"
STEEL_BLUE = "#7fb2d4"
STEEL_GREY = "#7d8a90"
DARK = "#2f3236"
WHITE = "#f1efe9"

#: default_part picks the SECOND entry: real size
SCALES = {"Model 1:2000": 1 / 2000.0, "Real size": 1.0,
          "Model 1:500": 1 / 500.0}


def _scaled(node, dims):
    k = _f(dims.get("scale"), 1.0)
    if abs(k - 1.0) < 1e-9:
        return node
    s = CadNode("scale", node.name, dict(x=k, y=k, z=k))
    s.add(node)
    return s


def _sizes():
    return {name: dict(scale=k) for name, k in SCALES.items()}


def _water(kit, x0, x1, half_width):
    kit.box(x0, -half_width, -8000, x1, half_width, 0, WATER, "Plastic")


def _deck(kit, x0, x1, z, width, colour, truss_depth=0.0, panel=15240.0,
          truss_colour=None, walks=True):
    """A road deck from x0 to x1 at road level z: slab, lane markings,
    kerbs, railings and (optionally) a stiffening truss under each edge
    with bottom lateral bracing."""
    hw = width / 2
    kit.box(x0, -hw, z - 700, x1, hw, z, CONCRETE, "Concrete")
    road = hw - (3000 if walks else 600)
    kit.box(x0, -road, z, x1, road, z + 60, ASPHALT, "Matte")
    lanes = 6
    for k in range(1, lanes):
        y = -road + 2 * road * k / lanes
        dash, gap = 3000.0, 9000.0
        x = x0
        while x + dash < x1:
            kit.box(x, y - 60, z + 60, x + dash, y + 60, z + 66, WHITE)
            x += dash + gap
    if walks:
        for s in (-1, 1):
            kit.box(x0, s * road, z, x1, s * hw, z + 250, CONCRETE,
                    "Concrete")
            # railing: top rail + posts
            kit.bar((x0, s * (hw - 80), z + 1300), (x1, s * (hw - 80),
                                                    z + 1300), 50, colour,
                    "Plastic")
            n = int((x1 - x0) // 3000)
            for i in range(n + 1):
                x = x0 + i * (x1 - x0) / max(n, 1)
                kit.bar((x, s * (hw - 80), z + 250),
                        (x, s * (hw - 80), z + 1300), 35, colour, "Plastic")
    if truss_depth > 0:
        tc = truss_colour or colour
        panels = max(1, int(round((x1 - x0) / panel)))
        for s in (-1, 1):
            y = s * (hw - 400)
            kit.truss((x0, y, z - 700), (x1, y, z - 700),
                      (x0, y, z - 700 - truss_depth),
                      (x1, y, z - 700 - truss_depth), panels, 380, 220, tc,
                      "Plastic")
        for i in range(panels):
            xa = x0 + i * (x1 - x0) / panels
            xb = x0 + (i + 1) * (x1 - x0) / panels
            zb = z - 700 - truss_depth
            kit.bar((xa, -hw + 400, zb), (xb, hw - 400, zb), 180, tc,
                    "Plastic")
            kit.bar((xa, -hw + 400, zb), (xa, hw - 400, zb), 180, tc,
                    "Plastic")


# ------------------------------------------------------------ Golden Gate
def build_golden_gate(dims):
    kit = Kit()
    span, side = 1280000.0, 343000.0
    total = 2737000.0
    tower_h, deck_z = 227000.0, 67000.0
    width = 27400.0
    cable_y = 13700.0
    towers = (-span / 2, span / 2)
    anchor = span / 2 + side
    end = total / 2

    _water(kit, -end - 20000, end + 20000, 300000)

    # deck over the whole length, truss under the suspended part
    _deck(kit, -anchor, anchor, deck_z, width, ORANGE, truss_depth=7600.0,
          panel=15240.0)
    # approach viaducts: lower deck on concrete piers down to the shores
    for s in (-1, 1):
        a, b = s * anchor, s * end
        x0, x1 = sorted((a, b))
        _deck(kit, x0, x1, deck_z, width, ORANGE, truss_depth=4500.0,
              panel=20000.0)
        n = int((x1 - x0) // 60000)
        for i in range(1, n + 1):
            x = x0 + i * (x1 - x0) / (n + 1)
            kit.box(x - 2500, -width / 2 + 1000, 0, x + 2500,
                    width / 2 - 1000, deck_z - 12100, CONCRETE, "Concrete")
        # anchorage: a massive stepped block where the cables tie down
        kit.box(a - s * 0 - 30000, -30000, 0, a + 30000, 30000, 30000,
                CONCRETE, "Concrete")
        kit.box(a - 22000, -26000, 30000, a + 22000, 26000, deck_z - 8400,
                CONCRETE, "Concrete")

    # towers: two legs, stepped setbacks, four portal struts above the
    # deck, a strut and X bracing below it, on a concrete pier
    for tx in towers:
        kit.box(tx - 40000, -48000, -2000, tx + 40000, 48000, 12000,
                CONCRETE, "Concrete")                          # pier
        kit.box(tx - 30000, -38000, 12000, tx + 30000, 38000, 15000,
                CONCRETE, "Concrete")
        steps = [(15000, 10000, 16000), (deck_z, 9400, 14800),
                 (120000, 8800, 13000), (160000, 8200, 11000),
                 (195000, 7600, 9400), (tower_h - 6000, 7000, 8000)]
        for s in (-1, 1):
            yc = s * (cable_y + 1500)
            for (z0, w0, d0), (z1, w1, d1) in zip(steps, steps[1:]):
                kit.frustum(tx, yc, z0, z1, (w0, d0), (w1 * 1.02, d1 * 1.02),
                            ORANGE, "Plastic")
                # the art-deco setback ledge
                kit.box(tx - w1 / 2 - 300, yc - d1 / 2 - 300, z1 - 900,
                        tx + w1 / 2 + 300, yc + d1 / 2 + 300, z1, ORANGE,
                        "Plastic")
                # vertical fluting: recessed-looking ribs on the faces
                for f in (-0.25, 0.25):
                    kit.box(tx + f * w1 - 250, yc - d1 / 2 - 150, z0,
                            tx + f * w1 + 250, yc - d1 / 2, z1 - 900, ORANGE,
                            "Plastic")
                    kit.box(tx + f * w1 - 250, yc + d1 / 2, z0,
                            tx + f * w1 + 250, yc + d1 / 2 + 150, z1 - 900,
                            ORANGE, "Plastic")
            # saddle house on top
            kit.box(tx - 4000, yc - 4500, tower_h - 6000, tx + 4000,
                    yc + 4500, tower_h, ORANGE, "Plastic")
        inner = cable_y + 1500 - 7000
        for zc, h in ((deck_z + 26000, 7000), (deck_z + 66000, 6500),
                      (deck_z + 104000, 6000), (tower_h - 16000, 9000)):
            kit.box(tx - 3500, -inner, zc, tx + 3500, inner, zc + h, ORANGE,
                    "Plastic")
            # the stepped art-deco panel on the strut's face
            kit.box(tx - 3700, -inner * 0.6, zc + h * 0.25, tx + 3700,
                    inner * 0.6, zc + h * 0.75, ORANGE, "Plastic")
        kit.box(tx - 4000, -inner, deck_z - 9000, tx + 4000, inner,
                deck_z - 700, ORANGE, "Plastic")
        for zb, zt in ((16000, 40000), (40000, deck_z - 9000)):
            kit.bar((tx, -inner, zb), (tx, inner, zt), 900, ORANGE, "Plastic")
            kit.bar((tx, inner, zb), (tx, -inner, zt), 900, ORANGE, "Plastic")

    # main cables: parabola over the main span, sagging chords over the
    # side spans down to the anchorages; suspenders every 50 ft
    top = tower_h - 1500
    low = deck_z + 2500

    def main_z(x):
        t = x / (span / 2)
        return low + (top - low) * t * t

    def side_z(x, s):
        a = s * span / 2
        b = s * anchor
        t = (x - a) / (b - a)
        chord = lerp(top, deck_z - 4000, t)
        return chord - 16000 * 4 * t * (1 - t)

    for yc in (-cable_y, cable_y):
        pts = [(s * anchor, yc, deck_z - 4000) for s in (-1,)]
        n = 60
        pts += [(lerp(-anchor, -span / 2, k / 20), yc,
                 side_z(lerp(-anchor, -span / 2, k / 20), -1))
                for k in range(1, 21)]
        pts += [(lerp(-span / 2, span / 2, k / n), yc,
                 main_z(lerp(-span / 2, span / 2, k / n)))
                for k in range(1, n + 1)]
        pts += [(lerp(span / 2, anchor, k / 20), yc,
                 side_z(lerp(span / 2, anchor, k / 20), 1))
                for k in range(1, 21)]
        kit.path(pts, 460, ORANGE, "Plastic", sides=10)
        step = 15240.0
        x = -anchor + step
        while x < anchor - step / 2:
            if abs(abs(x) - span / 2) > 6000:
                zc = main_z(x) if abs(x) < span / 2 else \
                    side_z(x, 1 if x > 0 else -1)
                if zc > deck_z + 800:
                    kit.bar((x, yc, deck_z + 400), (x, yc, zc), 90, ORANGE,
                            "Plastic", sides=4)
            x += step
        # cable bands where the suspenders clamp are too small to see
    return kit.node("Golden Gate Bridge")


# ------------------------------------------------------------ Tower Bridge
def build_tower_bridge(dims):
    kit = Kit()
    opening, side = 61000.0, 82000.0
    tower_w, tower_d, tower_h = 18000.0, 30000.0, 65000.0
    deck_z = 9000.0
    walk_z = 42000.0
    width = 18000.0
    tx = opening / 2 + tower_w / 2
    shore = tx + tower_w / 2 + side
    _water(kit, -shore - 20000, shore + 20000, 80000)

    for s in (-1, 1):
        cx = s * tx
        # pier
        kit.box(cx - tower_w / 2 - 3000, -tower_d / 2 - 3000, -2000,
                cx + tower_w / 2 + 3000, tower_d / 2 + 3000, deck_z - 1500,
                GRANITE, "Stone")
        # tower body with an arch-like passage (piers left and right)
        for py in (-1, 1):
            kit.box(cx - tower_w / 2, py * (width / 2 + 500), deck_z - 1500,
                    cx + tower_w / 2, py * tower_d / 2, tower_h - 12000,
                    STONE, "Stone")
        kit.box(cx - tower_w / 2, -width / 2 - 500, deck_z + 11000,
                cx + tower_w / 2, width / 2 + 500, tower_h - 12000, STONE,
                "Stone")
        # string courses and windows
        for z in (deck_z + 11000, 30000, walk_z - 2000, tower_h - 12500):
            kit.box(cx - tower_w / 2 - 400, -tower_d / 2 - 400, z,
                    cx + tower_w / 2 + 400, tower_d / 2 + 400, z + 800,
                    "#d9c9a3", "Stone")
        for z in (22000, 34000, 48000):
            for wy in (-8000, 0, 8000):
                kit.box(cx - tower_w / 2 - 100, wy - 900, z, cx - tower_w / 2,
                        wy + 900, z + 5000, "#3a3f47", "Plastic")
                kit.box(cx + tower_w / 2, wy - 900, z, cx + tower_w / 2 + 100,
                        wy + 900, z + 5000, "#3a3f47", "Plastic")
        # corner turrets with spires, the central roof and its spire
        for ox in (-1, 1):
            for oy in (-1, 1):
                x, y = cx + ox * tower_w / 2, oy * tower_d / 2
                kit.cone(x, y, deck_z, tower_h - 6000, 2300, 2100, STONE,
                         "Stone", sides=8)
                kit.cone(x, y, tower_h - 6000, tower_h + 5000, 2400, 0,
                         "#4e5156", "Slate", sides=8)
                kit.sphere((x, y, tower_h + 5200), 350, "#c9a54a", "Gold")
        kit.solid([(cx - tower_w / 2, -tower_d / 2, tower_h - 12000),
                   (cx + tower_w / 2, -tower_d / 2, tower_h - 12000),
                   (cx + tower_w / 2, tower_d / 2, tower_h - 12000),
                   (cx - tower_w / 2, tower_d / 2, tower_h - 12000),
                   (cx, -tower_d / 2 + 6000, tower_h + 2000),
                   (cx, tower_d / 2 - 6000, tower_h + 2000)], "#4e5156",
                  "Slate")
        kit.cone(cx, 0, tower_h + 2000, tower_h + 12000, 2200, 0, "#4e5156",
                 "Slate", sides=8)
        kit.sphere((cx, 0, tower_h + 12300), 500, "#c9a54a", "Gold")

    # the high-level walkways: two lattice girders between the towers
    for py in (-1, 1):
        y = py * 5000
        a, b = -tx + tower_w / 2, tx - tower_w / 2
        kit.truss((a, y - 1800, walk_z + 3500), (b, y - 1800, walk_z + 3500),
                  (a, y - 1800, walk_z), (b, y - 1800, walk_z), 14, 350, 160,
                  STEEL_BLUE, "Plastic")
        kit.truss((a, y + 1800, walk_z + 3500), (b, y + 1800, walk_z + 3500),
                  (a, y + 1800, walk_z), (b, y + 1800, walk_z), 14, 350, 160,
                  STEEL_BLUE, "Plastic")
        kit.box(a, y - 1800, walk_z - 300, b, y + 1800, walk_z, WHITE)
        kit.box(a, y - 1900, walk_z + 3500, b, y + 1900, walk_z + 3900,
                STEEL_BLUE, "Plastic")
    # the bascules (closed) and the side decks
    _deck(kit, -tx + tower_w / 2, tx - tower_w / 2, deck_z, width,
          STEEL_BLUE, truss_depth=0.0)
    for s in (-1, 1):
        x0, x1 = sorted((s * (tx + tower_w / 2), s * shore))
        _deck(kit, x0, x1, deck_z, width, STEEL_BLUE)
        # suspension side spans: a curved chain girder from the tower top
        # of walkway height down to the shore tower
        shore_x = s * shore
        kit.box(shore_x - s * 0 - 6000, -tower_d / 2, -2000, shore_x + 6000,
                tower_d / 2, 22000, STONE, "Stone")
        for oy in (-1, 1):
            y = oy * (width / 2 + 300)
            pts = []
            for k in range(21):
                t = k / 20
                x = lerp(s * (tx + tower_w / 2), shore_x, t)
                z = lerp(walk_z - 4000, 20000, t) - 9000 * 4 * t * (1 - t)
                pts.append((x, y, z))
            kit.path(pts, 700, STEEL_BLUE, "Plastic", sides=6)
            for k in range(1, 20, 2):
                x, _y, z = pts[k]
                kit.bar((x, y, deck_z + 250), (x, y, z), 250, STEEL_BLUE,
                        "Plastic")
    return kit.node("Tower Bridge")


# ---------------------------------------------------------- Brooklyn Bridge
def build_brooklyn(dims):
    kit = Kit()
    span, side = 486000.0, 283000.0
    tower_h, deck_z = 84000.0, 41000.0
    width = 26000.0
    towers = (-span / 2, span / 2)
    anchor = span / 2 + side
    _water(kit, -anchor - 20000, anchor + 20000, 200000)
    _deck(kit, -anchor, anchor, deck_z, width, DARK, truss_depth=5000.0,
          panel=10000.0, truss_colour="#6f6a62")
    # the raised central promenade
    kit.box(-anchor, -2500, deck_z + 2500, anchor, 2500, deck_z + 2700,
            "#9a7a55")
    tw, td = 42000.0, 12000.0
    for tx in towers:
        kit.box(tx - td / 2 - 2000, -tw / 2 - 2000, -2000, tx + td / 2 + 2000,
                tw / 2 + 2000, 12000, GRANITE, "Stone")
        # three piers between two pointed arches
        pier_w = (tw - 2 * 10000) / 3
        for i in range(3):
            y0 = -tw / 2 + i * (pier_w + 10000)
            kit.frustum(tx, y0 + pier_w / 2, 12000, 62000,
                        (td, pier_w), (td * 0.92, pier_w * 0.92), GRANITE,
                        "Stone")
        # the Gothic arches: pointed tops from two leaning slabs each
        for i in range(2):
            y0 = -tw / 2 + pier_w + i * (pier_w + 10000)
            kit.solid([(tx - td * 0.46, y0, 48000), (tx + td * 0.46, y0,
                                                      48000),
                       (tx - td * 0.46, y0 + 10000, 48000),
                       (tx + td * 0.46, y0 + 10000, 48000),
                       (tx - td * 0.46, y0 + 5000, 62000),
                       (tx + td * 0.46, y0 + 5000, 62000),
                       (tx - td * 0.46, y0, 62000),
                       (tx + td * 0.46, y0, 62000)], GRANITE, "Stone")
            kit.solid([(tx - td * 0.46, y0 + 10000, 48000),
                       (tx + td * 0.46, y0 + 10000, 48000),
                       (tx - td * 0.46, y0 + 10000, 62000),
                       (tx + td * 0.46, y0 + 10000, 62000),
                       (tx - td * 0.46, y0 + 5000, 62000),
                       (tx + td * 0.46, y0 + 5000, 62000)], GRANITE, "Stone")
        kit.frustum(tx, 0, 62000, tower_h - 2500, (td * 0.92, tw * 0.92),
                    (td * 0.88, tw * 0.88), GRANITE, "Stone")
        kit.box(tx - td * 0.5, -tw * 0.47, tower_h - 2500, tx + td * 0.5,
                tw * 0.47, tower_h, "#c4b69c", "Stone")
        for y in (-tw * 0.3, tw * 0.3):                  # blind windows
            kit.box(tx - td * 0.45 - 100, y - 1500, 66000, tx - td * 0.45,
                    y + 1500, 78000, "#6f6454", "Stone")
    cable_ys = (-width / 2 + 1500, -3500, 3500, width / 2 - 1500)
    top, low = tower_h + 1000, deck_z + 3000

    def cable_z(x):
        if abs(x) <= span / 2:
            t = x / (span / 2)
            return low + (top - low) * t * t
        s = 1 if x > 0 else -1
        t = (x - s * span / 2) / (s * anchor - s * span / 2)
        return lerp(top, deck_z, t) - 9000 * 4 * t * (1 - t)

    for y in cable_ys:
        pts = [(lerp(-anchor, anchor, k / 120), y,
                cable_z(lerp(-anchor, anchor, k / 120))) for k in range(121)]
        kit.path(pts, 420, DARK, "Metal", sides=8)
        x = -anchor + 6000
        while x < anchor:
            zc = cable_z(x)
            if zc > deck_z + 1500 and abs(abs(x) - span / 2) > 4000:
                kit.bar((x, y, deck_z + 300), (x, y, zc), 60, DARK, "Metal")
            x += 6000
    # the diagonal stays fanning from each tower top down to the deck
    for tx in towers:
        for y in (cable_ys[0], cable_ys[-1]):
            for k in range(1, 13):
                for sgn in (-1, 1):
                    xd = tx + sgn * k * 11000
                    if abs(xd) > anchor:
                        continue
                    kit.bar((tx, y, tower_h - 6000), (xd, y, deck_z + 300),
                            80, DARK, "Metal")
    return kit.node("Brooklyn Bridge")


# ----------------------------------------------------- Sydney Harbour
def build_sydney(dims):
    kit = Kit()
    span = 503000.0
    rise, deck_z = 134000.0, 49000.0
    width = 49000.0
    pylon_h = 89000.0
    end = span / 2 + 60000 + 150000
    _water(kit, -end, end, 250000)
    _deck(kit, -end, end, deck_z, width, STEEL_GREY, truss_depth=0.0)
    panels = 28
    for y in (-width / 2 + 1500, width / 2 - 1500):
        top, bottom = [], []
        for k in range(panels + 1):
            t = k / panels
            x = lerp(-span / 2, span / 2, t)
            u = x / (span / 2)
            zt = rise * (1 - u * u) + 6000 + 12000 * u * u   # upper chord
            zb = rise * (1 - u * u) - 18000 * (1 - u * u) - 4000
            top.append((x, y, zt))
            bottom.append((x, y, max(zb, 0.0)))
        for k in range(panels):
            kit.bar(top[k], top[k + 1], 1500, STEEL_GREY, "Metal")
            kit.bar(bottom[k], bottom[k + 1], 1800, STEEL_GREY, "Metal")
            kit.bar(top[k], bottom[k], 700, STEEL_GREY, "Metal")
            # diagonals lean towards the crown on each half
            if k < panels // 2:
                kit.bar(bottom[k], top[k + 1], 600, STEEL_GREY, "Metal")
            else:
                kit.bar(top[k], bottom[k + 1], 600, STEEL_GREY, "Metal")
        kit.bar(top[-1], bottom[-1], 700, STEEL_GREY, "Metal")
        # hangers from the lower chord to the deck
        for k in range(2, panels - 1):
            x, _y, zb = bottom[k]
            if zb > deck_z + 2000:
                kit.bar((x, y, deck_z), (x, y, zb), 400, STEEL_GREY, "Metal")
    # cross bracing between the two arch ribs
    for k in range(1, panels, 2):
        t = k / panels
        x = lerp(-span / 2, span / 2, t)
        u = x / (span / 2)
        z = rise * (1 - u * u) + 3000
        if z > deck_z + 8000:
            kit.bar((x, -width / 2 + 1500, z), (x, width / 2 - 1500, z), 500,
                    STEEL_GREY, "Metal")
    # granite pylons at both ends of the arch, approach trusses
    for s in (-1, 1):
        for oy in (-1, 1):
            cx, cy = s * (span / 2 + 18000), oy * (width / 2 + 2000)
            kit.frustum(cx, cy, 0, pylon_h, (30000, 22000), (26000, 19000),
                        GRANITE, "Stone")
            kit.box(cx - 14000, cy - 10500, pylon_h - 4000, cx + 14000,
                    cy + 10500, pylon_h - 2500, "#c8bba1", "Stone")
            for z in (60000, 72000):
                kit.box(cx - 6000, cy - 11000 - 50, z, cx + 6000, cy - 11000,
                        z + 8000, "#6f6454", "Stone")
        x0, x1 = sorted((s * (span / 2 + 36000), s * end))
        n = int((x1 - x0) // 60000)
        for i in range(n + 1):
            x = x0 + i * (x1 - x0) / max(n, 1)
            kit.box(x - 3000, -width / 2 + 3000, 0, x + 3000, width / 2 - 3000,
                    deck_z - 6000, GRANITE, "Stone")
        for y in (-width / 2 + 1500, width / 2 - 1500):
            kit.truss((x0, y, deck_z - 700), (x1, y, deck_z - 700),
                      (x0, y, deck_z - 6000), (x1, y, deck_z - 6000),
                      max(2, n * 4), 500, 300, STEEL_GREY, "Metal")
    return kit.node("Sydney Harbour Bridge")


def _entry(label, build):
    return dict(label=label, category=CATEGORY, sizes=_sizes(),
                build=lambda dims, b=build: _scaled(b(dims), dims),
                fields=[("scale", "Scale")])


PARTS = {
    "bridge_golden_gate": _entry("Golden Gate Bridge (San Francisco)",
                                 build_golden_gate),
    "bridge_tower": _entry("Tower Bridge (London)", build_tower_bridge),
    "bridge_brooklyn": _entry("Brooklyn Bridge (New York)", build_brooklyn),
    "bridge_sydney": _entry("Sydney Harbour Bridge", build_sydney),
}
