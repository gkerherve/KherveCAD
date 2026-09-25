"""Home furniture for the parts library: a section that furnishes a
whole house — dining room, living room, bedroom, kitchen and bathroom.

Dining table and chairs, sofas (classic, Chesterfield, mid-century
settee, cloud and tuxedo — each upholstered in a shader texture:
Fabric, Leather, Bouclé, Velvet) and an armchair, a coffee table, a
bookcase (with books), a sideboard and a floor lamp; a made-up bed
with duvet and pillows, a bedside table with its lamp, a wardrobe and a
chest of drawers; a run of kitchen units with sink, hob, oven, wall
cupboards and hood, and a fridge-freezer; a toilet, a washbasin on its
vanity, a bath and a shower enclosure.

Like library_room, every piece is a multi-coloured union of boxes,
rounded boxes, cylinders and capsules with NO booleans, so each
component keeps its own colour in the built-in preview and OpenSCAD
renders it quickly. Hollows (the bath, the basin) are walls around a
floor rather than a subtraction. The front faces -Y and the back (the
wall side) +Y; every part stands on z = 0, centred on X and Y.

Wood, fabric and kitchen-front colours come from the Part Library colour
list (``colors`` / ``dims["_color"]``); seats, shelves, doors, drawers
and units are integer fields (``COUNT_FIELDS``). Registered into
``library.PARTS`` via ``PARTS``; each entry carries a ``build``
callable dispatched by ``library.build_part``.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from .library_room import _dims
from .model import CadNode

CATEGORY = "Home furniture"

WHITE = "#f1efea"
CERAMIC = "#f8f8f6"
LINEN = "#ece6da"
CHROME = "#c9cdd3"
STEEL = "#b8bdc4"
BRASS = "#c8a45a"
BLACK = "#26282c"
GLASS = "#cfe3ea"
STONE = "#d6d2ca"
PLINTH = "#3a3d42"

#: wood finishes: (main, darker accent for legs and plinths)
WOODS = {"Oak": ("#c89f6e", "#a47a4f"), "Walnut": ("#7b5436", "#5b3d27"),
         "White": ("#f1efea", "#cfc9bf"), "Black": ("#2d2f33", "#1d1e21")}
FABRICS = {"Grey": "#8d949c", "Charcoal": "#4a4f56", "Navy": "#34496b",
           "Sage": "#8ea58a", "Mustard": "#c9a043",
           "Terracotta": "#b8674a", "Cream": "#e3d8c0"}
LEATHERS = {"Tan": "#9a5b32", "Oxblood": "#5e1f22", "Chocolate": "#4a2e22",
            "Black": "#2a2624", "Bottle green": "#2f4a3a"}
VELVETS = {"Emerald": "#1f5c46", "Navy": "#23345a", "Mustard": "#c08a2a",
           "Blush": "#c98f8a", "Plum": "#5a2d4a", "Teal": "#1f5c63"}
BOUCLES = {"Ivory": "#ebe4d6", "Oatmeal": "#d6c9b0", "Sand": "#c9b28f",
           "Stone grey": "#a9a59d", "Blush": "#dcb8ad"}
FRONTS = {"White": "#f1efea", "Sage": "#9aad96", "Navy": "#34496b",
          "Charcoal": "#4a4f56", "Oak": "#c89f6e"}
APPLIANCE = {"Steel": STEEL, "White": "#f4f4f2", "Black": "#2a2c30"}
BOOKS = ("#9b3b35", "#34496b", "#c9a043", "#4f7a58", "#6b4c7a",
         "#d9d2c3", "#2f3b45", "#b8674a")

#: dialog fields holding a count (integer spin box, no "mm" suffix)
COUNT_FIELDS = {"seats", "shelves", "doors", "drawers", "units"}


# ----------------------------------------------------------- primitives

def _paint(node, color, material="Default", alpha=1.0):
    col = CadNode("color", node.name, dict(color=color, alpha=alpha,
                                           material=material))
    col.add(node)
    return col


def _box(name, x, y, z, w, d, h, color, r=0.0, material="Default",
         alpha=1.0):
    """A box from its low corner (x, y, z); *r* rounds every edge."""
    r = min(r, w / 2.0, d / 2.0, h / 2.0) * 0.98
    if r > 0.5:
        node = CadNode("rounded_box", name, dict(
            x=x, y=y, z=z, width=w, depth=d, height=h, radius=r,
            center=False, segments=16))
    else:
        node = CadNode("cube", name, dict(x=x, y=y, z=z, width=w,
                                          depth=d, height=h, center=False))
    return _paint(node, color, material, alpha)


def _cyl(name, x, y, z, h, r, color, r2=None, seg=32, material="Default",
         alpha=1.0):
    node = CadNode("cylinder", name, dict(
        x=x, y=y, z=z, height=h, radius_bottom=r,
        radius_top=r if r2 is None else r2, segments=seg, center=False))
    return _paint(node, color, material, alpha)


def _ball(name, x, y, z, r, color, material="Default"):
    return _paint(CadNode("sphere", name, dict(x=x, y=y, z=z, radius=r,
                                               segments=24)),
                  color, material)


def _rod(name, a, b, r, color=CHROME, material="Metal"):
    """A round bar (capsule) from point *a* to point *b*."""
    return _paint(CadNode("capsule", name, dict(
        x1=a[0], y1=a[1], z1=a[2], x2=b[0], y2=b[1], z2=b[2], radius=r,
        segments=16)), color, material)


def _oval(name, cy, z, rx, ry, h):
    """An elliptic slab centred on (0, cy): *rx* across, *ry* front to
    back — a cylinder stretched along Y (uncoloured, for a hull)."""
    move = CadNode("translate", name, dict(x=0.0, y=cy, z=z))
    stretch = CadNode("scale", name, dict(x=1.0, y=ry / rx, z=1.0))
    stretch.add(CadNode("cylinder", name, dict(
        x=0.0, y=0.0, z=0.0, height=h, radius_bottom=rx, radius_top=rx,
        segments=48, center=False)))
    move.add(stretch)
    return move


def _legs(part, w, d, inset, h, r, color, r2=None):
    """Four round legs, *inset* from the corners of a w × d footprint."""
    for sx in (-1, 1):
        for sy in (-1, 1):
            part.add(_cyl("Leg", sx * (w / 2 - inset), sy * (d / 2 - inset),
                          0.0, h, r, color, r2=r2, seg=24))


def _count(p, key, lo, hi):
    try:
        n = int(round(float(p.get(key, lo))))
    except (TypeError, ValueError):
        n = lo
    return max(lo, min(hi, n))


def _pick(dims, table, default):
    return table.get(dims.get("_color") or default, table[default])


def _mix(hexcol, other, t):
    """*hexcol* moved a fraction *t* of the way towards *other*."""
    a = [int(hexcol[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(other[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(u + (v - u) * t)
                                   for u, v in zip(a, b))


def _bar(x, y, z, length=240.0, r=8.0):
    """A horizontal chrome bar handle centred on (x, y, z)."""
    return _rod("Handle", (x - length / 2, y, z), (x + length / 2, y, z), r)


# ---------------------------------------------------------- dining room

def build_dining_table(dims):
    p = _dims(dims, DINING_TABLE_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    wood, dark = _pick(dims, WOODS, "Oak")
    top, rail, inset = 36.0, 90.0, 110.0
    part = CadNode("union", "Dining table")
    part.add(_box("Top", -w / 2, -d / 2, h - top, w, d, top, wood, r=10))
    ax, ay, z = w / 2 - inset, d / 2 - inset, h - top - rail
    for sy in (-1, 1):
        part.add(_box("Apron", -ax, sy * ay - 11, z, 2 * ax, 22, rail,
                      dark))
    for sx in (-1, 1):
        part.add(_box("Apron", sx * ax - 11, -ay, z, 22, 2 * ay, rail,
                      dark))
    _legs(part, w, d, inset, h - top, 24, dark, r2=34)
    return part


def build_dining_chair(dims):
    p = _dims(dims, CHAIR_SIZES)
    w, d, seat, top = p["w"], p["d"], p["seat"], p["h"]
    wood, dark = _pick(dims, WOODS, "Oak")
    leg = 38.0
    lx, ly = w / 2 - leg / 2 - 4, d / 2 - leg / 2 - 4
    part = CadNode("union", "Dining chair")
    for sx in (-1, 1):
        x = sx * lx - leg / 2
        part.add(_box("Front leg", x, -ly - leg / 2, 0.0, leg, leg,
                      seat - 40, wood, r=4))
        part.add(_box("Back post", x, ly - leg / 2, 0.0, leg, leg, top,
                      wood, r=4))
        part.add(_box("Stretcher", sx * lx - 10, -ly, 150.0, 20, 2 * ly,
                      26, dark))
    part.add(_box("Seat frame", -w / 2, -d / 2, seat - 75, w, d, 40, wood,
                  r=5))
    part.add(_box("Cushion", -w / 2 + 14, -d / 2 + 14, seat - 40, w - 28,
                  d - 28, 42, FABRICS["Grey"], r=14))
    part.add(_box("Top rail", -lx - leg / 2, ly - 14, top - 110,
                  2 * lx + leg, 28, 110, wood, r=8))
    for x in (-w / 5, 0.0, w / 5):
        part.add(_box("Slat", x - 18, ly - 8, seat + 10, 36, 16,
                      top - 115 - seat, dark))
    return part


# ---------------------------------------------------------- living room

def build_sofa(dims, sizes=None):
    p = _dims(dims, sizes or SOFA_SIZES)
    w, d, h, seat = p["w"], p["d"], p["h"], p["seat"]
    n = _count(p, "seats", 1, 5)
    fab = _pick(dims, FABRICS, "Grey")
    soft = _mix(fab, "#ffffff", 0.12)
    arm, back, foot = 170.0, 190.0, 110.0
    part = CadNode("union", "Sofa" if n > 1 else "Armchair")
    _legs(part, w, d, 70, foot, 20, WOODS["Walnut"][1], r2=16)
    part.add(_box("Base", -w / 2, -d / 2, foot, w, d, seat - 130 - foot,
                  fab, r=25, material="Fabric"))
    part.add(_box("Back", -w / 2, d / 2 - back, foot, w, back, h - foot,
                  fab, r=45, material="Fabric"))
    for sx in (-1, 1):
        x = -w / 2 if sx < 0 else w / 2 - arm
        part.add(_box("Arm", x, -d / 2, foot, arm, d, seat + 190 - foot,
                      fab, r=50, material="Fabric"))
    cw = (w - 2 * arm) / n
    for i in range(n):
        x = -w / 2 + arm + i * cw
        part.add(_box("Seat cushion", x + 6, -d / 2 + 25, seat - 135,
                      cw - 12, d - back - 30, 140, soft, r=45,
                      material="Fabric"))
        part.add(_box("Back cushion", x + 8, d / 2 - back - 160, seat,
                      cw - 16, 180, h - seat - 30, soft, r=60,
                      material="Fabric"))
    return part


def _stud(name, x, y, z, r, color, material="Default"):
    """A small low-poly ball: a tufting button, a brass nail head."""
    return _paint(CadNode("sphere", name, dict(x=x, y=y, z=z, radius=r,
                                               segments=10)),
                  color, material)


def build_chesterfield(dims):
    """Deep-buttoned leather: arms as high as the back, both rolled."""
    p = _dims(dims, CHESTERFIELD_SIZES)
    w, d, h, seat = p["w"], p["d"], p["h"], p["seat"]
    n = _count(p, "seats", 1, 5)
    hide = _pick(dims, LEATHERS, "Tan")
    soft = _mix(hide, "#ffffff", 0.06)
    button = _mix(hide, "#000000", 0.35)
    arm, back, foot, roll = 210.0, 210.0, 90.0, 80.0
    part = CadNode("union", "Chesterfield")
    for sx in (-1, 1):
        for sy in (-1, 1):
            part.add(_ball("Bun foot", sx * (w / 2 - 90), sy * (d / 2 - 90),
                           50.0, 50.0, WOODS["Walnut"][1]))
    part.add(_box("Base", -w / 2, -d / 2, foot, w, d, seat - 120 - foot,
                  hide, r=30, material="Leather"))
    part.add(_box("Back", -w / 2 + arm / 2, d / 2 - back, foot, w - arm,
                  back, h - foot - roll, hide, r=50, material="Leather"))
    part.add(_rod("Back roll", (-w / 2 + arm / 2, d / 2 - back / 2, h - roll),
                  (w / 2 - arm / 2, d / 2 - back / 2, h - roll), roll, hide,
                  "Leather"))
    for sx in (-1, 1):
        x = -w / 2 if sx < 0 else w / 2 - arm
        part.add(_box("Arm", x, -d / 2, foot, arm, d, h - foot - roll - 10,
                      hide, r=45, material="Leather"))
        cx = sx * (w / 2 - arm / 2 + 12)
        part.add(_rod("Arm roll", (cx, -d / 2 + roll + 5, h - roll - 10),
                      (cx, d / 2 - back / 2, h - roll - 10), roll + 12, hide,
                      "Leather"))
    cw = (w - 2 * arm) / n
    for i in range(n):
        x = -w / 2 + arm + i * cw
        part.add(_box("Seat cushion", x + 5, -d / 2 + 30, seat - 120,
                      cw - 10, d - back - 35, 120, soft, r=35,
                      material="Leather"))
    # diamond tufting: staggered rows of buttons on the back and arms
    step, y = 150.0, d / 2 - back - 3
    rows = max(1, int((h - roll - seat - 40) // 80) + 1)
    for r in range(rows):
        z = seat + 50 + r * 80
        off = step / 2 if r % 2 else 0.0
        k = int((w - 2 * arm - off) // step)
        for j in range(k):
            x = -w / 2 + arm + off + step * (j + 0.5) + (
                w - 2 * arm - off - k * step) / 2
            part.add(_stud("Button", x, y, z, 11, button, "Leather"))
    for sx in (-1, 1):
        for r in range(max(1, int((h - roll - foot - 200) // 110))):
            z = foot + 140 + r * 110
            off = step / 2 if r % 2 else 0.0
            for j in range(int((d - 2 * roll - off) // step)):
                part.add(_stud("Button", sx * (w / 2 + 3),
                               -d / 2 + roll + off + step * (j + 0.5), z, 11,
                               button, "Leather"))
    return part


def build_settee(dims):
    """A slim mid-century settee on splayed walnut legs, wooden arms."""
    p = _dims(dims, SETTEE_SIZES)
    w, d, h, seat = p["w"], p["d"], p["h"], p["seat"]
    n = _count(p, "seats", 1, 4)
    fab = _pick(dims, FABRICS, "Mustard")
    soft = _mix(fab, "#ffffff", 0.08)
    wood = WOODS["Walnut"][0]
    frame, back, arm = 230.0, 110.0, 60.0
    part = CadNode("union", "Mid-century settee")
    for sx in (-1, 1):
        for sy in (-1, 1):
            part.add(_rod("Leg", (sx * (w / 2 - 50), sy * (d / 2 - 50), 14),
                          (sx * (w / 2 - 110), sy * (d / 2 - 110), frame),
                          14, wood, "Default"))
    part.add(_box("Frame", -w / 2 + 30, -d / 2 + 30, frame, w - 60, d - 60,
                  50, wood, r=8))
    part.add(_box("Back", -w / 2 + arm, d / 2 - back - 20, frame + 30,
                  w - 2 * arm, back, h - frame - 30, fab, r=30,
                  material="Fabric"))
    part.add(_box("Seat cushion", -w / 2 + arm + 10, -d / 2 + 35,
                  frame + 50, w - 2 * arm - 20, d - back - 70,
                  seat - frame - 50, fab, r=30, material="Fabric"))
    cw = (w - 2 * arm - 20) / n
    for i in range(n):
        x = -w / 2 + arm + 10 + i * cw
        part.add(_box("Back cushion", x + 6, d / 2 - back - 150, seat,
                      cw - 12, 135, h - seat - 50, soft, r=45,
                      material="Fabric"))
        for bx in (0.33, 0.67):
            part.add(_stud("Button", x + cw * bx, d / 2 - back - 152,
                           seat + (h - seat - 50) * 0.55, 9,
                           _mix(fab, "#000000", 0.3), "Fabric"))
    for sx in (-1, 1):
        x = -w / 2 if sx < 0 else w / 2 - arm
        for y in (-d / 2 + 40, d / 2 - 90):
            part.add(_box("Arm post", x + 10, y, frame + 50, arm - 20, 50,
                          seat + 150 - frame - 50, wood, r=8))
        part.add(_box("Arm rest", x, -d / 2 + 25, seat + 150, arm, d - 60,
                      32, wood, r=12))
    return part


def build_cloud_sofa(dims):
    """A low, deep, over-stuffed sofa in boucle with fat arms."""
    p = _dims(dims, CLOUD_SIZES)
    w, d, h, seat = p["w"], p["d"], p["h"], p["seat"]
    n = _count(p, "seats", 1, 5)
    fab = _pick(dims, BOUCLES, "Ivory")
    soft = _mix(fab, "#ffffff", 0.08)
    accent = _mix(fab, "#7a5a3c", 0.45)
    arm, back, plinth = 300.0, 230.0, 50.0
    part = CadNode("union", "Cloud sofa")
    part.add(_box("Plinth", -w / 2 + 60, -d / 2 + 60, 0.0, w - 120, d - 120,
                  plinth + 5, PLINTH))
    part.add(_box("Base", -w / 2, -d / 2, plinth, w, d, seat - 200 - plinth,
                  fab, r=60, material="Bouclé"))
    part.add(_box("Back", -w / 2 + arm - 30, d / 2 - back, plinth,
                  w - 2 * arm + 60, back, h - plinth - 80, fab, r=110,
                  material="Bouclé"))
    for sx in (-1, 1):
        x = -w / 2 if sx < 0 else w / 2 - arm
        part.add(_box("Arm", x, -d / 2, plinth, arm, d, seat + 170 - plinth,
                      fab, r=140, material="Bouclé"))
    cw = (w - 2 * arm) / n
    for i in range(n):
        x = -w / 2 + arm + i * cw
        part.add(_box("Seat cushion", x + 4, -d / 2 + 25, seat - 210,
                      cw - 8, d - back - 45, 215, soft, r=100,
                      material="Bouclé"))
        part.add(_box("Back pillow", x + 6, d / 2 - back - 230, seat - 10,
                      cw - 12, 270, h - seat + 50, soft, r=125,
                      material="Bouclé"))
    for sx in (-1, 1):
        part.add(_box("Scatter cushion", sx * (w / 2 - arm - 30) - 190,
                      d / 2 - back - 350, seat - 15, 380, 130, 360, accent,
                      r=60, material="Velvet"))
    return part


def build_tuxedo_sofa(dims):
    """Velvet with arms flush to the back, channel-tufted, brass legs."""
    p = _dims(dims, TUXEDO_SIZES)
    w, d, h, seat = p["w"], p["d"], p["h"], p["seat"]
    vel = _pick(dims, VELVETS, "Emerald")
    soft = _mix(vel, "#ffffff", 0.05)
    arm, back, foot = 180.0, 180.0, 150.0
    part = CadNode("union", "Tuxedo sofa")
    for sx in (-1, 1):
        for sy in (-1, 1):
            part.add(_cyl("Leg", sx * (w / 2 - 70), sy * (d / 2 - 70), 0.0,
                          foot, 12, BRASS, r2=20, seg=20, material="Metal"))
    part.add(_box("Base", -w / 2, -d / 2, foot, w, d, seat - 120 - foot, vel,
                  r=30, material="Velvet"))
    part.add(_box("Back", -w / 2, d / 2 - back, foot, w, back, h - foot, vel,
                  r=40, material="Velvet"))
    for sx in (-1, 1):
        x = -w / 2 if sx < 0 else w / 2 - arm
        part.add(_box("Arm", x, -d / 2, foot, arm, d, h - foot, vel, r=40,
                      material="Velvet"))
    inner = w - 2 * arm
    k = max(2, int(round(inner / 170.0)))
    cw = inner / k
    for i in range(k):
        part.add(_box("Channel", -w / 2 + arm + i * cw + 3,
                      d / 2 - back - 75, seat - 5, cw - 6, 85,
                      h - seat - 25, soft, r=40, material="Velvet"))
    part.add(_box("Seat cushion", -w / 2 + arm + 6, -d / 2 + 30, seat - 120,
                  inner - 12, d - back - 110, 120, soft, r=40,
                  material="Velvet"))
    part.add(_rod("Piping", (-w / 2 + 40, -d / 2 - 1, foot + 12),
                  (w / 2 - 40, -d / 2 - 1, foot + 12), 5, BRASS))
    return part


def build_armchair(dims):
    return build_sofa(dims, ARMCHAIR_SIZES)


def build_coffee_table(dims):
    p = _dims(dims, COFFEE_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    wood, _dark = _pick(dims, WOODS, "Oak")
    part = CadNode("union", "Coffee table")
    part.add(_box("Top", -w / 2, -d / 2, h - 32, w, d, 32, wood, r=12))
    part.add(_box("Shelf", -w / 2 + 45, -d / 2 + 45, 110.0, w - 90, d - 90,
                  20, wood, r=4))
    for sx in (-1, 1):
        for sy in (-1, 1):
            part.add(_box("Leg", sx * (w / 2 - 40) - 12,
                          sy * (d / 2 - 40) - 12, 0.0, 24, 24, h - 32,
                          BLACK, material="Metal"))
    return part


def build_bookcase(dims):
    p = _dims(dims, BOOKCASE_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    n = _count(p, "shelves", 1, 10)
    wood, dark = _pick(dims, WOODS, "Oak")
    t, plinth = 20.0, 70.0
    inner = w - 2 * t
    part = CadNode("union", "Bookcase")
    for sx in (-1, 1):
        part.add(_box("Side", -w / 2 if sx < 0 else w / 2 - t, -d / 2, 0.0,
                      t, d, h, wood))
    part.add(_box("Top", -w / 2, -d / 2, h - t, w, d, t, wood))
    part.add(_box("Plinth", -w / 2 + t, -d / 2 + 15, 0.0, inner, d - 15,
                  plinth, dark))
    part.add(_box("Bottom", -w / 2 + t, -d / 2, plinth, inner, d, t, wood))
    part.add(_box("Back", -w / 2 + t, d / 2 - 8, plinth, inner, 8,
                  h - plinth - t, dark))
    floor0 = plinth + t
    gap = (h - t - floor0 - n * t) / (n + 1)
    widths = (28, 36, 24, 42, 30, 26, 34, 22)
    heights = (0.78, 0.9, 0.7, 0.86, 0.95, 0.74, 0.88, 0.8)
    k = 0
    for level in range(n + 1):
        z = floor0 + level * (gap + t)
        if level < n:
            part.add(_box("Shelf", -w / 2 + t, -d / 2 + 5, z + gap, inner,
                          d - 13, t, wood))
        if gap < 80:
            continue
        # a row of books along ~60 % of the shelf, left and right in turn
        room = inner * 0.6
        x = (-w / 2 + t + 8) if level % 2 == 0 else (w / 2 - t - 8 - room)
        used = 0.0
        while used + widths[k % 8] <= room:
            bw = widths[k % 8]
            bh = min(gap - 25, 330.0) * heights[(k * 3) % 8]
            part.add(_box("Book", x + used, -d / 2 + 25, z, bw - 2,
                          min(d - 60, 230.0), bh, BOOKS[k % len(BOOKS)]))
            used += bw
            k += 1
    return part


def build_sideboard(dims):
    p = _dims(dims, SIDEBOARD_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    wood, dark = _pick(dims, WOODS, "Walnut")
    face = _mix(wood, dark, 0.25)
    # real timber shows its grain; the White and Black are painted
    grain = "Wood" if wood in (WOODS["Oak"][0], WOODS["Walnut"][0]) \
        else "Default"
    n = max(2, int(round(w / 500.0)))
    legs = 130.0
    part = CadNode("union", "Sideboard")
    _legs(part, w, d, 60, legs, 14, dark, r2=20)
    for leg in part.children:
        leg.params["material"] = grain
    part.add(_box("Body", -w / 2, -d / 2, legs, w, d, h - legs, wood, r=6,
                  material=grain))
    fw = (w - 12 - (n - 1) * 4) / n
    for i in range(n):
        x = -w / 2 + 6 + i * (fw + 4)
        part.add(_box("Front", x, -d / 2 - 16, legs + 12, fw, 18,
                      h - legs - 24, face, r=3,
                      material=grain))
        part.add(_rod("Handle", (x + fw / 2 - 60, -d / 2 - 22, h - 50),
                      (x + fw / 2 + 60, -d / 2 - 22, h - 50), 7, BRASS))
    return part


def build_floor_lamp(dims):
    p = _dims(dims, LAMP_SIZES)
    h, r = p["h"], p["shade"] / 2
    part = CadNode("union", "Floor lamp")
    part.add(_cyl("Base", 0.0, 0.0, 0.0, 24, 160, BLACK, r2=150, seg=48,
                  material="Metal"))
    part.add(_cyl("Pole", 0.0, 0.0, 24.0, h - 174, 11, BRASS, seg=20,
                  material="Metal"))
    part.add(_cyl("Shade", 0.0, 0.0, h - 320, 320, r, LINEN, r2=r * 0.82,
                  seg=48, alpha=0.92))
    return part


# -------------------------------------------------------------- bedroom

def build_bed(dims):
    p = _dims(dims, BED_SIZES)
    w, l, head = p["w"], p["l"], p["head"]
    fab = _pick(dims, FABRICS, "Grey")
    foot, base_top, mattress = 90.0, 330.0, 230.0
    part = CadNode("union", "Bed")
    _legs(part, w + 80, l + 80, 70, foot, 22, WOODS["Walnut"][1], r2=18)
    part.add(_box("Base", -w / 2 - 40, -l / 2 - 40, foot, w + 80, l + 80,
                  base_top - foot, fab, r=30))
    part.add(_box("Headboard", -w / 2 - 60, l / 2 + 25, foot, w + 120, 90,
                  head - foot, fab, r=40))
    part.add(_box("Mattress", -w / 2, -l / 2, base_top, w, l, mattress,
                  "#f7f6f2", r=55))
    top = base_top + mattress
    cover = l * 0.72
    part.add(_box("Duvet", -w / 2 - 25, -l / 2 - 25, top - 95, w + 50,
                  cover + 25, 115, LINEN, r=45))
    part.add(_rod("Duvet fold", (-w / 2 - 15, -l / 2 + cover - 20, top + 5),
                  (w / 2 + 15, -l / 2 + cover - 20, top + 5), 32, LINEN,
                  "Default"))
    part.add(_box("Throw", -w / 2 - 32, -l / 2 - 32, top - 50, w + 64, 430,
                  80, _mix(fab, "#000000", 0.15), r=35))
    count = 1 if w < 1100 else 2
    pw = min(700.0, (w - 60 - 30 * (count - 1)) / count)
    for i in range(count):
        cx = (i - (count - 1) / 2.0) * (pw + 30)
        part.add(_box("Pillow", cx - pw / 2, l / 2 - 440, top - 25, pw,
                      380, 150, "#fbfbf8", r=65))
    return part


def build_bedside_table(dims):
    p = _dims(dims, BEDSIDE_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    wood, dark = _pick(dims, WOODS, "Oak")
    legs = 150.0
    part = CadNode("union", "Bedside table")
    _legs(part, w, d, 40, legs, 13, dark, r2=18)
    part.add(_box("Body", -w / 2, -d / 2, legs, w, d, h - legs, wood, r=6))
    part.add(_box("Drawer", -w / 2 + 10, -d / 2 - 14, h - 170, w - 20, 16,
                  150, _mix(wood, dark, 0.25), r=3))
    part.add(_ball("Knob", 0.0, -d / 2 - 24, h - 95, 13, BRASS, "Metal"))
    part.add(_box("Open shelf", -w / 2 + 14, -d / 2 - 2, legs + 14, w - 28,
                  4, h - legs - 200, _mix(wood, "#000000", 0.45)))
    part.add(_cyl("Lamp base", 0.0, 40.0, h, 30, 60, CERAMIC, r2=48))
    part.add(_cyl("Lamp stem", 0.0, 40.0, h + 30, 200, 8, BRASS, seg=16,
                  material="Metal"))
    part.add(_cyl("Lamp shade", 0.0, 40.0, h + 170, 170, 125, LINEN, r2=95,
                  seg=40, alpha=0.92))
    return part


def build_wardrobe(dims):
    p = _dims(dims, WARDROBE_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    n = _count(p, "doors", 1, 6)
    wood, dark = _pick(dims, WOODS, "White")
    face = _mix(wood, dark, 0.2)
    part = CadNode("union", "Wardrobe")
    part.add(_box("Plinth", -w / 2 + 30, -d / 2 + 30, 0.0, w - 60, d - 60,
                  90, dark))
    part.add(_box("Carcass", -w / 2, -d / 2, 90.0, w, d, h - 125, wood, r=4))
    part.add(_box("Cornice", -w / 2 - 15, -d / 2 - 30, h - 35, w + 30,
                  d + 30, 35, wood, r=6))
    dw = (w - 12 - (n - 1) * 4) / n
    for i in range(n):
        x = -w / 2 + 6 + i * (dw + 4)
        part.add(_box("Door", x, -d / 2 - 20, 100.0, dw, 22, h - 145, face,
                      r=3))
        # doors open in pairs: the handle sits on the edge they meet at
        right = n == 1 or (i % 2 == 0 and i < n - 1)
        hx = x + dw - 45 if right else x + 45
        part.add(_rod("Handle", (hx, -d / 2 - 28, h * 0.45),
                      (hx, -d / 2 - 28, h * 0.45 + 360), 9))
    return part


def build_chest(dims):
    p = _dims(dims, CHEST_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    n = _count(p, "drawers", 2, 8)
    wood, dark = _pick(dims, WOODS, "Walnut")
    face = _mix(wood, dark, 0.2)
    legs, top_t, gap = 110.0, 26.0, 6.0
    part = CadNode("union", "Chest of drawers")
    _legs(part, w, d, 45, legs, 16, dark, r2=22)
    part.add(_box("Carcass", -w / 2, -d / 2, legs, w, d, h - top_t - legs,
                  wood, r=4))
    part.add(_box("Top", -w / 2 - 15, -d / 2 - 20, h - top_t, w + 30,
                  d + 20, top_t, wood, r=8))
    z0, z1 = legs + 8, h - top_t - 6
    fh = (z1 - z0 - (n - 1) * gap) / n
    for i in range(n):
        z = z0 + i * (fh + gap)
        part.add(_box("Drawer", -w / 2 + 6, -d / 2 - 18, z, w - 12, 20, fh,
                      face, r=3))
        for sx in (-1, 1):
            part.add(_ball("Knob", sx * w / 4, -d / 2 - 28, z + fh / 2, 14,
                           BRASS, "Metal"))
    return part


# -------------------------------------------------------------- kitchen

def build_kitchen(dims):
    p = _dims(dims, KITCHEN_SIZES)
    n = _count(p, "units", 2, 8)
    uw, d, h = p["unit"], p["d"], p["h"]
    front = _pick(dims, FRONTS, "White")
    width, x0 = n * uw, -n * uw / 2
    top_t = 40.0
    body = h - top_t
    part = CadNode("union", "Kitchen")
    part.add(_box("Plinth", x0, -d / 2 + 50, 0.0, width, d - 50, 100,
                  PLINTH))
    part.add(_box("Base units", x0, -d / 2, 100.0, width, d, body - 100,
                  WHITE))
    part.add(_box("Worktop", x0 - 10, -d / 2 - 25, body, width + 20, d + 25,
                  top_t, STONE, r=4))
    part.add(_box("Splashback", x0, d / 2 - 12, h, width, 12, 540,
                  "#e8eef0"))
    roles = ["door"] * n
    roles[0], roles[1], roles[-1] = "drawers", "sink", "oven"
    if n == 2:
        roles = ["sink", "oven"]
    fz, ftop, y = 110.0, body - 10.0, -d / 2 - 20
    for i, role in enumerate(roles):
        ux = x0 + i * uw
        fx, fw = ux + 3, uw - 6
        cx = ux + uw / 2
        if role == "drawers":
            z = ftop
            for frac in (0.24, 0.34, 0.42):
                fh = (ftop - fz - 8) * frac
                z -= fh
                part.add(_box("Drawer", fx, y, z, fw, 20, fh, front, r=3))
                part.add(_bar(cx, y - 8, z + fh - 45))
                z -= 4
        elif role == "oven":
            _oven_unit(part, ux, uw, d, h, fz, ftop, y, front)
        else:
            part.add(_box("Door", fx, y, fz, fw, 20, ftop - fz, front, r=3))
            part.add(_bar(cx, y - 8, ftop - 45))
        if role == "sink":
            part.add(_box("Sink", ux + 55, -d / 2 + 60, h, uw - 110, d - 170,
                          3, STEEL, material="Metal"))
            part.add(_box("Bowl", ux + 80, -d / 2 + 85, h + 3, uw - 160,
                          d - 240, 2, "#6f757d", material="Metal"))
            ty = d / 2 - 75
            part.add(_cyl("Tap", cx, ty, h, 70, 22, CHROME, seg=24,
                          material="Metal"))
            part.add(_rod("Spout", (cx, ty, h + 60), (cx, ty, h + 320), 11))
            part.add(_rod("Spout", (cx, ty, h + 320),
                          (cx, ty - 190, h + 320), 11))
            part.add(_rod("Spout", (cx, ty - 190, h + 320),
                          (cx, ty - 190, h + 260), 11))
        if role != "oven":
            part.add(_box("Wall unit", ux, d / 2 - 350, h + 550, uw, 350,
                          720, WHITE))
            part.add(_box("Wall door", ux + 3, d / 2 - 370, h + 556, uw - 6,
                          20, 708, front, r=3))
            part.add(_bar(cx, d / 2 - 378, h + 600))
    return part


def _oven_unit(part, ux, uw, d, h, fz, ftop, y, front):
    """A drawer, a built-in oven, the hob above it and the cooker hood."""
    fx, fw, cx = ux + 3, uw - 6, ux + uw / 2
    part.add(_box("Drawer", fx, y, fz, fw, 20, 150, front, r=3))
    part.add(_bar(cx, y - 8, fz + 105))
    oz = fz + 158
    part.add(_box("Oven door", fx, y, oz, fw, 22, ftop - oz - 110, BLACK,
                  r=4, material="Plastic"))
    part.add(_box("Oven controls", fx, y, ftop - 104, fw, 22, 104, STEEL,
                  r=3, material="Metal"))
    part.add(_rod("Oven handle", (fx + 50, y - 14, ftop - 150),
                  (fx + fw - 50, y - 14, ftop - 150), 10))
    hw, hd = uw - 80, d - 130
    hcy = -d / 2 + 50 + hd / 2
    part.add(_box("Hob", ux + 40, -d / 2 + 50, h, hw, hd, 6, BLACK, r=3,
                  material="Plastic"))
    for dx, dy, r in ((-1, -1, 85), (1, -1, 65), (-1, 1, 65), (1, 1, 85)):
        part.add(_cyl("Ring", cx + dx * hw / 4, hcy + dy * hd / 4, h + 6,
                      1.5, r, "#55585e", seg=40))
    hood = CadNode("hull", "Hood")
    hood.add(CadNode("cube", "Canopy", dict(
        x=ux + 20, y=d / 2 - 500, z=h + 650, width=uw - 40, depth=500,
        height=10, center=False)))
    hood.add(CadNode("cube", "Neck", dict(
        x=cx - uw * 0.2, y=d / 2 - 260, z=h + 800, width=uw * 0.4,
        depth=250, height=10, center=False)))
    part.add(_paint(hood, STEEL, "Metal"))
    part.add(_box("Chimney", cx - uw * 0.18, d / 2 - 250, h + 810,
                  uw * 0.36, 240, max(2400 - (h + 810), 200.0), STEEL,
                  material="Metal"))


def build_fridge(dims):
    p = _dims(dims, FRIDGE_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    body = _pick(dims, APPLIANCE, "Steel")
    mat = "Metal" if body == STEEL else "Default"
    split = h * 0.38
    hx = w / 2 - 55
    part = CadNode("union", "Fridge-freezer")
    part.add(_box("Cabinet", -w / 2, -d / 2 + 40, 0.0, w, d - 40, h,
                  _mix(body, "#000000", 0.08), r=8, material=mat))
    part.add(_box("Freezer door", -w / 2, -d / 2, 20.0, w, 44, split - 24,
                  body, r=10, material=mat))
    part.add(_box("Fridge door", -w / 2, -d / 2, split + 4, w, 44,
                  h - split - 8, body, r=10, material=mat))
    part.add(_rod("Freezer handle", (hx, -d / 2 - 22, split - 280),
                  (hx, -d / 2 - 22, split - 60), 11))
    part.add(_rod("Fridge handle", (hx, -d / 2 - 22, split + 60),
                  (hx, -d / 2 - 22, split + 460), 11))
    return part


# ------------------------------------------------------------- bathroom

def build_toilet(dims):
    p = _dims(dims, TOILET_SIZES)
    w, proj, seat = p["w"], p["d"], p["seat"]
    rx, ry = w / 2, (proj - 190) / 2
    cy = -proj / 2 + ry                  # the bowl's centre, cistern behind
    part = CadNode("union", "Toilet")
    pan = CadNode("hull", "Pan")
    pan.add(_oval("Foot", cy + 50, 0.0, rx * 0.55, ry * 0.6, 10))
    pan.add(_oval("Bowl", cy, seat - 70, rx, ry, 10))
    part.add(_paint(pan, CERAMIC))
    part.add(_paint(_oval("Rim", cy, seat - 70, rx, ry, 42), CERAMIC))
    part.add(_paint(_oval("Seat", cy, seat - 28, rx + 4, ry + 4, 22), WHITE))
    part.add(_paint(_oval("Lid", cy - 4, seat - 6, rx - 2, ry - 2, 18),
                    "#fdfdfb"))
    part.add(_box("Cistern", -w / 2 - 20, proj / 2 - 190, seat - 70, w + 40,
                  190, 400, CERAMIC, r=28))
    part.add(_cyl("Flush", 0.0, proj / 2 - 95, seat + 330, 8, 28, CHROME,
                  seg=24, material="Metal"))
    return part


def build_washbasin(dims):
    p = _dims(dims, BASIN_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    wood, dark = _pick(dims, WOODS, "White")
    bz, wall = h - 70, 40.0
    part = CadNode("union", "Washbasin")
    for sx in (-1, 1):
        for sy in (-1, 1):
            part.add(_cyl("Foot", sx * (w / 2 - 50), sy * (d / 2 - 50), 0.0,
                          100, 15, CHROME, seg=20, material="Metal"))
    part.add(_box("Vanity", -w / 2 + 10, -d / 2 + 10, 100.0, w - 20,
                  d - 10, bz - 100, wood, r=5))
    part.add(_box("Door", -w / 2 + 14, -d / 2 - 8, 110.0, w - 28, 20,
                  bz - 120, _mix(wood, dark, 0.2), r=3))
    part.add(_bar(0.0, -d / 2 - 16, bz - 50, 220))
    # the basin is walls around a floor, so it is really hollow
    part.add(_box("Basin front", -w / 2, -d / 2 - 10, bz, w, wall, 70,
                  CERAMIC, r=12))
    part.add(_box("Basin back", -w / 2, d / 2 - 90, bz, w, 90, 70, CERAMIC,
                  r=12))
    for sx in (-1, 1):
        part.add(_box("Basin side", -w / 2 if sx < 0 else w / 2 - wall,
                      -d / 2 - 10, bz, wall, d + 10, 70, CERAMIC, r=12))
    y0 = -d / 2 + 30
    part.add(_box("Basin floor", -w / 2 + wall - 5, y0 - 5, bz,
                  w - 2 * wall + 10, d - 110, 22, "#e9ecec", r=4))
    part.add(_cyl("Plug", 0.0, -30.0, bz + 22, 2, 20, CHROME, seg=24,
                  material="Metal"))
    ty = d / 2 - 45
    part.add(_cyl("Tap", 0.0, ty, h, 110, 22, CHROME, seg=24,
                  material="Metal"))
    part.add(_rod("Spout", (0.0, ty, h + 95), (0.0, ty - 130, h + 95), 10))
    part.add(_box("Mirror", -w / 2 + 30, d / 2 - 2, h + 260, w - 60, 12, 700,
                  "#dfe6ea", r=20, material="Metal"))
    return part


def build_bath(dims):
    p = _dims(dims, BATH_SIZES)
    l, w, h = p["l"], p["w"], p["h"]
    wall = 70.0
    part = CadNode("union", "Bath")
    part.add(_box("Bath floor", -l / 2, -w / 2, 0.0, l, w, 90, CERAMIC,
                  r=30))
    for sy in (-1, 1):
        part.add(_box("Bath side", -l / 2, -w / 2 if sy < 0 else w / 2 - wall,
                      0.0, l, wall, h, CERAMIC, r=30))
    for sx in (-1, 1):
        part.add(_box("Bath end", -l / 2 if sx < 0 else l / 2 - wall,
                      -w / 2, 0.0, wall, w, h, CERAMIC, r=30))
    part.add(_box("Inner floor", -l / 2 + wall - 10, -w / 2 + wall - 10,
                  90.0, l - 2 * wall + 20, w - 2 * wall + 20, 6, "#e9eced",
                  r=3))
    part.add(_box("Water", -l / 2 + wall, -w / 2 + wall, 96.0, l - 2 * wall,
                  w - 2 * wall, h - 230, "#9fcfe0", material="Glass",
                  alpha=0.35))
    tx = l / 2 - wall / 2
    part.add(_cyl("Mixer", tx, 0.0, h, 80, 22, CHROME, seg=24,
                  material="Metal"))
    part.add(_rod("Spout", (tx, 0.0, h + 70), (tx - 150, 0.0, h + 70), 11))
    part.add(_cyl("Plug", l / 2 - wall - 120, 0.0, 96.0, 2, 22, CHROME,
                  seg=24, material="Metal"))
    return part


def build_shower(dims):
    p = _dims(dims, SHOWER_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    corner = (-w / 2 + 14, -d / 2 + 14)
    part = CadNode("union", "Shower")
    part.add(_box("Tray", -w / 2, -d / 2, 0.0, w, d, 40, CERAMIC, r=8))
    part.add(_cyl("Drain", 0.0, 0.0, 40.0, 2, 45, CHROME, material="Metal"))
    part.add(_box("Door glass", -w / 2 + 15, -d / 2 + 10, 50.0, w - 30, 8,
                  h - 70, GLASS, material="Glass", alpha=0.3))
    part.add(_box("Side glass", -w / 2 + 10, -d / 2 + 15, 50.0, 8, d - 30,
                  h - 70, GLASS, material="Glass", alpha=0.3))
    part.add(_rod("Post", (corner[0], corner[1], 45.0),
                  (corner[0], corner[1], h - 15), 12))
    part.add(_rod("Top rail", (corner[0], corner[1], h - 15),
                  (w / 2 - 15, corner[1], h - 15), 10))
    part.add(_rod("Top rail", (corner[0], corner[1], h - 15),
                  (corner[0], d / 2 - 15, h - 15), 10))
    part.add(_rod("Door handle", (w / 2 - 140, -d / 2 + 4, h * 0.45),
                  (w / 2 - 140, -d / 2 + 4, h * 0.45 + 300), 10))
    part.add(_rod("Shower arm", (0.0, d / 2 - 15, h + 60),
                  (0.0, d / 2 - 240, h + 60), 12))
    part.add(_cyl("Shower head", 0.0, d / 2 - 240, h + 30, 14, 120, CHROME,
                  seg=40, material="Metal"))
    return part


# --------------------------------------------------------------- registry

DINING_TABLE_SIZES = {
    "4 seats (1400×800)": dict(w=1400.0, d=800.0, h=750.0),
    "6 seats (1800×900)": dict(w=1800.0, d=900.0, h=750.0),
    "8 seats (2200×1000)": dict(w=2200.0, d=1000.0, h=750.0),
}
CHAIR_SIZES = {
    "Dining": dict(w=450.0, d=500.0, seat=460.0, h=900.0),
    "Tall back": dict(w=460.0, d=520.0, seat=460.0, h=1050.0),
}
SOFA_SIZES = {
    "3-seater (2200)": dict(w=2200.0, d=950.0, h=820.0, seat=440.0,
                            seats=3),
    "2-seater (1700)": dict(w=1700.0, d=950.0, h=820.0, seat=440.0,
                            seats=2),
    "4-seater (2700)": dict(w=2700.0, d=980.0, h=820.0, seat=440.0,
                            seats=4),
}
CHESTERFIELD_SIZES = {
    "3-seater (2200)": dict(w=2200.0, d=950.0, h=760.0, seat=460.0,
                            seats=3),
    "2-seater (1700)": dict(w=1700.0, d=950.0, h=760.0, seat=460.0,
                            seats=2),
}
SETTEE_SIZES = {
    "3-seater (1900)": dict(w=1900.0, d=820.0, h=800.0, seat=430.0,
                            seats=3),
    "2-seater (1450)": dict(w=1450.0, d=820.0, h=800.0, seat=430.0,
                            seats=2),
}
CLOUD_SIZES = {
    "3-seater (2600)": dict(w=2600.0, d=1100.0, h=740.0, seat=420.0,
                            seats=3),
    "2-seater (2000)": dict(w=2000.0, d=1100.0, h=740.0, seat=420.0,
                            seats=2),
}
TUXEDO_SIZES = {
    "Standard (2100)": dict(w=2100.0, d=900.0, h=780.0, seat=450.0),
    "Loveseat (1600)": dict(w=1600.0, d=900.0, h=780.0, seat=450.0),
}
ARMCHAIR_SIZES = {
    "Armchair (900)": dict(w=900.0, d=900.0, h=820.0, seat=440.0, seats=1),
}
COFFEE_SIZES = {
    "1100 × 600": dict(w=1100.0, d=600.0, h=420.0),
    "Square 900": dict(w=900.0, d=900.0, h=400.0),
}
BOOKCASE_SIZES = {
    "800 × 1800": dict(w=800.0, d=300.0, h=1800.0, shelves=4),
    "1000 × 2000": dict(w=1000.0, d=320.0, h=2000.0, shelves=5),
    "Low 800 × 900": dict(w=800.0, d=300.0, h=900.0, shelves=1),
}
SIDEBOARD_SIZES = {
    "TV unit (1600)": dict(w=1600.0, d=450.0, h=560.0),
    "Sideboard (1200)": dict(w=1200.0, d=450.0, h=780.0),
    "Long (2000)": dict(w=2000.0, d=450.0, h=560.0),
}
LAMP_SIZES = {
    "Standard": dict(h=1600.0, shade=460.0),
    "Tall": dict(h=1800.0, shade=500.0),
}
BED_SIZES = {
    "Double (1350×1900)": dict(w=1350.0, l=1900.0, head=1150.0),
    "Single (900×1900)": dict(w=900.0, l=1900.0, head=1050.0),
    "King (1500×2000)": dict(w=1500.0, l=2000.0, head=1200.0),
    "Super king (1800×2000)": dict(w=1800.0, l=2000.0, head=1250.0),
}
BEDSIDE_SIZES = {"Standard": dict(w=450.0, d=400.0, h=560.0)}
WARDROBE_SIZES = {
    "2 doors (1000)": dict(w=1000.0, d=600.0, h=2100.0, doors=2),
    "3 doors (1500)": dict(w=1500.0, d=600.0, h=2100.0, doors=3),
    "4 doors (2000)": dict(w=2000.0, d=600.0, h=2200.0, doors=4),
}
CHEST_SIZES = {
    "4 drawers": dict(w=800.0, d=450.0, h=900.0, drawers=4),
    "3 drawers": dict(w=800.0, d=450.0, h=750.0, drawers=3),
    "5 drawers (tall)": dict(w=800.0, d=450.0, h=1150.0, drawers=5),
}
KITCHEN_SIZES = {
    "4 units (2400)": dict(units=4, unit=600.0, d=600.0, h=900.0),
    "3 units (1800)": dict(units=3, unit=600.0, d=600.0, h=900.0),
    "6 units (3600)": dict(units=6, unit=600.0, d=600.0, h=900.0),
}
FRIDGE_SIZES = {
    "Standard (600)": dict(w=600.0, d=650.0, h=1850.0),
    "Wide (700)": dict(w=700.0, d=680.0, h=1900.0),
}
TOILET_SIZES = {"Close-coupled": dict(w=360.0, d=650.0, seat=410.0)}
BASIN_SIZES = {
    "600 vanity": dict(w=600.0, d=460.0, h=850.0),
    "800 vanity": dict(w=800.0, d=480.0, h=850.0),
}
BATH_SIZES = {
    "1700 × 750": dict(l=1700.0, w=750.0, h=560.0),
    "1800 × 800": dict(l=1800.0, w=800.0, h=580.0),
}
SHOWER_SIZES = {
    "900 × 900": dict(w=900.0, d=900.0, h=1950.0),
    "1200 × 800": dict(w=1200.0, d=800.0, h=1950.0),
}

_WHD = [("w", "Width"), ("d", "Depth"), ("h", "Height")]


def _entry(label, build, sizes, fields, colors=None):
    entry = dict(label=label, category=CATEGORY, sizes=sizes, build=build,
                 fields=fields)
    if colors:
        entry["colors"] = list(colors)
    return entry


PARTS = {
    "home_dining_table": _entry("Dining table", build_dining_table,
                                DINING_TABLE_SIZES, _WHD, WOODS),
    "home_dining_chair": _entry(
        "Dining chair", build_dining_chair, CHAIR_SIZES,
        [("w", "Width"), ("d", "Depth"), ("seat", "Seat height"),
         ("h", "Height")], WOODS),
    "home_sofa": _entry(
        "Sofa", build_sofa, SOFA_SIZES,
        [("w", "Width"), ("d", "Depth"), ("h", "Back height"),
         ("seat", "Seat height"), ("seats", "Seats")], FABRICS),
    "home_chesterfield": _entry(
        "Chesterfield (buttoned leather)", build_chesterfield,
        CHESTERFIELD_SIZES,
        [("w", "Width"), ("d", "Depth"), ("h", "Back height"),
         ("seat", "Seat height"), ("seats", "Seats")], LEATHERS),
    "home_settee": _entry(
        "Mid-century settee", build_settee, SETTEE_SIZES,
        [("w", "Width"), ("d", "Depth"), ("h", "Back height"),
         ("seat", "Seat height"), ("seats", "Seats")], FABRICS),
    "home_cloud_sofa": _entry(
        "Cloud sofa (bouclé)", build_cloud_sofa, CLOUD_SIZES,
        [("w", "Width"), ("d", "Depth"), ("h", "Back height"),
         ("seat", "Seat height"), ("seats", "Seats")], BOUCLES),
    "home_tuxedo_sofa": _entry(
        "Tuxedo sofa (velvet)", build_tuxedo_sofa, TUXEDO_SIZES,
        [("w", "Width"), ("d", "Depth"), ("h", "Back height"),
         ("seat", "Seat height")], VELVETS),
    "home_armchair": _entry(
        "Armchair", build_armchair, ARMCHAIR_SIZES,
        [("w", "Width"), ("d", "Depth"), ("h", "Back height"),
         ("seat", "Seat height")], FABRICS),
    "home_coffee_table": _entry("Coffee table", build_coffee_table,
                                COFFEE_SIZES, _WHD, WOODS),
    "home_bookcase": _entry("Bookcase (with books)", build_bookcase,
                            BOOKCASE_SIZES, _WHD + [("shelves", "Shelves")],
                            WOODS),
    "home_sideboard": _entry("Sideboard / TV unit", build_sideboard,
                             SIDEBOARD_SIZES, _WHD, WOODS),
    "home_floor_lamp": _entry("Floor lamp", build_floor_lamp, LAMP_SIZES,
                              [("h", "Height"), ("shade", "Shade diameter")]),
    "home_bed": _entry(
        "Bed (made up)", build_bed, BED_SIZES,
        [("w", "Mattress width"), ("l", "Mattress length"),
         ("head", "Headboard height")], FABRICS),
    "home_bedside_table": _entry("Bedside table (with lamp)",
                                 build_bedside_table, BEDSIDE_SIZES, _WHD,
                                 WOODS),
    "home_wardrobe": _entry("Wardrobe", build_wardrobe, WARDROBE_SIZES,
                            _WHD + [("doors", "Doors")], WOODS),
    "home_chest": _entry("Chest of drawers", build_chest, CHEST_SIZES,
                         _WHD + [("drawers", "Drawers")], WOODS),
    "home_kitchen": _entry(
        "Kitchen (units, sink, hob, oven)", build_kitchen, KITCHEN_SIZES,
        [("units", "Units"), ("unit", "Unit width"), ("d", "Depth"),
         ("h", "Worktop height")], FRONTS),
    "home_fridge": _entry("Fridge-freezer", build_fridge, FRIDGE_SIZES,
                          _WHD, APPLIANCE),
    "home_toilet": _entry(
        "Toilet", build_toilet, TOILET_SIZES,
        [("w", "Width"), ("d", "Projection"), ("seat", "Seat height")]),
    "home_washbasin": _entry(
        "Washbasin (vanity + mirror)", build_washbasin, BASIN_SIZES,
        [("w", "Width"), ("d", "Depth"), ("h", "Basin height")], WOODS),
    "home_bath": _entry("Bath", build_bath, BATH_SIZES,
                        [("l", "Length"), ("w", "Width"), ("h", "Height")]),
    "home_shower": _entry("Shower enclosure", build_shower, SHOWER_SIZES,
                          _WHD),
}
