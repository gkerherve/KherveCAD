"""Laboratory and company furniture for the parts library — what a
chemistry lab, a physics lab and an office need, so the House Builder
can furnish them:

- chemistry lab: island bench with reagent shelf and gas taps, sink
  bench, fume hood, safety shower with eyewash, safety storage cabinet,
  lab fridge, drying oven, centrifuge, rotary evaporator, a set of
  glassware (library_chem's own pieces), lab stool, fire extinguisher,
  first-aid box;
- physics lab: optical table, laser, optics on posts, oscilloscope,
  power supply, signal generator, 19" instrument rack, UHV chamber on
  its frame, liquid-nitrogen dewar, electronics bench, whiteboard;
- company: bench desks with monitors, cubicle, meeting table with
  chairs, printer, server rack, lockers, coffee machine, vending
  machine, phone booth, acoustic partition.

Same rules as `library_home` (whose primitives this reuses): unions of
boxes, cylinders and capsules, NO booleans, true size in mm, front
facing -Y, standing on z = 0, centred on X and Y. ``on_top`` pieces sit
on the bench under them (`house.surface_below`), ``rest_z`` ones hang on
the wall. Registered into the home catalogue from the bottom of
`library_home_extra` (category "Home furniture"), so the House Builder
and the House & home menu list them by room.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import library_home as _home
from . import library_home_more as _more
from .library_home import (BLACK, BOOKS, CHROME, FABRICS, GLASS, PLINTH,
                           STEEL, WHITE, WOODS, _count, _paint, _pick)
from .library_room import _dims, build_monitor
from .model import CadNode

CATEGORY = "Home furniture"

#: A lab or an office stands dozens of these together, and the
#: document's common $fn (45) re-rounds every round thing with more than
#: 8 sides: a bench desk of rounded boxes came to 60k triangles. Small
#: rounds stay square, and small cylinders, rods and knobs keep 8 sides
#: (`model.keeps_segments`) — invisible at room scale.
SMALL_ROUND = 20.0


def _box(name, x, y, z, w, d, h, color, r=0.0, material="Default",
         alpha=1.0):
    return _home._box(name, x, y, z, w, d, h, color,
                      r if r >= SMALL_ROUND else 0.0, material, alpha)


def _cyl(name, x, y, z, h, r, color, r2=None, seg=32, material="Default",
         alpha=1.0):
    if max(r, r2 or 0.0) <= 60.0:
        seg = min(seg, 8)
    return _home._cyl(name, x, y, z, h, r, color, r2, seg, material, alpha)


def _rod(name, a, b, r, color=CHROME, material="Metal"):
    node = _home._rod(name, a, b, r, color, material)
    for n in node.walk():
        if n.type == "capsule":
            n.params["segments"] = 8
    return node


def _disc_y(name, x, y, z, r, t, color, material="Default", alpha=1.0,
            seg=40):
    return _more._disc_y(name, x, y, z, r, t, color, material, alpha,
                         min(seg, 8) if r <= 60 else seg)
COUNT_FIELDS = {"seats", "units"}

RESIN = "#2f3338"                      # black epoxy worktop
LAB_GREY = "#d9dcdf"
SAFETY_YELLOW = "#e8b923"
SAFETY_RED = "#c0392b"
SAFETY_GREEN = "#2e8b57"
SAFETY_BLUE = "#2f6db5"
INSTRUMENT = "#dfe2e5"
PANEL = "#2b2f36"
SCREEN = "#1d2530"
TRACE = "#6cff8a"
ANODISED = "#1c1d20"
LAB_FRONTS = {"Light grey": LAB_GREY, "White": "#f4f4f2",
              "Blue": "#3f6ea8", "Green": "#5e8f6a"}
CABINET_KINDS = {"Flammables (yellow)": SAFETY_YELLOW,
                 "Acids (blue)": SAFETY_BLUE, "Toxics (red)": SAFETY_RED}
DESK_TOPS = {"White": "#f1efea", "Oak": WOODS["Oak"][0],
             "Walnut": WOODS["Walnut"][0]}
BOOTH_COLORS = {"Charcoal": "#4a4f56", "Green": "#6f8f5a",
                "Blue": "#3f5f8a", "Terracotta": "#b8674a"}


def _at(node, x=0.0, y=0.0, z=0.0, rz=0.0):
    """*node* turned by *rz* about Z, then moved to (x, y, z)."""
    if rz:
        turn = CadNode("rotate", node.name, dict(x=0.0, y=0.0, z=rz))
        turn.add(node)
        node = turn
    move = CadNode("translate", node.name, dict(x=x, y=y, z=z))
    move.add(node)
    return move


def _knob(name, x, y, z, color=BLACK, r=9.0):
    return _disc_y(name, x, y, z, r, 12.0, color, seg=16)


def _screen(part, x, y, z, w, h, color=SCREEN, glow=None):
    """A flat screen on the front face at y, low-left corner (x, z)."""
    part.add(_box("Screen", x, y - 2, z, w, 4, h, color))
    if glow:
        part.add(_box("Trace", x + w * 0.1, y - 3, z + h * 0.45, w * 0.8, 2,
                      h * 0.06, glow, material="Emissive"))


def _cupboards(part, w, d, h, front, y0=None, doors=None):
    """A base-cabinet run w wide from -w/2, fronts at y0 (default -d/2)."""
    y0 = -d / 2 if y0 is None else y0
    part.add(_box("Plinth", -w / 2 + 30, y0 + 40, 0.0, w - 60, d - 60, 100,
                  PLINTH))
    part.add(_box("Carcass", -w / 2, y0 + 20, 100.0, w, d - 20, h - 100,
                  front))
    n = doors or max(1, round(w / 600))
    dw = w / n
    for i in range(n):
        x = -w / 2 + i * dw
        part.add(_box("Door", x + 4, y0, 110.0, dw - 8, 20, h - 120, front,
                      r=3))
        part.add(_rod("Handle", (x + dw / 2 - 60, y0 - 12, h - 80),
                      (x + dw / 2 + 60, y0 - 12, h - 80), 6))


# ------------------------------------------------------------- chemistry

def build_lab_bench(dims):
    """An island bench: cupboards both sides, a black resin top, a
    reagent shelf down the middle with gas and power on its posts."""
    p = _dims(dims, BENCH_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    front = _pick(dims, LAB_FRONTS, "Light grey")
    part = CadNode("union", "Lab bench")
    part.add(_box("Carcass", -w / 2, -d / 2 + 20, 100.0, w, d - 40, h - 130,
                  front))
    part.add(_box("Plinth", -w / 2 + 30, -d / 2 + 60, 0.0, w - 60, d - 120,
                  100, PLINTH))
    n = max(1, round(w / 600))
    dw = w / n
    for side in (-1, 1):
        y = side * (d / 2 - 10) - 10
        for i in range(n):
            x = -w / 2 + i * dw
            part.add(_box("Door", x + 4, y, 110.0, dw - 8, 20, h - 140,
                          front, r=3))
    part.add(_box("Worktop", -w / 2 - 15, -d / 2 - 15, h - 30, w + 30,
                  d + 30, 30, RESIN, r=3))
    sh = 650.0
    for x in (-w / 2 + 40, 0.0, w / 2 - 40):
        part.add(_box("Shelf post", x - 20, -20.0, h, 40, 40, sh, STEEL,
                      material="Metal"))
    for z in (h + 300, h + sh - 20):
        part.add(_box("Reagent shelf", -w / 2 + 20, -130.0, z, w - 40, 260,
                      20, WHITE))
    for i, x in enumerate(range(int(-w / 2 + 150), int(w / 2 - 100), 140)):
        col = BOOKS[i % len(BOOKS)]
        part.add(_cyl("Reagent bottle", x, -60.0, h + 320, 150, 40, col,
                      seg=16))
        part.add(_cyl("Cap", x, -60.0, h + 470, 25, 20, BLACK, seg=12))
    service = CadNode("union", "Services")
    for x in (-w / 4, w / 4):
        for side in (-1, 1):
            service.add(_box("Socket", x - 60, side * 22 - 12, h + 120, 120,
                             24, 80, WHITE))
            service.add(_rod("Gas tap", (x + 120, side * 20, h + 100),
                             (x + 120, side * 90, h + 100), 10, SAFETY_YELLOW,
                             "Default"))
    part.add(service)
    return part


def build_lab_sink_bench(dims):
    p = _dims(dims, SINK_BENCH_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    front = _pick(dims, LAB_FRONTS, "Light grey")
    part = CadNode("union", "Sink bench")
    _cupboards(part, w, d, h - 30, front)
    top = CadNode("union", "Worktop")
    sw, sd = min(500.0, w * 0.4), d - 220
    sx = w / 2 - sw - 150
    for x0, ww in ((-w / 2, sx + w / 2), (sx + sw, w / 2 - sx - sw)):
        top.add(_box("Worktop", x0, -d / 2 - 15, h - 30, ww, d + 15, 30,
                     RESIN))
    top.add(_box("Worktop front", sx, -d / 2 - 15, h - 30, sw, 110, 30,
                 RESIN))
    top.add(_box("Worktop back", sx, -d / 2 + 95 + sd, h - 30, sw,
                 d - 95 - sd, 30, RESIN))
    part.add(top)
    part.add(_box("Sink floor", sx, -d / 2 + 95, h - 280, sw, sd, 20, RESIN))
    for x0, y0, ww, dd in ((sx, -d / 2 + 95, sw, 15),
                           (sx, -d / 2 + 80 + sd, sw, 15),
                           (sx, -d / 2 + 95, 15, sd),
                           (sx + sw - 15, -d / 2 + 95, 15, sd)):
        part.add(_box("Sink wall", x0, y0, h - 280, ww, dd, 250, RESIN))
    cx, by = sx + sw / 2, d / 2 - 60
    part.add(_cyl("Tap base", cx, by, h, 60, 20, CHROME, material="Metal"))
    part.add(_rod("Gooseneck", (cx, by, h + 60), (cx, by, h + 380), 12))
    part.add(_rod("Gooseneck", (cx, by, h + 380), (cx, by - 220, h + 380),
                  12))
    part.add(_rod("Spout", (cx, by - 220, h + 380), (cx, by - 220, h + 300),
                  10))
    for i, x in enumerate((-w / 2 + 150, -w / 2 + 300)):
        part.add(_cyl("Drying peg board", x, d / 2 - 40, h, 600, 6, WHITE,
                      seg=8))
    part.add(_box("Peg board", -w / 2 + 60, d / 2 - 30, h + 100, 340, 20,
                  560, WHITE))
    return part


def build_fume_hood(dims):
    p = _dims(dims, HOOD_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    front = _pick(dims, LAB_FRONTS, "White")
    part = CadNode("union", "Fume hood")
    base_h, work = 900.0, 30.0
    _cupboards(part, w, d, base_h - work, SAFETY_YELLOW, doors=2)
    part.add(_box("Work surface", -w / 2, -d / 2, base_h - work, w, d, work,
                  RESIN))
    top_z = h - 450
    part.add(_box("Back wall", -w / 2, d / 2 - 60, base_h, w, 60,
                  top_z - base_h, front))
    for sx in (-1, 1):
        x = -w / 2 if sx < 0 else w / 2 - 120
        part.add(_box("Side wall", x, -d / 2, base_h, 120, d,
                      top_z - base_h, front, r=4))
        part.add(_box("Side window", x - 1, -d / 2 + 150, base_h + 200, 122,
                      d - 350, top_z - base_h - 400, GLASS, alpha=0.3,
                      material="Glass"))
    part.add(_box("Canopy", -w / 2, -d / 2, top_z, w, d, h - top_z - 200,
                  front, r=6))
    part.add(_cyl("Extract duct", 0.0, 80.0, h - 200, 200, 125, STEEL,
                  material="Metal"))
    sash_z = base_h + 380
    part.add(_box("Sash frame", -w / 2 + 120, -d / 2 - 30, sash_z, w - 240,
                  30, 40, front))
    part.add(_box("Sash glass", -w / 2 + 130, -d / 2 - 25, sash_z + 40,
                  w - 260, 12, top_z - sash_z - 40, GLASS, alpha=0.25,
                  material="Glass"))
    part.add(_rod("Sash handle", (-w / 2 + 250, -d / 2 - 60, sash_z + 15),
                  (w / 2 - 250, -d / 2 - 60, sash_z + 15), 12))
    part.add(_box("Airflow display", w / 2 - 110, -d / 2 - 2, top_z - 250,
                  90, 4, 120, SCREEN))
    part.add(_box("Status light", w / 2 - 95, -d / 2 - 4, top_z - 90, 60, 4,
                  25, TRACE, material="Emissive"))
    part.add(_box("Lamp", -w / 2 + 130, -d / 2 + 60, top_z - 30, w - 260,
                  d - 200, 25, "#fff7dc", material="Emissive"))
    return part


def build_safety_shower(dims):
    p = _dims(dims, SHOWER_SIZES)
    h = p["h"]
    part = CadNode("union", "Safety shower")
    part.add(_cyl("Floor plate", 0.0, 200.0, 0.0, 12, 90, SAFETY_YELLOW))
    part.add(_rod("Riser", (0.0, 200.0, 37.0), (0.0, 200.0, h), 25,
                  SAFETY_YELLOW, "Default"))
    part.add(_rod("Arm", (0.0, 200.0, h), (0.0, -250.0, h), 22,
                  SAFETY_YELLOW, "Default"))
    part.add(_cyl("Shower head", 0.0, -250.0, h - 120, 100, 170,
                  SAFETY_GREEN, r2=40))
    part.add(_rod("Pull rod", (0.0, 50.0, h - 20), (0.0, 50.0, 1500.0), 8,
                  SAFETY_YELLOW, "Default"))
    part.add(_rod("Pull ring", (-60.0, 50.0, 1500.0), (60.0, 50.0, 1500.0),
                  12, SAFETY_YELLOW, "Default"))
    part.add(_rod("Eyewash arm", (0.0, 200.0, 950.0), (0.0, -120.0, 950.0),
                  18, SAFETY_YELLOW, "Default"))
    part.add(_cyl("Eyewash bowl", 0.0, -220.0, 930.0, 60, 90, SAFETY_GREEN,
                  r2=150))
    for x in (-40.0, 40.0):
        part.add(_cyl("Eyewash nozzle", x, -220.0, 960.0, 40, 16,
                      SAFETY_GREEN))
    part.add(_box("Sign", -150.0, 280.0, h - 500, 300, 10, 300,
                  SAFETY_GREEN))
    part.add(_box("Sign cross", -40.0, 275.0, h - 450, 80, 6, 200, WHITE))
    part.add(_box("Sign cross", -100.0, 275.0, h - 390, 200, 6, 80, WHITE))
    return part


def build_safety_cabinet(dims):
    p = _dims(dims, CABINET_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    col = _pick(dims, CABINET_KINDS, "Flammables (yellow)")
    part = CadNode("union", "Safety cabinet")
    part.add(_box("Body", -w / 2, -d / 2 + 20, 0.0, w, d - 20, h, col, r=6,
                  material="Metal"))
    for sx in (-1, 1):
        x = -w / 2 + 5 if sx < 0 else 5.0
        part.add(_box("Door", x, -d / 2, 60.0, w / 2 - 10, 22, h - 120, col,
                      r=4, material="Metal"))
    part.add(_rod("Handle", (-30.0, -d / 2 - 15, h / 2 - 150),
                  (-30.0, -d / 2 - 15, h / 2 + 150), 10, BLACK))
    part.add(_rod("Handle", (30.0, -d / 2 - 15, h / 2 - 150),
                  (30.0, -d / 2 - 15, h / 2 + 150), 10, BLACK))
    for sx in (-1, 1):
        part.add(_box("Warning label", sx * w / 4 - 110, -d / 2 - 3,
                      h - 450, 220, 4, 220, SAFETY_RED if col != SAFETY_RED
                      else WHITE))
        part.add(_box("Warning symbol", sx * w / 4 - 50, -d / 2 - 5,
                      h - 400, 100, 4, 120, BLACK))
    return part


def build_lab_fridge(dims):
    p = _dims(dims, LAB_FRIDGE_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    part = CadNode("union", "Lab fridge")
    part.add(_box("Body", -w / 2, -d / 2 + 30, 0.0, w, d - 30, h, WHITE,
                  r=10))
    part.add(_box("Glass door", -w / 2 + 10, -d / 2, 60.0, w - 20, 30,
                  h - 80, GLASS, alpha=0.35, material="Glass"))
    for z in range(400, int(h - 200), 380):
        part.add(_box("Shelf", -w / 2 + 40, -d / 2 + 80, z, w - 80, d - 150,
                      10, STEEL, material="Metal"))
        for i, x in enumerate(range(int(-w / 2 + 90), int(w / 2 - 60), 90)):
            part.add(_cyl("Bottle", x, -20.0, z + 10, 180, 30,
                          BOOKS[(i + z) % len(BOOKS)], seg=12))
    part.add(_rod("Handle", (w / 2 - 50, -d / 2 - 30, h * 0.35),
                  (w / 2 - 50, -d / 2 - 30, h * 0.65), 12))
    part.add(_box("Display", -60.0, -d / 2 - 2, h - 45, 120, 4, 30, SCREEN))
    part.add(_box("Label", -w / 2 + 40, -d / 2 - 3, h - 160, 160, 4, 90,
                  SAFETY_YELLOW))
    return part


def build_drying_oven(dims):
    p = _dims(dims, OVEN_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    part = CadNode("union", "Drying oven")
    part.add(_box("Body", -w / 2, -d / 2 + 30, 0.0, w, d - 30, h, INSTRUMENT,
                  r=8))
    dw = w * 0.72
    part.add(_box("Door", -w / 2 + 15, -d / 2, 15.0, dw, 30, h - 30,
                  INSTRUMENT, r=6))
    part.add(_box("Window", -w / 2 + 80, -d / 2 - 2, 90.0, dw - 130, 4,
                  h - 180, SCREEN, alpha=0.8))
    part.add(_rod("Handle", (-w / 2 + dw - 20, -d / 2 - 30, h * 0.3),
                  (-w / 2 + dw - 20, -d / 2 - 30, h * 0.7), 10))
    px = -w / 2 + dw + 30
    part.add(_box("Control panel", px, -d / 2 + 25, 20.0, w / 2 - px - 15,
                  8, h - 40, PANEL))
    cw = w / 2 - px - 15
    part.add(_box("Display", px + 20, -d / 2 + 22, h - 140, cw - 40, 4, 60,
                  "#ff5a36", material="Emissive"))
    part.add(_knob("Knob", px + cw / 2, -d / 2 + 25, h * 0.45))
    return part


def build_centrifuge(dims):
    p = _dims(dims, CENTRIFUGE_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    part = CadNode("union", "Centrifuge")
    part.add(_box("Body", -w / 2, -d / 2, 0.0, w, d, h * 0.8, WHITE, r=40))
    part.add(_cyl("Lid", 0.0, 30.0, h * 0.8, h * 0.2, min(w, d) * 0.4,
                  INSTRUMENT, r2=min(w, d) * 0.3))
    part.add(_cyl("Lid window", 0.0, 30.0, h, 4, min(w, d) * 0.22, SCREEN))
    part.add(_box("Panel", -w * 0.35, -d / 2 - 2, h * 0.25, w * 0.7, 6,
                  h * 0.35, PANEL, r=4))
    part.add(_box("Display", -w * 0.25, -d / 2 - 4, h * 0.4, w * 0.3, 4,
                  h * 0.1, TRACE, material="Emissive"))
    return part


def build_rotavap(dims):
    """Rotary evaporator: base with heating bath, tilted arm with the
    rotating flask, a coil condenser and the receiving flask."""
    p = _dims(dims, ROTAVAP_SIZES)
    w = p["w"]
    s = w / 600.0
    part = CadNode("union", "Rotary evaporator")
    part.add(_box("Base", -300 * s, -150 * s, 0.0, 600 * s, 300 * s, 60 * s,
                  WHITE, r=10))
    part.add(_cyl("Bath", -150 * s, -20 * s, 60 * s, 130 * s, 130 * s,
                  STEEL, material="Metal"))
    part.add(_cyl("Water", -150 * s, -20 * s, 180 * s, 5 * s, 120 * s,
                  "#8ecae6", alpha=0.6))
    part.add(_box("Tower", 150 * s, 40 * s, 60 * s, 90 * s, 90 * s, 520 * s,
                  WHITE, r=8))
    part.add(_rod("Arm", (190 * s, 40 * s, 450 * s),
                  (-60 * s, -20 * s, 330 * s), 30 * s, INSTRUMENT, "Default"))
    part.add(_rod("Vapour duct", (-60 * s, -20 * s, 330 * s),
                  (-120 * s, -20 * s, 290 * s), 12 * s, GLASS, "Glass"))
    flask = _paint(CadNode("sphere", "Evaporating flask", dict(
        x=-150 * s, y=-20 * s, z=240 * s, radius=85 * s, segments=24)),
        GLASS, "Glass", 0.35)
    part.add(flask)
    part.add(_cyl("Condenser", 195 * s, 40 * s, 470 * s, 330 * s, 45 * s,
                  GLASS, alpha=0.35, material="Glass"))
    part.add(_cyl("Coil", 195 * s, 40 * s, 490 * s, 290 * s, 30 * s,
                  "#6fa8dc", alpha=0.6))
    part.add(_paint(CadNode("sphere", "Receiving flask", dict(
        x=195 * s, y=40 * s, z=330 * s, radius=70 * s, segments=24)),
        GLASS, "Glass", 0.35))
    return part


def build_glassware_set(dims):
    """A tray of glassware — beakers, conical flasks, a cylinder, a wash
    bottle, a tube rack — drawn light (no graduations: library_chem's
    printed scales cost 30k triangles a tray; insert those for close-ups).
    """
    p = _dims(dims, GLASSWARE_SIZES)
    w, d = p["w"], p["d"]
    part = CadNode("union", "Glassware")
    part.add(_box("Tray", -w / 2, -d / 2, 0.0, w, d, 12, WHITE, r=4))
    z = 12.0
    for x, y, r, h, liquid in ((-0.33, -0.2, 35, 95, "#4a90d9"),
                               (-0.12, -0.25, 25, 70, None),
                               (0.3, 0.22, 16, 190, "#cfe8f0")):
        x, y = x * w, y * d
        part.add(_cyl("Glass", x, y, z, h, r, GLASS, seg=20, alpha=0.3,
                      material="Glass"))
        if liquid:
            part.add(_cyl("Liquid", x, y, z + 2, h * 0.55, r - 2, liquid,
                          seg=20, alpha=0.7))
    for x, y, liquid in ((0.08, -0.18, "#57b35a"), (0.3, -0.2, "#e0c040")):
        x, y = x * w, y * d
        part.add(_cyl("Flask", x, y, z, 90, 45, GLASS, r2=14, seg=20,
                      alpha=0.3, material="Glass"))
        part.add(_cyl("Neck", x, y, z + 90, 40, 13, GLASS, seg=16,
                      alpha=0.3, material="Glass"))
        part.add(_cyl("Liquid", x, y, z + 2, 40, 40, liquid, r2=30, seg=20,
                      alpha=0.7))
    bx, by = -0.34 * w, 0.22 * d
    part.add(_cyl("Wash bottle", bx, by, z, 150, 35, WHITE, seg=20))
    part.add(_rod("Wash spout", (bx, by, z + 170), (bx + 40, by - 30, z + 190),
                  3, WHITE, "Default"))
    rack = CadNode("union", "Tube rack")
    rx, ry = 0.0, 0.22 * d
    rack.add(_box("Rack", rx - 90, ry - 30, z, 180, 60, 10, WHITE))
    rack.add(_box("Rack top", rx - 90, ry - 30, z + 60, 180, 60, 10, WHITE))
    for i in range(6):
        tx = rx - 75 + i * 30
        rack.add(_cyl("Test tube", tx, ry, z + 10, 130, 8, GLASS, seg=12,
                      alpha=0.3, material="Glass"))
        rack.add(_cyl("Sample", tx, ry, z + 12, 40, 6,
                      BOOKS[i % len(BOOKS)], seg=12))
    part.add(rack)
    return part


def build_task_chair(dims=None):
    """A light office chair (under 200 triangles) for desks and tables
    where dozens stand together; `home_office_chair` is the detailed
    one."""
    fab = FABRICS["Charcoal"]
    part = CadNode("union", "Chair")
    part.add(_home._cyl("Base", 0.0, 0.0, 0.0, 60, 280, BLACK, r2=60,
                        seg=5, material="Metal"))
    part.add(_cyl("Column", 0.0, 0.0, 60.0, 360, 25, CHROME,
                  material="Metal"))
    part.add(_box("Seat", -240.0, -240.0, 420.0, 480, 480, 70, fab))
    part.add(_box("Back", -220.0, 210.0, 520.0, 440, 60, 520, fab))
    return part


def build_lab_stool(dims):
    p = _dims(dims, STOOL_SIZES)
    seat = p["seat"]
    part = CadNode("union", "Lab stool")
    part.add(_cyl("Base", 0.0, 0.0, 0.0, 40, 280, BLACK, r2=250,
                  material="Metal"))
    part.add(_cyl("Column", 0.0, 0.0, 40.0, seat - 100, 30, CHROME,
                  material="Metal"))
    part.add(_cyl("Foot ring", 0.0, 0.0, 300.0, 20, 220, CHROME,
                  material="Metal"))
    part.add(_cyl("Seat", 0.0, 0.0, seat - 60, 60, 190, PANEL, r2=180,
                  material="Rubber"))
    return part


def build_fire_extinguisher(dims):
    part = CadNode("union", "Fire extinguisher")
    part.add(_box("Wall bracket", -70.0, 60.0, 50.0, 140, 10, 300, BLACK))
    part.add(_cyl("Cylinder", 0.0, 0.0, 0.0, 480, 80, SAFETY_RED, seg=24,
                  material="Metal"))
    part.add(_cyl("Shoulder", 0.0, 0.0, 480.0, 50, 80, SAFETY_RED, r2=30))
    part.add(_cyl("Valve", 0.0, 0.0, 530.0, 60, 22, CHROME,
                  material="Metal"))
    part.add(_rod("Nozzle", (0.0, 0.0, 570.0), (0.0, -80.0, 570.0), 10,
                  BLACK))
    part.add(_box("Sign", -110.0, 65.0, 650.0, 220, 6, 220, SAFETY_RED))
    return part


def build_first_aid(dims):
    part = CadNode("union", "First aid box")
    part.add(_box("Box", -200.0, -60.0, 0.0, 400, 130, 300, SAFETY_GREEN,
                  r=10))
    part.add(_box("Cross", -30.0, -63.0, 70.0, 60, 4, 160, WHITE))
    part.add(_box("Cross", -80.0, -63.0, 120.0, 160, 4, 60, WHITE))
    return part


# --------------------------------------------------------------- physics

def build_optical_table(dims):
    """A vibration-isolated optical table: steel top on four isolator
    legs, the tapped-hole grid drawn as dark lines every 25 mm x 4."""
    p = _dims(dims, OPTICAL_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    part = CadNode("union", "Optical table")
    top = 300.0
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * (w / 2 - 250), sy * (d / 2 - 200)
            part.add(_box("Isolator leg", x - 150, y - 150, 0.0, 300, 300,
                          h - top - 80, "#3b5f8f", r=12))
            part.add(_cyl("Isolator", x, y, h - top - 80, 80, 110, BLACK))
    part.add(_box("Table top", -w / 2, -d / 2, h - top, w, d, top - 4,
                  "#8a9098", material="Metal"))
    grid = CadNode("union", "Hole grid")
    pitch = 100.0
    nx, ny = int(w // pitch), int(d // pitch)
    for i in range(1, nx):
        x = -w / 2 + i * pitch
        grid.add(_box("Row", x - 2, -d / 2 + 25, h - 4, 4, d - 50, 4, "#5d636b"))
    for j in range(1, ny):
        y = -d / 2 + j * pitch
        grid.add(_box("Row", -w / 2 + 25, y - 2, h - 4, w - 50, 4, 4, "#5d636b"))
    part.add(grid)
    part.add(_box("Skin", -w / 2 + 25, -d / 2 + 25, h - 6, w - 50, d - 50, 4,
                  "#b3b9c0", material="Metal"))
    return part


def build_laser(dims):
    p = _dims(dims, LASER_SIZES)
    l = p["l"]
    part = CadNode("union", "Laser")
    part.add(_box("Base plate", -l / 2 - 20, -60.0, 0.0, l + 40, 120, 12,
                  ANODISED))
    part.add(_box("Head", -l / 2, -45.0, 12.0, l, 90, 70, WHITE, r=6))
    part.add(_box("Warning label", -l / 4, -47.0, 30.0, 80, 3, 40,
                  SAFETY_YELLOW))
    move = CadNode("translate", "Aperture", dict(x=l / 2, y=0.0, z=47.0))
    turn = CadNode("rotate", "Aperture", dict(x=0.0, y=90.0, z=0.0))
    turn.add(CadNode("cylinder", "Aperture", dict(
        x=0.0, y=0.0, z=0.0, height=20, radius_bottom=12, radius_top=12,
        segments=16, center=False)))
    move.add(turn)
    part.add(_paint(move, ANODISED, "Metal"))
    part.add(_rod("Beam", (l / 2 + 20, 0.0, 47.0), (l / 2 + 600, 0.0, 47.0),
                  1.2, "#ff2a2a", "Emissive"))
    return part


def _post_mount(name, x, y, z, color):
    node = CadNode("union", name)
    node.add(_cyl("Post holder", x, y, z, 60, 13, ANODISED, seg=16,
                  material="Metal"))
    node.add(_cyl("Post", x, y, z + 60, 50, 6, STEEL, seg=12,
                  material="Metal"))
    node.add(_box("Mount", x - 30, y - 8, z + 100, 60, 16, 60, ANODISED))
    node.add(_disc_y("Optic", x, y - 8, z + 130, 13, 4, color, seg=24))
    return node


def build_optics_set(dims):
    """Mirrors, lenses and a beam splitter on posts, laid along a beam."""
    p = _dims(dims, OPTICS_SIZES)
    n = _count(p, "units", 2, 12)
    part = CadNode("union", "Optics")
    pitch = 120.0
    for i in range(n):
        x = (i - (n - 1) / 2) * pitch
        col = ("#c9d6e3", GLASS, "#e8d89a")[i % 3]
        part.add(_post_mount(f"Optic {i + 1}", x, 0.0, 0.0, col))
    part.add(_rod("Beam", (-(n - 1) / 2 * pitch - 60, 0.0, 130.0),
                  ((n - 1) / 2 * pitch + 60, 0.0, 130.0), 1.0, "#ff2a2a",
                  "Emissive"))
    return part


def _instrument(name, w, d, h, color=INSTRUMENT):
    part = CadNode("union", name)
    part.add(_box("Case", -w / 2, -d / 2 + 15, 0.0, w, d - 15, h, color,
                  r=8))
    part.add(_box("Front bezel", -w / 2 + 5, -d / 2, 5.0, w - 10, 15, h - 10,
                  PANEL, r=4))
    for sx in (-1, 1):
        part.add(_box("Foot", sx * (w / 2 - 40) - 20, -d / 2 + 30, 0.0, 40,
                      40, 10, BLACK))
    return part


def build_oscilloscope(dims):
    p = _dims(dims, SCOPE_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    part = _instrument("Oscilloscope", w, d, h)
    sw = w * 0.58
    _screen(part, -w / 2 + 25, -d / 2, 25.0, sw, h - 50, glow=TRACE)
    part.add(_box("Trace 2", -w / 2 + 25 + sw * 0.1, -d / 2 - 3, h * 0.3,
                  sw * 0.8, 2, h * 0.04, "#ffd84a", material="Emissive"))
    kx = -w / 2 + sw + 60
    for row in range(3):
        for col in range(3):
            part.add(_knob("Knob", kx + col * (w / 2 - kx - 20) / 2.6,
                           -d / 2, h - 50 - row * (h - 90) / 2.6,
                           r=12 if row else 16))
    for i in range(4):
        part.add(_disc_y("BNC", kx + i * 35, -d / 2 - 2, 25.0, 8, 14, CHROME,
                         seg=12))
    return part


def build_power_supply(dims):
    p = _dims(dims, PSU_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    part = _instrument("Power supply", w, d, h)
    for i, x in enumerate((-w * 0.25, w * 0.1)):
        part.add(_box("Readout", x - 60, -d / 2 - 2, h * 0.55, 120, 4, 40,
                      "#ff5a36" if i else TRACE, material="Emissive"))
        part.add(_knob("Voltage", x - 30, -d / 2, h * 0.3, r=14))
        part.add(_knob("Current", x + 30, -d / 2, h * 0.3, r=14))
    for i, col in enumerate((SAFETY_RED, BLACK, SAFETY_GREEN)):
        part.add(_disc_y("Terminal", w * 0.3 + i * 30, -d / 2 - 2, h * 0.25,
                         8, 18, col, seg=12))
    return part


def build_signal_generator(dims):
    p = _dims(dims, SIGGEN_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    part = _instrument("Signal generator", w, d, h)
    _screen(part, -w / 2 + 25, -d / 2, h * 0.35, w * 0.4, h * 0.5,
            color="#15324a", glow="#66d9ff")
    for i in range(10):
        part.add(_box("Key", w * 0.02 + (i % 5) * 38, -d / 2 - 6,
                      h * 0.55 - (i // 5) * 35, 28, 6, 24, "#c8ccd1"))
    part.add(_knob("Dial", w * 0.38, -d / 2, h * 0.5, r=24))
    for i in range(2):
        part.add(_disc_y("Output", w * 0.3 + i * 50, -d / 2 - 2, 25.0, 8,
                         14, CHROME, seg=12))
    return part


def build_instrument_rack(dims):
    """A 19-inch rack of instruments on castors (lock-in, controllers,
    a pump controller, a PC)."""
    p = _dims(dims, RACK_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    part = CadNode("union", "Instrument rack")
    part.add(_box("Frame", -w / 2, -d / 2 + 20, 60.0, w, d - 20, h - 60,
                  ANODISED, r=6))
    for sx in (-1, 1):
        for sy in (-1, 1):
            part.add(_cyl("Castor", sx * (w / 2 - 60), sy * (d / 2 - 60),
                          0.0, 60, 30, BLACK))
    units, u = int((h - 160) // 44.45), 44.45
    z, i = h - 60, 0
    sizes, colors = (2, 3, 1, 4, 2, 3, 2), (INSTRUMENT, "#9ea7b0", PANEL,
                                            "#d6d0c2", WHITE)
    while units > 0:
        n = min(sizes[i % len(sizes)], units)
        z -= n * u
        col = colors[i % len(colors)]
        part.add(_box("Instrument", -w / 2 + 40, -d / 2, z + 2, w - 80, 20,
                      n * u - 4, col, r=2))
        if n >= 2:
            part.add(_box("Display", -w / 2 + 70, -d / 2 - 3, z + n * u * 0.4,
                          140, 4, n * u * 0.35, TRACE if i % 2 else
                          "#ff5a36", material="Emissive"))
            part.add(_knob("Knob", w / 2 - 110, -d / 2 + 2, z + n * u / 2,
                           r=12))
        units -= n
        i += 1
    return part


def build_uhv_chamber(dims):
    """A UHV chamber: a stainless sphere on a frame, CF ports, a turbo
    pump below, an ion gauge, a viewport and a manipulator on top."""
    p = _dims(dims, UHV_SIZES)
    r, frame_h = p["d"] / 2, p["h"]
    part = CadNode("union", "UHV chamber")
    fw = r * 2 + 300
    for sx in (-1, 1):
        for sy in (-1, 1):
            part.add(_box("Frame leg", sx * fw / 2 - 25, sy * fw / 2 - 25,
                          0.0, 50, 50, frame_h, "#8d949c",
                          material="Metal"))
    for z in (150.0, frame_h - 50):
        part.add(_box("Frame rail", -fw / 2, -fw / 2, z, fw, 50, 50,
                      "#8d949c", material="Metal"))
        part.add(_box("Frame rail", -fw / 2, fw / 2 - 50, z, fw, 50, 50,
                      "#8d949c", material="Metal"))
    part.add(_box("Table", -fw / 2, -fw / 2, frame_h, fw, fw, 20, "#8d949c",
                  material="Metal"))
    cz = frame_h + 20 + r + 150
    part.add(_paint(CadNode("sphere", "Chamber", dict(
        x=0.0, y=0.0, z=cz, radius=r, segments=32)), STEEL, "Metal"))
    part.add(_cyl("Pedestal", 0.0, 0.0, frame_h + 20, 150 + r * 0.2, 70,
                  STEEL, material="Metal"))
    part.add(_cyl("Turbo flange", 0.0, 0.0, frame_h - 60, 60, 100, STEEL,
                  material="Metal"))
    part.add(_cyl("Turbo pump", 0.0, 0.0, frame_h - 300, 240, 80, "#c9cdd3",
                  material="Metal"))
    ports = ((90, 0), (-90, 0), (0, 0), (180, 0), (45, 35), (-45, 35),
             (135, -30))
    for az, el in ports:
        port = CadNode("union", "Port")
        port.add(_cyl("Tube", 0.0, 0.0, r * 0.8, 160, 38, STEEL,
                      material="Metal"))
        port.add(_cyl("CF flange", 0.0, 0.0, r * 0.8 + 140, 20, 57, STEEL,
                      material="Metal"))
        turn = CadNode("rotate", "Port", dict(x=0.0, y=90.0 - el, z=az))
        turn.add(port)
        part.add(_at(turn, 0.0, 0.0, cz))
    part.add(_disc_y("Viewport", 0.0, -r * 0.8 - 162, cz, 38, 6, GLASS,
                     material="Glass", alpha=0.4))
    part.add(_cyl("Manipulator flange", 0.0, 0.0, cz + r * 0.85, 30, 76,
                  STEEL, material="Metal"))
    part.add(_cyl("Bellows", 0.0, 0.0, cz + r * 0.85 + 30, 300, 55,
                  "#b8bdc4", material="Metal"))
    part.add(_box("XY stage", -110.0, -110.0, cz + r * 0.85 + 330, 220, 220,
                  60, STEEL, material="Metal"))
    part.add(_cyl("Micrometer", 0.0, 0.0, cz + r * 0.85 + 390, 250, 20,
                  CHROME, material="Metal"))
    part.add(_cyl("Ion gauge", -r * 1.1, 0.0, cz + 10, 150, 25, GLASS,
                  alpha=0.4, material="Glass"))
    return part


def build_dewar(dims):
    p = _dims(dims, DEWAR_SIZES)
    r, h = p["d"] / 2, p["h"]
    part = CadNode("union", "LN2 dewar")
    part.add(_cyl("Trolley", 0.0, 0.0, 0.0, 60, r + 40, BLACK))
    part.add(_cyl("Body", 0.0, 0.0, 60.0, h - 260, r, STEEL, material="Metal"))
    part.add(_cyl("Shoulder", 0.0, 0.0, h - 200, 120, r, STEEL, r2=r * 0.35,
                  material="Metal"))
    part.add(_cyl("Neck", 0.0, 0.0, h - 80, 80, r * 0.25, STEEL,
                  material="Metal"))
    for sx in (-1, 1):
        part.add(_rod("Handle", (sx * r * 0.7, 0.0, h - 140),
                      (sx * r * 0.7, 0.0, h + 40), 12))
    part.add(_rod("Handle bar", (-r * 0.7, 0.0, h + 40),
                  (r * 0.7, 0.0, h + 40), 12))
    part.add(_rod("Withdrawal tube", (0.0, 0.0, h), (r * 0.9, -r * 0.3, h),
                  8))
    part.add(_box("Label", -80.0, -r - 3, h * 0.5, 160, 4, 120,
                  SAFETY_BLUE))
    return part


def build_electronics_bench(dims):
    """A workbench with an instrument shelf, anti-static mat, a scope,
    a supply, a soldering station and a magnifier lamp."""
    p = _dims(dims, E_BENCH_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    part = CadNode("union", "Electronics bench")
    part.add(_box("Top", -w / 2, -d / 2, h - 40, w, d, 40, WOODS["Beech"][0]
                  if "Beech" in WOODS else WOODS["Oak"][0]))
    for sx in (-1, 1):
        for sy in (-1, 1):
            part.add(_box("Leg", sx * (w / 2 - 40) - 25, sy * (d / 2 - 40)
                          - 25, 0.0, 50, 50, h - 40, "#5d636b",
                          material="Metal"))
    part.add(_box("Anti-static mat", -w / 2 + 50, -d / 2 + 30, h, w - 100,
                  d - 250, 3, "#3b7fb5"))
    sz = h + 450
    for x in (-w / 2 + 30, w / 2 - 60):
        part.add(_box("Shelf upright", x, d / 2 - 90, h, 30, 60, 500,
                      "#5d636b", material="Metal"))
    part.add(_box("Instrument shelf", -w / 2 + 20, d / 2 - 300, sz, w - 40,
                  280, 25, WOODS["Oak"][0]))
    part.add(_at(build_oscilloscope({}), -w * 0.2, d / 2 - 160, sz + 35))
    part.add(_at(build_power_supply({}), w * 0.2, d / 2 - 160, sz + 35))
    part.add(_at(build_signal_generator({}), w * 0.2, d / 2 - 160, h + 10))
    part.add(_box("Soldering station", -w * 0.35, -d / 2 + 80, h, 150, 180,
                  110, PANEL, r=10))
    part.add(_rod("Iron holder", (-w * 0.35 + 190, -d / 2 + 120, h + 20),
                  (-w * 0.35 + 250, -d / 2 + 160, h + 120), 12, CHROME))
    part.add(_rod("Magnifier arm", (w / 2 - 150, d / 2 - 350, h),
                  (w / 2 - 350, -d / 2 + 250, h + 420), 10, WHITE,
                  "Default"))
    part.add(_cyl("Magnifier", w / 2 - 350, -d / 2 + 250, h + 400, 40, 90,
                  WHITE))
    return part


def build_whiteboard(dims):
    p = _dims(dims, BOARD_SIZES)
    w, h = p["w"], p["h"]
    part = CadNode("union", "Whiteboard")
    part.add(_box("Frame", -w / 2, -20.0, 40.0, w, 20, h, "#b8bdc4",
                  material="Metal"))
    part.add(_box("Board", -w / 2 + 15, -24.0, 55.0, w - 30, 6, h - 30,
                  "#fbfbf9"))
    part.add(_box("Pen tray", -w / 2 + 100, -80.0, 0.0, w - 200, 60, 20,
                  "#b8bdc4", material="Metal"))
    for i, col in enumerate((SAFETY_BLUE, SAFETY_RED, BLACK, SAFETY_GREEN)):
        part.add(_rod("Pen", (-w / 4 + i * 70, -50.0, 25.0),
                      (-w / 4 + i * 70 + 120, -50.0, 25.0), 8, col,
                      "Default"))
    for i, (x, z, ww) in enumerate(((-0.35, 0.75, 0.3), (-0.3, 0.6, 0.45),
                                    (0.05, 0.7, 0.3), (0.1, 0.4, 0.25))):
        part.add(_box("Writing", w * x, -28.0, 40 + h * z, w * ww, 2, 10,
                      (SAFETY_BLUE, BLACK, SAFETY_RED)[i % 3]))
    return part


# --------------------------------------------------------------- company

def build_bench_desks(dims):
    """Back-to-back bench desks with a screen divider, a monitor, a task
    chair and a pedestal at every seat."""
    p = _dims(dims, BENCH_DESK_SIZES)
    n = _count(p, "seats", 2, 12)
    seat_w, dd = p["w"], p["d"]
    top_col = _pick(dims, DESK_TOPS, "White")
    rows = 2 if n > 1 else 1
    per_row = (n + rows - 1) // rows
    W = per_row * seat_w
    D = rows * dd
    part = CadNode("union", "Bench desks")
    part.add(_box("Desk top", -W / 2, -D / 2, 710.0, W, D, 25, top_col, r=3))
    for x in (-W / 2 + 30, W / 2 - 60):
        part.add(_box("Frame", x, -D / 2 + 60, 0.0, 30, D - 120, 710,
                      "#8d949c", material="Metal"))
    part.add(_box("Beam", -W / 2 + 30, -20.0, 650.0, W - 60, 40, 40,
                  "#8d949c", material="Metal"))
    if rows == 2:
        part.add(_box("Divider", -W / 2 + 20, -15.0, 735.0, W - 40, 30, 380,
                      "#6f8f5a", r=8))
    seat = CadNode("union", "Seat")         # one place, facing -Y
    seat.add(_at(build_monitor({"_size": "24 inch"}), 0.0, -180.0, 735.0))
    seat.add(_box("Keyboard", -220.0, -dd + 150, 735.0, 440, 150, 20,
                  "#e8e9eb", r=4))
    seat.add(_box("Pedestal", seat_w / 2 - 480, -520.0, 0.0, 420, 470, 600,
                  WHITE, r=4))
    seat.add(_at(build_task_chair(), 0.0, -dd - 250, 0.0))
    k = 0
    for row in range(rows):
        for i in range(per_row):
            if k >= n:
                break
            k += 1
            x = -W / 2 + (i + 0.5) * seat_w
            part.add(_at(seat, x, 0.0, 0.0, 0.0 if row == 0 else 180.0))
    return part


def build_cubicle(dims):
    p = _dims(dims, CUBICLE_SIZES)
    w, d = p["w"], p["d"]
    fab = _pick(dims, BOOTH_COLORS, "Charcoal")
    top_col = DESK_TOPS["White"]
    part = CadNode("union", "Cubicle")
    ph, t = 1400.0, 60.0
    part.add(_box("Back panel", -w / 2, d / 2 - t, 0.0, w, t, ph, fab, r=10))
    for sx in (-1, 1):
        x = -w / 2 if sx < 0 else w / 2 - t
        part.add(_box("Side panel", x, -d / 2, 0.0, t, d - t, ph, fab, r=10))
    part.add(_box("Desk", -w / 2 + t, d / 2 - t - 750, 710.0, w - 2 * t, 750,
                  25, top_col, r=3))
    part.add(_box("Return", -w / 2 + t, -d / 2 + 100, 710.0, 600,
                  d - t - 850, 25, top_col, r=3))
    part.add(_box("Pedestal", w / 2 - t - 450, d / 2 - t - 600, 0.0, 420,
                  560, 600, WHITE, r=4))
    part.add(_at(build_monitor({"_size": "27 inch"}), 0.0, d / 2 - 250,
                 735.0))
    part.add(_box("Shelf", -w / 2 + t, d / 2 - t - 300, 1150.0, w - 2 * t,
                  300, 25, top_col))
    part.add(_at(build_task_chair(), 0.0,
                 d / 2 - 1050, 0.0))
    return part


def build_meeting_table(dims):
    p = _dims(dims, MEETING_SIZES)
    n = _count(p, "seats", 2, 20)
    top_col = _pick(dims, DESK_TOPS, "Oak")
    per_side = (n + 1) // 2
    w = max(p["w"], per_side * 700.0 + 300)
    d = p["d"]
    part = CadNode("union", "Meeting table")
    part.add(_box("Top", -w / 2, -d / 2, 720.0, w, d, 30, top_col, r=12))
    for x in (-w / 2 + 400, w / 2 - 400):
        part.add(_box("Pedestal", x - 60, -d / 4, 30.0, 120, d / 2, 690,
                      "#5d636b", material="Metal"))
        part.add(_box("Foot", x - 200, -d / 3, 0.0, 400, d * 2 / 3, 30,
                      "#5d636b", material="Metal"))
    part.add(_box("Power box", -150.0, -60.0, 750.0, 300, 120, 12, BLACK))
    chair = build_task_chair()
    k = 0
    for side in (-1, 1):
        for i in range(per_side):
            if k >= n:
                break
            k += 1
            x = (i - (per_side - 1) / 2) * 700.0
            part.add(_at(chair, x, side * (d / 2 + 280), 0.0,
                         0.0 if side < 0 else 180.0))
    return part


def build_printer(dims):
    p = _dims(dims, PRINTER_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    part = CadNode("union", "Office printer")
    part.add(_box("Body", -w / 2, -d / 2, 0.0, w, d, h * 0.75, WHITE, r=10))
    for i in range(3):
        part.add(_box("Paper tray", -w / 2 + 20, -d / 2 - 4,
                      60 + i * h * 0.16, w - 40, 6, h * 0.14, "#e3e5e8", r=4))
    part.add(_box("Output bay", -w / 2 + 40, -d / 2 + 40, h * 0.75, w - 80,
                  d - 80, 30, PANEL))
    part.add(_box("Scanner", -w / 2, -d / 2, h * 0.75 + 30, w, d,
                  h * 0.25 - 30, WHITE, r=8))
    part.add(_box("Touch panel", w / 2 - 280, -d / 2 - 60, h - 60, 240, 120,
                  30, SCREEN))
    return part


def build_server_rack(dims):
    p = _dims(dims, SERVER_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    part = CadNode("union", "Server rack")
    part.add(_box("Cabinet", -w / 2, -d / 2 + 20, 0.0, w, d - 20, h, BLACK,
                  r=4, material="Metal"))
    u = 44.45
    z = 120.0
    i = 0
    while z + 2 * u < h - 150:
        n = 2 if i % 3 else 1
        part.add(_box("Server", -w / 2 + 40, -d / 2 + 30, z, w - 80, 10,
                      n * u - 4, "#3a3d42"))
        for j in range(4):
            part.add(_box("LED", -w / 2 + 70 + j * 25, -d / 2 + 27,
                          z + n * u / 2, 8, 4, 6,
                          TRACE if (i + j) % 3 else "#4aa3ff",
                          material="Emissive"))
        z += n * u
        i += 1
    part.add(_box("Glass door", -w / 2 + 10, -d / 2, 20.0, w - 20, 20,
                  h - 40, SCREEN, alpha=0.35, material="Glass"))
    return part


def build_lockers(dims):
    p = _dims(dims, LOCKER_SIZES)
    n = _count(p, "units", 1, 12)
    col_w, d, h = p["w"], p["d"], p["h"]
    col = _pick(dims, LAB_FRONTS, "Light grey")
    W = n * col_w
    part = CadNode("union", "Lockers")
    part.add(_box("Plinth", -W / 2, -d / 2 + 20, 0.0, W, d - 20, 100,
                  PLINTH))
    part.add(_box("Carcass", -W / 2, -d / 2 + 20, 100.0, W, d - 20, h - 100,
                  col, material="Metal"))
    for i in range(n):
        x = -W / 2 + i * col_w
        for k in range(2):
            z0 = 110 + k * (h - 110) / 2
            part.add(_box("Door", x + 5, -d / 2, z0, col_w - 10, 20,
                          (h - 110) / 2 - 10, col, material="Metal"))
            part.add(_box("Lock", x + col_w - 60, -d / 2 - 6,
                          z0 + (h - 110) / 4, 30, 6, 50, BLACK))
            for s in range(3):
                part.add(_box("Vent", x + 30, -d / 2 - 2,
                              z0 + (h - 110) / 2 - 80 - s * 20,
                              col_w - 120, 3, 6, PLINTH))
    return part


def build_coffee_machine(dims):
    part = CadNode("union", "Coffee machine")
    part.add(_box("Body", -160.0, -200.0, 0.0, 320, 420, 420, "#2d2f33",
                  r=12, material="Metal"))
    part.add(_box("Bean hopper", -120.0, 40.0, 420.0, 240, 160, 90, GLASS,
                  alpha=0.4, material="Glass"))
    part.add(_box("Drip tray", -130.0, -260.0, 0.0, 260, 120, 30, CHROME,
                  material="Metal"))
    part.add(_box("Spout", -40.0, -230.0, 230.0, 80, 80, 40, CHROME,
                  material="Metal"))
    part.add(_cyl("Cup", 0.0, -200.0, 30.0, 100, 40, WHITE, seg=20))
    part.add(_box("Display", -80.0, -203.0, 330.0, 160, 4, 60, "#66d9ff",
                  material="Emissive"))
    return part


def build_vending_machine(dims):
    p = _dims(dims, VENDING_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    part = CadNode("union", "Vending machine")
    part.add(_box("Cabinet", -w / 2, -d / 2 + 20, 0.0, w, d - 20, h,
                  SAFETY_RED, r=10, material="Metal"))
    gw = w * 0.68
    part.add(_box("Window", -w / 2 + 30, -d / 2 + 5, 500.0, gw, 20, h - 650,
                  GLASS, alpha=0.3, material="Glass"))
    rows, cols = 6, 5
    for r in range(rows):
        z = 520 + r * (h - 700) / rows
        part.add(_box("Shelf", -w / 2 + 40, -d / 2 + 40, z, gw - 20, d - 100,
                      8, STEEL, material="Metal"))
        for c in range(cols):
            part.add(_box("Snack", -w / 2 + 50 + c * (gw - 40) / cols,
                          -d / 2 + 60, z + 8, (gw - 40) / cols - 15, 60, 120,
                          BOOKS[(r * 3 + c) % len(BOOKS)]))
    part.add(_box("Keypad", w / 2 - w * 0.25, -d / 2 + 5, h * 0.55, w * 0.18,
                  8, 260, PANEL))
    part.add(_box("Flap", -w / 2 + 60, -d / 2 + 5, 150.0, gw - 60, 12, 200,
                  BLACK))
    return part


def build_phone_booth(dims):
    p = _dims(dims, BOOTH_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    col = _pick(dims, BOOTH_COLORS, "Green")
    part = CadNode("union", "Phone booth")
    t = 60.0
    part.add(_box("Floor", -w / 2, -d / 2, 0.0, w, d, 60, col, r=8))
    part.add(_box("Roof", -w / 2, -d / 2, h - 80, w, d, 80, col, r=8))
    part.add(_box("Back", -w / 2, d / 2 - t, 60.0, w, t, h - 140, col))
    for sx in (-1, 1):
        part.add(_box("Side", -w / 2 if sx < 0 else w / 2 - t, -d / 2, 60.0,
                      t, d - t, h - 140, col))
    part.add(_box("Glass door", -w / 2 + t, -d / 2, 60.0, w - 2 * t, 20,
                  h - 140, GLASS, alpha=0.25, material="Glass"))
    part.add(_rod("Door handle", (w / 2 - 150, -d / 2 - 40, 900.0),
                  (w / 2 - 150, -d / 2 - 40, 1200.0), 12))
    part.add(_box("Shelf desk", -w / 2 + t, d / 2 - t - 350, 1000.0,
                  w - 2 * t, 350, 25, DESK_TOPS["Oak"]))
    part.add(_box("Stool", -180.0, -120.0, 60.0, 360, 300, 600,
                  FABRICS["Charcoal"], r=40))
    part.add(_box("Light", -w / 2 + 100, -d / 2 + 100, h - 90, w - 200,
                  d - 200, 10, "#fff7dc", material="Emissive"))
    return part


def build_partition(dims):
    p = _dims(dims, PARTITION_SIZES)
    w, h = p["w"], p["h"]
    col = _pick(dims, BOOTH_COLORS, "Charcoal")
    part = CadNode("union", "Acoustic partition")
    part.add(_box("Panel", -w / 2, -30.0, 60.0, w, 60, h - 60, col, r=25))
    for sx in (-1, 1):
        part.add(_box("Foot", sx * (w / 2 - 150) - 30, -250.0, 0.0, 60, 500,
                      60, "#8d949c", material="Metal"))
    return part


# ---------------------------------------------------------------- sizes
BENCH_SIZES = {"3.0 × 1.5 m island": dict(w=3000.0, d=1500.0, h=900.0),
               "2.4 × 1.5 m island": dict(w=2400.0, d=1500.0, h=900.0),
               "3.6 × 1.5 m island": dict(w=3600.0, d=1500.0, h=900.0)}
SINK_BENCH_SIZES = {"1.8 m": dict(w=1800.0, d=750.0, h=900.0),
                    "2.4 m": dict(w=2400.0, d=750.0, h=900.0)}
HOOD_SIZES = {"1.5 m": dict(w=1500.0, d=900.0, h=2500.0),
              "1.8 m": dict(w=1800.0, d=900.0, h=2500.0),
              "1.2 m": dict(w=1200.0, d=900.0, h=2500.0)}
SHOWER_SIZES = {"Standard": dict(h=2300.0)}
CABINET_SIZES = {"Tall": dict(w=1100.0, d=600.0, h=1950.0),
                 "Under-bench": dict(w=1100.0, d=570.0, h=640.0)}
LAB_FRIDGE_SIZES = {"Tall": dict(w=600.0, d=650.0, h=1850.0),
                    "Under-bench": dict(w=600.0, d=600.0, h=820.0)}
OVEN_SIZES = {"Bench": dict(w=620.0, d=520.0, h=640.0)}
CENTRIFUGE_SIZES = {"Benchtop": dict(w=400.0, d=550.0, h=320.0)}
ROTAVAP_SIZES = {"Standard": dict(w=600.0)}
GLASSWARE_SIZES = {"Tray": dict(w=520.0, d=320.0)}
STOOL_SIZES = {"Bench height": dict(seat=650.0)}
EXTINGUISHER_SIZES = {"6 kg": dict()}
FIRST_AID_SIZES = {"Wall box": dict()}
OPTICAL_SIZES = {"1.2 × 2.4 m": dict(w=2400.0, d=1200.0, h=800.0),
                 "1.5 × 3.0 m": dict(w=3000.0, d=1500.0, h=800.0),
                 "0.9 × 1.8 m": dict(w=1800.0, d=900.0, h=800.0)}
LASER_SIZES = {"HeNe (500 mm)": dict(l=500.0),
               "Diode (150 mm)": dict(l=150.0)}
OPTICS_SIZES = {"5 optics": dict(units=5), "3 optics": dict(units=3),
                "8 optics": dict(units=8)}
SCOPE_SIZES = {"Bench": dict(w=380.0, d=150.0, h=200.0)}
PSU_SIZES = {"Dual channel": dict(w=260.0, d=300.0, h=150.0)}
SIGGEN_SIZES = {"Bench": dict(w=260.0, d=300.0, h=110.0)}
RACK_SIZES = {"24 U": dict(w=600.0, d=800.0, h=1250.0),
              "42 U": dict(w=600.0, d=800.0, h=2000.0)}
UHV_SIZES = {"Ø400 on a 1 m frame": dict(d=400.0, h=1000.0),
             "Ø600 on a 1 m frame": dict(d=600.0, h=1000.0)}
DEWAR_SIZES = {"35 L": dict(d=420.0, h=900.0),
               "100 L": dict(d=520.0, h=1250.0)}
E_BENCH_SIZES = {"1.8 m": dict(w=1800.0, d=800.0, h=900.0)}
BOARD_SIZES = {"1.8 × 1.2 m": dict(w=1800.0, h=1200.0),
               "2.4 × 1.2 m": dict(w=2400.0, h=1200.0)}
BENCH_DESK_SIZES = {"4 seats": dict(seats=4, w=1400.0, d=800.0),
                    "6 seats": dict(seats=6, w=1400.0, d=800.0),
                    "8 seats": dict(seats=8, w=1400.0, d=800.0),
                    "2 seats": dict(seats=2, w=1400.0, d=800.0)}
CUBICLE_SIZES = {"1.8 × 1.8 m": dict(w=1800.0, d=1800.0)}
MEETING_SIZES = {"8 seats": dict(seats=8, w=3000.0, d=1200.0),
                 "6 seats": dict(seats=6, w=2400.0, d=1100.0),
                 "12 seats": dict(seats=12, w=4500.0, d=1400.0),
                 "4 seats": dict(seats=4, w=1600.0, d=1000.0)}
PRINTER_SIZES = {"Multifunction": dict(w=600.0, d=650.0, h=1150.0)}
SERVER_SIZES = {"42 U": dict(w=600.0, d=1000.0, h=2000.0)}
LOCKER_SIZES = {"4 columns": dict(units=4, w=380.0, d=500.0, h=1800.0),
                "6 columns": dict(units=6, w=380.0, d=500.0, h=1800.0)}
COFFEE_SIZES = {"Bean to cup": dict()}
VENDING_SIZES = {"Snacks": dict(w=900.0, d=800.0, h=1830.0)}
BOOTH_SIZES = {"Single": dict(w=1100.0, d=1100.0, h=2250.0)}
PARTITION_SIZES = {"1.6 m": dict(w=1600.0, h=1700.0),
                   "1.2 m": dict(w=1200.0, h=1500.0)}

_WHD = [("w", "Width"), ("d", "Depth"), ("h", "Height")]


def _entry(label, build, sizes, fields, colors=None, **extra):
    entry = dict(label=label, category=CATEGORY, sizes=sizes, build=build,
                 fields=fields, **extra)
    if colors:
        entry["colors"] = list(colors)
    return entry


PARTS = {
    # chemistry lab
    "lab_bench": _entry("Lab island bench (reagent shelf)", build_lab_bench,
                        BENCH_SIZES, _WHD, LAB_FRONTS),
    "lab_sink_bench": _entry("Lab sink bench", build_lab_sink_bench,
                             SINK_BENCH_SIZES, _WHD, LAB_FRONTS),
    "lab_fume_hood": _entry("Fume hood", build_fume_hood, HOOD_SIZES, _WHD,
                            LAB_FRONTS),
    "lab_safety_shower": _entry("Safety shower & eyewash",
                                build_safety_shower, SHOWER_SIZES,
                                [("h", "Height")]),
    "lab_safety_cabinet": _entry("Chemical safety cabinet",
                                 build_safety_cabinet, CABINET_SIZES, _WHD,
                                 CABINET_KINDS),
    "lab_fridge": _entry("Lab fridge", build_lab_fridge, LAB_FRIDGE_SIZES,
                         _WHD),
    "lab_drying_oven": _entry("Drying oven", build_drying_oven, OVEN_SIZES,
                              _WHD, on_top=True),
    "lab_centrifuge": _entry("Centrifuge", build_centrifuge,
                             CENTRIFUGE_SIZES, _WHD, on_top=True),
    "lab_rotavap": _entry("Rotary evaporator", build_rotavap, ROTAVAP_SIZES,
                          [("w", "Width")], on_top=True),
    "lab_glassware": _entry("Glassware tray", build_glassware_set,
                            GLASSWARE_SIZES, [("w", "Width"), ("d", "Depth")],
                            on_top=True),
    "lab_stool": _entry("Lab stool", build_lab_stool, STOOL_SIZES,
                        [("seat", "Seat height")]),
    "lab_fire_extinguisher": _entry("Fire extinguisher (on the wall)",
                                    build_fire_extinguisher,
                                    EXTINGUISHER_SIZES, [], rest_z=400.0),
    "lab_first_aid": _entry("First aid box (on the wall)", build_first_aid,
                            FIRST_AID_SIZES, [], rest_z=1400.0),
    # physics lab
    "lab_optical_table": _entry("Optical table", build_optical_table,
                                OPTICAL_SIZES, _WHD),
    "lab_laser": _entry("Laser", build_laser, LASER_SIZES,
                        [("l", "Length")], on_top=True),
    "lab_optics": _entry("Optics on posts", build_optics_set, OPTICS_SIZES,
                         [("units", "Optics")], on_top=True),
    "lab_oscilloscope": _entry("Oscilloscope", build_oscilloscope,
                               SCOPE_SIZES, _WHD, on_top=True),
    "lab_power_supply": _entry("Bench power supply", build_power_supply,
                               PSU_SIZES, _WHD, on_top=True),
    "lab_signal_generator": _entry("Signal generator",
                                   build_signal_generator, SIGGEN_SIZES,
                                   _WHD, on_top=True),
    "lab_instrument_rack": _entry("Instrument rack (19 inch)",
                                  build_instrument_rack, RACK_SIZES, _WHD),
    "lab_uhv_chamber": _entry("UHV chamber on frame", build_uhv_chamber,
                              UHV_SIZES, [("d", "Sphere diameter"),
                                          ("h", "Frame height")]),
    "lab_dewar": _entry("Liquid nitrogen dewar", build_dewar, DEWAR_SIZES,
                        [("d", "Diameter"), ("h", "Height")]),
    "lab_electronics_bench": _entry("Electronics bench (with instruments)",
                                    build_electronics_bench, E_BENCH_SIZES,
                                    _WHD),
    "lab_whiteboard": _entry("Whiteboard (on the wall)", build_whiteboard,
                             BOARD_SIZES, [("w", "Width"), ("h", "Height")],
                             rest_z=900.0),
    # company
    "office_bench_desks": _entry("Bench desks (with monitors & chairs)",
                                 build_bench_desks, BENCH_DESK_SIZES,
                                 [("seats", "Seats"), ("w", "Width a seat"),
                                  ("d", "Depth")], DESK_TOPS),
    "office_cubicle": _entry("Cubicle workstation", build_cubicle,
                             CUBICLE_SIZES, [("w", "Width"), ("d", "Depth")],
                             BOOTH_COLORS),
    "office_meeting_table": _entry("Meeting table (with chairs)",
                                   build_meeting_table, MEETING_SIZES,
                                   [("seats", "Seats"), ("w", "Length"),
                                    ("d", "Width")], DESK_TOPS),
    "office_task_chair": _entry("Task chair (light)", build_task_chair,
                                {"Standard": dict()}, []),
    "office_printer": _entry("Office printer", build_printer, PRINTER_SIZES,
                             _WHD),
    "office_server_rack": _entry("Server rack", build_server_rack,
                                 SERVER_SIZES, _WHD),
    "office_lockers": _entry("Lockers", build_lockers, LOCKER_SIZES,
                             [("units", "Columns"), ("w", "Column width"),
                              ("d", "Depth"), ("h", "Height")], LAB_FRONTS),
    "office_coffee_machine": _entry("Coffee machine", build_coffee_machine,
                                    COFFEE_SIZES, [], on_top=True),
    "office_vending_machine": _entry("Vending machine",
                                     build_vending_machine, VENDING_SIZES,
                                     _WHD),
    "office_phone_booth": _entry("Phone booth", build_phone_booth,
                                 BOOTH_SIZES, _WHD, BOOTH_COLORS),
    "office_partition": _entry("Acoustic partition", build_partition,
                               PARTITION_SIZES,
                               [("w", "Width"), ("h", "Height")],
                               BOOTH_COLORS),
}
