"""Room & furniture parts for the parts library.

Tables, a lab workbench, chairs, a stool, a monitor, a TV, a door, a
wall panel and coloured carpet squares for decorating a floor. These
are multi-coloured unions of boxes and cylinders with no booleans, so
every component keeps its own colour in the built-in preview. Parts
are ordinary node subtrees and stay editable after insertion.

Registered into ``library.PARTS`` via ``PARTS`` here; each entry
carries a ``build`` callable dispatched by ``library.build_part``.
Dimensions are in millimetres and any value can be edited first.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from .model import CadNode

CATEGORY = "Room & furniture"

WOOD = "#b8895a"
WOOD_DK = "#8a6540"
METAL = "#9aa0a8"
METAL_DK = "#4a4f56"
SCREEN = "#15181d"
WHITE = "#eceff2"
CARPET = {
    "Red": "#b23b3b", "Blue": "#3b5fb2", "Green": "#3b9a5a",
    "Beige": "#d8c9a3", "Charcoal": "#3a3f45", "Teal": "#2e8b8b",
    "Mustard": "#c8a13a", "Purple": "#6d4b9a",
}


# ----------------------------------------------------------- primitives

def _box(name, w, d, h, x=0.0, y=0.0, z=0.0, color=None):
    node = CadNode("cube", name, dict(x=x, y=y, z=z, width=w, depth=d,
                                      height=h, center=False))
    return _col(node, color, name) if color else node


def _cyl(name, radius, height, z=0.0, x=0.0, y=0.0, r2=None,
         segments=48, color=None):
    node = CadNode("cylinder", name, dict(
        x=x, y=y, z=z, height=height, radius_bottom=radius,
        radius_top=radius if r2 is None else r2,
        segments=segments, center=False))
    return _col(node, color, name) if color else node


def _col(node, color, name=None):
    c = CadNode("color", name or "Colour", dict(color=color, alpha=1.0))
    c.add(node)
    return c


def _legs(part, span_x, span_y, leg, height, color, inset=None):
    """Four vertical legs at the corners of a span_x × span_y frame."""
    inset = leg / 2.0 if inset is None else inset
    ax = span_x / 2.0 - leg - inset
    ay = span_y / 2.0 - leg - inset
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            part.add(_box("Leg", leg, leg, height,
                          x=sx * ax - leg / 2.0, y=sy * ay - leg / 2.0,
                          z=0.0, color=color))


def _dims(dims, sizes):
    entry = sizes.get(dims.get("_size", ""),
                      next(iter(sizes.values())))
    out = dict(entry)
    out.update({k: v for k, v in dims.items()
                if k != "_size" and v is not None})
    return out


# --------------------------------------------------------------- furniture

def build_table(dims):
    p = _dims(dims, TABLE_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    top_t, leg = 30.0, 45.0
    part = CadNode("union", "Table")
    part.add(_box("Top", w, d, top_t, x=-w / 2.0, y=-d / 2.0,
                  z=h - top_t, color=WOOD))
    _legs(part, w, d, leg, h - top_t, WOOD_DK)
    return part


def build_workbench(dims):
    p = _dims(dims, TABLE_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    top_t, leg = 45.0, 55.0
    part = CadNode("union", "Workbench")
    part.add(_box("Worktop", w, d, top_t, x=-w / 2.0, y=-d / 2.0,
                  z=h - top_t, color=WOOD_DK))
    # a lower shelf
    part.add(_box("Shelf", w - 2 * leg, d - 2 * leg, 20.0,
                  x=-(w - 2 * leg) / 2.0, y=-(d - 2 * leg) / 2.0,
                  z=h * 0.28, color=WOOD))
    _legs(part, w, d, leg, h - top_t, METAL_DK)
    return part


def build_chair(dims):
    p = _dims(dims, CHAIR_SIZES)
    w, d, seat_h = p["w"], p["d"], p["seat"]
    back_h = p["back"]
    seat_t, leg = 25.0, 32.0
    part = CadNode("union", "Chair")
    part.add(_box("Seat", w, d, seat_t, x=-w / 2.0, y=-d / 2.0,
                  z=seat_h - seat_t, color=WOOD))
    # backrest at the -Y edge
    part.add(_box("Backrest", w, seat_t, back_h,
                  x=-w / 2.0, y=-d / 2.0, z=seat_h, color=WOOD))
    _legs(part, w, d, leg, seat_h - seat_t, WOOD_DK)
    return part


def build_stool(dims):
    p = _dims(dims, CHAIR_SIZES)
    r, seat_h = p["w"] / 2.0, p["seat"]
    part = CadNode("union", "Stool")
    part.add(_cyl("Seat", r, 26.0, z=seat_h - 26.0, color=WOOD))
    # three splayed legs
    leg = CadNode("for_loop", "Legs", dict(variable="a", start=0.0,
                  end=240.0, step=120.0))
    rot = CadNode("rotate", "Leg angle", dict(x=0.0, y=0.0, z="a"))
    rot.add(_cyl("Leg", 12.0, seat_h - 26.0, x=r * 0.7, segments=20))
    leg.add(rot)
    part.add(_col(leg, METAL_DK, "Legs"))
    return part


# ----------------------------------------------------------- electronics

def build_monitor(dims):
    p = _dims(dims, MONITOR_SIZES)
    w, h = p["w"], p["h"]
    bezel, panel_t = 12.0, 22.0
    stand_h = h * 0.28
    part = CadNode("union", "Monitor")
    # panel raised on the stand
    z0 = stand_h
    part.add(_box("Panel", w, panel_t, h, x=-w / 2.0, y=0.0, z=z0,
                  color=METAL_DK))
    part.add(_box("Screen", w - 2 * bezel, 4.0, h - 2 * bezel,
                  x=-(w - 2 * bezel) / 2.0, y=-4.0,
                  z=z0 + bezel, color=SCREEN))
    # neck + base
    part.add(_box("Neck", 40.0, 30.0, stand_h, x=-20.0, y=panel_t,
                  z=0.0, color=METAL_DK))
    part.add(_cyl("Base", w * 0.28, 12.0, x=0.0, y=panel_t + 15.0,
                  z=0.0, color=METAL))
    return part


def build_tv(dims):
    p = _dims(dims, TV_SIZES)
    w, h = p["w"], p["h"]
    bezel, panel_t = 16.0, 28.0
    part = CadNode("union", "TV")
    z0 = p.get("stand", 60.0)
    part.add(_box("Panel", w, panel_t, h, x=-w / 2.0, y=0.0, z=z0,
                  color=METAL_DK))
    part.add(_box("Screen", w - 2 * bezel, 5.0, h - 2 * bezel,
                  x=-(w - 2 * bezel) / 2.0, y=-5.0, z=z0 + bezel,
                  color=SCREEN))
    # two-foot stand
    for sx in (-1.0, 1.0):
        part.add(_box("Foot", 20.0, panel_t + 60.0, z0,
                      x=sx * (w * 0.35) - 10.0, y=-30.0, z=0.0,
                      color=METAL_DK))
    return part


# -------------------------------------------------------- doors & carpet

def build_door(dims):
    p = _dims(dims, DOOR_SIZES)
    w, h, jamb = p["w"], p["h"], 60.0
    slab_t, frame_t = 40.0, 30.0
    part = CadNode("union", "Door")
    # frame: two jambs + lintel
    part.add(_box("Left jamb", jamb, frame_t, h, x=-w / 2.0 - jamb,
                  y=0.0, z=0.0, color=WHITE))
    part.add(_box("Right jamb", jamb, frame_t, h, x=w / 2.0,
                  y=0.0, z=0.0, color=WHITE))
    part.add(_box("Lintel", w + 2 * jamb, frame_t, jamb,
                  x=-w / 2.0 - jamb, y=0.0, z=h, color=WHITE))
    # slab
    part.add(_box("Slab", w, slab_t, h, x=-w / 2.0, y=-5.0, z=0.0,
                  color=WOOD))
    # handle
    part.add(_cyl("Handle", 14.0, 30.0, x=w / 2.0 - 60.0,
                  y=-5.0 - 30.0, z=h * 0.45, segments=24,
                  color=METAL))
    return part


def build_wall(dims):
    p = _dims(dims, WALL_SIZES)
    part = CadNode("union", "Wall")
    part.add(_box("Wall panel", p["w"], p["t"], p["h"],
                  x=-p["w"] / 2.0, y=-p["t"] / 2.0, z=0.0, color=WHITE))
    return part


def build_carpet(dims):
    p = _dims(dims, CARPET_SIZES)
    side, t = p["side"], p.get("t", 12.0)
    color = CARPET.get(dims.get("_size", "Red"), "#b23b3b")
    return _box("Carpet", side, side, t, x=-side / 2.0, y=-side / 2.0,
                z=0.0, color=color)


# --------------------------------------------------------------- registry

TABLE_SIZES = {
    "Desk (1200×600)": dict(w=1200.0, d=600.0, h=740.0),
    "Dining (1600×900)": dict(w=1600.0, d=900.0, h=750.0),
    "Small (800×800)": dict(w=800.0, d=800.0, h=740.0),
}
CHAIR_SIZES = {
    "Standard": dict(w=440.0, d=440.0, seat=460.0, back=420.0),
    "Bar height": dict(w=400.0, d=400.0, seat=650.0, back=300.0),
}
MONITOR_SIZES = {
    "24 inch": dict(w=540.0, h=320.0),
    "27 inch": dict(w=610.0, h=360.0),
    "32 inch": dict(w=710.0, h=420.0),
}
TV_SIZES = {
    "43 inch": dict(w=960.0, h=560.0, stand=60.0),
    "55 inch": dict(w=1230.0, h=710.0, stand=70.0),
    "65 inch": dict(w=1450.0, h=830.0, stand=80.0),
}
DOOR_SIZES = {
    "Standard (900×2000)": dict(w=900.0, h=2000.0),
    "Wide (1000×2100)": dict(w=1000.0, h=2100.0),
}
WALL_SIZES = {
    "3 m panel": dict(w=3000.0, h=2400.0, t=120.0),
    "5 m panel": dict(w=5000.0, h=2700.0, t=150.0),
}
CARPET_SIZES = {name: dict(side=1000.0, t=12.0, color=hexcol)
                for name, hexcol in CARPET.items()}

PARTS = {
    "room_table": dict(label="Table", category=CATEGORY,
                       sizes=TABLE_SIZES, build=build_table,
                       fields=[("w", "Width"), ("d", "Depth"),
                               ("h", "Height")]),
    "room_workbench": dict(label="Workbench (lab)", category=CATEGORY,
                           sizes=TABLE_SIZES, build=build_workbench,
                           fields=[("w", "Width"), ("d", "Depth"),
                                   ("h", "Height")]),
    "room_chair": dict(label="Chair", category=CATEGORY,
                       sizes=CHAIR_SIZES, build=build_chair,
                       fields=[("w", "Width"), ("d", "Depth"),
                               ("seat", "Seat height"),
                               ("back", "Back height")]),
    "room_stool": dict(label="Stool", category=CATEGORY,
                       sizes=CHAIR_SIZES, build=build_stool,
                       fields=[("w", "Diameter"),
                               ("seat", "Seat height")]),
    "room_monitor": dict(label="Monitor", category=CATEGORY,
                         sizes=MONITOR_SIZES, build=build_monitor,
                         fields=[("w", "Width"), ("h", "Height")]),
    "room_tv": dict(label="TV", category=CATEGORY, sizes=TV_SIZES,
                    build=build_tv,
                    fields=[("w", "Width"), ("h", "Height"),
                            ("stand", "Stand height")]),
    "room_door": dict(label="Door (with frame)", category=CATEGORY,
                      sizes=DOOR_SIZES, build=build_door,
                      fields=[("w", "Width"), ("h", "Height")]),
    "room_wall": dict(label="Wall panel", category=CATEGORY,
                      sizes=WALL_SIZES, build=build_wall,
                      fields=[("w", "Length"), ("h", "Height"),
                              ("t", "Thickness")]),
    "room_carpet": dict(label="Carpet square (pick colour)",
                        category=CATEGORY, sizes=CARPET_SIZES,
                        build=build_carpet,
                        fields=[("side", "Side"),
                                ("t", "Thickness")]),
}
