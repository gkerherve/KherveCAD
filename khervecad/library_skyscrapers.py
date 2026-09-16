"""The **Skyscrapers** library: famous towers modelled from their
published heights, footprints and setbacks, at true size (or a model
scale), mm, standing on z = 0 and centred.

- Empire State Building (381 m roof, 443 m tip): the five-storey base on
  its 129 x 57 m lot, the setbacks at floors 6, 21, 25, 30, 72, 81 and
  85, the observation deck, the mooring mast and antenna; limestone with
  vertical window bands.
- Chrysler Building (319 m): the stepped base, the brick shaft with its
  white bands, the terraced stainless-steel crown of seven sunburst
  arches pierced by triangular windows, the eagle gargoyles and spire.
- One World Trade Center (541 m): the 61 m square podium, the tower
  whose square base turns into a 45°-rotated square at the 417 m roof —
  eight tall triangular faces — the parapet and the 124 m spire.
- Burj Khalifa (828 m): the Y-shaped plan of three wings round a
  hexagonal core, stepping back one wing at a time in a spiral, the
  spire.
- Petronas Towers (452 m): twin towers on an eight-pointed star plan
  (two squares and a round core), tiered setbacks, the double-decker
  skybridge at 170 m with its legs, the pinnacles.
- Taipei 101 (508 m): the tapering base, eight flared pagoda segments of
  eight floors each, the coin discs, the top and spire.
- Shanghai Tower (632 m): a rounded-triangle plan twisting 120° and
  tapering as it rises, in nine zones parted by bands.
- The Shard (310 m): a pyramid of splayed glass shards that do not meet
  at the top.

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
from .library_landmarks import SCALES, moved
from .model import CadNode

CATEGORY = "Skyscrapers"

GLASS = "#8fb3c9"
DARK_GLASS = "#34495a"
STEEL = "#c9ced3"


def _window_strips(kit, x0, y0, x1, y1, z0, z1, pitch, colour,
                   width=None, material="Plastic"):
    """Vertical window bands down every face of a box block."""
    for face in range(4):
        if face in (0, 2):
            length = x1 - x0
            n = max(1, int(length // pitch))
            y = y0 if face == 0 else y1
            for k in range(n):
                u = x0 + (k + 0.5) * length / n
                w = width or pitch * 0.45
                kit.box(u - w / 2, y - 60, z0 + 1000, u + w / 2, y + 60,
                        z1 - 1000, colour, material)
        else:
            length = y1 - y0
            n = max(1, int(length // pitch))
            x = x0 if face == 3 else x1
            for k in range(n):
                v = y0 + (k + 0.5) * length / n
                w = width or pitch * 0.45
                kit.box(x - 60, v - w / 2, z0 + 1000, x + 60, v + w / 2,
                        z1 - 1000, colour, material)


# -------------------------------------------------------- Empire State
def build_empire_state(dims):
    kit = Kit()
    stone = "#d8d2c2"
    blocks = [(0, 25000, 129000, 57000), (25000, 80000, 97000, 50000),
              (80000, 95000, 88000, 46000), (95000, 112000, 78000, 42000),
              (112000, 270000, 57000, 42000), (270000, 303000, 45000, 36000),
              (303000, 318000, 37000, 30000)]
    for z0, z1, w, d in blocks:
        kit.box(-w / 2, -d / 2, z0, w / 2, d / 2, z1, stone, "Render")
        kit.box(-w / 2 - 400, -d / 2 - 400, z1 - 800, w / 2 + 400,
                d / 2 + 400, z1, "#e6e0d0", "Render")
        _window_strips(kit, -w / 2, -d / 2, w / 2, d / 2, z0, z1 - 800, 3000,
                       DARK_GLASS)
        # the chrome-nickel mullions between the window bands
        for u in (-w / 4, 0, w / 4):
            kit.box(u - 250, -d / 2 - 250, z0, u + 250, -d / 2, z1 - 800,
                    STEEL, "Metal")
            kit.box(u - 250, d / 2, z0, u + 250, d / 2 + 250, z1 - 800,
                    STEEL, "Metal")
    # the shaft's wings: the notched corners of the tower
    for sx in (-1, 1):
        kit.box(sx * 28500 - (6000 if sx > 0 else 0), -26000, 112000,
                sx * 28500 + (0 if sx > 0 else 6000), 26000, 250000, stone,
                "Render")
    # observation deck, mast, antenna
    kit.box(-20000, -16000, 318000, 20000, 16000, 320000, "#e6e0d0",
            "Render")
    mast = [(320000, 11000), (340000, 10000), (355000, 8000), (368000, 6000),
            (376000, 3500)]
    for (z0, r0), (z1, r1) in zip(mast, mast[1:]):
        kit.cone(0, 0, z0, z1, r0, r1, stone, "Render", sides=8,
                 phase=math.pi / 8)
        kit.cone(0, 0, z0 + 2000, z1 - 1000, r0 * 1.01, r1 * 1.01,
                 DARK_GLASS, "Plastic", sides=8, phase=math.pi / 8 + 0.2)
    kit.cone(0, 0, 376000, 381000, 3500, 1500, STEEL, "Metal", sides=8)
    kit.cone(0, 0, 381000, 443000, 900, 150, STEEL, "Metal", sides=6)
    return kit.node("Empire State Building")


# -------------------------------------------------------- Chrysler
def build_chrysler(dims):
    kit = Kit()
    brick = "#b8b4ad"
    steel = "#dfe3e6"
    blocks = [(0, 55000, 60000, 60000), (55000, 85000, 46000, 46000),
              (85000, 215000, 30000, 30000)]
    for z0, z1, w, d in blocks:
        kit.box(-w / 2, -d / 2, z0, w / 2, d / 2, z1, brick, "Brick")
        _window_strips(kit, -w / 2, -d / 2, w / 2, d / 2, z0, z1, 2400,
                       DARK_GLASS)
        for z in range(int(z0) + 12000, int(z1), 12000):
            kit.box(-w / 2 - 150, -d / 2 - 150, z, w / 2 + 150, d / 2 + 150,
                    z + 700, "#f2f0ea", "Render")        # white bands
    # the eagles at the 61st floor corners
    for sx in (-1, 1):
        for sy in (-1, 1):
            kit.solid([(sx * 15000, sy * 15000, 214000),
                       (sx * 21000, sy * 21000, 213000),
                       (sx * 15000, sy * 12000, 215500),
                       (sx * 12000, sy * 15000, 215500),
                       (sx * 21500, sy * 21500, 215800)], steel, "Metal")
    # the crown: seven terraces of sunburst arches
    z = 215000.0
    half = 15000.0
    for tier in range(7):
        h = 9000.0 - tier * 400
        top_half = half * 0.82
        kit.frustum(0, 0, z, z + h, (2 * half, 2 * half),
                    (2 * top_half, 2 * top_half), steel, "Metal")
        for face in range(4):
            a = math.radians(face * 90)
            nx, ny = math.sin(a), -math.cos(a)
            tx, ty = math.cos(a), math.sin(a)
            # the arch rib over this terrace's face
            pts = []
            for k in range(13):
                t = math.pi * k / 12
                u = math.cos(t) * half * 0.9
                v = z + h * 0.15 + math.sin(t) * h * 0.95
                inset = lerp(half, top_half, (v - z) / h) + 200
                pts.append((nx * inset + tx * u, ny * inset + ty * u, v))
            kit.path(pts, 350, steel, "Metal", sides=6)
            # triangular windows under the arch
            for k in range(-2, 3):
                u = k * half * 0.3
                inset = lerp(half, top_half, 0.35) + 120
                bx, by = nx * inset + tx * u, ny * inset + ty * u
                kit.solid([(bx - tx * 900, by - ty * 900, z + h * 0.2),
                           (bx + tx * 900, by + ty * 900, z + h * 0.2),
                           (bx, by, z + h * 0.62),
                           (bx - tx * 900 + nx * 150,
                            by - ty * 900 + ny * 150, z + h * 0.2)],
                          "#2a2f36", "Plastic")
        z += h
        half = top_half
    kit.cone(0, 0, z, z + 37000, half * 1.2, 200, steel, "Metal", sides=8,
             phase=math.pi / 4)
    return kit.node("Chrysler Building")


# ----------------------------------------------- One World Trade Center
def build_one_wtc(dims):
    kit = Kit()
    side = 61000.0
    kit.box(-side / 2, -side / 2, 0, side / 2, side / 2, 57000, "#9fb3c0",
            "Plastic")
    for k in range(40):                          # the podium's glass fins
        u = -side / 2 + (k + 0.5) * side / 40
        for s in (-1, 1):
            kit.box(u - 150, s * side / 2 - 300, 2000, u + 150,
                    s * side / 2 + 300, 55000, "#dfe7ec", "Metal")
            kit.box(s * side / 2 - 300, u - 150, 2000, s * side / 2 + 300,
                    u + 150, 55000, "#dfe7ec", "Metal")
    roof = 417000.0
    top = 43000.0
    base_pts = [(-side / 2, -side / 2, 57000), (side / 2, -side / 2, 57000),
                (side / 2, side / 2, 57000), (-side / 2, side / 2, 57000)]
    r = top / math.sqrt(2)
    top_pts = [(r * math.cos(a), r * math.sin(a), roof)
               for a in (0, math.pi / 2, math.pi, 3 * math.pi / 2)]
    kit.solid(base_pts + top_pts, GLASS, "Plastic")
    # the eight long edges (mullion lines) catch the light
    for i, p in enumerate(base_pts):
        for q in (top_pts[i], top_pts[(i - 1) % 4]):
            kit.bar(p, q, 350, STEEL, "Metal")
    # floor lines: a thin ring every 12 floors
    for k in range(1, 9):
        t = k / 9
        z = lerp(57000, roof, t)
        ring = [tuple(lerp(b[i], s[i], t) for i in range(3))
                for b, s in zip(base_pts, top_pts)]
        ring2 = [tuple(lerp(top_pts[(i - 1) % 4][j], base_pts[i][j], 1 - t)
                       for j in range(3)) for i in range(4)]
        loop8 = []
        for a, b in zip(ring, ring2):
            loop8 += [b, a]
        for a, b in zip(loop8, loop8[1:] + loop8[:1]):
            kit.bar(a, b, 120, STEEL, "Metal")
    kit.box(-top / 2 - 200, -top / 2 - 200, roof, top / 2 + 200, top / 2 + 200,
            roof + 4000, "#dfe7ec", "Metal")
    kit.cone(0, 0, roof + 4000, roof + 12000, 8000, 7000, "#dfe7ec", "Metal",
             sides=16)
    kit.cone(0, 0, roof + 12000, 541000, 1400, 250, STEEL, "Metal", sides=8)
    for z in (roof + 30000, roof + 60000, roof + 90000):
        kit.cone(0, 0, z, z + 1500, 4000, 4000, STEEL, "Metal", sides=12)
    return kit.node("One World Trade Center")


# ---------------------------------------------------------- Burj Khalifa
def build_burj(dims):
    kit = Kit()
    silver = "#c9d6df"
    fin = "#eef2f4"
    wing_w = 26000.0
    wing_len = 62000.0
    core_r = 20000.0
    steps = 27
    top = 585000.0
    heights = [lerp(0, top, k / steps) for k in range(steps + 1)]
    lengths = [wing_len, wing_len, wing_len]
    for k in range(steps):
        z0, z1 = heights[k], heights[k + 1]
        cut = k % 3
        if k > 0:
            lengths[cut] = max(0.0, lengths[cut] - wing_len / 9.5)
        cr = core_r * (1 - 0.55 * k / steps)
        kit.cone(0, 0, z0, z1, cr, cr, silver, "Plastic", sides=6)
        for w in range(3):
            L = lengths[w]
            if L < 1000:
                continue
            a = math.radians(90 + w * 120)
            cx, cy = math.cos(a) * L / 2, math.sin(a) * L / 2
            width = wing_w * (1 - 0.35 * k / steps)
            kit.obox(cx, cy, z0, L, width, z1 - z0, math.degrees(a), silver,
                     "Plastic")
            # the vertical fins down each wing's flanks and nose
            ex, ey = math.cos(a) * L, math.sin(a) * L
            kit.obox(ex, ey, z0, 1200, width * 0.5, z1 - z0 - 800,
                     math.degrees(a), fin, "Metal")
            kit.obox(cx, cy, z1 - 900, L + 800, width + 800, 900,
                     math.degrees(a), fin, "Metal")
    # the spire
    kit.cone(0, 0, top, top + 60000, 9000, 6000, silver, "Plastic", sides=6)
    kit.cone(0, 0, top + 60000, 828000, 5000, 300, fin, "Metal", sides=6)
    for z in range(int(top + 70000), 800000, 20000):
        kit.cone(0, 0, z, z + 1500, 4500 * (1 - (z - top) / 260000),
                 4500 * (1 - (z - top) / 260000), fin, "Metal", sides=6)
    return kit.node("Burj Khalifa")


# ------------------------------------------------------------ Petronas
def _petronas_tower(kit, cx, height=452000.0):
    steel = "#d7dbe0"
    tiers = [(0, 250000, 23000), (250000, 300000, 21000),
             (300000, 336000, 18500), (336000, 360000, 15500),
             (360000, 372000, 12500), (372000, 380000, 9500)]
    for z0, z1, r in tiers:
        s = r * 1.414
        kit.prism([(cx - s / 2, -s / 2), (cx + s / 2, -s / 2),
                   (cx + s / 2, s / 2), (cx - s / 2, s / 2)], z0, z1,
                  GLASS, "Plastic")
        kit.prism([(cx + math.cos(a) * r, math.sin(a) * r)
                   for a in (0, math.pi / 2, math.pi, 1.5 * math.pi)],
                  z0, z1, GLASS, "Plastic")
        kit.cone(cx, 0, z0, z1, r * 0.92, r * 0.92, GLASS, "Plastic",
                 sides=24)
        for z in range(int(z0) + 4000, int(z1), 4000):     # steel bands
            kit.cone(cx, 0, z, z + 700, r * 0.97, r * 0.97, steel, "Metal",
                     sides=16, phase=math.pi / 16)
    kit.cone(cx, 0, 380000, 392000, 8000, 3000, steel, "Metal", sides=16)
    kit.cone(cx, 0, 392000, height, 1500, 150, steel, "Metal", sides=8)
    for z in (400000, 415000, 428000):
        kit.sphere((cx, 0, z), 2600 - (z - 400000) / 20, steel, "Metal")
        kit.cone(cx, 0, z - 4000, z - 3200, 3500, 3500, steel, "Metal",
                 sides=16)


def build_petronas(dims):
    kit = Kit()
    gap = 104000.0
    for s in (-1, 1):
        _petronas_tower(kit, s * gap / 2)
    # the double-decker skybridge at floors 41-42 and its legs
    z = 170000.0
    kit.box(-gap / 2 + 20000, -3500, z, gap / 2 - 20000, 3500, z + 9000,
            DARK_GLASS, "Plastic")
    kit.box(-gap / 2 + 20000, -3900, z + 4300, gap / 2 - 20000, 3900,
            z + 4700, STEEL, "Metal")
    for s in (-1, 1):
        kit.bar((0, s * 3000, z), (s * gap / 2 * 0.62, s * 3000, 120000), 900,
                STEEL, "Metal")
        kit.bar((0, -s * 3000, z), (s * gap / 2 * 0.62, -s * 3000, 120000),
                900, STEEL, "Metal")
    kit.box(-4000, -4000, z - 3000, 4000, 4000, z, STEEL, "Metal")
    return kit.node("Petronas Towers")


# ------------------------------------------------------------ Taipei 101
def build_taipei(dims):
    kit = Kit()
    glass = "#6f9f9a"
    frame = "#dfe7e4"

    def octo(w, d):
        c = w * 0.18
        return [(-w / 2 + c, -d / 2), (w / 2 - c, -d / 2), (w / 2, -d / 2 + c),
                (w / 2, d / 2 - c), (w / 2 - c, d / 2), (-w / 2 + c, d / 2),
                (-w / 2, d / 2 - c), (-w / 2, -d / 2 + c)]

    def flare(z0, z1, w0, w1):
        pts = [(x, y, z0) for x, y in octo(w0, w0)] + \
              [(x, y, z1) for x, y in octo(w1, w1)]
        kit.solid(pts, glass, "Plastic")
        kit.solid([(x, y, z1 - 900) for x, y in octo(w1 + 800, w1 + 800)] +
                  [(x, y, z1) for x, y in octo(w1 + 800, w1 + 800)], frame,
                  "Metal")
    kit.box(-80000, -60000, 0, 80000, 60000, 25000, "#9aa8a6", "Plastic")
    flare(0, 100000, 62000, 50000)
    # the coins on each face at floor 26
    for face in range(4):
        a = math.radians(face * 90)
        nx, ny = math.sin(a), -math.cos(a)
        c = CadNode("cylinder", "Coin", dict(x=0.0, y=0.0, z=0.0,
                                            height=800.0, radius_bottom=8000,
                                            radius_top=8000, segments=32,
                                            center=False))
        col = CadNode("color", "Coin", dict(color="#d4af37", alpha=1.0,
                                            material="Gold"))
        col.add(c)
        kit.add(moved(col, nx * 25200, ny * 25200, 92000, rx=90.0,
                      rz=face * 90.0, name="Coin"))
    z = 100000.0
    for _k in range(8):
        flare(z, z + 34000, 46000, 54000)
        z += 34000
    flare(z, z + 30000, 38000, 30000)
    flare(z + 30000, z + 60000, 26000, 20000)
    kit.cone(0, 0, z + 60000, 508000, 3000, 400, frame, "Metal", sides=8)
    return kit.node("Taipei 101")


# -------------------------------------------------------- Shanghai Tower
def build_shanghai(dims):
    group = CadNode("union", "Shanghai Tower", {})
    height = 580000.0
    zones = 9
    twist_total = 120.0
    base = 41000.0

    def outline(scale):
        pts = []
        for k in range(60):
            a = 2 * math.pi * k / 60
            # a rounded triangle with a notch at one corner
            r = base * (1 + 0.12 * math.cos(3 * a))
            if abs(math.cos((a - math.pi / 2) / 2)) > 0.995:
                r *= 0.9
            pts.append([round(math.cos(a) * r * scale, 1),
                        round(math.sin(a) * r * scale, 1)])
        return pts

    def scale_at(i):
        return 1.0 - 0.42 * i / zones

    zone_h = height / zones
    for i in range(zones):
        s0, s1 = scale_at(i), scale_at(i + 1)
        ex = CadNode("linear_extrude", f"Zone {i + 1}", dict(
            height=zone_h - 1500, twist=twist_total / zones * (zone_h - 1500)
            / zone_h, scale=s1 / s0, center=False, segments=8))
        ex.add(CadNode("polygon", "Plan", dict(x=0.0, y=0.0,
                                               points=outline(s0))))
        col = CadNode("color", "Glass", dict(color="#9cc1cf", alpha=1.0,
                                             material="Plastic"))
        col.add(ex)
        group.add(moved(col, 0, 0, i * zone_h,
                        rz=-twist_total / zones * i, name=f"Zone {i + 1}"))
        band = CadNode("linear_extrude", "Band", dict(
            height=1500.0, twist=0.0, scale=1.0, center=False, segments=1))
        band.add(CadNode("polygon", "Band plan", dict(
            x=0.0, y=0.0, points=outline(s1 * 1.02))))
        bc = CadNode("color", "Band", dict(color="#e8eef1", alpha=1.0,
                                           material="Metal"))
        bc.add(band)
        group.add(moved(bc, 0, 0, (i + 1) * zone_h - 1500,
                        rz=-twist_total / zones * (i + 1), name="Band"))
    kit = Kit()
    kit.cone(0, 0, height, 632000, base * scale_at(zones) * 0.8, 3000,
             "#e8eef1", "Metal", sides=24)
    group.add(kit.node("Crown"))
    return group


# ---------------------------------------------------------------- Shard
def build_shard(dims):
    kit = Kit()
    glass = "#b9cdd8"
    height = 310000.0
    # a solid core pyramid, then eight shards leaning in over it
    kit.cone(0, 0, 0, 290000, 38000, 2500, "#8aa0ad", "Plastic", sides=8,
             phase=math.pi / 8)
    shards = [(0, 44000, 26000), (45, 40000, 22000), (90, 46000, 28000),
              (135, 38000, 20000), (180, 44000, 26000), (225, 41000, 22000),
              (270, 46000, 28000), (315, 39000, 21000)]
    for ang, dist, half in shards:
        a = math.radians(ang)
        nx, ny = math.cos(a), math.sin(a)
        tx, ty = -ny, nx
        top_h = height - (ang % 90) * 250 - (0 if ang % 90 else 0)
        tip = 3000 + (ang % 45) * 60
        b0 = (nx * dist, ny * dist)
        pts = []
        for depth in (0.0, 1500.0):
            ox, oy = nx * -depth, ny * -depth
            pts += [(b0[0] + tx * half + ox, b0[1] + ty * half + oy, 0),
                    (b0[0] - tx * half + ox, b0[1] - ty * half + oy, 0),
                    (nx * tip + tx * 2500 + ox, ny * tip + ty * 2500 + oy,
                     top_h),
                    (nx * tip - tx * 2500 + ox, ny * tip - ty * 2500 + oy,
                     top_h)]
        kit.solid(pts, glass, "Plastic")
    return kit.node("The Shard")


def _entry(label, build):
    return dict(label=label, category=CATEGORY,
                sizes={name: dict(scale=k) for name, k in SCALES.items()},
                build=lambda dims, b=build: _scaled(b(dims), dims),
                fields=[("scale", "Scale")])


PARTS = {
    "sky_empire_state": _entry("Empire State Building (New York)",
                               build_empire_state),
    "sky_chrysler": _entry("Chrysler Building (New York)", build_chrysler),
    "sky_one_wtc": _entry("One World Trade Center (New York)",
                          build_one_wtc),
    "sky_burj_khalifa": _entry("Burj Khalifa (Dubai)", build_burj),
    "sky_petronas": _entry("Petronas Towers (Kuala Lumpur)", build_petronas),
    "sky_taipei_101": _entry("Taipei 101", build_taipei),
    "sky_shanghai": _entry("Shanghai Tower", build_shanghai),
    "sky_shard": _entry("The Shard (London)", build_shard),
}
