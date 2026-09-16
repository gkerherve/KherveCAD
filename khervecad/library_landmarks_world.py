"""More **Landmarks**, from their published dimensions (true size, or a
model scale; mm, standing on z = 0, centred):

- CN Tower (553 m): the Y of three tapering concrete legs round the
  hexagonal core, the main pod at 342-360 m with its glass band, the
  SkyPod at 447 m and the red-and-white antenna.
- Space Needle (184 m): three pairs of hourglass legs, the halo at
  30 m, the core, the flying-saucer top house at 158 m and the spire.
- Gateway Arch (192 m high, 192 m wide): the weighted catenary
  y = 211.49 - 20.96 cosh(0.03292 x) ft, an equilateral stainless
  section tapering from 16.5 m to 5.2 m.
- London Eye (135 m): the 120 m rim truss, 32 egg capsules, cable
  spokes, the hub and the cantilevered A-frame.
- Atomium (102 m): nine 18 m spheres at the corners and centre of a cube
  stood on its vertex, joined by tubes, on three bipods.
- Brandenburg Gate (26 m): twelve Doric columns in two rows of six, the
  five passages, the attic, the side wings and the Quadriga.
- Parthenon: the three-step stylobate (69.5 x 30.9 m), the 8 x 17
  peristyle of fluted columns (10.4 m), entablature and triglyph frieze,
  the pediments and the cella walls — the temple as it stands, unroofed.
- Stonehenge: the 33 m sarsen circle (uprights and lintels, gaps where
  stones have fallen), the five trilithons of the horseshoe, the
  bluestones, the Altar and Heel stones, the bank and ditch.
- Sydney Opera House: the podium and steps, the Concert Hall and Joan
  Sutherland Theatre each a row of nested tiled shells, the Bennelong
  restaurant shells, and the glass walls under their open ends.
- St Basil's Cathedral: the central tent-roofed church, four large and
  four small chapels with patterned onion domes in their colours, the
  bell tower and the gallery.

Same construction kit as the other landmarks: members appended into one
polyhedron per colour (`landmark_kit.Kit`), revolved domes as nodes.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from .landmark_kit import Kit, lerp
from .library_bridges import _scaled
from .library_landmarks import SCALES, _onion, moved, revolve
from .model import CadNode

CATEGORY = "Landmarks"
CONCRETE = "#c9c4ba"
STEEL = "#d9dee2"
STONE = "#d8ccb0"


def _ring(n, r, phase=0.0, cx=0.0, cy=0.0):
    return [(cx + math.cos(phase + 2 * math.pi * k / n) * r,
             cy + math.sin(phase + 2 * math.pi * k / n) * r)
            for k in range(n)]


def _sphere_node(name, x, y, z, r, colour, material, segments=32):
    s = CadNode("sphere", name, dict(x=0.0, y=0.0, z=0.0, radius=r,
                                     segments=segments))
    c = CadNode("color", name, dict(color=colour, alpha=1.0,
                                    material=material))
    c.add(s)
    return moved(c, x, y, z, name=name)


# ------------------------------------------------------------ CN Tower
def build_cn_tower(dims):
    kit = Kit()
    glass = "#4d6273"
    white = "#f2f2ee"
    red = "#c0392b"
    # the hexagonal core, tapering
    kit.cone(0, 0, 0, 447000, 11000, 6000, CONCRETE, "Concrete", sides=6)
    # three legs: wedges from a wide foot to the core at 335 m
    for k in range(3):
        a = math.radians(90 + k * 120)
        ux, uy, tx, ty = math.cos(a), math.sin(a), -math.sin(a), math.cos(a)
        pts = []
        for z, reach, half in ((0, 38000, 5500), (60000, 30000, 4800),
                               (180000, 17000, 3800), (335000, 8000, 2500)):
            for s in (-1, 1):
                pts.append((ux * reach + tx * s * half,
                            uy * reach + ty * s * half, z))
                pts.append((tx * s * half, ty * s * half, z))
        kit.solid(pts, CONCRETE, "Concrete")
    # the main pod: skirt, glass levels, the observation decks, the roof
    kit.cone(0, 0, 330000, 342000, 9000, 21000, CONCRETE, "Concrete",
             sides=36)
    kit.cone(0, 0, 342000, 350000, 22000, 22000, glass, "Plastic", sides=36)
    kit.cone(0, 0, 350000, 353000, 23500, 23500, white, "Concrete",
             sides=36)
    kit.cone(0, 0, 353000, 360000, 22500, 21000, glass, "Plastic", sides=36)
    kit.cone(0, 0, 360000, 366000, 21000, 12000, white, "Concrete",
             sides=36)
    kit.cone(0, 0, 366000, 372000, 12000, 8000, CONCRETE, "Concrete",
             sides=24)
    # the SkyPod
    kit.cone(0, 0, 444000, 447000, 6000, 8000, CONCRETE, "Concrete",
             sides=24)
    kit.cone(0, 0, 447000, 452000, 8000, 8000, glass, "Plastic", sides=24)
    kit.cone(0, 0, 452000, 456000, 8000, 3500, CONCRETE, "Concrete",
             sides=24)
    # the antenna in red and white sections
    z, r = 456000.0, 3200.0
    k = 0
    while z < 553000:
        h = min(9000.0, 553000 - z)
        r1 = max(250.0, r - 300)
        kit.cone(0, 0, z, z + h, r, r1, red if k % 2 else white, "Metal",
                 sides=12)
        z, r, k = z + h, r1, k + 1
    return kit.node("CN Tower")


# -------------------------------------------------------- Space Needle
def build_space_needle(dims):
    kit = Kit()
    white = "#f1f0ea"
    gold = "#e0a526"
    glass = "#5a6f7e"

    def leg_r(z):
        waist = 112000.0
        if z <= waist:
            return 5600 + 14500 * ((waist - z) / waist) ** 1.6
        return 5600 + 11000 * ((z - waist) / (158000 - waist)) ** 1.4

    for k in range(3):
        a = math.radians(90 + k * 120)
        for s in (-1, 1):
            off = math.radians(s * 7)
            pts = []
            for i in range(17):
                z = 158000 * i / 16
                r = leg_r(z)
                aa = a + off * (r / 12000)
                pts.append((math.cos(aa) * r, math.sin(aa) * r, z))
            kit.path(pts, 900, white, "Plastic", sides=8)
    # core with the elevator shafts and stair
    kit.cone(0, 0, 0, 158000, 3800, 3800, "#cfcfca", "Concrete", sides=12)
    # the halo at 30 m
    halo_r = leg_r(30000) + 1500
    kit.path([(math.cos(2 * math.pi * k / 36) * halo_r,
               math.sin(2 * math.pi * k / 36) * halo_r, 30000)
              for k in range(37)], 700, gold, "Plastic", sides=6)
    # the top house (the saucer)
    kit.cone(0, 0, 150000, 156000, 7000, 19000, white, "Plastic", sides=36)
    kit.cone(0, 0, 156000, 163000, 20000, 20000, glass, "Plastic", sides=36)
    kit.cone(0, 0, 163000, 164500, 21500, 21500, white, "Plastic", sides=36)
    kit.cone(0, 0, 164500, 169000, 20500, 9000, gold, "Plastic", sides=36)
    kit.cone(0, 0, 169000, 172000, 9000, 4000, white, "Plastic", sides=24)
    # radial ribs under the saucer
    for k in range(18):
        a = 2 * math.pi * k / 18
        kit.bar((math.cos(a) * 7000, math.sin(a) * 7000, 150500),
                (math.cos(a) * 19000, math.sin(a) * 19000, 156000), 350,
                white, "Plastic")
    kit.cone(0, 0, 172000, 184000, 800, 120, STEEL, "Metal", sides=8)
    return kit.node("Space Needle")


# -------------------------------------------------------- Gateway Arch
def build_gateway_arch(dims):
    kit = Kit()
    FT = 304.8
    L = 299.2239
    A, B, C = 211.49, 20.96, 3.0 / L    # y = A - B cosh(C x), feet

    def centre(t):
        x = t * L
        return x * FT, (A - B * math.cosh(C * x)) * FT

    def side(t):
        """Triangle side, mm: 54 ft at the legs to 17 ft at the top."""
        u = abs(t)
        return (17 + (54 - 17) * u ** 1.4) * FT

    n = 60
    sections = []
    for i in range(n + 1):
        t = -1 + 2 * i / n
        x, z = centre(t)
        e = 1e-3
        x2, z2 = centre(min(1.0, t + e))
        x1, z1 = centre(max(-1.0, t - e))
        tx, tz = x2 - x1, z2 - z1
        ln = math.hypot(tx, tz)
        nx, nz = -tz / ln, tx / ln        # normal in the arch plane
        if nz < 0:
            nx, nz = -nx, -nz            # pointing up / outward
        s = side(t)
        h = s * math.sqrt(3) / 2
        # an equilateral section: flat face inside, apex outside
        tri = [(x - nx * h / 3 + 0.0, -s / 2, z - nz * h / 3),
               (x - nx * h / 3, s / 2, z - nz * h / 3),
               (x + nx * 2 * h / 3, 0.0, z + nz * 2 * h / 3)]
        tri = [(px, py, max(pz, 0.0)) for px, py, pz in tri]
        sections.append(tri)
    for a, b in zip(sections, sections[1:]):
        kit.solid(a + b, STEEL, "Metal")
    kit.box(-120000, -40000, -300, 120000, 40000, 0, "#9fae8c", "Matte")
    return kit.node("Gateway Arch")


# ---------------------------------------------------------- London Eye
def build_london_eye(dims):
    kit = Kit()
    white = "#f4f4f2"
    glass = "#a9c7d6"
    R = 60000.0
    hub_z = 75000.0
    n = 64

    def rim(r, y):
        return [(math.cos(2 * math.pi * k / n) * r, y,
                 hub_z + math.sin(2 * math.pi * k / n) * r)
                for k in range(n + 1)]
    for r, y in ((R, -2600), (R, 2600), (R - 3500, 0)):
        kit.path(rim(r, y), 550, white, "Metal", sides=6)
    # rim bracing between the three chords
    for k in range(n):
        a0 = 2 * math.pi * k / n
        a1 = 2 * math.pi * (k + 1) / n
        for y in (-2600, 2600):
            kit.bar((math.cos(a0) * R, y, hub_z + math.sin(a0) * R),
                    (math.cos(a1) * (R - 3500), 0,
                     hub_z + math.sin(a1) * (R - 3500)), 200, white, "Metal")
    # cable spokes, the hub and the spindle
    for k in range(64):
        a = 2 * math.pi * k / 64
        y = -2600 if k % 2 else 2600
        kit.bar((0, y * 0.3, hub_z),
                (math.cos(a) * (R - 3500), 0, hub_z + math.sin(a) * (R - 3500)),
                60, "#bfc5c9", "Metal")
    kit.bar((0, -5000, hub_z), (0, 5000, hub_z), 2800, white, "Metal",
            sides=16)
    kit.bar((0, -9000, hub_z), (0, 9000, hub_z), 900, "#aab0b4", "Metal",
            sides=12)
    # 32 capsules hanging outside the rim (egg shapes, level)
    for k in range(32):
        a = 2 * math.pi * k / 32
        cx = math.cos(a) * (R + 3800)
        cz = hub_z + math.sin(a) * (R + 3800)
        if cz < 2500:
            continue
        pts = []
        for j in range(9):
            t = -1 + 2 * j / 8
            half = 4000 * math.sqrt(max(0.0, 1 - t * t)) + 150
            for i in range(8):
                ph = 2 * math.pi * i / 8
                pts.append((cx + t * 4000, math.cos(ph) * half * 0.6,
                            cz + math.sin(ph) * half * 0.55))
        kit.solid(pts, glass, "Glass")
    # the A-frame leaning back from the river bank and its ties
    for sx in (-1, 1):
        kit.bar((sx * 32000, -52000, 0), (sx * 1500, -6000, hub_z), 1300,
                white, "Metal", sides=12)
    kit.bar((-20000, -36000, 25000), (20000, -36000, 25000), 700, white,
            "Metal", sides=8)
    for sx in (-1, 1):
        kit.bar((0, -7000, hub_z), (sx * 22000, -58000, 0), 250, "#bfc5c9",
                "Metal")
    kit.box(-40000, -60000, -1500, 40000, 12000, 0, "#9b968b", "Concrete")
    return kit.node("London Eye")


# ------------------------------------------------------------- Atomium
def build_atomium(dims):
    kit = Kit()
    steel = "#d4d9dc"
    r = 9000.0
    edge = 43000.0
    # a cube stood on a vertex: rotate so the body diagonal is vertical
    ax = math.atan(1 / math.sqrt(2))
    corners = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                x, y, z = sx * edge / 2, sy * edge / 2, sz * edge / 2
                # 45 deg about z, then tilt about x
                x, y = (x - y) / math.sqrt(2), (x + y) / math.sqrt(2)
                y, z = (y * math.cos(ax) - z * math.sin(ax),
                        y * math.sin(ax) + z * math.cos(ax))
                corners.append((x, y, z))
    low = min(c[2] for c in corners)
    lift = 102000 - r - (max(c[2] for c in corners) - low) - 0.0
    pts = [(x, y, z - low + lift) for x, y, z in corners]
    centre = (0.0, 0.0, -low + lift)
    for i, p in enumerate(pts):
        kit.add(_sphere_node(f"Sphere {i + 1}", p[0], p[1], p[2], r, steel,
                             "Metal"))
        kit.bar(centre, p, 1500, steel, "Metal", sides=12)
    kit.add(_sphere_node("Centre sphere", *centre, r, steel, "Metal"))
    for i, a in enumerate(pts):
        for b in pts[i + 1:]:
            if abs(math.dist(a, b) - edge) < 10:
                kit.bar(a, b, 1500, steel, "Metal", sides=12)
    # three bipods and the entrance from the lowest sphere
    bottom = min(pts, key=lambda p: p[2])
    for k in range(3):
        a = math.radians(30 + k * 120)
        foot = (math.cos(a) * 30000, math.sin(a) * 30000, 0.0)
        near = min((p for p in pts if p is not bottom),
                   key=lambda p: math.dist((p[0], p[1]), foot[:2]))
        for s in (-1, 1):
            kit.bar((foot[0] + s * 1500 * math.sin(a),
                     foot[1] - s * 1500 * math.cos(a), 0), near, 900,
                    "#9aa1a6", "Metal", sides=8)
    kit.bar((0, 0, 0), bottom, 1800, "#9aa1a6", "Metal", sides=12)
    return kit.node("Atomium")


# ---------------------------------------------------- Brandenburg Gate
def build_brandenburg(dims):
    kit = Kit()
    stone = "#dcd2bb"
    shade = "#c8bca2"
    copper = "#4f9b86"
    W, D = 65500.0, 11000.0
    kit.box(-W / 2, -D / 2, 0, W / 2, D / 2, 1200, shade, "Stone")
    # twelve columns: two rows of six, passages between (middle widest)
    xs = [-21000, -12600, -5600, 5600, 12600, 21000]
    for y in (-D / 2 + 1200, D / 2 - 1200):
        for x in xs:
            kit.cone(x, y, 1200, 1800, 1100, 1100, shade, "Stone", sides=16)
            kit.cone(x, y, 1800, 14000, 875, 760, stone, "Stone", sides=20)
            kit.box(x - 1150, y - 1150, 14000, x + 1150, y + 1150, 14600,
                    shade, "Stone")
    # walls between column pairs across the depth
    for x in xs:
        kit.box(x - 500, -D / 2 + 1900, 1200, x + 500, D / 2 - 1900, 14000,
                shade, "Stone")
    # entablature, frieze and attic
    kit.box(-23500, -D / 2, 14600, 23500, D / 2, 16200, stone, "Stone")
    kit.box(-23700, -D / 2 - 200, 16200, 23700, D / 2 + 200, 18000, shade,
            "Stone")
    kit.box(-24000, -D / 2 - 300, 18000, 24000, D / 2 + 300, 18600, stone,
            "Stone")
    kit.box(-18000, -D / 2 + 300, 18600, 18000, D / 2 - 300, 22500, stone,
            "Stone")
    kit.solid([(-9000, -D / 2 + 300, 22500), (9000, -D / 2 + 300, 22500),
               (-9000, D / 2 - 300, 22500), (9000, D / 2 - 300, 22500),
               (-6000, -D / 2 + 900, 24000), (6000, -D / 2 + 900, 24000),
               (-6000, D / 2 - 900, 24000), (6000, D / 2 - 900, 24000)],
              shade, "Stone")
    # the side wings (guard houses) with their porticos
    for s in (-1, 1):
        kit.box(s * 24000, -D / 2 + 1500, 0, s * 32750, D / 2 - 1500, 10500,
                stone, "Stone")
        kit.box(s * 23800, -D / 2 + 1300, 10500, s * 32950, D / 2 - 1300,
                11800, shade, "Stone")
    # the Quadriga: goddess on a chariot drawn by four horses, facing east
    kit.box(-1600, -1200, 24000, 1600, 1200, 26000, copper, "Copper")
    kit.cone(0, 0, 26000, 29500, 650, 450, copper, "Copper", sides=8)
    kit.sphere((0, 0, 29900), 450, copper, "Copper")
    kit.bar((600, 0, 28500), (900, 0, 32500), 90, copper, "Copper")
    for k in range(4):
        x = -2700 + k * 1800
        kit.obox(x, -3200, 25400, 800, 2600, 1300, 0, copper, "Copper")
        kit.bar((x, -4400, 26400), (x, -5000, 27900), 280, copper, "Copper")
        for lx in (-250, 250):
            for ly in (-2200, -4200):
                kit.bar((x + lx, ly, 24000), (x + lx, ly, 25400), 150, copper,
                        "Copper")
    return kit.node("Brandenburg Gate")


# ------------------------------------------------------------ Parthenon
def build_parthenon(dims):
    kit = Kit()
    marble = "#e3dac6"
    worn = "#cbbfa6"
    W, D = 69500.0, 30900.0
    for k, pad in enumerate((1800, 1200, 600)):
        kit.box(-W / 2 - pad, -D / 2 - pad, k * 550, W / 2 + pad,
                D / 2 + pad, (k + 1) * 550, worn, "Stone")
    base = 1650.0
    col_h = 10430.0
    r0, r1 = 955.0, 740.0
    # 8 x 17 peristyle, corner columns shared
    xs = [lerp(-W / 2 + 1100, W / 2 - 1100, i / 16) for i in range(17)]
    ys = [lerp(-D / 2 + 1100, D / 2 - 1100, i / 7) for i in range(8)]
    spots = {(x, ys[0]) for x in xs} | {(x, ys[-1]) for x in xs} | \
        {(xs[0], y) for y in ys} | {(xs[-1], y) for y in ys}
    for x, y in sorted(spots):
        kit.cone(x, y, base, base + col_h, r0, r1, marble, "Stone", sides=20)
        kit.cone(x, y, base + col_h, base + col_h + 450, r1, 1150, marble,
                 "Stone", sides=16)
        kit.box(x - 1150, y - 1150, base + col_h + 450, x + 1150, y + 1150,
                base + col_h + 800, marble, "Stone")
    top = base + col_h + 800
    # architrave, triglyph frieze, cornice
    kit.box(-W / 2 + 100, -D / 2 + 100, top, W / 2 - 100, D / 2 - 100,
            top + 1350, marble, "Stone")
    kit.box(-W / 2 + 150, -D / 2 + 150, top + 1350, W / 2 - 150,
            D / 2 - 150, top + 2700, worn, "Stone")
    for x in xs + [lerp(a, b, 0.5) for a, b in zip(xs, xs[1:])]:
        for y in (-D / 2 + 100, D / 2 - 100):
            kit.box(x - 420, y - 60, top + 1350, x + 420, y + 60, top + 2700,
                    "#b9ad93", "Stone")
    kit.box(-W / 2, -D / 2, top + 2700, W / 2, D / 2, top + 3300, marble,
            "Stone")
    # pediments: the west one whole, the east one broken
    for sx, keep in ((-1, 1.0), (1, 0.55)):
        x0 = sx * (W / 2 - 1500)
        x1 = sx * W / 2
        zp = top + 3300
        ridge = 4500 * keep
        half = D / 2 * keep
        kit.solid([(x0, -D / 2, zp), (x0, D / 2, zp), (x1, -D / 2, zp),
                   (x1, D / 2, zp), (x0, -D / 2 + (D / 2 - half), zp + ridge),
                   (x1, -D / 2 + (D / 2 - half), zp + ridge)], marble,
                  "Stone")
    # the cella: walls standing to part height, the inner porches
    kit.box(-W / 2 + 7000, -D / 2 + 5200, base, W / 2 - 7000, -D / 2 + 6400,
            base + 6000, worn, "Stone")
    kit.box(-W / 2 + 7000, D / 2 - 6400, base, W / 2 - 7000, D / 2 - 5200,
            base + 4500, worn, "Stone")
    kit.box(-4000, -D / 2 + 6400, base, -2800, D / 2 - 6400, base + 3000,
            worn, "Stone")
    for x in (-W / 2 + 5500, W / 2 - 5500):
        for i in range(6):
            y = lerp(-D / 2 + 6000, D / 2 - 6000, i / 5)
            kit.cone(x, y, base, base + col_h * 0.92, 800, 640, marble,
                     "Stone", sides=16)
    return kit.node("Parthenon")


# ----------------------------------------------------------- Stonehenge
def build_stonehenge(dims):
    kit = Kit()
    sarsen = "#9c968a"
    blue = "#7d8284"
    grass = "#7ea05a"
    kit.cone(0, 0, -400, 0, 58000, 58000, grass, "Matte", sides=48)
    # the bank and ditch round the monument
    for k in range(64):
        a0, a1 = 2 * math.pi * k / 64, 2 * math.pi * (k + 1) / 64
        kit.bar((math.cos(a0) * 50000, math.sin(a0) * 50000, 0),
                (math.cos(a1) * 50000, math.sin(a1) * 50000, 0), 900,
                "#8fae66", "Matte")
    # sarsen circle: 30 uprights, 16.5 m radius; those standing today
    standing = {0, 1, 2, 3, 4, 5, 6, 7, 10, 11, 14, 16, 21, 22, 23, 27, 28,
                29}
    lintels = {(29, 0), (0, 1), (1, 2), (2, 3), (3, 4), (5, 6), (6, 7),
               (27, 28), (10, 11), (22, 23)}
    R = 16500.0
    for k in range(30):
        a = math.radians(90 + k * 12)
        x, y = math.cos(a) * R, math.sin(a) * R
        if k in standing:
            kit.obox(x, y, 0, 1100, 2100, 4100, math.degrees(a), sarsen,
                     "Stone")
        elif k % 3 == 0:                         # a fallen stone
            kit.obox(x * 1.08, y * 1.08, 0, 4000, 2000, 1000,
                     math.degrees(a) + 60, sarsen, "Stone")
    for a_i, b_i in lintels:
        a0 = math.radians(90 + a_i * 12)
        a1 = math.radians(90 + b_i * 12)
        am = (a0 + a1) / 2 if abs(a1 - a0) < math.pi else a0 + math.radians(6)
        kit.obox(math.cos(am) * R, math.sin(am) * R, 4100, 3500, 1000, 800,
                 math.degrees(am) + 90, sarsen, "Stone")
    # the horseshoe of five trilithons opening north-east
    tri = [(-150, 6000, 6300), (-110, 7000, 6800), (-70, 7500, 7300),
           (-30, 7000, 6800), (10, 6000, 6300)]
    for i, (deg, rr, h) in enumerate(tri):
        a = math.radians(deg + 45)
        cx, cy = math.cos(a) * rr, math.sin(a) * rr
        tx, ty = -math.sin(a), math.cos(a)
        if i == 2:                               # the great trilithon fell
            kit.obox(cx + tx * 1200, cy + ty * 1200, 0, 2200, 1200, h, deg,
                     sarsen, "Stone")
            kit.obox(cx - tx * 2500, cy - ty * 2500, 0, h, 2200, 1200,
                     deg + 20, sarsen, "Stone")
            continue
        for s in (-1, 1):
            kit.obox(cx + tx * s * 1250, cy + ty * s * 1250, 0, 1300, 2200,
                     h, math.degrees(math.atan2(ty, tx)), sarsen, "Stone")
        kit.obox(cx, cy, h, 1300, 4800, 1000,
                 math.degrees(math.atan2(ty, tx)), sarsen, "Stone")
    # bluestone circle and horseshoe
    for k in range(40):
        if k % 3 == 2:
            continue
        a = 2 * math.pi * k / 40
        kit.obox(math.cos(a) * 12000, math.sin(a) * 12000, 0, 500, 900,
                 1800 + (k * 7) % 5 * 150, math.degrees(a), blue, "Stone")
    for k in range(12):
        a = math.radians(-170 + k * 15 + 45)
        kit.obox(math.cos(a) * 4800, math.sin(a) * 4800, 0, 450, 700, 2000,
                 math.degrees(a), blue, "Stone")
    kit.obox(-1500, 500, 0, 4900, 1000, 500, 45, "#8a7f76", "Stone")
    kit.obox(math.cos(math.radians(45)) * 78000,
             math.sin(math.radians(45)) * 78000, 0, 2400, 2000, 4700, 30,
             sarsen, "Stone")
    return kit.node("Stonehenge")


# --------------------------------------------------- Sydney Opera House
def _shell(kit, x, y, span, height, length, rz, colour, glass):
    """A tiled shell: its open end an arch (span wide, height tall) at
    (x, y), closing to a point on the podium `length` behind, facing -Y
    before `rz` turns it. Returned solid is the hull of the arch, a
    thickness and the back point."""
    a = math.radians(rz)
    ca, sa = math.cos(a), math.sin(a)

    def P(u, v, z):
        return (x + u * ca - v * sa, y + u * sa + v * ca, z)
    pts = []
    for i in range(13):
        t = -1 + 2 * i / 12
        u = t * span / 2
        z = height * (1 - t * t) ** 0.8
        pts.append(P(u, 0, z))
        pts.append(P(u * 0.94, length * 0.08, z * 1.02))
    pts.append(P(0, length, 0))
    pts.append(P(0, length * 0.55, height * 0.7))
    kit.solid(pts, colour, "Plastic")
    glass_pts = [P(t * span / 2 * 0.9, 600, height * 0.93 *
                   (1 - t * t) ** 0.8) for t in [-1 + 2 * i / 10
                                                 for i in range(11)]]
    glass_pts += [P(t * span / 2 * 0.9, 2200, 0) for t in (-1, 1)]
    kit.solid(glass_pts + [P(0, 2200, height * 0.8)], glass, "Plastic")


def build_opera_house(dims):
    kit = Kit()
    tile = "#f1efe7"
    glass = "#3d4b55"
    podium = "#c7a887"
    # the podium on Bennelong Point and the monumental steps (south)
    kit.box(-60000, -95000, 0, 60000, 90000, 7000, podium, "Stone")
    kit.solid([(-45000, 90000, 0), (45000, 90000, 0),
               (-45000, 90000, 7000), (45000, 90000, 7000),
               (-45000, 125000, 0), (45000, 125000, 0)], "#b99a79", "Stone")
    # Concert Hall (west) and Joan Sutherland Theatre (east): shells in a
    # row, open ends facing the harbour (north, -Y here)
    for cx, scale in ((-22000, 1.0), (22000, 0.9)):
        rows = [(-70000, 44000, 60000, 60000), (-40000, 40000, 55000, 55000),
                (-12000, 34000, 44000, 42000), (14000, 28000, 32000, 30000)]
        for y, span, h, length in rows:
            _shell(kit, cx, y, span * scale, h * scale + 7000,
                   length * scale, 0.0, tile, glass)
            # the reversed shell over the back of each hall
        _shell(kit, cx, 60000, 26000 * scale, 30000 * scale, 22000 * scale,
               180.0, tile, glass)
    # Bennelong restaurant (south-west, smaller)
    for y, span, h in ((40000, 18000, 18000), (54000, 15000, 15000)):
        _shell(kit, -50000, y, span, h + 7000, 16000, 0.0, tile, glass)
    return kit.node("Sydney Opera House")


# --------------------------------------------------------- St Basil's
def build_st_basils(dims):
    kit = Kit()
    brick = "#a8412f"
    white = "#efe9dc"
    green = "#3f7d4f"
    gold = "#d4af37"
    # the platform and gallery
    kit.box(-36000, -36000, 0, 36000, 36000, 5000, brick, "Brick")
    kit.box(-37000, -37000, 5000, 37000, 37000, 5600, white, "Stone")
    # central church: octagon, tent roof, small cupola
    kit.prism(_ring(8, 10000, math.pi / 8), 5600, 30000, brick, "Brick")
    for z in (12000, 20000, 28000):
        kit.prism(_ring(8, 10400, math.pi / 8), z, z + 700, white, "Stone")
    kit.prism(_ring(8, 7500, math.pi / 8), 30000, 34000, white, "Stone")
    kit.cone(0, 0, 34000, 50000, 7500, 1500, "#e8d8a6", "Roof tiles",
             sides=8, phase=math.pi / 8)
    kit.cone(0, 0, 50000, 52500, 1500, 1500, brick, "Brick", sides=8)
    kit.add(moved(revolve(_onion(1800, 3500), "Central cupola", gold,
                          "Gold"), 0, 0, 52500))
    # four large and four small chapels round it, each dome its own
    domes = [(0, 20000, 7000, 26000, [("#2f6db3", white)]),
             (90, 20000, 7000, 26000, [("#d7a726", green)]),
             (180, 20000, 7000, 26000, [(green, "#d7a726")]),
             (270, 20000, 7000, 24000, [(brick, green)]),
             (45, 21000, 4500, 18000, [(green, white)]),
             (135, 21000, 4500, 18000, [("#c43b2e", "#e6c14e")]),
             (225, 21000, 4500, 18000, [("#2f6db3", "#e6c14e")]),
             (315, 21000, 4500, 18000, [(white, green)])]
    for deg, dist, r, top, ((c1, c2),) in domes:
        a = math.radians(deg + 90)
        cx, cy = math.cos(a) * dist, math.sin(a) * dist
        sides = 8
        kit.prism(_ring(sides, r, math.pi / 8, cx, cy), 5600, top, brick,
                  "Brick")
        kit.prism(_ring(sides, r + 300, math.pi / 8, cx, cy), top - 1500,
                  top, white, "Stone")
        drum_r = r * 0.62
        kit.cone(cx, cy, top, top + r * 0.9, drum_r, drum_r, brick, "Brick",
                 sides=16)
        kit.cone(cx, cy, top + r * 0.5, top + r * 0.6, drum_r + 250,
                 drum_r + 250, white, "Stone", sides=16)
        dz = top + r * 0.9
        h = r * 1.9
        # a patterned onion: bands of the two colours stacked
        prof = _onion(drum_r, h)
        bands = 6
        for b in range(bands):
            lo, hi = b / bands, (b + 1) / bands
            part = [(0.0, lo * h)] + [(rr, z) for rr, z in prof
                                      if lo * h <= z <= hi * h] + \
                [(0.0, hi * h)]
            if len(part) < 4:
                continue
            node = revolve(part, "Onion dome", c1 if b % 2 else c2,
                           "Plastic", segments=24)
            kit.add(moved(node, cx, cy, dz))
        kit.cone(cx, cy, dz + h, dz + h + 2500, 150, 60, gold, "Gold",
                 sides=6)
    # the bell tower on the south-east corner
    bx, by = 30000, -30000
    kit.prism(_ring(4, 4500, math.pi / 4, bx, by), 0, 20000, white, "Stone")
    kit.prism(_ring(8, 3600, math.pi / 8, bx, by), 20000, 30000, brick,
              "Brick")
    kit.cone(bx, by, 30000, 38000, 3600, 700, green, "Roof tiles", sides=8,
             phase=math.pi / 8)
    kit.add(moved(revolve(_onion(700, 1800), "Bell tower cupola", gold,
                          "Gold"), bx, by, 38000))
    return kit.node("St Basil's Cathedral")


def _entry(label, build):
    return dict(label=label, category=CATEGORY,
                sizes={name: dict(scale=k) for name, k in SCALES.items()},
                build=lambda dims, b=build: _scaled(b(dims), dims),
                fields=[("scale", "Scale")])


PARTS = {
    "landmark_cn_tower": _entry("CN Tower (Toronto)", build_cn_tower),
    "landmark_space_needle": _entry("Space Needle (Seattle)",
                                    build_space_needle),
    "landmark_gateway_arch": _entry("Gateway Arch (St. Louis)",
                                    build_gateway_arch),
    "landmark_london_eye": _entry("London Eye", build_london_eye),
    "landmark_atomium": _entry("Atomium (Brussels)", build_atomium),
    "landmark_brandenburg": _entry("Brandenburg Gate (Berlin)",
                                   build_brandenburg),
    "landmark_parthenon": _entry("Parthenon (Athens)", build_parthenon),
    "landmark_stonehenge": _entry("Stonehenge", build_stonehenge),
    "landmark_opera_house": _entry("Sydney Opera House", build_opera_house),
    "landmark_st_basils": _entry("St Basil's Cathedral (Moscow)",
                                 build_st_basils),
}
