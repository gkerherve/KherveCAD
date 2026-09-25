"""More home furniture for the parts library — enough for every room of
a house, so the House Builder's catalogue has plenty in each:

- living room: corner sofa, side table, ottoman, rug, plant, table
  lamp, upright piano, fireplace;
- dining room: round table, bench, display cabinet, pendant light;
- bedroom and kids' room: dressing table, bunk bed, cot, toy box;
- kitchen: island, bar stool, microwave, dishwasher;
- bathroom: towel radiator, mirror cabinet, laundry basket;
- office: desk, office chair, filing cabinet, laptop, wall shelf;
- utility: washing machine, tumble dryer;
- hallway: console table, coat stand, shoe cabinet.

Same rules as `library_home` (whose primitives and colour tables this
reuses): multi-coloured unions of boxes, rounded boxes, cylinders,
capsules and hulls, NO booleans, true dimensions in mm, front facing -Y,
standing on z = 0 and centred on X and Y. A piece hung on a wall or a
ceiling is built from its own bottom up too; its entry's ``rest_z`` is
the height the House Builder puts it at. An entry with ``on_top`` sits
on whatever is under it when placed (a lamp on a table, a microwave on
the worktop — `house.surface_below`).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from .library_home import (APPLIANCE, BLACK, BOOKS, BRASS, CERAMIC, CHROME,
                           FABRICS, FRONTS, GLASS, LINEN, PLINTH, STEEL,
                           STONE, WHITE, WOODS, _ball, _bar, _box, _count,
                           _cyl, _legs, _mix, _paint, _pick, _rod)
from .library_room import _dims
from .model import CadNode

CATEGORY = "Home furniture"

#: dialog fields holding a count (integer spin box, no "mm" suffix)
COUNT_FIELDS = {"drawers"}

RUGS = {"Terracotta": ("#b8674a", "#7e3f2a"), "Navy": ("#34496b", "#1f2c43"),
        "Sage": ("#8ea58a", "#5d7159"), "Cream": ("#e3d8c0", "#b9a98a"),
        "Grey": ("#9aa0a6", "#5f656b")}
POTS = {"Terracotta": "#b8674a", "White": "#f1efea", "Charcoal": "#4a4f56"}
PIANOS = {"Black": "#1b1c1f", "Walnut": "#5b3d27", "White": "#f1efea"}
SURROUNDS = {"Stone": STONE, "White": WHITE, "Brick": "#9c5a45"}
LAMP_BASES = {"Ceramic": CERAMIC, "Brass": BRASS, "Black": BLACK}
PENDANTS = {"Black": BLACK, "Brass": BRASS, "White": "#f4f4f2"}
TOYS = {"Blue": "#2e6fb5", "Red": "#c0392b", "Yellow": "#e3b53b",
        "Green": "#4f9a58"}
RADIATORS = {"Chrome": CHROME, "White": "#f4f4f2", "Anthracite": "#3a3d42"}
CABINETS = {"Grey": "#9aa0a6", "White": "#f1efea", "Black": "#2d2f33"}
LAPTOPS = {"Silver": STEEL, "Space grey": "#5b5f66"}
BASKETS = {"Wicker": "#b8935a", "White": "#f1efea", "Grey": "#9aa0a6"}
LEAF, LEAF_LIGHT = "#4f7f45", "#6a9c55"
FIRE, FLAME = "#ff8a2a", "#ffb347"
SCREEN = "#1d2530"


# ----------------------------------------------------------- primitives

def _cube(name, x, y, z, w, d, h):
    return CadNode("cube", name, dict(x=x, y=y, z=z, width=w, depth=d,
                                      height=h, center=False))


def _ball8(name, x, y, z, r, color, material="Default"):
    """A low-poly ball for foliage and flowers: 8 segments or fewer is
    an intended polygon the document's common $fn leaves alone, where a
    smooth ball became ~2000 triangles and a flower bed 70 000."""
    return _paint(CadNode("sphere", name, dict(x=x, y=y, z=z, radius=r,
                                               segments=8)),
                  color, material)


def _hull(name, parts, color, material="Default"):
    """The convex hull of uncoloured *parts* in one colour — a sloped
    board or a wedge without a boolean."""
    node = CadNode("hull", name)
    for p in parts:
        node.add(p)
    return _paint(node, color, material)


def _disc_y(name, x, y, z, r, t, color, material="Default", alpha=1.0,
            seg=40):
    """A disc facing the front: axis along -Y, from *y* to *y* - *t*,
    centred on (x, z) — a porthole, a dial."""
    move = CadNode("translate", name, dict(x=x, y=y, z=z))
    turn = CadNode("rotate", name, dict(x=90.0, y=0.0, z=0.0))
    turn.add(CadNode("cylinder", name, dict(
        x=0.0, y=0.0, z=0.0, height=t, radius_bottom=r, radius_top=r,
        segments=seg, center=False)))
    move.add(turn)
    return _paint(move, color, material, alpha)


def _appliance(dims, default="White"):
    body = _pick(dims, APPLIANCE, default)
    return body, ("Metal" if body == STEEL else "Default")


# ---------------------------------------------------------- living room

def build_corner_sofa(dims):
    p = _dims(dims, CORNER_SIZES)
    w, l, d, h, seat = p["w"], p["l"], p["d"], p["h"], p["seat"]
    fab = _pick(dims, FABRICS, "Grey")
    soft = _mix(fab, "#ffffff", 0.12)
    arm, back, foot = 170.0, 190.0, 110.0
    base_h = seat - 130 - foot
    part = CadNode("union", "Corner sofa")
    leg = WOODS["Walnut"][1]
    for x, y in ((-w / 2 + 70, d / 2 - 70), (w / 2 - 70, d / 2 - 70),
                 (w / 2 - 70, -d / 2 + 70), (-w / 2 + 70, d / 2 - l + 70),
                 (-w / 2 + d - 70, d / 2 - l + 70)):
        part.add(_cyl("Leg", x, y, 0.0, foot, 20, leg, r2=16, seg=24))
    part.add(_box("Base", -w / 2, -d / 2, foot, w, d, base_h, fab, r=25, material="Fabric"))
    part.add(_box("Chaise base", -w / 2, d / 2 - l, foot, d, l - d + 25,
                  base_h, fab, r=25, material="Fabric"))
    part.add(_box("Back", -w / 2, d / 2 - back, foot, w, back, h - foot, fab,
                  r=45, material="Fabric"))
    part.add(_box("Side back", -w / 2, d / 2 - l, foot, back, l - back,
                  h - foot, fab, r=45, material="Fabric"))
    part.add(_box("Arm", w / 2 - arm, -d / 2, foot, arm, d,
                  seat + 190 - foot, fab, r=50, material="Fabric"))
    part.add(_box("End arm", -w / 2, d / 2 - l, foot, d, arm,
                  seat + 190 - foot, fab, r=50, material="Fabric"))
    run = w - arm - d
    n = max(1, int(round(run / 700.0)))
    cw = run / n
    for i in range(n):
        x = -w / 2 + d + i * cw
        part.add(_box("Seat cushion", x + 6, -d / 2 + 25, seat - 135,
                      cw - 12, d - back - 30, 140, soft, r=45, material="Fabric"))
    part.add(_box("Chaise cushion", -w / 2 + back + 6, d / 2 - l + arm + 6,
                  seat - 135, d - back - 12, l - arm - back - 12, 140, soft,
                  r=45, material="Fabric"))
    run = w - back - arm
    m = max(1, int(round(run / 750.0)))
    bw = run / m
    for i in range(m):
        x = -w / 2 + back + i * bw
        part.add(_box("Back cushion", x + 8, d / 2 - back - 160, seat,
                      bw - 16, 180, h - seat - 30, soft, r=60, material="Fabric"))
    part.add(_box("Back cushion", -w / 2 + back, d / 2 - l + arm + 8, seat,
                  180, l - arm - back - 176, h - seat - 30, soft, r=60, material="Fabric"))
    return part


def build_side_table(dims):
    p = _dims(dims, SIDE_TABLE_SIZES)
    d, h = p["d"], p["h"]
    wood, dark = _pick(dims, WOODS, "Oak")
    part = CadNode("union", "Side table")
    part.add(_cyl("Foot", 0.0, 0.0, 0.0, 20, d * 0.32, dark, r2=d * 0.3,
                  seg=40))
    part.add(_cyl("Pedestal", 0.0, 0.0, 20.0, h - 45, 28, dark, seg=24))
    part.add(_cyl("Top", 0.0, 0.0, h - 25, 25, d / 2, wood, seg=48))
    return part


def build_ottoman(dims):
    p = _dims(dims, OTTOMAN_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    fab = _pick(dims, FABRICS, "Mustard")
    part = CadNode("union", "Ottoman")
    _legs(part, w, d, 50, 60, 16, WOODS["Walnut"][1], r2=12)
    part.add(_box("Body", -w / 2, -d / 2, 60.0, w, d, h - 60, fab, r=60))
    part.add(_box("Top", -w / 2 + 10, -d / 2 + 10, h - 40, w - 20, d - 20,
                  40, _mix(fab, "#ffffff", 0.1), r=30))
    return part


def build_rug(dims):
    p = _dims(dims, RUG_SIZES)
    w, d = p["w"], p["d"]
    main, dark = _pick(dims, RUGS, "Terracotta")
    part = CadNode("union", "Rug")
    part.add(_box("Border", -w / 2, -d / 2, 0.0, w, d, 8, dark,
                  material="Matte"))
    part.add(_box("Field", -w / 2 + 90, -d / 2 + 90, 8.0, w - 180, d - 180,
                  4, main, material="Matte"))
    part.add(_box("Medallion", -w * 0.18, -d * 0.18, 12.0, w * 0.36,
                  d * 0.36, 2, _mix(main, "#ffffff", 0.35),
                  material="Matte"))
    return part


def build_plant(dims):
    p = _dims(dims, PLANT_SIZES)
    h, pot = p["h"], p["pot"]
    colour = _pick(dims, POTS, "Terracotta")
    ph, r = pot * 0.9, pot / 2
    crown = h - ph
    part = CadNode("union", "Plant")
    part.add(_cyl("Pot", 0.0, 0.0, 0.0, ph, r * 0.78, colour, r2=r, seg=40,
                  material="Clay" if colour == POTS["Terracotta"]
                  else "Default"))
    part.add(_cyl("Soil", 0.0, 0.0, ph - 30, 22, r * 0.9, "#4a3526", seg=40))
    part.add(_cyl("Stem", 0.0, 0.0, ph - 10, crown * 0.55,
                  max(8.0, pot * 0.03), "#6b4f35", seg=16))
    n = 7
    for i in range(n):
        a = 2 * math.pi * i / n
        part.add(_ball8("Leaves", crown * 0.28 * math.cos(a),
                       crown * 0.28 * math.sin(a),
                       ph + crown * (0.45 + 0.12 * (i % 3)), crown * 0.26,
                       LEAF if i % 2 else LEAF_LIGHT))
    part.add(_ball8("Leaves", 0.0, 0.0, ph + crown * 0.72, crown * 0.26,
                   LEAF_LIGHT))
    return part


def build_table_lamp(dims):
    p = _dims(dims, TABLE_LAMP_SIZES)
    h, shade = p["h"], p["shade"]
    base = _pick(dims, LAMP_BASES, "Ceramic")
    part = CadNode("union", "Table lamp")
    part.add(_cyl("Foot", 0.0, 0.0, 0.0, 12, h * 0.1, base, seg=32))
    part.add(_ball("Base", 0.0, 0.0, h * 0.16, h * 0.16, base))
    part.add(_cyl("Stem", 0.0, 0.0, h * 0.3, h * 0.45, 8, BRASS, seg=16,
                  material="Metal"))
    part.add(_cyl("Shade", 0.0, 0.0, h - shade * 0.62, shade * 0.62,
                  shade / 2, LINEN, r2=shade * 0.38, seg=40, alpha=0.92))
    return part


def build_piano(dims):
    p = _dims(dims, PIANO_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    body = _pick(dims, PIANOS, "Black")
    edge = _mix(body, "#000000", 0.25)
    kz = 720.0
    part = CadNode("union", "Piano")
    part.add(_box("Case", -w / 2, -d / 2 + 220, 0.0, w, d - 220, h, body,
                  r=8))
    part.add(_box("Lid", -w / 2 - 10, -d / 2 + 210, h, w + 20, d - 200, 20,
                  body, r=6))
    part.add(_box("Key bed", -w / 2, -d / 2 + 60, kz - 80, w, 180, 80, body))
    part.add(_box("Keys", -w / 2 + 70, -d / 2 + 70, kz, w - 140, 150, 22,
                  "#f7f5ef"))
    ww, x0 = (w - 140) / 52.0, -w / 2 + 70
    for k in range(51):
        if k % 7 in (0, 1, 3, 4, 5):          # C#, D#, F#, G#, A#
            part.add(_box("Black key", x0 + (k + 1) * ww - 7,
                          -d / 2 + 130, kz + 22, 14, 90, 12, BLACK))
    part.add(_box("Music desk", -w / 2 + 200, -d / 2 + 215, kz + 120,
                  w - 400, 20, 260, edge))
    for sx in (-1, 1):
        part.add(_box("Leg", sx * (w / 2 - 60) - 30, -d / 2 + 60, 0.0, 60,
                      60, kz - 80, body))
    for i in (-1, 0, 1):
        part.add(_box("Pedal", i * 70 - 20, -d / 2 + 150, 80.0, 40, 90, 20,
                      BRASS, material="Metal"))
    return part


def build_fireplace(dims):
    p = _dims(dims, FIREPLACE_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    stone = _pick(dims, SURROUNDS, "Stone")
    pillar, opening = 220.0, h - 300
    part = CadNode("union", "Fireplace")
    part.add(_box("Hearth", -w / 2 - 100, -d / 2 - 250, 0.0, w + 200,
                  d + 250, 40, _mix(stone, "#000000", 0.2)))
    for sx in (-1, 1):
        part.add(_box("Pillar", -w / 2 if sx < 0 else w / 2 - pillar,
                      -d / 2, 40.0, pillar, d, h - 100, stone))
    part.add(_box("Lintel", -w / 2 + pillar - 5, -d / 2, 40 + opening,
                  w - 2 * pillar + 10, d, h - 100 - opening, stone))
    part.add(_box("Mantel", -w / 2 - 60, -d / 2 - 60, h - 60, w + 120,
                  d + 60, 60, WOODS["Walnut"][0], r=6))
    part.add(_box("Firebox", -w / 2 + pillar, -d / 2 + 80, 40.0,
                  w - 2 * pillar, d - 80, opening, "#1d1d1f"))
    part.add(_box("Embers", -180.0, -d / 2 + 120, 40.0, 360, 160, 40, FIRE,
                  material="Emissive"))
    part.add(_rod("Log", (-200.0, -d / 2 + 160, 110.0),
                  (200.0, -d / 2 + 200, 110.0), 45, "#6b4a33", "Default"))
    part.add(_rod("Log", (-160.0, -d / 2 + 230, 150.0),
                  (180.0, -d / 2 + 150, 150.0), 40, "#5b3d27", "Default"))
    part.add(_cyl("Flame", 0.0, -d / 2 + 180, 80.0, 260, 110, FLAME, r2=10,
                  seg=24, material="Emissive", alpha=0.85))
    return part


# ---------------------------------------------------------- dining room

def build_round_table(dims):
    p = _dims(dims, ROUND_TABLE_SIZES)
    d, h = p["d"], p["h"]
    wood, dark = _pick(dims, WOODS, "Oak")
    part = CadNode("union", "Round table")
    part.add(_box("Foot", -d * 0.3, -40.0, 0.0, d * 0.6, 80, 80, dark, r=10))
    part.add(_box("Foot", -40.0, -d * 0.3, 0.0, 80, d * 0.6, 80, dark, r=10))
    part.add(_cyl("Pedestal", 0.0, 0.0, 80.0, h - 115, 70, dark, r2=55,
                  seg=32))
    part.add(_cyl("Top", 0.0, 0.0, h - 35, 35, d / 2, wood, seg=64))
    return part


def build_bench(dims):
    p = _dims(dims, BENCH_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    wood, dark = _pick(dims, WOODS, "Oak")
    part = CadNode("union", "Bench")
    part.add(_box("Seat", -w / 2, -d / 2, h - 40, w, d, 40, wood, r=8))
    for sx in (-1, 1):
        part.add(_box("Leg", sx * (w / 2 - 120) - 20, -d / 2 + 30, 0.0, 40,
                      d - 60, h - 40, dark))
    part.add(_box("Stretcher", -w / 2 + 120, -20.0, 120.0, w - 240, 40, 50,
                  dark))
    return part


def build_display_cabinet(dims):
    p = _dims(dims, DISPLAY_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    wood, dark = _pick(dims, WOODS, "Oak")
    t, plinth = 25.0, 80.0
    part = CadNode("union", "Display cabinet")
    part.add(_box("Plinth", -w / 2 + 20, -d / 2 + 20, 0.0, w - 40, d - 20,
                  plinth, dark))
    for sx in (-1, 1):
        part.add(_box("Side", -w / 2 if sx < 0 else w / 2 - t, -d / 2,
                      plinth, t, d, h - plinth, wood))
    part.add(_box("Top", -w / 2, -d / 2, h - t, w, d, t, wood))
    part.add(_box("Bottom", -w / 2 + t, -d / 2, plinth, w - 2 * t, d, t,
                  wood))
    part.add(_box("Back", -w / 2 + t, d / 2 - 10, plinth + t, w - 2 * t, 10,
                  h - plinth - 2 * t, dark))
    shelves = 3
    gap = (h - plinth - 2 * t - shelves * 18) / (shelves + 1)
    for i in range(shelves + 1):
        z = plinth + t + i * (gap + 18)
        if i < shelves:
            part.add(_box("Shelf", -w / 2 + t, -d / 2 + 20, z + gap,
                          w - 2 * t, d - 30, 18, GLASS, material="Glass",
                          alpha=0.5))
        for sx in (-1, 1):
            for k in range(5):
                part.add(_cyl("Plate", sx * w * 0.2, 20.0, z + 2 + k * 16,
                              13, min(110.0, gap * 0.9, w * 0.18), CERAMIC,
                              seg=32))
    dw = (w - 12) / 2
    for i in range(2):
        x = -w / 2 + 6 + i * (dw + 0.0)
        part.add(_box("Glass door", x + 2, -d / 2 - 10, plinth + 10, dw - 4,
                      8, h - plinth - 40, GLASS, material="Glass",
                      alpha=0.25))
        part.add(_box("Door rail", x + 2, -d / 2 - 14, plinth + 10, dw - 4,
                      12, 50, wood))
        part.add(_box("Door rail", x + 2, -d / 2 - 14, h - 80, dw - 4, 12,
                      50, wood))
        hx = x + dw - 40 if i == 0 else x + 40
        part.add(_rod("Handle", (hx, -d / 2 - 22, h * 0.45),
                      (hx, -d / 2 - 22, h * 0.45 + 160), 7, BRASS))
    return part


def build_pendant(dims):
    p = _dims(dims, PENDANT_SIZES)
    shade, drop = p["shade"], p["drop"]
    colour = _pick(dims, PENDANTS, "Black")
    mat = "Default" if colour == PENDANTS["White"] else "Metal"
    sh = shade * 0.45
    part = CadNode("union", "Pendant light")
    part.add(_cyl("Shade", 0.0, 0.0, 0.0, sh, shade / 2, colour,
                  r2=shade * 0.12, seg=48, material=mat))
    part.add(_ball("Bulb", 0.0, 0.0, sh * 0.35, shade * 0.12, "#fff4d6",
                   "Emissive"))
    part.add(_cyl("Cord", 0.0, 0.0, sh, drop, 4, BLACK, seg=12))
    part.add(_cyl("Ceiling rose", 0.0, 0.0, sh + drop, 30, 55, colour,
                  seg=32, material=mat))
    return part


# ------------------------------------------------ bedroom and kids' room

def build_dressing_table(dims):
    p = _dims(dims, DRESSING_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    wood, dark = _pick(dims, WOODS, "White")
    part = CadNode("union", "Dressing table")
    _legs(part, w, d, 40, h - 30, 16, dark, r2=20)
    part.add(_box("Top", -w / 2, -d / 2, h - 30, w, d, 30, wood, r=6))
    part.add(_box("Drawer", -w / 2 + 40, -d / 2 - 2, h - 150, w - 80, 20,
                  110, _mix(wood, dark, 0.2), r=3))
    for sx in (-1, 1):
        part.add(_ball("Knob", sx * w / 4, -d / 2 - 12, h - 95, 13, BRASS,
                       "Metal"))
    part.add(_box("Mirror frame", -w * 0.3, d / 2 - 40, h, w * 0.6, 30, 800,
                  wood, r=20))
    part.add(_box("Mirror", -w * 0.3 + 30, d / 2 - 44, h + 30, w * 0.6 - 60,
                  6, 740, "#dfe6ea", r=12, material="Metal"))
    return part


def build_bunk_bed(dims):
    p = _dims(dims, BUNK_SIZES)
    w, l, h = p["w"], p["l"], p["h"]
    wood, dark = _pick(dims, WOODS, "White")
    post = 60.0
    W, L = w + 2 * post, l + 2 * post
    part = CadNode("union", "Bunk bed")
    for sx in (-1, 1):
        for sy in (-1, 1):
            part.add(_box("Post", sx * (W / 2 - post / 2) - post / 2,
                          sy * (L / 2 - post / 2) - post / 2, 0.0, post,
                          post, h, wood, r=6))
    duvets = (FABRICS["Sage"], FABRICS["Navy"])
    for level, z in enumerate((300.0, 1150.0)):
        for sx in (-1, 1):
            part.add(_box("Side rail", -W / 2 if sx < 0 else W / 2 - post,
                          -L / 2 + post, z - 140, post, L - 2 * post, 140,
                          wood))
        for sy in (-1, 1):
            part.add(_box("End rail", -W / 2 + post,
                          -L / 2 if sy < 0 else L / 2 - post, z - 140,
                          W - 2 * post, post, 140, wood))
        part.add(_box("Slats", -w / 2, -l / 2, z - 40, w, l, 20, dark))
        part.add(_box("Mattress", -w / 2, -l / 2, z - 20, w, l, 160,
                      "#f7f6f2", r=40))
        part.add(_box("Duvet", -w / 2 - 5, -l / 2 - 5, z + 100, w + 10,
                      l * 0.7, 70, duvets[level], r=30))
        part.add(_box("Pillow", -w / 2 + 60, l / 2 - 420, z + 120, w - 120,
                      340, 110, "#fbfbf8", r=50))
    for sx in (-1, 1):
        part.add(_box("Guard rail", -W / 2 if sx < 0 else W / 2 - post,
                      -L / 2 + post, 1150.0 + 180, post, L - 2 * post, 50,
                      wood))
    ly = -L / 2 - 40
    for sx in (-1, 1):
        part.add(_rod("Ladder", (sx * w * 0.25, ly, 18.0),
                      (sx * w * 0.25, ly, 1150.0 + 200), 18, wood, "Default"))
    for k in range(1, 5):
        z = k * 1150.0 / 4.4
        part.add(_rod("Rung", (-w * 0.25, ly, z), (w * 0.25, ly, z), 14,
                      wood, "Default"))
    return part


def build_cot(dims):
    p = _dims(dims, COT_SIZES)
    w, l, h = p["w"], p["l"], p["h"]
    wood, _dark = _pick(dims, WOODS, "White")
    base = 300.0
    part = CadNode("union", "Cot")
    for sy in (-1, 1):
        part.add(_box("End panel", -w / 2 - 25,
                      -l / 2 - 25 if sy < 0 else l / 2, 0.0, w + 50, 25, h,
                      wood, r=6))
    for sx in (-1, 1):
        x = sx * (w / 2 + 12)
        part.add(_box("Bottom rail", x - 12, -l / 2, base - 60, 24, l, 40,
                      wood))
        part.add(_box("Top rail", x - 15, -l / 2, h - 40, 30, l, 40, wood,
                      r=8))
        n = max(2, int(l / 90))
        for i in range(1, n):
            y = -l / 2 + i * l / n
            part.add(_rod("Bar", (x, y, base - 20), (x, y, h - 40), 10,
                          wood, "Default"))
    part.add(_box("Base", -w / 2, -l / 2, base - 40, w, l, 20, wood))
    part.add(_box("Mattress", -w / 2 + 5, -l / 2 + 5, base - 20, w - 10,
                  l - 10, 100, "#f7f6f2", r=25))
    part.add(_box("Blanket", -w / 2 + 10, -l / 2 + 10, base + 70, w - 20,
                  l * 0.5, 30, "#cfe0ec", r=12))
    return part


def build_toy_box(dims):
    p = _dims(dims, TOY_BOX_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    colour = _pick(dims, TOYS, "Blue")
    part = CadNode("union", "Toy box")
    part.add(_box("Box", -w / 2, -d / 2, 0.0, w, d, h - 30, colour, r=12))
    part.add(_box("Lid", -w / 2 - 10, -d / 2 - 10, h - 30, w + 20, d + 20, 30,
                  _mix(colour, "#ffffff", 0.25), r=10))
    part.add(_ball("Ball", w * 0.25, 0.0, h + 80, 80, TOYS["Yellow"]))
    part.add(_box("Block", -w * 0.3, -60.0, h, 120, 120, 120, TOYS["Red"],
                  r=8))
    return part


# -------------------------------------------------------------- kitchen

def build_island(dims):
    p = _dims(dims, ISLAND_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    front = _pick(dims, FRONTS, "White")
    over = 250.0                          # worktop overhang for stools
    body = d - over
    part = CadNode("union", "Kitchen island")
    part.add(_box("Plinth", -w / 2 + 50, -d / 2 + over + 50, 0.0, w - 100,
                  body - 100, 100, PLINTH))
    part.add(_box("Units", -w / 2, -d / 2 + over, 100.0, w, body, h - 140,
                  WHITE))
    n = max(1, int(round(w / 600.0)))
    dw = w / n
    for i in range(n):
        x = -w / 2 + i * dw
        part.add(_box("Door", x + 3, d / 2 - 2, 110.0, dw - 6, 20, h - 160,
                      front, r=3))
        part.add(_bar(x + dw / 2, d / 2 + 26, h - 100))
    part.add(_box("Worktop", -w / 2 - 20, -d / 2, h - 40, w + 40, d + 20, 40,
                  STONE, r=4))
    return part


def build_bar_stool(dims):
    p = _dims(dims, BAR_STOOL_SIZES)
    w, seat = p["w"], p["seat"]
    fab = _pick(dims, FABRICS, "Charcoal")
    r, zf = w * 0.4, seat * 0.4
    part = CadNode("union", "Bar stool")
    part.add(_cyl("Base", 0.0, 0.0, 0.0, 15, w * 0.5, CHROME, r2=w * 0.45,
                  seg=40, material="Metal"))
    part.add(_cyl("Column", 0.0, 0.0, 15.0, seat - 75, 25, CHROME, seg=24,
                  material="Metal"))
    corners = ((-r, -r), (r, -r), (r, r), (-r, r))
    for (ax, ay), (bx, by) in zip(corners, corners[1:] + corners[:1]):
        part.add(_rod("Footrest", (ax, ay, zf), (bx, by, zf), 10))
    part.add(_rod("Spoke", (-r, -r, zf), (r, r, zf), 9))
    part.add(_rod("Spoke", (-r, r, zf), (r, -r, zf), 9))
    part.add(_cyl("Seat", 0.0, 0.0, seat - 60, 60, w / 2, fab, seg=40))
    part.add(_box("Back", -w * 0.35, w * 0.3, seat, w * 0.7, 30, 200, fab,
                  r=12))
    return part


def build_microwave(dims):
    p = _dims(dims, MICROWAVE_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    body, mat = _appliance(dims, "Steel")
    dw = w * 0.7
    part = CadNode("union", "Microwave")
    part.add(_box("Body", -w / 2, -d / 2, 0.0, w, d, h, body, r=8,
                  material=mat))
    part.add(_box("Door", -w / 2 + 10, -d / 2 - 4, 15.0, dw, 8, h - 30,
                  BLACK, r=4, material="Plastic"))
    part.add(_box("Window", -w / 2 + 40, -d / 2 - 6, 45.0, dw - 60, 4, h - 90,
                  "#30343a", material="Glass", alpha=0.8))
    part.add(_box("Controls", -w / 2 + dw + 18, -d / 2 - 4, 15.0,
                  w - dw - 28, 8, h - 30, _mix(body, "#000000", 0.2), r=3))
    return part


def build_dishwasher(dims):
    p = _dims(dims, DISHWASHER_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    body, mat = _appliance(dims, "White")
    part = CadNode("union", "Dishwasher")
    part.add(_box("Cabinet", -w / 2, -d / 2 + 30, 0.0, w, d - 30, h,
                  _mix(body, "#000000", 0.06), r=6, material=mat))
    part.add(_box("Door", -w / 2, -d / 2, 20.0, w, 34, h - 120, body, r=6,
                  material=mat))
    part.add(_box("Controls", -w / 2, -d / 2, h - 95, w, 34, 95,
                  _mix(body, "#000000", 0.3), r=4))
    part.add(_bar(0.0, -d / 2 - 14, h - 140, 380))
    return part


# ------------------------------------------------------------- bathroom

def build_towel_radiator(dims):
    p = _dims(dims, RADIATOR_SIZES)
    w, h = p["w"], p["h"]
    colour = _pick(dims, RADIATORS, "Chrome")
    part = CadNode("union", "Towel radiator")
    for sx in (-1, 1):
        part.add(_rod("Upright", (sx * w / 2, 0.0, 15.0),
                      (sx * w / 2, 0.0, h - 15), 15, colour))
        for z in (h * 0.2, h * 0.8):
            part.add(_rod("Bracket", (sx * w / 2, 0.0, z),
                          (sx * w / 2, 60.0, z), 8, colour))
    n = max(3, int(h / 110))
    for i in range(n):
        z = 60 + i * (h - 120) / (n - 1)
        part.add(_rod("Rail", (-w / 2, 0.0, z), (w / 2, 0.0, z), 10, colour))
    return part


def build_bath_cabinet(dims):
    p = _dims(dims, BATH_CABINET_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    wood, _dark = _pick(dims, WOODS, "White")
    part = CadNode("union", "Mirror cabinet")
    part.add(_box("Cabinet", -w / 2, -d / 2, 0.0, w, d, h, wood, r=6))
    for i in range(2):
        part.add(_box("Mirror door", -w / 2 + 5 + i * w / 2, -d / 2 - 6, 5.0,
                      w / 2 - 10, 8, h - 10, "#dfe6ea", r=4,
                      material="Metal"))
    return part


def build_laundry_basket(dims):
    p = _dims(dims, BASKET_SIZES)
    d, h = p["d"], p["h"]
    colour = _pick(dims, BASKETS, "Wicker")
    part = CadNode("union", "Laundry basket")
    part.add(_cyl("Basket", 0.0, 0.0, 0.0, h - 40, d / 2 * 0.9, colour,
                  r2=d / 2, seg=40, material="Matte"))
    part.add(_cyl("Lid", 0.0, 0.0, h - 40, 40, d / 2 + 10,
                  _mix(colour, "#000000", 0.1), r2=d / 2, seg=40))
    return part


# --------------------------------------------------------------- office

def build_desk(dims):
    p = _dims(dims, DESK_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    wood, dark = _pick(dims, WOODS, "Oak")
    face = _mix(wood, dark, 0.2)
    pw = 400.0
    part = CadNode("union", "Desk")
    part.add(_box("Top", -w / 2, -d / 2, h - 30, w, d, 30, wood, r=5))
    part.add(_box("Pedestal", w / 2 - pw, -d / 2 + 10, 0.0, pw, d - 20,
                  h - 30, _mix(wood, dark, 0.1)))
    fh = (h - 30 - 60) / 3 - 8
    for i in range(3):
        z = 40 + i * (fh + 8)
        part.add(_box("Drawer", w / 2 - pw + 10, -d / 2, z, pw - 20, 12, fh,
                      face, r=3))
        part.add(_bar(w / 2 - pw / 2, -d / 2 - 8, z + fh - 40, 160))
    part.add(_box("Side", -w / 2 + 10, -d / 2 + 10, 0.0, 30, d - 20, h - 30,
                  dark))
    part.add(_box("Modesty panel", -w / 2 + 40, d / 2 - 40, h - 330,
                  w - pw - 40, 18, 300, dark))
    return part


def build_office_chair(dims):
    p = _dims(dims, OFFICE_CHAIR_SIZES)
    w, seat, h = p["w"], p["seat"], p["h"]
    fab = _pick(dims, FABRICS, "Charcoal")
    part = CadNode("union", "Office chair")
    for i in range(5):
        a = 2 * math.pi * i / 5 + math.pi / 2
        ex, ey = math.cos(a) * w * 0.45, math.sin(a) * w * 0.45
        part.add(_rod("Leg", (0.0, 0.0, 90.0), (ex, ey, 70.0), 16, BLACK,
                      "Plastic"))
        part.add(_ball("Caster", ex, ey, 30.0, 30, BLACK, "Plastic"))
    part.add(_cyl("Gas lift", 0.0, 0.0, 80.0, seat - 170, 25, CHROME, seg=24,
                  material="Metal"))
    part.add(_box("Seat", -w * 0.4, -w * 0.4, seat - 90, w * 0.8, w * 0.8,
                  90, fab, r=40))
    part.add(_rod("Back stem", (0.0, w * 0.35, seat - 50),
                  (0.0, w * 0.4 - 20, seat + 120), 18, BLACK, "Plastic"))
    part.add(_box("Back", -w * 0.36, w * 0.4 - 60, seat + 60, w * 0.72, 70,
                  h - seat - 60, fab, r=35))
    for sx in (-1, 1):
        part.add(_rod("Arm post", (sx * w * 0.38, 0.0, seat - 60),
                      (sx * w * 0.38, 0.0, seat + 180), 14, BLACK, "Plastic"))
        part.add(_box("Arm pad", sx * w * 0.38 - 30, -140.0, seat + 180, 60,
                      280, 30, BLACK, r=12, material="Plastic"))
    return part


def build_filing_cabinet(dims):
    p = _dims(dims, FILING_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    n = _count(p, "drawers", 1, 6)
    colour = _pick(dims, CABINETS, "Grey")
    part = CadNode("union", "Filing cabinet")
    part.add(_box("Body", -w / 2, -d / 2 + 20, 0.0, w, d - 20, h, colour, r=4,
                  material="Metal"))
    fh = (h - 40 - (n - 1) * 10) / n
    for i in range(n):
        z = 20 + i * (fh + 10)
        part.add(_box("Drawer", -w / 2 + 15, -d / 2, z, w - 30, 24, fh,
                      _mix(colour, "#ffffff", 0.1), r=3, material="Metal"))
        part.add(_bar(0.0, -d / 2 - 8, z + fh - 60, 140))
    return part


def build_laptop(dims):
    p = _dims(dims, LAPTOP_SIZES)
    w, d = p["w"], p["d"]
    colour = _pick(dims, LAPTOPS, "Silver")
    top = 14 + d * 0.95
    part = CadNode("union", "Laptop")
    part.add(_box("Base", -w / 2, -d / 2, 0.0, w, d, 16, colour, r=4,
                  material="Metal"))
    part.add(_box("Keyboard", -w / 2 + 20, -d / 2 + 70, 16.0, w - 40,
                  d - 110, 1, "#2b2d31"))
    part.add(_hull("Lid", [_cube("Hinge", -w / 2, d / 2 - 8, 14.0, w, 8, 2),
                           _cube("Top edge", -w / 2, d / 2 + 40, top, w, 8,
                                 2)], colour, "Metal"))
    part.add(_hull("Screen", [_cube("Low", -w / 2 + 15, d / 2 - 12, 30.0,
                                    w - 30, 2, 2),
                              _cube("High", -w / 2 + 15, d / 2 + 34,
                                    top - 15, w - 30, 2, 2)], SCREEN))
    return part


def build_wall_shelf(dims):
    p = _dims(dims, WALL_SHELF_SIZES)
    w, d = p["w"], p["d"]
    wood, _dark = _pick(dims, WOODS, "Oak")
    part = CadNode("union", "Wall shelf")
    for sx in (-1, 1):
        x = sx * w * 0.35
        part.add(_box("Bracket", x - 10, d / 2 - 20, 0.0, 20, 20, 200, BLACK,
                      material="Metal"))
        part.add(_box("Bracket arm", x - 10, -d / 2 + 30, 170.0, 20, d - 50,
                      30, BLACK, material="Metal"))
    part.add(_box("Shelf", -w / 2, -d / 2, 200.0, w, d, 28, wood, r=3))
    x = -w / 2 + 40
    for k, bw in enumerate((30, 38, 26, 42, 32, 28, 36)):
        part.add(_box("Book", x, -d / 2 + 30, 228.0, bw - 2, d - 70,
                      200 + (k * 37) % 60, BOOKS[k % len(BOOKS)]))
        x += bw
    return part


# -------------------------------------------------------------- utility

def build_washing_machine(dims, dryer=False):
    p = _dims(dims, WASHER_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    body, mat = _appliance(dims, "White")
    zc = h * 0.45
    part = CadNode("union", "Tumble dryer" if dryer else "Washing machine")
    part.add(_box("Cabinet", -w / 2, -d / 2, 0.0, w, d, h, body, r=8,
                  material=mat))
    part.add(_box("Control panel", -w / 2 + 10, -d / 2 - 4, h - 130, w - 20,
                  8, 110, _mix(body, "#000000", 0.08), r=4))
    part.add(_disc_y("Dial", w / 2 - 120, -d / 2 - 4, h - 75, 35, 20, CHROME,
                     "Metal"))
    part.add(_box("Display", -60.0, -d / 2 - 6, h - 100, 140, 4, 50, SCREEN))
    if not dryer:
        part.add(_box("Soap drawer", -w / 2 + 20, -d / 2 - 6, h - 110, 160, 6,
                      70, _mix(body, "#ffffff", 0.1)))
    part.add(_disc_y("Door ring", 0.0, -d / 2, zc, w * 0.36, 30,
                     "#55585e" if dryer else CHROME, "Metal"))
    part.add(_disc_y("Door glass", 0.0, -d / 2 - 30, zc, w * 0.27, 8,
                     "#2b2d31" if dryer else "#3b4650", "Glass",
                     alpha=0.9 if dryer else 0.6))
    return part


def build_tumble_dryer(dims):
    return build_washing_machine(dims, dryer=True)


# -------------------------------------------------------------- hallway

def build_console_table(dims):
    p = _dims(dims, CONSOLE_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    wood, dark = _pick(dims, WOODS, "Walnut")
    part = CadNode("union", "Console table")
    _legs(part, w, d, 30, h - 25, 12, dark, r2=12)
    part.add(_box("Top", -w / 2, -d / 2, h - 25, w, d, 25, wood, r=5))
    part.add(_box("Shelf", -w / 2 + 30, -d / 2 + 30, 150.0, w - 60, d - 60,
                  18, wood))
    return part


def build_coat_stand(dims):
    p = _dims(dims, COAT_STAND_SIZES)
    h = p["h"]
    wood, dark = _pick(dims, WOODS, "Walnut")
    part = CadNode("union", "Coat stand")
    for i in range(3):
        a = 2 * math.pi * i / 3 + math.pi / 2
        part.add(_rod("Foot", (0.0, 0.0, 120.0),
                      (math.cos(a) * 260, math.sin(a) * 260, 18.0), 18,
                      dark, "Default"))
    part.add(_cyl("Pole", 0.0, 0.0, 60.0, h - 60, 22, wood, seg=24))
    part.add(_ball("Knob", 0.0, 0.0, h, 30, dark))
    for i in range(6):
        a = 2 * math.pi * i / 6 - math.pi / 4
        part.add(_rod("Hook", (0.0, 0.0, h - 150),
                      (math.cos(a) * 180, math.sin(a) * 180, h - 60), 10,
                      dark, "Default"))
    part.add(_box("Coat", 30.0, -230.0, h - 1000, 300, 150, 900,
                  FABRICS["Navy"], r=60))
    return part


def build_shoe_cabinet(dims):
    p = _dims(dims, SHOE_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    wood, dark = _pick(dims, WOODS, "White")
    face = _mix(wood, dark, 0.2)
    part = CadNode("union", "Shoe cabinet")
    part.add(_box("Body", -w / 2, -d / 2, 0.0, w, d, h, wood, r=4))
    fh = (h - 40) / 2 - 8
    for i in range(2):
        z = 20 + i * (fh + 8)
        part.add(_box("Flap", -w / 2 + 8, -d / 2 - 16, z, w - 16, 18, fh,
                      face, r=3))
        part.add(_bar(0.0, -d / 2 - 24, z + fh - 50, 300))
    return part


# --------------------------------------------------------------- registry

CORNER_SIZES = {
    "Corner (2600×1700)": dict(w=2600.0, l=1700.0, d=950.0, h=820.0,
                               seat=440.0),
    "Large corner (3000×2000)": dict(w=3000.0, l=2000.0, d=980.0, h=820.0,
                                     seat=440.0),
}
SIDE_TABLE_SIZES = {"Round 500": dict(d=500.0, h=550.0),
                    "Round 400": dict(d=400.0, h=500.0)}
OTTOMAN_SIZES = {"Square 700": dict(w=700.0, d=700.0, h=420.0),
                 "Bench 1200": dict(w=1200.0, d=450.0, h=440.0)}
RUG_SIZES = {"2000 × 1400": dict(w=2000.0, d=1400.0),
             "3000 × 2000": dict(w=3000.0, d=2000.0),
             "Runner 2400 × 800": dict(w=2400.0, d=800.0)}
PLANT_SIZES = {"Floor (1400)": dict(h=1400.0, pot=400.0),
               "Tall (1800)": dict(h=1800.0, pot=450.0),
               "Table (450)": dict(h=450.0, pot=160.0)}
TABLE_LAMP_SIZES = {"Small": dict(h=450.0, shade=300.0),
                    "Large": dict(h=620.0, shade=400.0)}
PIANO_SIZES = {"Upright": dict(w=1500.0, d=600.0, h=1250.0)}
FIREPLACE_SIZES = {"Stove + mantel (1300)": dict(w=1300.0, d=380.0,
                                                 h=1150.0),
                   "Wide (1800)": dict(w=1800.0, d=400.0, h=1200.0)}
ROUND_TABLE_SIZES = {"4 seats (1100)": dict(d=1100.0, h=750.0),
                     "6 seats (1400)": dict(d=1400.0, h=750.0)}
BENCH_SIZES = {"1400": dict(w=1400.0, d=380.0, h=450.0),
               "1800": dict(w=1800.0, d=380.0, h=450.0)}
DISPLAY_SIZES = {"1000 × 1900": dict(w=1000.0, d=420.0, h=1900.0)}
PENDANT_SIZES = {"Dome (400)": dict(shade=400.0, drop=650.0),
                 "Wide (550)": dict(shade=550.0, drop=600.0)}
DRESSING_SIZES = {"1100": dict(w=1100.0, d=450.0, h=750.0)}
BUNK_SIZES = {"Single (900×1900)": dict(w=900.0, l=1900.0, h=1600.0)}
COT_SIZES = {"Cot (600×1200)": dict(w=600.0, l=1200.0, h=900.0),
             "Cot bed (700×1400)": dict(w=700.0, l=1400.0, h=900.0)}
TOY_BOX_SIZES = {"800 × 450": dict(w=800.0, d=450.0, h=450.0)}
ISLAND_SIZES = {"1800 × 900": dict(w=1800.0, d=900.0, h=900.0),
                "2400 × 1000": dict(w=2400.0, d=1000.0, h=900.0)}
BAR_STOOL_SIZES = {"Counter (650)": dict(w=420.0, seat=650.0),
                   "Bar (750)": dict(w=420.0, seat=750.0)}
MICROWAVE_SIZES = {"Standard": dict(w=500.0, d=380.0, h=290.0)}
DISHWASHER_SIZES = {"Freestanding 600": dict(w=600.0, d=600.0, h=850.0),
                    "Slimline 450": dict(w=450.0, d=600.0, h=850.0)}
RADIATOR_SIZES = {"500 × 1200": dict(w=500.0, h=1200.0),
                  "600 × 1600": dict(w=600.0, h=1600.0)}
BATH_CABINET_SIZES = {"600 × 700": dict(w=600.0, d=150.0, h=700.0),
                      "800 × 700": dict(w=800.0, d=150.0, h=700.0)}
BASKET_SIZES = {"Standard": dict(d=420.0, h=600.0)}
DESK_SIZES = {"1200 × 600": dict(w=1200.0, d=600.0, h=750.0),
              "1400 × 700": dict(w=1400.0, d=700.0, h=750.0)}
OFFICE_CHAIR_SIZES = {"Task chair": dict(w=620.0, seat=480.0, h=1050.0)}
FILING_SIZES = {"4 drawers": dict(w=460.0, d=620.0, h=1320.0, drawers=4),
                "2 drawers": dict(w=460.0, d=620.0, h=720.0, drawers=2)}
LAPTOP_SIZES = {"14 inch": dict(w=320.0, d=225.0),
                "16 inch": dict(w=360.0, d=250.0)}
WALL_SHELF_SIZES = {"900": dict(w=900.0, d=250.0),
                    "1200": dict(w=1200.0, d=250.0)}
WASHER_SIZES = {"Standard 600": dict(w=600.0, d=600.0, h=850.0)}
CONSOLE_SIZES = {"1000 × 300": dict(w=1000.0, d=300.0, h=800.0)}
COAT_STAND_SIZES = {"Standard": dict(h=1800.0)}
SHOE_SIZES = {"800 × 1000": dict(w=800.0, d=300.0, h=1000.0)}

_WHD = [("w", "Width"), ("d", "Depth"), ("h", "Height")]
_WD = [("w", "Width"), ("d", "Depth")]


def _entry(label, build, sizes, fields, colors=None, **extra):
    entry = dict(label=label, category=CATEGORY, sizes=sizes, build=build,
                 fields=fields, **extra)
    if colors:
        entry["colors"] = list(colors)
    return entry


PARTS = {
    # living room
    "home_corner_sofa": _entry(
        "Corner sofa", build_corner_sofa, CORNER_SIZES,
        [("w", "Width"), ("l", "Chaise length"), ("d", "Depth"),
         ("h", "Back height"), ("seat", "Seat height")], FABRICS),
    "home_side_table": _entry("Side table", build_side_table,
                              SIDE_TABLE_SIZES,
                              [("d", "Diameter"), ("h", "Height")], WOODS),
    "home_ottoman": _entry("Ottoman / footstool", build_ottoman,
                           OTTOMAN_SIZES, _WHD, FABRICS),
    "home_rug": _entry("Rug", build_rug, RUG_SIZES, _WD, RUGS),
    "home_plant": _entry("Plant in a pot", build_plant, PLANT_SIZES,
                         [("h", "Height"), ("pot", "Pot diameter")], POTS,
                         on_top=True),
    "home_table_lamp": _entry("Table lamp", build_table_lamp,
                              TABLE_LAMP_SIZES,
                              [("h", "Height"), ("shade", "Shade diameter")],
                              LAMP_BASES, on_top=True),
    "home_piano": _entry("Upright piano", build_piano, PIANO_SIZES, _WHD,
                         PIANOS),
    "home_fireplace": _entry("Fireplace (with mantel)", build_fireplace,
                             FIREPLACE_SIZES, _WHD, SURROUNDS),
    # dining room
    "home_round_table": _entry("Round table", build_round_table,
                               ROUND_TABLE_SIZES,
                               [("d", "Diameter"), ("h", "Height")], WOODS),
    "home_bench": _entry("Bench", build_bench, BENCH_SIZES, _WHD, WOODS),
    "home_display_cabinet": _entry("Display cabinet (glass doors)",
                                   build_display_cabinet, DISPLAY_SIZES,
                                   _WHD, WOODS),
    "home_pendant": _entry("Pendant light (hangs from the ceiling)",
                           build_pendant, PENDANT_SIZES,
                           [("shade", "Shade diameter"),
                            ("drop", "Cord length")], PENDANTS,
                           rest_z=1540.0),
    # bedroom and kids' room
    "home_dressing_table": _entry("Dressing table (with mirror)",
                                  build_dressing_table, DRESSING_SIZES,
                                  _WHD, WOODS),
    "home_bunk_bed": _entry(
        "Bunk bed", build_bunk_bed, BUNK_SIZES,
        [("w", "Mattress width"), ("l", "Mattress length"),
         ("h", "Height")], WOODS),
    "home_cot": _entry(
        "Baby cot", build_cot, COT_SIZES,
        [("w", "Mattress width"), ("l", "Mattress length"),
         ("h", "Height")], WOODS),
    "home_toy_box": _entry("Toy box", build_toy_box, TOY_BOX_SIZES, _WHD,
                           TOYS),
    # kitchen
    "home_island": _entry("Kitchen island", build_island, ISLAND_SIZES,
                          [("w", "Width"), ("d", "Depth"),
                           ("h", "Worktop height")], FRONTS),
    "home_bar_stool": _entry("Bar stool", build_bar_stool, BAR_STOOL_SIZES,
                             [("w", "Width"), ("seat", "Seat height")],
                             FABRICS),
    "home_microwave": _entry("Microwave", build_microwave, MICROWAVE_SIZES,
                             _WHD, APPLIANCE, on_top=True),
    "home_dishwasher": _entry("Dishwasher", build_dishwasher,
                              DISHWASHER_SIZES, _WHD, APPLIANCE),
    # bathroom
    "home_towel_radiator": _entry("Towel radiator", build_towel_radiator,
                                  RADIATOR_SIZES,
                                  [("w", "Width"), ("h", "Height")],
                                  RADIATORS, rest_z=150.0),
    "home_bath_cabinet": _entry("Mirror cabinet (on the wall)",
                                build_bath_cabinet, BATH_CABINET_SIZES, _WHD,
                                WOODS, rest_z=1250.0),
    "home_laundry_basket": _entry("Laundry basket", build_laundry_basket,
                                  BASKET_SIZES,
                                  [("d", "Diameter"), ("h", "Height")],
                                  BASKETS),
    # office
    "home_desk": _entry("Desk (with drawers)", build_desk, DESK_SIZES, _WHD,
                        WOODS),
    "home_office_chair": _entry(
        "Office chair", build_office_chair, OFFICE_CHAIR_SIZES,
        [("w", "Width"), ("seat", "Seat height"), ("h", "Height")],
        FABRICS),
    "home_filing_cabinet": _entry("Filing cabinet", build_filing_cabinet,
                                  FILING_SIZES,
                                  _WHD + [("drawers", "Drawers")], CABINETS),
    "home_laptop": _entry("Laptop", build_laptop, LAPTOP_SIZES, _WD,
                          LAPTOPS, on_top=True),
    "home_wall_shelf": _entry("Wall shelf (with books)", build_wall_shelf,
                              WALL_SHELF_SIZES, _WD, WOODS, rest_z=1300.0),
    # utility
    "home_washing_machine": _entry("Washing machine", build_washing_machine,
                                   WASHER_SIZES, _WHD, APPLIANCE),
    "home_tumble_dryer": _entry("Tumble dryer", build_tumble_dryer,
                                WASHER_SIZES, _WHD, APPLIANCE),
    # hallway
    "home_console_table": _entry("Console table", build_console_table,
                                 CONSOLE_SIZES, _WHD, WOODS),
    "home_coat_stand": _entry("Coat stand", build_coat_stand,
                              COAT_STAND_SIZES, [("h", "Height")], WOODS),
    "home_shoe_cabinet": _entry("Shoe cabinet", build_shoe_cabinet,
                                SHOE_SIZES, _WHD, WOODS),
}
