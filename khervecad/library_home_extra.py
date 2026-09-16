"""The rest of a house for the parts library: what goes beyond the
furnished rooms of `library_home` / `library_home_more`:

- stairs: a straight flight and a spiral, a full storey high;
- garage and driveway: car (hatchback, estate, SUV), bicycle, wheelie
  bin, garage shelving, lawn mower;
- reception: reception desk, a row of waiting chairs, water cooler;
- hallway, corridor, entrance and porch: wall light, doormat,
  umbrella stand, wall mirror;
- garden: broadleaf tree (summer, autumn, blossom, apple), conifer,
  birch, shrub, hedge, flower bed, planter, garden bench, patio set,
  barbecue.

Same rules as `library_home_more` (whose helpers this reuses): true
dimensions in mm, no booleans, front facing -Y, standing on z = 0 and
centred on X and Y; a car's and a bicycle's length runs along Y. A wall
light or mirror is built from its own bottom up; its entry's ``rest_z``
is the height the House Builder hangs it at.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from .library_home import (BLACK, BRASS, CHROME, FABRICS, FRONTS, LINEN,
                           PLINTH, STEEL, STONE, WHITE, WOODS, _box, _cyl,
                           _mix, _paint, _pick, _rod)
from .library_home_more import _ball8, _cube, _disc_y, _hull
from .library_room import _dims
from .model import CadNode

CATEGORY = "Home furniture"

CARS = {"Red": "#b3261e", "Blue": "#2b5aa8", "Silver": "#b9bec6",
        "Black": "#1f2125", "White": "#eeeeea"}
BINS = {"Green": "#3f6e3a", "Black": "#2a2c30", "Blue": "#2e5f9e",
        "Brown": "#6b4a33"}
TREES = {"Summer": ("#4f7f45", "#6a9c55"), "Autumn": ("#c9772f", "#b8452a"),
         "Blossom": ("#f3c1d3", "#e79bb8"), "Apple": ("#4f7f45", "#6a9c55")}
CONIFERS = {"Fir": "#2f5b3a", "Blue spruce": "#4f7a7a",
            "Golden cypress": "#9aa83f"}
SHRUBS = {"Green": "#4f7f45", "Dark green": "#2f5b3a",
          "Purple": "#6b2f3a", "Flowering": "#d98cb3"}
CANOPIES = {"Cream": "#e3d8c0", "Navy": "#34496b", "Terracotta": "#b8674a"}
FLOWERS = ("#d94f4f", "#f0c330", "#9b59b6", "#f39c12", "#ffffff",
           "#e86aa6")
BARK, BIRCH_BARK, SOIL = "#6b4f35", "#ece9e1", "#5a4030"
TYRE = "#1f2023"
GLASS_DARK = "#3b4650"


def _disc_x(name, x, y, z, r, t, color, material="Default", alpha=1.0,
            seg=40):
    """A disc with its axis along +X, from *x* to *x* + *t*, centred on
    (y, z) — a wheel."""
    move = CadNode("translate", name, dict(x=x, y=y, z=z))
    turn = CadNode("rotate", name, dict(x=0.0, y=90.0, z=0.0))
    turn.add(CadNode("cylinder", name, dict(
        x=0.0, y=0.0, z=0.0, height=t, radius_bottom=r, radius_top=r,
        segments=seg, center=False)))
    move.add(turn)
    return _paint(move, color, material, alpha)


# ---------------------------------------------------------------- stairs

def build_stairs_straight(dims):
    p = _dims(dims, STRAIGHT_STAIR_SIZES)
    w, rise, run = p["w"], p["rise"], p["run"]
    wood, _dark = _pick(dims, WOODS, "Oak")
    n = max(3, int(round(rise / 180.0)))
    step, tread = rise / n, run / n
    part = CadNode("union", "Stairs")
    for i in range(n):
        top, y0 = (i + 1) * step, -run / 2 + i * tread
        part.add(_box("Tread", -w / 2, y0 - 25, top - 40, w, tread + 25, 40,
                      wood))
        part.add(_box("Riser", -w / 2, y0, top - step, w, 20, step - 40,
                      WHITE))
    for x in (-w / 2 - 40, w / 2):
        part.add(_hull("Stringer", [
            _cube("Foot", x, -run / 2 - 25, 0.0, 40, 60, 300),
            _cube("Head", x, run / 2 - 60, rise - 300, 40, 60, 300)], WHITE))
    hx = w / 2 + 20

    def rail_z(y):
        return 900 + (y + run / 2) / run * rise

    part.add(_box("Newel post", hx - 45, -run / 2 - 70, 0.0, 90, 90, 1000,
                  wood))
    part.add(_rod("Handrail", (hx, -run / 2, rail_z(-run / 2)),
                  (hx, run / 2, rail_z(run / 2)), 25, wood, "Default"))
    for i in range(n):
        yc = -run / 2 + (i + 0.5) * tread
        part.add(_rod("Baluster", (hx, yc, (i + 1) * step),
                      (hx, yc, rail_z(yc)), 12, WHITE, "Default"))
    return part


def build_stairs_spiral(dims):
    p = _dims(dims, SPIRAL_STAIR_SIZES)
    r, rise = p["d"] / 2, p["rise"]
    wood, _dark = _pick(dims, WOODS, "Oak")
    n = max(6, int(round(rise / 200.0)))
    step, da = rise / n, math.radians(330.0 / n)
    part = CadNode("union", "Spiral stairs")
    part.add(_cyl("Column", 0.0, 0.0, 0.0, rise + 900, 55, BLACK, seg=24,
                  material="Metal"))
    prev = None
    for i in range(n):
        a0 = i * da - math.pi / 2           # starts at the front (-Y)
        a1, z = a0 + da, (i + 1) * step
        pts = [(0.0, 0.0), (r * math.cos(a0), r * math.sin(a0)),
               (r * math.cos(a1), r * math.sin(a1))]
        part.add(_hull("Tread", [_cube("Corner", x - 10, y - 10, z - 40, 20,
                                       20, 40) for x, y in pts], wood))
        post = (r * 0.95 * math.cos(a1), r * 0.95 * math.sin(a1), z + 900)
        part.add(_rod("Baluster", (post[0], post[1], z), post, 10, BLACK))
        if prev is not None:
            part.add(_rod("Handrail", prev, post, 18, BLACK))
        prev = post
    return part


# -------------------------------------------------------------- garage

def build_car(dims):
    p = _dims(dims, CAR_SIZES)
    L, W, H = p["l"], p["w"], p["h"]
    body = _pick(dims, CARS, "Red")
    wheel = 330.0
    part = CadNode("union", "Car")
    part.add(_box("Body", -W / 2, -L / 2, 220.0, W, L, 560, body, r=160,
                  material="Metal"))
    part.add(_hull("Windows", [
        _cube("Belt", -W / 2 + 60, -L / 2 + 900, 770.0, W - 120, L - 1500,
              10),
        _cube("Roofline", -W / 2 + 140, -L / 2 + 1500, H - 60, W - 280,
              L - 2350, 10)], GLASS_DARK, "Glass"))
    part.add(_box("Roof", -W / 2 + 150, -L / 2 + 1550, H - 50, W - 300,
                  L - 2450, 50, body, r=20, material="Metal"))
    for sy in (-1, 1):
        y = sy * (L / 2 - 720)
        for sx in (-1, 1):
            x = -W / 2 - 5 if sx < 0 else W / 2 - 215
            part.add(_disc_x("Tyre", x, y, wheel, wheel, 220, TYRE))
            part.add(_disc_x("Hub", x - 8 if sx < 0 else x + 220, y, wheel,
                             150, 8, CHROME, "Metal"))
    for sx in (-1, 1):
        part.add(_box("Headlight", sx * (W / 2 - 260) - 110, -L / 2 - 4,
                      560.0, 220, 20, 90, "#fffbe6", r=20,
                      material="Emissive"))
        part.add(_box("Tail light", sx * (W / 2 - 250) - 100, L / 2 - 16,
                      600.0, 200, 20, 80, "#c0392b", r=15,
                      material="Emissive"))
    for y in (-L / 2 - 20, L / 2 - 100):
        part.add(_box("Bumper", -W / 2 + 40, y, 250.0, W - 80, 120, 150,
                      "#2a2c30", r=40))
    return part


def build_bicycle(dims):
    p = _dims(dims, BIKE_SIZES)
    L, r = p["l"], p["wheel"] / 2
    frame = _pick(dims, CARS, "Blue")
    k = L / 1750.0
    yf, yb = -L / 2 + r, L / 2 - r
    part = CadNode("union", "Bicycle")
    for y in (yf, yb):
        part.add(_disc_x("Tyre", -18.0, y, r, r, 36, TYRE))
        part.add(_disc_x("Rim", -20.0, y, r, r * 0.85, 40, "#9aa0a6",
                         "Metal"))
    bb, seat = (0.0, 100 * k, 300 * k), (0.0, 250 * k, 850 * k)
    head, low = (0.0, -350 * k, 820 * k), (0.0, -330 * k, 700 * k)
    for a, b in ((bb, seat), ((0.0, 235 * k, 790 * k), head), (bb, low),
                 (bb, (0.0, yb, r)), ((0.0, 240 * k, 780 * k), (0.0, yb, r)),
                 (low, (0.0, yf, r)), (head, (0.0, -380 * k, 950 * k))):
        part.add(_rod("Frame", a, b, 16, frame))
    part.add(_rod("Handlebar", (-280.0, -380 * k, 950 * k),
                  (280.0, -380 * k, 950 * k), 12, BLACK))
    part.add(_box("Saddle", -70.0, 170 * k, 850 * k, 140, 260, 40, BLACK,
                  r=15))
    return part


def build_wheelie_bin(dims):
    p = _dims(dims, BIN_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    colour = _pick(dims, BINS, "Green")
    part = CadNode("union", "Wheelie bin")
    part.add(_hull("Bin", [_cube("Base", -w / 2 + 30, -d / 2 + 40, 40.0,
                                 w - 60, d - 80, 1),
                           _cube("Rim", -w / 2, -d / 2, h - 60, w, d, 1)],
                   colour, "Plastic"))
    part.add(_box("Lid", -w / 2 - 10, -d / 2 - 20, h - 60, w + 20, d + 30, 50,
                  _mix(colour, "#000000", 0.15), r=10, material="Plastic"))
    part.add(_box("Foot", -w / 2 + 60, -d / 2 + 40, 0.0, w - 120, 60, 60,
                  _mix(colour, "#000000", 0.2)))
    for x in (-w / 2 + 10, w / 2 - 60):
        part.add(_disc_x("Wheel", x, d / 2 - 80, 100.0, 100, 50, BLACK))
    return part


def build_garage_shelving(dims):
    p = _dims(dims, SHELVING_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    grey = "#7d838a"
    part = CadNode("union", "Garage shelving")
    for sx in (-1, 1):
        for sy in (-1, 1):
            part.add(_box("Upright", sx * (w / 2 - 20) - 20,
                          sy * (d / 2 - 20) - 20, 0.0, 40, 40, h, grey,
                          material="Metal"))
    levels = 5
    crates = ("#c0392b", "#2e6fb5", "#3a3d42", "#e3b53b", "#4f9a58")
    for i in range(levels):
        z = 80 + i * (h - 120) / (levels - 1)
        part.add(_box("Shelf", -w / 2, -d / 2, z, w, d, 20, "#b98f5e"))
        if 0 < i < levels - 1:
            for j, x in enumerate((-w / 2 + 40, -60.0, w / 2 - 340)):
                part.add(_box("Crate", x, -d / 2 + 40, z + 20, 300, d - 80,
                              260, crates[(i + j) % len(crates)], r=10,
                              material="Plastic"))
    return part


def build_lawn_mower(dims):
    p = _dims(dims, MOWER_SIZES)
    w, l = p["w"], p["l"]
    green = "#3e7d3a"
    part = CadNode("union", "Lawn mower")
    part.add(_box("Deck", -w / 2, -l / 2, 60.0, w, l, 220, green, r=40,
                  material="Plastic"))
    part.add(_cyl("Engine", 0.0, -l * 0.1, 280.0, 160, 150, BLACK,
                  material="Plastic"))
    for sx in (-1, 1):
        part.add(_rod("Handle", (sx * (w / 2 - 40), l / 2 - 40, 250.0),
                      (sx * (w / 2 - 40), l / 2 + 450, 950.0), 12, BLACK))
        for y in (-l / 2 + 90, l / 2 - 90):
            part.add(_disc_x("Wheel", -w / 2 - 30 if sx < 0 else w / 2,
                             y, 90.0, 90, 30, BLACK))
    part.add(_rod("Grip", (-w / 2 + 40, l / 2 + 450, 950.0),
                  (w / 2 - 40, l / 2 + 450, 950.0), 14, BLACK))
    return part


# ------------------------------------------------------------ reception

def build_reception_desk(dims):
    p = _dims(dims, RECEPTION_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    front = _pick(dims, FRONTS, "White")
    wood, _dark = WOODS["Oak"]
    part = CadNode("union", "Reception desk")
    part.add(_box("Plinth", -w / 2 + 20, -d / 2 - 10, 0.0, w - 40, 20, 100,
                  PLINTH))
    part.add(_box("Front panel", -w / 2, -d / 2, 0.0, w, 60, h, front, r=6))
    for sx in (-1, 1):
        part.add(_box("End panel", -w / 2 if sx < 0 else w / 2 - 60, -d / 2,
                      0.0, 60, d, h, front, r=6))
    part.add(_box("Counter", -w / 2 - 20, -d / 2 - 80, h, w + 40, 320, 30,
                  STONE, r=6))
    part.add(_box("Desk", -w / 2 + 60, -d / 2 + 60, 710.0, w - 120, d - 60,
                  30, wood, r=4))
    part.add(_box("Light strip", -w / 2 + 100, -d / 2 - 4, h - 120, w - 200,
                  6, 40, "#fff4d6", material="Emissive"))
    return part


def build_waiting_chairs(dims):
    p = _dims(dims, WAITING_SIZES)
    n, seat = int(p["seats"]), p["seat"]
    fab = _pick(dims, FABRICS, "Navy")
    pitch = 560.0
    W = n * pitch
    part = CadNode("union", "Waiting chairs")
    part.add(_box("Beam", -W / 2, -40.0, 280.0, W, 80, 50, BLACK,
                  material="Metal"))
    for sx in (-1, 1):
        x = sx * (W / 2 - 60)
        part.add(_box("Foot", x - 25, -250.0, 0.0, 50, 500, 40, BLACK,
                      material="Metal"))
        part.add(_box("Post", x - 25, -25.0, 40.0, 50, 50, 240, BLACK,
                      material="Metal"))
    for i in range(n):
        x = -W / 2 + (i + 0.5) * pitch
        part.add(_box("Seat", x - 230, -230.0, seat - 60, 460, 460, 60, fab,
                      r=25))
        part.add(_box("Back", x - 230, 190.0, seat, 460, 50, 420, fab, r=25))
    return part


def build_water_cooler(dims):
    p = _dims(dims, COOLER_SIZES)
    h = p["h"]
    part = CadNode("union", "Water cooler")
    part.add(_box("Body", -160.0, -160.0, 0.0, 320, 320, h, WHITE, r=12))
    part.add(_cyl("Bottle", 0.0, 0.0, h, 420, 140, "#8fc3e6", r2=120,
                  material="Glass", alpha=0.6))
    for x, colour in ((-50.0, "#2e6fb5"), (50.0, "#c0392b")):
        part.add(_box("Tap", x - 20, -175.0, h - 260, 40, 20, 50, colour,
                      r=6, material="Plastic"))
    return part


# ------------------------------------------- hallway, entrance, porch

def build_wall_light(dims):
    p = _dims(dims, WALL_LIGHT_SIZES)
    shade = p["shade"]
    part = CadNode("union", "Wall light")
    part.add(_box("Back plate", -60.0, 20.0, 0.0, 120, 20, 180, BRASS,
                  material="Metal"))
    part.add(_rod("Arm", (0.0, 20.0, 90.0), (0.0, -120.0, 160.0), 8, BRASS))
    part.add(_cyl("Shade", 0.0, -120.0, 120.0, 140, shade / 2, LINEN,
                  r2=shade * 0.38, seg=40, alpha=0.92))
    return part


def build_doormat(dims):
    p = _dims(dims, DOORMAT_SIZES)
    w, d = p["w"], p["d"]
    part = CadNode("union", "Doormat")
    part.add(_box("Border", -w / 2, -d / 2, 0.0, w, d, 12, "#4a3a28",
                  material="Matte"))
    part.add(_box("Coir", -w / 2 + 40, -d / 2 + 40, 12.0, w - 80, d - 80, 6,
                  "#a5804f", material="Matte"))
    return part


def build_umbrella_stand(dims):
    p = _dims(dims, UMBRELLA_SIZES)
    h = p["h"]
    part = CadNode("union", "Umbrella stand")
    part.add(_cyl("Stand", 0.0, 0.0, 0.0, h, 120, BLACK, r2=130,
                  material="Metal"))
    for (x, y, colour) in ((30.0, 20.0, "#34496b"), (-40.0, -10.0, "#c0392b")):
        part.add(_rod("Umbrella", (x * 0.5, y * 0.5, 100.0),
                      (x * 2, y * 2, h + 350), 22, colour, "Default"))
        part.add(_rod("Handle", (x * 2, y * 2, h + 350),
                      (x * 2 + 60, y * 2, h + 420), 12, BLACK, "Default"))
    return part


def build_wall_mirror(dims):
    p = _dims(dims, WALL_MIRROR_SIZES)
    w, h = p["w"], p["h"]
    frame = _pick(dims, {"Brass": BRASS, "Oak": WOODS["Oak"][0],
                         "Black": BLACK}, "Brass")
    part = CadNode("union", "Wall mirror")
    part.add(_box("Frame", -w / 2, -15.0, 0.0, w, 30, h, frame, r=10,
                  material="Metal" if frame == BRASS else "Default"))
    part.add(_box("Mirror", -w / 2 + 40, -19.0, 40.0, w - 80, 6, h - 80,
                  "#dfe6ea", r=6, material="Metal"))
    return part


# --------------------------------------------------------------- garden

def build_tree_broadleaf(dims):
    p = _dims(dims, TREE_SIZES)
    h, spread = p["h"], p["spread"]
    name = dims.get("_color") or "Summer"
    leaf, light = TREES.get(name, TREES["Summer"])
    trunk = h * 0.42
    rt = max(60.0, h * 0.025)
    R = min(spread / 2, (h - trunk) / 2)
    zc = h - R
    part = CadNode("union", "Tree")
    part.add(_cyl("Trunk", 0.0, 0.0, 0.0, trunk + h * 0.1, rt, BARK,
                  r2=rt * 0.6, seg=24))
    for i in range(3):
        a = 2 * math.pi * i / 3
        part.add(_rod("Branch", (0.0, 0.0, trunk * 0.8),
                      (math.cos(a) * R * 0.25, math.sin(a) * R * 0.25,
                       zc - R * 0.35), rt * 0.35, BARK, "Default"))
    part.add(_ball8("Crown", 0.0, 0.0, zc, R * 0.6, leaf))
    for i in range(6):
        a = 2 * math.pi * i / 6
        part.add(_ball8("Crown", math.cos(a) * R * 0.5, math.sin(a) * R * 0.5,
                       zc + (0.15 if i % 2 else -0.1) * R, R * 0.5,
                       light if i % 2 else leaf))
    part.add(_ball8("Crown", 0.0, 0.0, h - R * 0.45, R * 0.45, light))
    if name == "Apple":
        for i in range(10):
            a = 2 * math.pi * i / 10 + 0.3
            part.add(_ball8("Apple", math.cos(a) * R * 0.93,
                           math.sin(a) * R * 0.93,
                           zc + ((i % 3) - 1) * 0.25 * R, R * 0.07,
                           "#c0392b"))
    return part


def build_tree_conifer(dims):
    p = _dims(dims, CONIFER_SIZES)
    h, spread = p["h"], p["spread"]
    colour = _pick(dims, CONIFERS, "Fir")
    part = CadNode("union", "Conifer")
    part.add(_cyl("Trunk", 0.0, 0.0, 0.0, h * 0.3, max(50.0, h * 0.02), BARK,
                  seg=20))
    for k in range(4):
        rb = spread / 2 * (1 - k * 0.2)
        part.add(_cyl("Foliage", 0.0, 0.0, h * 0.1 + k * h * 0.18, h * 0.36,
                      rb, _mix(colour, "#ffffff", 0.06 * k), r2=rb * 0.08,
                      seg=24))
    return part


def build_tree_birch(dims):
    p = _dims(dims, BIRCH_SIZES)
    h, spread = p["h"], p["spread"]
    leaf, light = TREES.get(dims.get("_color") or "Summer", TREES["Summer"])
    trunk = h * 0.55
    rt = max(45.0, h * 0.015)
    R = min(spread / 2, (h - trunk * 0.7) / 2)
    part = CadNode("union", "Birch")
    part.add(_cyl("Trunk", 0.0, 0.0, 0.0, trunk + R, rt, BIRCH_BARK,
                  r2=rt * 0.6, seg=20))
    for k in range(6):
        part.add(_cyl("Bark mark", 0.0, 0.0, 150 + k * trunk / 6, 25,
                      rt * 1.04, "#2d2f33", seg=20))
    for i in range(8):
        a = 2 * math.pi * i / 8
        z = h - R + (0.3 if i % 2 else -0.25) * R
        part.add(_ball8("Leaves", math.cos(a) * R * 0.55,
                       math.sin(a) * R * 0.55, z, R * 0.42,
                       _mix(light if i % 2 else leaf, "#ffffff", 0.1)))
    part.add(_ball8("Leaves", 0.0, 0.0, h - R * 0.4, R * 0.4, light))
    return part


def build_shrub(dims):
    p = _dims(dims, SHRUB_SIZES)
    s = p["size"]
    colour = _pick(dims, SHRUBS, "Green")
    r = s * 0.32
    part = CadNode("union", "Shrub")
    for i in range(5):
        a = 2 * math.pi * i / 5
        part.add(_ball8("Leaves", math.cos(a) * s * 0.2, math.sin(a) * s * 0.2,
                       r, r, _mix(colour, "#ffffff", 0.08 * (i % 2))))
    part.add(_ball8("Leaves", 0.0, 0.0, s - r, r, colour))
    return part


def build_hedge(dims):
    p = _dims(dims, HEDGE_SIZES)
    l, d, h = p["l"], p["d"], p["h"]
    colour = _pick(dims, SHRUBS, "Dark green")
    part = CadNode("union", "Hedge")
    part.add(_box("Hedge", -l / 2, -d / 2, 0.0, l, d, h, colour, r=250,
                  material="Matte"))
    n = max(2, int(l / 700))
    for i in range(n):
        x = -l / 2 + (i + 0.5) * l / n
        part.add(_ball8("Leaves", x, 0.0, h - d * 0.32, d * 0.38,
                       _mix(colour, "#ffffff", 0.07)))
    return part


def build_flower_bed(dims):
    p = _dims(dims, FLOWER_BED_SIZES)
    w, d = p["w"], p["d"]
    part = CadNode("union", "Flower bed")
    part.add(_box("Edging", -w / 2, -d / 2, 0.0, w, d, 150, STONE))
    part.add(_box("Soil", -w / 2 + 60, -d / 2 + 60, 150.0, w - 120, d - 120,
                  20, SOIL, material="Matte"))
    cols, rows = max(2, int(w / 250)), max(1, int(d / 250))
    k = 0
    for i in range(cols):
        for j in range(rows):
            x = -w / 2 + 60 + (i + 0.5) * (w - 120) / cols
            y = -d / 2 + 60 + (j + 0.5) * (d - 120) / rows
            top = 170 + 150 + 60 * ((i + j) % 3)
            part.add(_cyl("Stem", x, y, 170.0, top - 170, 8, "#4f7f45",
                          seg=8))
            part.add(_ball8("Flower", x, y, top, 55, FLOWERS[k % len(FLOWERS)]))
            k += 1
    return part


def build_planter(dims):
    p = _dims(dims, PLANTER_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    wood, dark = _pick(dims, WOODS, "Oak")
    part = CadNode("union", "Planter")
    part.add(_box("Box", -w / 2, -d / 2, 0.0, w, d, h, wood, r=6))
    part.add(_box("Soil", -w / 2 + 30, -d / 2 + 30, h, w - 60, d - 60, 5,
                  SOIL))
    r = min(w, d) * 0.35
    for i in range(3):
        x = (i - 1) * w * 0.28
        part.add(_ball8("Leaves", x, 0.0, h + r * 0.8, r,
                       "#4f7f45" if i % 2 else "#6a9c55"))
    return part


def build_garden_bench(dims):
    p = _dims(dims, GARDEN_BENCH_SIZES)
    w = p["w"]
    wood, _dark = _pick(dims, WOODS, "Oak")
    d, seat = 600.0, 450.0
    part = CadNode("union", "Garden bench")
    for sx in (-1, 1):
        x = sx * (w / 2 - 30) - 20
        part.add(_box("End", x, -d / 2, 0.0, 40, 80, 650, BLACK,
                      material="Metal"))
        part.add(_box("End", x, d / 2 - 80, 0.0, 40, 80, 850, BLACK,
                      material="Metal"))
        part.add(_box("Arm", x, -d / 2, 640.0, 40, d, 40, BLACK,
                      material="Metal"))
        part.add(_box("Seat rail", x, -d / 2, seat - 70, 40, d, 40, BLACK,
                      material="Metal"))
    for i in range(5):
        part.add(_box("Slat", -w / 2 + 40, -d / 2 + 20 + i * 105, seat - 30,
                      w - 80, 90, 30, wood, r=6))
    for i in range(3):
        part.add(_box("Back slat", -w / 2 + 40, d / 2 - 60, seat + 80 + i * 110,
                      w - 80, 25, 80, wood, r=6))
    return part


def build_patio_set(dims):
    p = _dims(dims, PATIO_SIZES)
    d, ph = p["d"], p["parasol"]
    canopy = _pick(dims, CANOPIES, "Cream")
    part = CadNode("union", "Patio table & parasol")
    part.add(_cyl("Foot", 0.0, 0.0, 0.0, 30, 250, "#55585e", seg=40,
                  material="Metal"))
    for sx in (-1, 1):
        for sy in (-1, 1):
            part.add(_rod("Leg", (sx * d * 0.3, sy * d * 0.3, 20.0),
                          (sx * d * 0.2, sy * d * 0.2, 710.0), 14, "#55585e"))
    part.add(_cyl("Table top", 0.0, 0.0, 720.0, 20, d / 2, "#cfe3ea", seg=48,
                  material="Glass", alpha=0.6))
    part.add(_cyl("Parasol pole", 0.0, 0.0, 30.0, ph - 30, 20, WHITE, seg=16))
    # a hull of the rim and the crown: always wound outward, where the
    # shallow cone came out with faces the plan's culling dropped
    rim = CadNode("cylinder", "Rim", dict(
        x=0.0, y=0.0, z=ph - 380, height=10, radius_bottom=1350,
        radius_top=1350, segments=8, center=False))
    crown = CadNode("cylinder", "Crown", dict(
        x=0.0, y=0.0, z=ph - 60, height=10, radius_bottom=60,
        radius_top=60, segments=8, center=False))
    part.add(_hull("Canopy", [rim, crown], canopy, "Matte"))
    return part


def build_bbq(dims):
    part = CadNode("union", "Barbecue")
    for i in range(3):
        a = 2 * math.pi * i / 3 + math.pi / 2
        part.add(_rod("Leg", (0.0, 0.0, 520.0),
                      (math.cos(a) * 320, math.sin(a) * 320, 18.0), 18, BLACK))
    part.add(_cyl("Bowl", 0.0, 0.0, 480.0, 260, 200, BLACK, r2=290, seg=40,
                  material="Metal"))
    part.add(_cyl("Lid", 0.0, 0.0, 740.0, 220, 290, BLACK, r2=110, seg=40,
                  material="Metal"))
    part.add(_rod("Handle", (-80.0, 0.0, 990.0), (80.0, 0.0, 990.0), 14,
                  STEEL))
    return part


# --------------------------------------------------------------- registry

STRAIGHT_STAIR_SIZES = {
    "Straight (900 wide, 2.6 m)": dict(w=900.0, rise=2600.0, run=3600.0),
    "Wide (1000 wide, 2.8 m)": dict(w=1000.0, rise=2800.0, run=3900.0),
}
SPIRAL_STAIR_SIZES = {"Ø1600, 2.6 m": dict(d=1600.0, rise=2600.0),
                      "Ø1400, 2.6 m": dict(d=1400.0, rise=2600.0)}
CAR_SIZES = {"Hatchback (4.0 m)": dict(l=4000.0, w=1750.0, h=1450.0),
             "Estate (4.7 m)": dict(l=4700.0, w=1820.0, h=1500.0),
             "SUV (4.6 m)": dict(l=4600.0, w=1900.0, h=1700.0)}
BIKE_SIZES = {"Adult": dict(l=1750.0, wheel=700.0),
              "Child": dict(l=1300.0, wheel=500.0)}
BIN_SIZES = {"240 litres": dict(w=580.0, d=740.0, h=1070.0),
             "140 litres": dict(w=480.0, d=550.0, h=1060.0)}
SHELVING_SIZES = {"1200 × 450": dict(w=1200.0, d=450.0, h=1800.0)}
MOWER_SIZES = {"Push mower": dict(w=450.0, l=600.0)}
RECEPTION_SIZES = {"2400": dict(w=2400.0, d=800.0, h=1100.0),
                   "1800": dict(w=1800.0, d=800.0, h=1100.0)}
WAITING_SIZES = {"3 seats": dict(seats=3, seat=450.0),
                 "4 seats": dict(seats=4, seat=450.0)}
COOLER_SIZES = {"Standard": dict(h=1000.0)}
WALL_LIGHT_SIZES = {"Standard": dict(shade=180.0)}
DOORMAT_SIZES = {"800 × 500": dict(w=800.0, d=500.0),
                 "1200 × 700": dict(w=1200.0, d=700.0)}
UMBRELLA_SIZES = {"Standard": dict(h=550.0)}
WALL_MIRROR_SIZES = {"700 × 1000": dict(w=700.0, h=1000.0),
                     "Long 500 × 1500": dict(w=500.0, h=1500.0)}
TREE_SIZES = {"Small (3 m)": dict(h=3000.0, spread=2200.0),
              "Medium (5 m)": dict(h=5000.0, spread=3800.0),
              "Large (8 m)": dict(h=8000.0, spread=6000.0)}
CONIFER_SIZES = {"Medium (4 m)": dict(h=4000.0, spread=2000.0),
                 "Tall (8 m)": dict(h=8000.0, spread=3500.0)}
BIRCH_SIZES = {"Medium (6 m)": dict(h=6000.0, spread=2800.0)}
SHRUB_SIZES = {"Small (600)": dict(size=600.0),
               "Large (1200)": dict(size=1200.0)}
HEDGE_SIZES = {"3 m": dict(l=3000.0, d=700.0, h=1400.0),
               "6 m": dict(l=6000.0, d=800.0, h=1600.0)}
FLOWER_BED_SIZES = {"2000 × 800": dict(w=2000.0, d=800.0),
                    "3000 × 1000": dict(w=3000.0, d=1000.0)}
PLANTER_SIZES = {"800 × 400": dict(w=800.0, d=400.0, h=450.0)}
GARDEN_BENCH_SIZES = {"1500": dict(w=1500.0), "1200": dict(w=1200.0)}
PATIO_SIZES = {"Round 900": dict(d=900.0, parasol=2400.0)}
BBQ_SIZES = {"Kettle": dict(d=580.0)}

_WHD = [("w", "Width"), ("d", "Depth"), ("h", "Height")]
_WD = [("w", "Width"), ("d", "Depth")]


def _entry(label, build, sizes, fields, colors=None, **extra):
    entry = dict(label=label, category=CATEGORY, sizes=sizes, build=build,
                 fields=fields, **extra)
    if colors:
        entry["colors"] = list(colors)
    return entry


PARTS = {
    # stairs
    "home_stairs_straight": _entry(
        "Stairs (straight flight)", build_stairs_straight,
        STRAIGHT_STAIR_SIZES,
        [("w", "Width"), ("rise", "Total rise"), ("run", "Total run")],
        WOODS),
    "home_stairs_spiral": _entry(
        "Spiral stairs", build_stairs_spiral, SPIRAL_STAIR_SIZES,
        [("d", "Diameter"), ("rise", "Total rise")], WOODS),
    # garage and driveway
    "home_car": _entry("Car", build_car, CAR_SIZES,
                       [("l", "Length"), ("w", "Width"), ("h", "Height")],
                       CARS),
    "home_bicycle": _entry("Bicycle", build_bicycle, BIKE_SIZES,
                           [("l", "Length"), ("wheel", "Wheel diameter")],
                           CARS),
    "home_wheelie_bin": _entry("Wheelie bin", build_wheelie_bin, BIN_SIZES,
                               _WHD, BINS),
    "home_garage_shelving": _entry("Garage shelving (with crates)",
                                   build_garage_shelving, SHELVING_SIZES,
                                   _WHD),
    "home_lawn_mower": _entry("Lawn mower", build_lawn_mower, MOWER_SIZES,
                              [("w", "Width"), ("l", "Length")]),
    # reception
    "home_reception_desk": _entry("Reception desk", build_reception_desk,
                                  RECEPTION_SIZES, _WHD, FRONTS),
    "home_waiting_chairs": _entry(
        "Waiting chairs (row)", build_waiting_chairs, WAITING_SIZES,
        [("seats", "Seats"), ("seat", "Seat height")], FABRICS),
    "home_water_cooler": _entry("Water cooler", build_water_cooler,
                                COOLER_SIZES, [("h", "Height")]),
    # hallway, entrance, porch
    "home_wall_light": _entry("Wall light", build_wall_light,
                              WALL_LIGHT_SIZES,
                              [("shade", "Shade diameter")], rest_z=1700.0),
    "home_doormat": _entry("Doormat", build_doormat, DOORMAT_SIZES, _WD),
    "home_umbrella_stand": _entry("Umbrella stand", build_umbrella_stand,
                                  UMBRELLA_SIZES, [("h", "Height")]),
    "home_wall_mirror": _entry("Wall mirror", build_wall_mirror,
                               WALL_MIRROR_SIZES,
                               [("w", "Width"), ("h", "Height")],
                               ["Brass", "Oak", "Black"], rest_z=900.0),
    # garden
    "home_tree_broadleaf": _entry("Tree (broadleaf)", build_tree_broadleaf,
                                  TREE_SIZES,
                                  [("h", "Height"), ("spread", "Spread")],
                                  TREES),
    "home_tree_conifer": _entry("Tree (conifer)", build_tree_conifer,
                                CONIFER_SIZES,
                                [("h", "Height"), ("spread", "Spread")],
                                CONIFERS),
    "home_tree_birch": _entry("Tree (silver birch)", build_tree_birch,
                              BIRCH_SIZES,
                              [("h", "Height"), ("spread", "Spread")],
                              ["Summer", "Autumn"]),
    "home_shrub": _entry("Shrub", build_shrub, SHRUB_SIZES,
                         [("size", "Size")], SHRUBS),
    "home_hedge": _entry("Hedge", build_hedge, HEDGE_SIZES,
                         [("l", "Length"), ("d", "Depth"), ("h", "Height")],
                         SHRUBS),
    "home_flower_bed": _entry("Flower bed", build_flower_bed,
                              FLOWER_BED_SIZES, _WD),
    "home_planter": _entry("Planter (with shrubs)", build_planter,
                           PLANTER_SIZES, _WHD, WOODS),
    "home_garden_bench": _entry("Garden bench", build_garden_bench,
                                GARDEN_BENCH_SIZES, [("w", "Width")], WOODS),
    "home_patio_set": _entry("Patio table & parasol", build_patio_set,
                             PATIO_SIZES,
                             [("d", "Table diameter"),
                              ("parasol", "Parasol height")], CANOPIES),
    "home_bbq": _entry("Barbecue", build_bbq, BBQ_SIZES, [("d", "Diameter")]),
}

#: dialog fields holding a count (integer spin box, no "mm" suffix)
COUNT_FIELDS = {"seats"}

# laboratory and company pieces join the home catalogue (the House
# Builder furnishes labs and offices from it)
from . import library_lab  # noqa: E402

PARTS.update(library_lab.PARTS)
COUNT_FIELDS |= library_lab.COUNT_FIELDS
