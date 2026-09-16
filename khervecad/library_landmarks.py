"""The **Landmarks** library: world monuments modelled from their
published dimensions, at true size (or a model scale), mm, standing on
z = 0 and centred.

- Eiffel Tower (330 m): four curved lattice legs from a 125 m base
  merging at about 180 m into one braced shaft; the first platform at
  57.6 m (70.7 m square) with its decorative arches between the legs,
  the second at 115.7 m (41 m square), the third floor cabin at 276 m,
  the lantern and antenna; bronze-brown.
- Statue of Liberty (93 m to the torch): Fort Wood's eleven-pointed star,
  the stepped granite pedestal with its loggias and cornice, and the
  46 m copper figure — robe with folds, raised right arm and torch with
  its gilded flame, tablet in the left arm, head and seven-rayed crown;
  verdigris green.
- Big Ben / Elizabeth Tower (96 m): 12 m square shaft with Gothic ribs
  and window panels, the clock stage with four 7 m dials (gilded frames,
  hands), the belfry arcade, corner pinnacles, the cast-iron spire
  roof and gilded finial.
- Great Pyramid of Giza (230.3 m base, 138.5 m today): 40 stepped
  courses of limestone blocks, the summit platform.
- Leaning Tower of Pisa (56.7 m, 3.97°): marble ground storey with blind
  arcade, six open galleries of 30 columns each, the belfry, leaning.
- Arc de Triomphe (50 x 45 x 22 m): the 29 m central arch and the
  transverse arches cut through four piers, relief panels, cornice,
  shields and attic.
- Colosseum (189 x 156 m ellipse, 48 m): 80 bays of three arcaded
  storeys and the attic wall with its windows (the south side ruined
  down to the inner ring), the tiered cavea and the arena floor.
- Taj Mahal (73 m): the 95 m plinth, the chamfered mausoleum with a
  pointed iwan on every face, the onion dome on its drum with a gilded
  finial, four chhatris, and four 40 m minarets with balconies.

Members are written with `landmark_kit.Kit`; curved profiles (domes)
are revolved polygons.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from .landmark_kit import Kit, _f, lerp
from .library_bridges import _scaled
from .model import CadNode

CATEGORY = "Landmarks"

SCALES = {"Model 1:500": 1 / 500.0, "Real size": 1.0,
          "Model 1:100": 1 / 100.0}

GOLD = "#d4af37"


def _interp(table, z):
    """Linear interpolation in a [(z, value...)] table."""
    for (z0, *v0), (z1, *v1) in zip(table, table[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / (z1 - z0) if z1 > z0 else 0.0
            return [lerp(a, b, t) for a, b in zip(v0, v1)]
    return list(table[-1][1:]) if z > table[-1][0] else list(table[0][1:])


def revolve(profile, name, colour, material="Matte", segments=48):
    """A revolved shape from (radius, z) points listed from the axis at
    the bottom round to the axis at the top."""
    rx = CadNode("rotate_extrude", name, dict(angle=360.0,
                                              segments=segments))
    rx.add(CadNode("polygon", name, dict(
        x=0.0, y=0.0, points=[[round(r, 1), round(z, 1)]
                              for r, z in profile])))
    c = CadNode("color", name, dict(color=colour, alpha=1.0,
                                    material=material))
    c.add(rx)
    return c


def moved(node, x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0, name=None):
    inner = node
    if rx or ry or rz:
        inner = CadNode("rotate", "Turn", dict(x=rx, y=ry, z=rz))
        inner.add(node)
    t = CadNode("translate", name or node.name, dict(x=x, y=y, z=z))
    t.add(inner)
    return t


# ------------------------------------------------------------ Eiffel
def build_eiffel(dims):
    kit = Kit()
    iron = "#6e5a44"
    # z (mm), outer half-width of the tower, half-size of one leg
    profile = [(0, 62500, 13000), (57600, 35350, 9000),
               (115700, 20500, 6500), (180000, 11000, 5500),
               (276100, 5600, 2800), (300000, 3600, 1800)]

    def leg_corners(z, sx, sy):
        W, a = _interp(profile, z)
        c = max(W - a, a)
        cx, cy = sx * c, sy * c
        return [(cx - a, cy - a, z), (cx + a, cy - a, z), (cx + a, cy + a, z),
                (cx - a, cy + a, z)]

    levels = [0.0]
    z = 0.0
    while z < 180000:
        z += 4500.0
        levels.append(min(z, 180000.0))
    for sx in (-1, 1):
        for sy in (-1, 1):
            rings = [leg_corners(z, sx, sy) for z in levels]
            for k in range(len(rings) - 1):
                r = 900 if levels[k] < 57600 else 650
                for i in range(4):
                    kit.bar(rings[k][i], rings[k + 1][i], r, iron, "Metal")
                if k % 2 == 0 and k + 2 < len(rings):
                    lo, hi = rings[k], rings[k + 2]
                    for i in range(4):
                        j = (i + 1) % 4
                        kit.bar(lo[i], hi[j], 260, iron, "Metal")
                        kit.bar(lo[j], hi[i], 260, iron, "Metal")
                        kit.bar(hi[i], hi[j], 220, iron, "Metal")
    # the merged shaft from 180 m to the third floor
    top_levels = [180000.0 + k * 6000.0 for k in range(17)] + [276100.0]

    def shaft(z):
        W, _a = _interp(profile, z)
        return [(-W, -W, z), (W, -W, z), (W, W, z), (-W, W, z)]
    rings = [shaft(z) for z in top_levels]
    for k in range(len(rings) - 1):
        for i in range(4):
            j = (i + 1) % 4
            kit.bar(rings[k][i], rings[k + 1][i], 500, iron, "Metal")
            kit.bar(rings[k][i], rings[k + 1][j], 180, iron, "Metal")
            kit.bar(rings[k][j], rings[k + 1][i], 180, iron, "Metal")
            kit.bar(rings[k + 1][i], rings[k + 1][j], 160, iron, "Metal")
    # masonry piers under the four feet
    for sx in (-1, 1):
        for sy in (-1, 1):
            c = 62500 - 13000
            kit.box(sx * c - 15000, sy * c - 15000, -1000, sx * c + 15000,
                    sy * c + 15000, 1500, "#b8ad9a", "Stone")
    # first platform: a girder frame round a 70.7 m square, the gallery
    for z0, W, h in ((57600, 35350, 7000), (115700, 20500, 5500)):
        for i in range(4):
            a = [(-W, -W), (W, -W), (W, W), (-W, W)][i]
            b = [(-W, -W), (W, -W), (W, W), (-W, W)][(i + 1) % 4]
            kit.truss((a[0], a[1], z0 + h), (b[0], b[1], z0 + h),
                      (a[0], a[1], z0), (b[0], b[1], z0), 12, 450, 220, iron,
                      "Metal")
            kit.bar((a[0], a[1], z0 + h + 1100), (b[0], b[1], z0 + h + 1100),
                    120, iron, "Metal")                       # parapet rail
        kit.box(-W + 800, -W + 800, z0 + h - 400, W - 800, W - 800, z0 + h,
                "#5a4a38", "Metal")
        kit.box(-W * 0.55, -W * 0.55, z0 + h, W * 0.55, W * 0.55,
                z0 + h + 3500, "#8a7a64", "Metal")              # pavilions
    # the decorative arches between the legs under the first platform
    for side in range(4):
        pts = []
        for k in range(25):
            t = k / 24
            u = lerp(-31000, 31000, t)
            zz = 22000 + 17000 * math.sqrt(max(0.0, 1 - (u / 31000) ** 2))
            pts.append((u, zz))
        path = []
        for u, zz in pts:
            x, y = [(u, -37000), (37000, u), (u, 37000), (-37000, u)][side]
            path.append((x, y, zz))
        kit.path(path, 650, iron, "Metal", sides=6)
        for k in range(2, 24, 2):
            x, y, zz = path[k]
            kit.bar((x, y, zz), (x, y, 57600), 180, iron, "Metal")
    # third floor cabin, the top, the antenna
    kit.box(-8250, -8250, 276100, 8250, 8250, 283000, "#8a7a64", "Metal")
    kit.box(-9000, -9000, 276100, 9000, 9000, 276900, iron, "Metal")
    kit.frustum(0, 0, 283000, 295000, (11000, 11000), (6000, 6000), iron,
                "Metal")
    kit.cone(0, 0, 295000, 300000, 3500, 2000, iron, "Metal", sides=8)
    kit.cone(0, 0, 300000, 312000, 1200, 700, "#d9d9d9", "Metal", sides=8)
    kit.cone(0, 0, 312000, 330000, 500, 80, "#d9d9d9", "Metal", sides=6)
    return kit.node("Eiffel Tower")


# ------------------------------------------------------------ Liberty
def build_liberty(dims):
    kit = Kit()
    stone = "#b9ad97"
    copper = "#8fbfad"
    # Fort Wood: an eleven-pointed star
    n = 11
    outer, inner, fort_h = 50000.0, 34000.0, 7000.0
    for k in range(n):
        a0 = 2 * math.pi * k / n
        a1 = 2 * math.pi * (k + 0.5) / n
        a2 = 2 * math.pi * (k + 1) / n
        tri = [(math.cos(a0) * inner, math.sin(a0) * inner),
               (math.cos(a1) * outer, math.sin(a1) * outer),
               (math.cos(a2) * inner, math.sin(a2) * inner), (0.0, 0.0)]
        kit.prism(tri, 0, fort_h, stone, "Stone")
    kit.cone(0, 0, fort_h, fort_h + 1200, inner, inner, "#6f9e4c", "Matte",
             sides=11)
    # pedestal
    ped = [(fort_h, 32000, 32000), (fort_h + 5000, 28000, 28000),
           (fort_h + 8000, 21000, 21000), (fort_h + 30000, 19000, 19000),
           (fort_h + 34000, 21500, 21500), (fort_h + 36000, 17500, 17500),
           (fort_h + 40000, 16500, 16500)]
    for (z0, w0, _d0), (z1, w1, _d1) in zip(ped, ped[1:]):
        kit.frustum(0, 0, z0, z1, (w0, w0), (w1, w1), "#c9bda5", "Stone")
    base = ped[-1][0]
    for s in range(4):                     # loggias: columns and dark bays
        for c in (-1, 1):
            x = c * 4500
            p = [(x, -10000), (10000, x), (x, 10000), (-10000, x)][s]
            kit.cone(p[0], p[1], fort_h + 20000, fort_h + 29000, 700, 650,
                     "#d8ccb3", "Stone", sides=10)
        q = [(0, -9600), (9600, 0), (0, 9600), (-9600, 0)][s]
        kit.box(q[0] - (3000 if s % 2 == 0 else 60),
                q[1] - (60 if s % 2 == 0 else 3000), fort_h + 20000,
                q[0] + (3000 if s % 2 == 0 else 60),
                q[1] + (60 if s % 2 == 0 else 3000), fort_h + 29000,
                "#4a4238", "Stone")

    z0 = base
    # robe: a hull of stacked rings, flaring to the hem
    rings = []
    for z, rx, ry in ((0, 7200, 6200), (4000, 6000, 5200), (14000, 5000, 4300),
                      (22000, 4600, 3700), (26500, 4400, 3000)):
        for k in range(12):
            a = 2 * math.pi * k / 12
            rings.append((math.cos(a) * rx, math.sin(a) * ry, z0 + z))
    kit.solid(rings, copper, "Matte")
    for k in range(14):                        # robe folds
        a = 2 * math.pi * k / 14 + 0.2
        kit.bar((math.cos(a) * 7000, math.sin(a) * 6000, z0 + 300),
                (math.cos(a) * 4700, math.sin(a) * 3900, z0 + 20000), 420,
                copper, "Matte", sides=6)
    kit.bar((-4200, -2000, z0 + 26000), (3800, -3200, z0 + 14000), 700,
            copper, "Matte", sides=6)           # the drape over the shoulder
    # neck, head, crown
    kit.cone(0, -300, z0 + 26500, z0 + 29000, 1400, 1150, copper, "Matte",
             sides=10)
    kit.sphere((0, -400, z0 + 31200), 2600, copper, "Matte")
    kit.cone(0, -400, z0 + 32300, z0 + 33300, 2750, 2650, copper, "Matte",
             sides=16)
    for k in range(7):
        a = math.radians(-160 + k * 23.3)
        root = (math.cos(a) * 2600, -400 + math.sin(a) * 2600, z0 + 33000)
        tip = (math.cos(a) * 5600, -400 + math.sin(a) * 5600, z0 + 36000)
        kit.solid([(root[0] - 350, root[1], root[2]),
                   (root[0] + 350, root[1], root[2]),
                   (root[0], root[1] - 350, root[2]),
                   (root[0], root[1] + 350, root[2]),
                   (root[0], root[1], root[2] + 500), tip], copper, "Matte")
    # raised right arm, torch and flame
    shoulder, elbow = (4000, -500, z0 + 26000), (5200, -900, z0 + 32500)
    hand = (5700, -1200, z0 + 38000)
    kit.path([shoulder, elbow, hand], 1100, copper, "Matte", sides=8)
    kit.sphere(hand, 1300, copper, "Matte")
    kit.cone(hand[0], hand[1], hand[2] + 600, hand[2] + 3200, 500, 650,
             copper, "Matte", sides=10)
    kit.cone(hand[0], hand[1], hand[2] + 3200, hand[2] + 4600, 900, 1700,
             GOLD, "Gold", sides=16)                           # the cup
    kit.cone(hand[0], hand[1], hand[2] + 4600, hand[2] + 8000, 1500, 0,
             "#ffd36a", "Emissive", sides=12)                  # the flame
    # left arm and the tablet
    kit.path([(-4100, -300, z0 + 25500), (-5200, -1600, z0 + 20000),
              (-3200, -3600, z0 + 20500)], 1000, copper, "Matte", sides=8)
    kit.obox(-4300, -2600, z0 + 17000, 4100, 700, 7200, 25, copper, "Matte")
    return kit.node("Statue of Liberty")


# ------------------------------------------------------------ Big Ben
def build_big_ben(dims):
    kit = Kit()
    stone = "#cdbf96"
    iron = "#3d4550"
    side = 12000.0
    h = side / 2
    kit.box(-h - 1200, -h - 1200, 0, h + 1200, h + 1200, 4000, "#bdb08a",
            "Stone")
    kit.box(-h, -h, 4000, h, h, 50000, stone, "Stone")
    # buttress ribs at the corners and down each face, string courses
    for sx in (-1, 1):
        for sy in (-1, 1):
            kit.box(sx * h - 500, sy * h - 500, 4000, sx * h + 500,
                    sy * h + 500, 62500, stone, "Stone")
    for face in range(4):
        for u in (-3000, 0, 3000):
            x0, y0, x1, y1 = {0: (u - 150, -h - 200, u + 150, -h),
                              1: (h, u - 150, h + 200, u + 150),
                              2: (u - 150, h, u + 150, h + 200),
                              3: (-h - 200, u - 150, -h, u + 150)}[face]
            kit.box(x0, y0, 4000, x1, y1, 50000, stone, "Stone")
        for z in range(8000, 48000, 5000):             # window panels
            for u in (-1500, 1500):
                x0, y0, x1, y1 = {0: (u - 900, -h - 80, u + 900, -h),
                                  1: (h, u - 900, h + 80, u + 900),
                                  2: (u - 900, h, u + 900, h + 80),
                                  3: (-h - 80, u - 900, -h, u + 900)}[face]
                kit.box(x0, y0, z, x1, y1, z + 3200, "#6d6552", "Stone")
    for z in (20000, 35000, 50000, 62500):
        kit.box(-h - 350, -h - 350, z - 600, h + 350, h + 350, z, "#d9cca4",
                "Stone")
    # clock stage with the four dials
    kit.box(-h - 300, -h - 300, 50000, h + 300, h + 300, 62500, stone,
            "Stone")
    dial_z = 56000.0
    for face in range(4):
        rz = face * 90.0
        a = math.radians(rz)
        nx, ny = math.sin(a), -math.cos(a)            # outward normal
        cx, cy = nx * (h + 300), ny * (h + 300)
        frame = CadNode("cylinder", "Dial frame", dict(
            x=0.0, y=0.0, z=0.0, height=250.0, radius_bottom=3900.0,
            radius_top=3900.0, segments=48, center=False))
        dial = CadNode("cylinder", "Dial", dict(
            x=0.0, y=0.0, z=0.0, height=300.0, radius_bottom=3500.0,
            radius_top=3500.0, segments=48, center=False))
        for node, colour, mat in ((frame, GOLD, "Gold"),
                                  (dial, "#f4efe0", "Emissive")):
            c = CadNode("color", node.name, dict(color=colour, alpha=1.0,
                                                 material=mat))
            c.add(node)
            kit.add(moved(c, cx, cy, dial_z, rx=90.0, rz=rz))
        # hands pointing at ten past ten
        for ang, length, width in ((-60, 2300, 260), (60, 3100, 180)):
            b = math.radians(ang)
            tip = (cx + nx * 350 + math.cos(a) * math.sin(b) * length,
                   cy + ny * 350 + math.sin(a) * math.sin(b) * length,
                   dial_z + math.cos(b) * length)
            kit.bar((cx + nx * 350, cy + ny * 350, dial_z), tip, width,
                    "#1b1b1b", "Metal")
        # the square gilded surround
        for dz in (-4200, 4200):
            kit.box(cx - 4300 * abs(math.cos(a)) - 150 * abs(nx),
                    cy - 4300 * abs(math.sin(a)) - 150 * abs(ny),
                    dial_z + dz - 250,
                    cx + 4300 * abs(math.cos(a)) + 150 * abs(nx),
                    cy + 4300 * abs(math.sin(a)) + 150 * abs(ny),
                    dial_z + dz + 250, GOLD, "Gold")
    # belfry arcade
    kit.box(-h + 1200, -h + 1200, 62500, h - 1200, h - 1200, 72000,
            "#4a4336", "Stone")
    for face in range(4):
        for u in (-4500, -1500, 1500, 4500):
            x, y = {0: (u, -h + 700), 1: (h - 700, u), 2: (u, h - 700),
                    3: (-h + 700, u)}[face]
            kit.box(x - 500, y - 500, 62500, x + 500, y + 500, 72000, stone,
                    "Stone")
    kit.box(-h - 400, -h - 400, 72000, h + 400, h + 400, 73500, "#d9cca4",
            "Stone")
    # corner pinnacles and the spire roof
    for sx in (-1, 1):
        for sy in (-1, 1):
            kit.cone(sx * h, sy * h, 62500, 76000, 900, 800, stone, "Stone",
                     sides=8)
            kit.cone(sx * h, sy * h, 76000, 80000, 900, 0, iron, "Metal",
                     sides=8)
    kit.frustum(0, 0, 73500, 80000, (side, side), (side * 0.6, side * 0.6),
                iron, "Metal")
    for face in range(4):                    # the lantern gables
        a = math.radians(face * 90)
        nx, ny = math.sin(a), -math.cos(a)
        kit.solid([(nx * 3800 + ny * 1800, ny * 3800 - nx * 1800, 76000),
                   (nx * 3800 - ny * 1800, ny * 3800 + nx * 1800, 76000),
                   (nx * 3800, ny * 3800, 80500),
                   (nx * 1500 + ny * 1800, ny * 1500 - nx * 1800, 76000),
                   (nx * 1500 - ny * 1800, ny * 1500 + nx * 1800, 76000),
                   (nx * 1500, ny * 1500, 80500)], iron, "Metal")
    kit.frustum(0, 0, 80000, 84000, (side * 0.6, side * 0.6),
                (side * 0.42, side * 0.42), GOLD, "Gold")
    kit.cone(0, 0, 84000, 94000, side * 0.3, 300, iron, "Metal", sides=8,
             phase=math.pi / 8)
    kit.cone(0, 0, 94000, 96000, 250, 0, GOLD, "Gold", sides=8)
    return kit.node("Big Ben (Elizabeth Tower)")


# ------------------------------------------------------------ pyramid
def build_pyramid(dims):
    kit = Kit()
    base, height = 230300.0, 138500.0
    full = 146600.0
    courses = 40
    step = height / courses
    for k in range(courses):
        z0 = k * step
        w0 = base * (1 - z0 / full)
        w1 = base * (1 - (z0 + step) / full)
        tone = "#d6bf8f" if k % 3 else "#cdb483"
        kit.frustum(0, 0, z0, z0 + step, (w0, w0), (w1 + step * 0.9,
                                                   w1 + step * 0.9), tone,
                    "Stone")
    kit.box(-5000, -5000, height - 1, 5000, 5000, height + 1500, "#d6bf8f",
            "Stone")
    # the entrance on the north face
    kit.box(-2000, -base * (1 - 17000 / full) / 2 - 900, 17000, 2000,
            -base * (1 - 17000 / full) / 2 + 100, 21000, "#5a4a36", "Stone")
    return kit.node("Great Pyramid of Giza")


# --------------------------------------------------------------- Pisa
def build_pisa(dims):
    kit = Kit()
    marble = "#efe9dd"
    grey = "#cfc6b6"
    r = 7740.0
    core = 6300.0
    z = 0.0
    storeys = [("ground", 11000.0)] + [("gallery", 6500.0)] * 6 + \
              [("belfry", 7800.0)]
    for kind, height in storeys:
        if kind == "belfry":
            br = 4800.0
            kit.cone(0, 0, z, z + height, br - 800, br - 800, grey, "Matte",
                     sides=24)
            for k in range(16):
                a = 2 * math.pi * k / 16
                kit.cone(math.cos(a) * br, math.sin(a) * br, z, z + height -
                         1200, 300, 260, marble, "Matte", sides=8)
            kit.cone(0, 0, z + height - 1200, z + height, br + 300, br + 300,
                     marble, "Matte", sides=32)
            z += height
            break
        kit.cone(0, 0, z, z + height, core if kind == "gallery" else r,
                 core if kind == "gallery" else r, marble if kind == "ground"
                 else grey, "Matte", sides=32)
        cols = 15 if kind == "ground" else 30
        for k in range(cols):
            a = 2 * math.pi * k / cols
            cx, cy = math.cos(a) * (r - 400), math.sin(a) * (r - 400)
            kit.cone(cx, cy, z + (500 if kind == "gallery" else 0),
                     z + height - 1500, 330, 290, marble, "Matte", sides=8)
            # the arch over each bay: a small wedge between columns
            a2 = 2 * math.pi * (k + 0.5) / cols
            kit.obox(math.cos(a2) * (r - 400), math.sin(a2) * (r - 400),
                     z + height - 1500, 2 * math.pi * r / cols * 0.9, 700,
                     900, math.degrees(a2) + 90, marble, "Matte")
        kit.cone(0, 0, z + height - 600, z + height, r + 250, r + 250, marble,
                 "Matte", sides=40)                        # cornice
        if kind == "gallery":
            kit.cone(0, 0, z, z + 500, r + 150, r + 150, marble, "Matte",
                     sides=40)                             # gallery floor
        z += height
    tower = kit.node("Leaning Tower of Pisa")
    lean = CadNode("rotate", "Lean 3.97°", dict(x=0.0, y=3.97, z=0.0))
    lean.add(tower)
    base = CadNode("union", "Leaning Tower of Pisa", {})
    step = Kit()
    step.cone(0, 0, -1000, 0, r + 1500, r + 1500, "#d8d0c0", "Matte",
              sides=40)
    base.add(step.node("Base"))
    base.add(moved(lean, r * 0.0, 0, 0, name="Leaning"))
    return base


# ----------------------------------------------------- Arc de Triomphe
def build_arc(dims):
    kit = Kit()
    stone = "#e3d7bb"
    W, D, H = 45000.0, 22000.0, 50000.0
    main_w, main_h = 14620.0, 29190.0
    side_w, side_h = 8440.0, 18680.0
    hw, hd = W / 2, D / 2
    # four piers
    for sx in (-1, 1):
        for sy in (-1, 1):
            x0, x1 = sorted((sx * main_w / 2, sx * hw))
            y0, y1 = sorted((sy * side_w / 2, sy * hd))
            kit.box(x0, y0, 0, x1, y1, 36000.0, stone, "Render")
    # the mass over the openings, shaped to the arches in slices
    slices = 18
    spring = main_h - main_w / 2
    top = 36000.0
    for k in range(slices):
        u0 = -main_w / 2 + main_w * k / slices
        u1 = u0 + main_w / slices
        um = (u0 + u1) / 2
        zb = spring + math.sqrt(max(0.0, (main_w / 2) ** 2 - um * um))
        kit.box(u0, -hd, zb, u1, hd, top, stone, "Render")
    sspring = side_h - side_w / 2
    for sx in (-1, 1):
        x0, x1 = sorted((sx * main_w / 2, sx * hw))
        for k in range(slices):
            v0 = -side_w / 2 + side_w * k / slices
            v1 = v0 + side_w / slices
            vm = (v0 + v1) / 2
            zb = sspring + math.sqrt(max(0.0, (side_w / 2) ** 2 - vm * vm))
            kit.box(x0, v0, zb, x1, v1, top, stone, "Render")
    # cornices, attic, shields
    kit.box(-hw - 800, -hd - 800, top, hw + 800, hd + 800, top + 2500,
            "#d8ccae", "Render")
    kit.box(-hw, -hd, top + 2500, hw, hd, H - 1500, stone, "Render")
    kit.box(-hw - 500, -hd - 500, H - 1500, hw + 500, hd + 500, H,
            "#d8ccae", "Render")
    for sy in (-1, 1):
        for k in range(15):
            x = -hw + 1500 + k * (W - 3000) / 14
            kit.box(x - 700, sy * (hd + 150) - 150, top + 5000, x + 700,
                    sy * (hd + 150) + 150, top + 7200, "#cfc2a2", "Render")
        # relief groups on the piers, the frieze
        for sx in (-1, 1):
            cx = sx * (main_w / 2 + (hw - main_w / 2) / 2)
            kit.box(cx - 4500, sy * hd - (400 if sy > 0 else -400) * 0 - 400,
                    6000, cx + 4500, sy * hd + 400, 17000, "#d6c9a8", "Render")
            kit.box(cx - 3500, sy * hd - 200, 21000, cx + 3500, sy * hd + 200,
                    26500, "#d6c9a8", "Render")
        kit.box(-hw, sy * hd - 300, top - 3500, hw, sy * hd + 300, top - 500,
                "#d6c9a8", "Render")
    # the arch mouldings (archivolts)
    for k in range(25):
        a = math.pi * k / 24
        x = math.cos(a) * (main_w / 2 + 600)
        z = spring + math.sin(a) * (main_w / 2 + 600)
        for sy in (-1, 1):
            kit.box(x - 500, sy * hd - 300, z - 500, x + 500, sy * hd + 300,
                    z + 500, "#d8ccae", "Render")
    return kit.node("Arc de Triomphe")


# ----------------------------------------------------------- Colosseum
def build_colosseum(dims):
    kit = Kit()
    travertine = "#d6c7a6"
    ruin = "#c7b590"
    A, B = 94500.0, 78000.0          # outer semi-axes
    bays = 80
    storeys = [(0.0, 10500.0), (10500.0, 22350.0), (22350.0, 33950.0)]
    attic_top = 48000.0

    def at(t, scale=1.0):
        return (math.cos(t) * A * scale, math.sin(t) * B * scale)

    def tangent_deg(t):
        dx, dy = -math.sin(t) * A, math.cos(t) * B
        return math.degrees(math.atan2(dy, dx))

    for k in range(bays):
        t0 = 2 * math.pi * k / bays
        tm = 2 * math.pi * (k + 0.5) / bays
        ruined = math.sin(t0) < -0.25 and abs(math.cos(t0)) < 0.8
        bay_len = math.hypot(*[a - b for a, b in zip(at(t0), at(tm))]) * 2
        x, y = at(t0)
        rz = tangent_deg(t0)
        top_storey = 2 if ruined else 3
        for s, (z0, z1) in enumerate(storeys[:top_storey]):
            # pier with an engaged column, the arch lintel over the bay
            kit.obox(x, y, z0, bay_len * 0.28, 2600, z1 - z0, rz, travertine,
                     "Stone")
            xm, ym = at(tm)
            kit.obox(xm, ym, z1 - 2600, bay_len * 0.75, 2400, 2600,
                     tangent_deg(tm), travertine, "Stone")
            nx, ny = at(t0, 1.02)
            kit.obox(nx, ny, z0 + 600, 900, 700, z1 - z0 - 1800, rz, "#e3d6b8",
                     "Stone")
        if not ruined:
            kit.obox(xm, ym, storeys[2][1], bay_len * 1.02, 2400,
                     attic_top - storeys[2][1], tangent_deg(tm), travertine,
                     "Stone")
            if k % 2 == 0:
                wx, wy = at(tm, 1.003)
                kit.obox(wx, wy, storeys[2][1] + 4000, 1500, 400, 2500,
                         tangent_deg(tm), "#5e5240", "Stone")
            px, py = at(t0, 1.012)
            kit.obox(px, py, storeys[2][1], 800, 600,
                     attic_top - storeys[2][1], rz, "#e3d6b8", "Stone")
        else:
            # the inner ring stands behind the lost outer wall
            ix, iy = at(tm, 0.88)
            kit.obox(ix, iy, 0, bay_len * 0.9, 3000, 30000, tangent_deg(tm),
                     ruin, "Stone")
    # the cavea: tiers of seating stepping down to the arena
    arena_a, arena_b = 43000.0, 24000.0
    tiers = 7
    for i in range(tiers):
        f = i / tiers
        sa = lerp(0.84, arena_a / A + 0.04, f)
        z = lerp(30000, 4000, f)
        for k in range(bays):
            tm = 2 * math.pi * (k + 0.5) / bays
            cx, cy = math.cos(tm) * A * sa, math.sin(tm) * B * (
                lerp(0.84, arena_b / B + 0.06, f))
            kit.obox(cx, cy, 0, 2 * math.pi * A * sa / bays * 1.08, 9000, z,
                     tangent_deg(tm), "#bfae8c" if i % 2 else "#c9b996",
                     "Stone")
    ring = [(math.cos(2 * math.pi * k / 48) * arena_a,
             math.sin(2 * math.pi * k / 48) * arena_b) for k in range(48)]
    kit.prism(ring, 0, 3000, "#c8b58a", "Render")               # arena floor
    return kit.node("Colosseum")


# ----------------------------------------------------------- Taj Mahal
def _onion(r, h):
    """(radius, z) profile of an onion dome on a drum of radius r, h
    tall: it swells past the drum to its widest a third of the way up,
    then draws in to a slender point — the concave tip is what makes it
    an onion and not a bell."""
    pts = [(0.0, 0.0), (r, 0.0)]
    widest = 0.38
    for k in range(1, 40):
        t = k / 40
        if t <= widest:
            rad = r * (1.0 + 0.22 * math.sin(math.pi / 2 * t / widest))
        else:
            u = (t - widest) / (1 - widest)
            rad = r * 1.22 * math.cos(u * math.pi / 2) ** 1.7
        pts.append((rad, t * h))
    pts.append((0.0, h))
    return pts


def build_taj(dims):
    kit = Kit()
    marble = "#f3efe6"
    shade = "#dcd4c4"
    red = "#a1553f"
    P = 95000.0
    # the red sandstone base and the marble plinth
    kit.box(-P / 2 - 8000, -P / 2 - 8000, -1000, P / 2 + 8000, P / 2 + 8000,
            0, red, "Stone")
    kit.box(-P / 2, -P / 2, 0, P / 2, P / 2, 7000, marble, "Matte")
    # the mausoleum: a 57 m square with chamfered corners
    S, C = 57000.0, 12000.0
    body_h = 33000.0
    octo = [(-S / 2 + C, -S / 2), (S / 2 - C, -S / 2), (S / 2, -S / 2 + C),
            (S / 2, S / 2 - C), (S / 2 - C, S / 2), (-S / 2 + C, S / 2),
            (-S / 2, S / 2 - C), (-S / 2, -S / 2 + C)]
    kit.prism(octo, 7000, 7000 + body_h, marble, "Matte")
    kit.prism([(x * 1.02, y * 1.02) for x, y in octo], 7000 + body_h - 1500,
              7000 + body_h, shade, "Matte")
    # iwans: a pointed-arch recess and its frame on every face
    for face in range(4):
        a = math.radians(face * 90)
        nx, ny = math.sin(a), -math.cos(a)
        tx, ty = math.cos(a), math.sin(a)
        cx, cy = nx * (S / 2 + 10), ny * (S / 2 + 10)
        arch_w, arch_h = 17000.0, 26000.0
        spring = 7000 + arch_h - arch_w * 0.55
        pts = []
        for k in range(9):                      # a pointed arch outline
            t = k / 8
            ang = math.pi * (1 - t)
            px = math.cos(ang) * arch_w / 2
            pz = spring + math.sin(ang) * arch_w * 0.55 * (
                1 + 0.25 * (1 - abs(1 - 2 * t)))
            pts.append((px, pz))
        pts = [(-arch_w / 2, 7000.0)] + pts + [(arch_w / 2, 7000.0)]
        prism = []
        for px, pz in pts:
            for depth in (0.0, 300.0):
                prism.append((cx + tx * px + nx * depth,
                              cy + ty * px + ny * depth, pz))
        kit.solid(prism, "#cfc4ae", "Matte")
        frame_w = arch_w + 4000
        kit.solid([(cx + tx * frame_w / 2 + nx * 350,
                    cy + ty * frame_w / 2 + ny * 350, z)
                   for z in (7000 + arch_h + 3000,)] +
                  [(cx - tx * frame_w / 2 + nx * 350,
                    cy - ty * frame_w / 2 + ny * 350, 7000 + arch_h + 3000),
                   (cx + tx * frame_w / 2 + nx * 350,
                    cy + ty * frame_w / 2 + ny * 350, 7000 + arch_h + 2000),
                   (cx - tx * frame_w / 2 + nx * 350,
                    cy - ty * frame_w / 2 + ny * 350, 7000 + arch_h + 2000),
                   (cx + tx * frame_w / 2, cy + ty * frame_w / 2,
                    7000 + arch_h + 3000),
                   (cx - tx * frame_w / 2, cy - ty * frame_w / 2,
                    7000 + arch_h + 2000)], shade, "Matte")
        for s in (-1, 1):                         # side panels of arches
            for level in (0, 1):
                z0 = 9000 + level * 13000
                bx, by = cx + tx * s * 18000 + nx * 100, cy + ty * s * 18000 \
                    + ny * 100
                kit.solid([(bx - tx * 3000, by - ty * 3000, z0),
                           (bx + tx * 3000, by + ty * 3000, z0),
                           (bx - tx * 3000, by - ty * 3000, z0 + 8000),
                           (bx + tx * 3000, by + ty * 3000, z0 + 8000),
                           (bx, by, z0 + 10500),
                           (bx - tx * 3000 + nx * 200,
                            by - ty * 3000 + ny * 200, z0)], "#cfc4ae",
                          "Stone")
    top = 7000 + body_h
    # drum, onion dome, finial
    kit.cone(0, 0, top, top + 7000, 14500, 14500, marble, "Matte", sides=32)
    kit.cone(0, 0, top + 6500, top + 7200, 15300, 15300, shade, "Matte",
             sides=32)
    kit.add(moved(revolve(_onion(14500, 26000), "Onion dome", marble,
                          "Stone"), z=top + 7000, name="Onion dome"))
    kit.cone(0, 0, top + 32500, top + 33500, 1500, 900, GOLD, "Gold")
    kit.cone(0, 0, top + 33500, top + 40000, 500, 80, GOLD, "Gold", sides=8)
    kit.sphere((0, 0, top + 35000), 900, GOLD, "Gold")
    # four chhatris round the dome
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = sx * 17500, sy * 17500
            for k in range(8):
                a = 2 * math.pi * k / 8
                kit.cone(cx + math.cos(a) * 3200, cy + math.sin(a) * 3200,
                         top, top + 5500, 250, 250, marble, "Matte", sides=6)
            kit.cone(cx, cy, top + 5500, top + 6200, 3800, 3800, shade,
                     "Stone", sides=16)
            kit.add(moved(revolve(_onion(3500, 6000), "Chhatri dome", marble,
                                  "Stone", 24), cx, cy, top + 6200,
                          name="Chhatri"))
            kit.cone(cx, cy, top + 12000, top + 13500, 150, 40, GOLD, "Gold",
                     sides=6)
    # the four minarets
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = sx * (P / 2 - 3500), sy * (P / 2 - 3500)
            kit.cone(cx, cy, 7000, 7000 + 40000, 3000, 2200, marble, "Matte",
                     sides=16)
            for f in (0.33, 0.66, 1.0):
                z = 7000 + 40000 * f
                kit.cone(cx, cy, z - 800, z, 3700, 3400, shade, "Matte",
                         sides=16)
            for k in range(8):
                a = 2 * math.pi * k / 8
                kit.cone(cx + math.cos(a) * 1800, cy + math.sin(a) * 1800,
                         47000, 50500, 150, 150, marble, "Matte", sides=6)
            kit.add(moved(revolve(_onion(2300, 4500), "Minaret dome", marble,
                                  "Stone", 24), cx, cy, 50500,
                          name="Minaret dome"))
            kit.cone(cx, cy, 55000, 56500, 120, 30, GOLD, "Gold", sides=6)
    return kit.node("Taj Mahal")


def _entry(label, build):
    return dict(label=label, category=CATEGORY,
                sizes={name: dict(scale=k) for name, k in SCALES.items()},
                build=lambda dims, b=build: _scaled(b(dims), dims),
                fields=[("scale", "Scale")])


PARTS = {
    "landmark_eiffel": _entry("Eiffel Tower (Paris)", build_eiffel),
    "landmark_liberty": _entry("Statue of Liberty (New York)", build_liberty),
    "landmark_big_ben": _entry("Big Ben / Elizabeth Tower (London)",
                               build_big_ben),
    "landmark_pyramid": _entry("Great Pyramid of Giza", build_pyramid),
    "landmark_pisa": _entry("Leaning Tower of Pisa", build_pisa),
    "landmark_arc": _entry("Arc de Triomphe (Paris)", build_arc),
    "landmark_colosseum": _entry("Colosseum (Rome)", build_colosseum),
    "landmark_taj": _entry("Taj Mahal (Agra)", build_taj),
}
