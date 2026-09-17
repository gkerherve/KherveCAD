"""Vitamins — the bought parts a 3D printer or an electronics project is
designed around (NopSCADlib's name for them): NEMA stepper motors,
aluminium extrusions, linear rails and carriages, GT2 pulleys, ball and
linear bearings, fans, and Raspberry Pi / Arduino boards, at their
published dimensions.

They are for designing AROUND — a bracket's bolt pattern, an
enclosure's port holes — so their placement matters more than hidden
detail: mounting holes, shaft flats, slot openings and connectors are
where the datasheets put them. Built from ordinary nodes (and the
thread / hole / gear features), each part is an editable Object.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from .library_print import (_cube, _cyl, _extrude, _group, _move, _polygon,
                            _vbox)
from .model import CadNode

MOTION = "Motion & motors"
ELECTRONICS = "Electronics boards"

ALU = "#b9bec6"
BLACK = "#2a2c30"
STEEL = "#9aa1a9"
PCB_GREEN = "#1f6b3b"
PCB_BLUE = "#1d5c96"
BRASS = "#c8a24a"
WHITE = "#e9e9e6"


def _paint(node, colour, material="Default"):
    col = CadNode("color", node.name, dict(color=colour, alpha=1.0,
                                           material=material))
    col.add(node)
    return col


def _d(dims, sizes):
    entry = dict(sizes.get(dims.get("_size", ""), next(iter(sizes.values()))))
    entry.update({k: v for k, v in dims.items()
                  if not k.startswith("_") and v is not None})
    return entry


def _hole(kind, diameter, depth, **extra):
    params = dict(kind=kind, diameter=diameter, depth=depth,
                  head_diameter=extra.get("head", diameter * 2),
                  head_depth=extra.get("head_depth", 0.0),
                  countersink_angle=90.0, nut_width=5.5, nut_height=2.4,
                  length=0.0, extra=1.0, segments=24)
    return CadNode("hole", f"Hole Ø{diameter:g}", params)


# ------------------------------------------------------------ steppers

NEMA_SIZES = {
    "NEMA 17 (40 mm)": dict(size=42.3, length=40.0, holes=31.0, screw=3.0,
                            boss=22.0, boss_h=2.0, shaft=5.0, shaft_l=24.0,
                            chamfer=5.0),
    "NEMA 17 (48 mm)": dict(size=42.3, length=48.0, holes=31.0, screw=3.0,
                            boss=22.0, boss_h=2.0, shaft=5.0, shaft_l=24.0,
                            chamfer=5.0),
    "NEMA 23 (56 mm)": dict(size=56.4, length=56.0, holes=47.14, screw=5.0,
                            boss=38.1, boss_h=1.6, shaft=6.35, shaft_l=21.0,
                            chamfer=6.0),
}


def build_nema(dims):
    """A NEMA stepper: the square body with chamfered corners (black
    caps over an aluminium stack), the boss, the shaft with its D flat,
    and the four tapped holes of the face pattern, face up at z = 0."""
    p = _d(dims, NEMA_SIZES)
    s, L, c = p["size"], p["length"], p["chamfer"]
    outline = [(-s / 2 + c, -s / 2), (s / 2 - c, -s / 2), (s / 2, -s / 2 + c),
               (s / 2, s / 2 - c), (s / 2 - c, s / 2), (-s / 2 + c, s / 2),
               (-s / 2, s / 2 - c), (-s / 2, -s / 2 + c)]
    cap = 8.0
    stack = _paint(_move(_extrude("Stator stack", _polygon("Section",
                                                           outline),
                                  L - 2 * cap), z=-L + cap), ALU, "Metal")
    caps = _paint(_group("End caps",
                         _move(_extrude("Front cap", _polygon("Section",
                                                              outline), cap),
                               z=-cap),
                         _move(_extrude("Back cap", _polygon("Section",
                                                             outline), cap),
                               z=-L)), BLACK)
    face = _group("Front cap (tapped)", caps, kind="difference")
    for sx in (-1, 1):
        for sy in (-1, 1):
            face.add(_move(_hole("plain", p["screw"] * 0.85, 4.5),
                           x=sx * p["holes"] / 2, y=sy * p["holes"] / 2))
    boss = _paint(_cyl("Boss", 0, 0, 0, p["boss_h"], p["boss"] / 2), ALU,
                  "Metal")
    r = p["shaft"] / 2
    flat = _group("Shaft", _cyl("Shaft", 0, 0, 0, p["boss_h"] + p["shaft_l"],
                                r),
                  _cube("D flat", r - 0.5, -r - 1, p["boss_h"] + 5, r, 2 * r + 2,
                        p["shaft_l"]),
                  kind="difference")
    return _group("NEMA stepper", stack, face, boss,
                  _paint(flat, STEEL, "Metal"))


# ----------------------------------------------------------- extrusions

EXTRUSION_SIZES = {"2020 × 300": dict(size=20.0, count=1, length=300.0,
                                      slot=6.2, bore=4.2),
                   "2040 × 300": dict(size=20.0, count=2, length=300.0,
                                      slot=6.2, bore=4.2),
                   "3030 × 300": dict(size=30.0, count=1, length=300.0,
                                      slot=8.2, bore=6.8)}


def _extrusion_section(size, slot, bore):
    """One square cell of a T-slot extrusion, centred: the outline with a
    slot opening in the middle of each side, and the centre bore."""
    h = size / 2
    lip = size * 0.09                              # slot lip thickness
    inner = slot * 1.75 / 2                        # the T widening inside
    depth = size * 0.3
    pts = []
    for k in range(4):
        side = [(-h, -h), (-slot / 2, -h), (-slot / 2, -h + lip),
                (-inner, -h + lip), (-inner * 0.45, -h + depth),
                (inner * 0.45, -h + depth), (inner, -h + lip),
                (slot / 2, -h + lip), (slot / 2, -h)]
        a = math.radians(90 * k)
        ca, sa = math.cos(a), math.sin(a)
        pts.extend((x * ca - y * sa, x * sa + y * ca) for x, y in side)
    return pts


def build_extrusion(dims):
    """An aluminium T-slot extrusion (2020, 2040, 3030…) along Z: one
    slotted cell per `count` stacked along X, each with its centre bore."""
    p = _d(dims, EXTRUSION_SIZES)
    size, n = p["size"], max(int(p["count"]), 1)
    cells = []
    for i in range(n):
        section = [(x + i * size, y)
                   for x, y in _extrusion_section(size, p["slot"], p["bore"])]
        cell = _group(f"Cell {i + 1}", _extrude("Profile",
                                                _polygon("Section", section),
                                                p["length"]),
                      _move(_cyl("Bore", 0, 0, -1, p["length"] + 2,
                                 p["bore"] / 2), x=i * size),
                      kind="difference")
        cells.append(cell)
    if n > 1:
        cells.append(_move(_cube("Web", 0, -size * 0.2, 0, size * (n - 1),
                                 size * 0.4, p["length"]), x=0))
    return _paint(_group("Aluminium extrusion", *cells), ALU, "Metal")


# ----------------------------------------------------------------- rails

RAIL_SIZES = {"MGN12H × 200": dict(rail_w=12.0, rail_h=8.0, length=200.0,
                                   pitch=25.0, block_w=27.0, block_l=45.4,
                                   block_h=10.0, holes_x=20.0, holes_y=20.0,
                                   screw=3.0),
              "MGN9H × 150": dict(rail_w=9.0, rail_h=6.5, length=150.0,
                                  pitch=20.0, block_w=20.0, block_l=39.9,
                                  block_h=8.0, holes_x=15.0, holes_y=16.0,
                                  screw=3.0)}


def build_rail(dims):
    """A miniature linear rail (MGN) along X with its counterbored mount
    holes, and a carriage block with its four tapped holes."""
    p = _d(dims, RAIL_SIZES)
    w, h, L = p["rail_w"], p["rail_h"], p["length"]
    rail = _group("Rail", _cube("Rail", 0, -w / 2, 0, L, w, h),
                  kind="difference")
    n = max(int((L - p["pitch"] / 2) // p["pitch"]) + 1, 1)
    for i in range(n):
        rail.add(_move(_hole("counterbore", 3.5, h, head=6.0,
                             head_depth=h * 0.45),
                       x=p["pitch"] / 2 + i * p["pitch"], z=h))
    bw, bl, bh = p["block_w"], p["block_l"], p["block_h"]
    block = _group("Carriage", _cube("Block", L / 2 - bl / 2, -bw / 2,
                                     h * 0.35, bl, bw, bh),
                   _cube("Rail channel", L / 2 - bl / 2 - 1, -w / 2 - 0.2,
                         h * 0.35 - 1, bl + 2, w + 0.4, h * 0.65 + 1),
                   kind="difference")
    for sx in (-1, 1):
        for sy in (-1, 1):
            block.add(_move(_hole("plain", p["screw"] * 0.85, 4.0),
                            x=L / 2 + sx * p["holes_x"] / 2,
                            y=sy * p["holes_y"] / 2, z=h * 0.35 + bh))
    return _group("Linear rail", _paint(rail, STEEL, "Metal"),
                  _paint(block, STEEL, "Metal"))


# --------------------------------------------------------------- pulleys

PULLEY_SIZES = {"GT2 20T, 5 mm bore": dict(teeth=20, bore=5.0, belt=6.0),
                "GT2 16T, 5 mm bore": dict(teeth=16, bore=5.0, belt=6.0),
                "GT2 20T, 8 mm bore": dict(teeth=20, bore=8.0, belt=6.0)}


def build_gt2_pulley(dims):
    """A GT2 timing pulley: the toothed belt section (2 mm pitch, the
    outside diameter teeth × 2 / π − 0.508), flanges either side, a hub
    with the bore."""
    p = _d(dims, PULLEY_SIZES)
    n = max(int(p["teeth"]), 8)
    od = n * 2.0 / math.pi - 0.508
    tooth_r = 0.555                                  # GT2 groove radius
    belt = _group("Toothed section",
                  _cyl("Blank", 0, 0, 0, p["belt"] + 1, od / 2, seg=n * 4),
                  kind="difference")
    for k in range(n):
        a = 2 * math.pi * k / n
        belt.add(_cyl(f"Groove {k + 1}", (od / 2) * math.cos(a),
                      (od / 2) * math.sin(a), -1, p["belt"] + 3, tooth_r,
                      seg=12))
    flange = od / 2 + 1.5
    body = _group("GT2 pulley",
                  _cyl("Hub", 0, 0, 0, 8.0, max(od / 2 - 1, p["bore"] / 2 + 2.5)),
                  _cyl("Lower flange", 0, 0, 8.0, 1.0, flange),
                  _move(belt, z=9.0),
                  _cyl("Upper flange", 0, 0, 9.0 + p["belt"] + 1, 1.0, flange))
    bored = _group("GT2 pulley", body,
                   _cyl("Bore", 0, 0, -1, 20 + p["belt"], p["bore"] / 2),
                   _move(_hole("plain", 3.0, 12.0), x=0, y=0, z=4.0,
                         ry=-90), kind="difference")
    return _paint(bored, ALU, "Metal")


BEARING_SIZES = {"608 (8 × 22 × 7)": dict(bore=8.0, od=22.0, width=7.0),
                 "625 (5 × 16 × 5)": dict(bore=5.0, od=16.0, width=5.0),
                 "6001 (12 × 28 × 8)": dict(bore=12.0, od=28.0, width=8.0),
                 "LM8UU (8 × 15 × 24)": dict(bore=8.0, od=15.0, width=24.0)}


def build_bearing(dims):
    """A ball bearing (or linear bearing): outer and inner steel rings
    and the dark seal between them."""
    p = _d(dims, BEARING_SIZES)
    bore, od, w = p["bore"], p["od"], p["width"]
    wall = (od - bore) / 2

    def ring(name, r_out, r_in, z, h, colour):
        return _paint(_group(name, _cyl("Ring", 0, 0, z, h, r_out),
                             _cyl("Hole", 0, 0, z - 1, h + 2, r_in),
                             kind="difference"), colour, "Metal")
    return _group("Bearing",
                  ring("Outer ring", od / 2, od / 2 - wall * 0.22, 0, w, STEEL),
                  ring("Inner ring", bore / 2 + wall * 0.22, bore / 2, 0, w,
                       STEEL),
                  _paint(_group("Seal", _cyl("Seal", 0, 0, 0.3, w - 0.6,
                                             od / 2 - wall * 0.22),
                                _cyl("Hole", 0, 0, -1, w + 2,
                                     bore / 2 + wall * 0.22),
                                kind="difference"), BLACK))


# ------------------------------------------------------------------ fans

FAN_SIZES = {"40 × 10": dict(size=40.0, depth=10.0, holes=32.0, screw=3.4),
             "60 × 15": dict(size=60.0, depth=15.0, holes=50.0, screw=3.4),
             "80 × 25": dict(size=80.0, depth=25.0, holes=71.5, screw=4.4),
             "120 × 25": dict(size=120.0, depth=25.0, holes=105.0,
                              screw=4.4)}


def build_fan(dims):
    """An axial case fan: the square frame with its round duct and the
    four corner holes, a hub and seven twisted blades."""
    p = _d(dims, FAN_SIZES)
    s, depth = p["size"], p["depth"]
    frame = _group("Frame", _vbox("Frame", -s / 2, -s / 2, 0, s, s, depth,
                                  s * 0.08),
                   _cyl("Duct", 0, 0, -1, depth + 2, s * 0.47, seg=64),
                   kind="difference")
    for sx in (-1, 1):
        for sy in (-1, 1):
            frame.add(_cyl("Hole", sx * p["holes"] / 2, sy * p["holes"] / 2,
                           -1, depth + 2, p["screw"] / 2, seg=16))
    hub_r = s * 0.17
    blade = _polygon("Blade", [(hub_r * 0.8, -s * 0.03), (s * 0.45, -s * 0.09),
                               (s * 0.45, s * 0.05), (hub_r * 0.8, s * 0.03)])
    blades = CadNode("pattern", "Blades", dict(
        kind="polar", count=7, dx=0.0, dy=0.0, dz=0.0, angle=360.0, axis="z",
        count_x=1, count_y=1, count_z=1))
    twisted = CadNode("linear_extrude", "Blade", dict(
        height=depth * 0.7, twist=35.0, scale=1.0, center=False, segments=8))
    twisted.add(blade)
    blades.add(twisted)
    rotor = _group("Rotor", _cyl("Hub", 0, 0, depth * 0.1, depth * 0.8, hub_r),
                   _move(blades, z=depth * 0.15))
    return _group("Fan", _paint(frame, BLACK), _paint(rotor, BLACK))


# ---------------------------------------------------------------- boards

def _board(name, w, d, holes, hole_d, parts, colour):
    pcb = _group("PCB", _vbox("Board", 0, 0, 0, w, d, 1.6, 3.0),
                 kind="difference")
    for x, y in holes:
        pcb.add(_cyl("Mount hole", x, y, -1, 3.6, hole_d / 2, seg=20))
    node = _group(name, _paint(pcb, colour))
    for label, x, y, bw, bd, bh, col, mat in parts:
        node.add(_paint(_cube(label, x, y, 1.6, bw, bd, bh), col, mat))
    return node


BOARD_SIZES = {"Raspberry Pi 4": dict(kind=0), "Arduino Uno": dict(kind=1)}


def build_board(dims):
    """A Raspberry Pi 4 (85 × 56 mm, M2.5 holes on 58 × 49) or an Arduino
    Uno (68.6 × 53.4 mm) with its connectors where they sit."""
    p = _d(dims, BOARD_SIZES)
    if int(p.get("kind", 0)) == 1:
        holes = [(14.0, 2.5), (15.3, 50.7), (66.1, 7.6), (66.1, 35.5)]
        parts = [("USB-B", -6.2, 38.1, 16.3, 12.2, 10.9, STEEL, "Metal"),
                 ("DC jack", -1.8, 3.3, 14.2, 9.0, 11.0, BLACK, "Default"),
                 ("ATmega328P", 30.0, 16.0, 35.0, 9.5, 4.0, BLACK, "Default"),
                 ("Digital header", 18.0, 50.4, 45.0, 2.5, 8.5, BLACK,
                  "Default"),
                 ("Analog header", 27.0, 0.6, 38.0, 2.5, 8.5, BLACK,
                  "Default")]
        return _board("Arduino Uno", 68.6, 53.4, holes, 3.2, parts, PCB_BLUE)
    holes = [(3.5, 3.5), (61.5, 3.5), (3.5, 52.5), (61.5, 52.5)]
    parts = [("Ethernet", 65.0, 38.0, 21.0, 16.0, 13.5, STEEL, "Metal"),
             ("USB 3 (pair)", 69.0, 20.0, 17.5, 13.5, 16.0, STEEL, "Metal"),
             ("USB 2 (pair)", 69.0, 2.5, 17.5, 13.5, 16.0, STEEL, "Metal"),
             ("USB-C power", 3.5 + 7.7 - 4.5, -1.5, 9.0, 7.5, 3.3, STEEL,
              "Metal"),
             ("Micro-HDMI 0", 3.5 + 22.5 - 3.5, -1.5, 7.0, 8.0, 3.0, STEEL,
              "Metal"),
             ("Micro-HDMI 1", 3.5 + 36.0 - 3.5, -1.5, 7.0, 8.0, 3.0, STEEL,
              "Metal"),
             ("SoC", 22.0, 20.0, 15.0, 15.0, 2.4, "#8a8f96", "Metal"),
             ("GPIO header", 7.1, 50.0, 51.0, 5.0, 8.5, BLACK, "Default")]
    return _board("Raspberry Pi 4", 85.0, 56.0, holes, 2.75, parts, PCB_GREEN)


def _spec(label, category, sizes, build, fields):
    return dict(label=label, category=category, sizes=sizes, build=build,
                fields=fields)


PARTS = {
    "vit_nema": _spec("NEMA stepper motor", MOTION, NEMA_SIZES, build_nema,
                      [("size", "Body size"), ("length", "Body length"),
                       ("holes", "Hole spacing"), ("shaft", "Shaft Ø"),
                       ("shaft_l", "Shaft length")]),
    "vit_extrusion": _spec("Aluminium T-slot extrusion", MOTION,
                           EXTRUSION_SIZES, build_extrusion,
                           [("size", "Cell size"), ("count", "Cells"),
                            ("length", "Length"), ("slot", "Slot width")]),
    "vit_rail": _spec("Linear rail + carriage (MGN)", MOTION, RAIL_SIZES,
                      build_rail, [("length", "Rail length"),
                                   ("pitch", "Hole pitch")]),
    "vit_gt2": _spec("GT2 timing pulley", MOTION, PULLEY_SIZES,
                     build_gt2_pulley, [("teeth", "Teeth"), ("bore", "Bore"),
                                        ("belt", "Belt width")]),
    "vit_bearing": _spec("Ball / linear bearing", MOTION, BEARING_SIZES,
                         build_bearing, [("bore", "Bore"),
                                         ("od", "Outside Ø"),
                                         ("width", "Width")]),
    "vit_fan": _spec("Axial fan", ELECTRONICS, FAN_SIZES, build_fan,
                     [("size", "Size"), ("depth", "Depth"),
                      ("holes", "Hole spacing")]),
    "vit_board": _spec("Raspberry Pi / Arduino board", ELECTRONICS,
                       BOARD_SIZES, build_board, []),
}

COUNT_FIELDS = {"count", "teeth"}
