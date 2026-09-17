"""Finished houses (Qt-free): whole furnished homes as `build_house`
specs — bungalows and two-storey houses with 1, 2 or 3 bedrooms, and a
ten-storey block of flats — in six brick styles, each with the roof and
window colours that suit it.

Every design is a plan a builder would draw: a hall with the front door
on the south side, rooms reached through doors on shared walls, windows
on every outside wall, a stairwell (a "void" room, open to the landing
over a balustrade) above the stairs of the floor below, landings drawn
as several rectangles of the same name so they are one open space. The
block's stairs switch back floor by floor (odd floors climb the other
column) round a lift shaft.

They are Library parts (House & home ▸ Finished houses; the colour combo
is the brick, "Empty" builds the shell without furniture) and House
Builder templates, so a design can be opened in the builder and edited.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

CATEGORY = "Finished houses"

#: brick -> (roof covering, window & door colour)
BRICKS = {
    "Red brick": ("Slate", "White"),
    "Buff brick": ("Brown tiles", "White"),
    "Yellow stock brick": ("Grey tiles", "Sage green"),
    "Brown brick": ("Red clay", "Cream"),
    "Painted brick": ("Dark slate", "Anthracite grey"),
    "Blue engineering brick": ("Black pantiles", "Black"),
}

OUTER = 250.0          # cavity wall
INNER = 100.0          # partition


# ------------------------------------------------------------- helpers
def _room(name, x, y, w, d, openings=(), furniture=(), **kw):
    return dict(name=name, x=x, y=y, w=w, d=d, openings=list(openings),
                furniture=list(furniture), **kw)


def _door(side, offset, width=850.0):
    return {"kind": "door", "side": side, "offset": offset, "width": width}


def _win(side, length, width=1500.0, offset=None, sill=900.0,
         height=1200.0):
    """A window on a side *length* long, centred unless *offset*."""
    if offset is None:
        offset = (length - width) / 2.0
    return {"kind": "window", "side": side, "offset": offset,
            "width": width, "sill": sill, "height": height}


def _small(side, length, offset=None):
    """A bathroom's small, high window."""
    return _win(side, length, 600.0, offset, sill=1300.0, height=800.0)


def _wall(part, wall, along=None, **kw):
    out = {"part_id": part, "wall": wall}
    if along is not None:
        out["along"] = along
    out.update(kw)
    return out


def _at(part, x, y, rz=0.0, **kw):
    return dict(part_id=part, x=x, y=y, rz=rz, **kw)


def _floor(rooms, name=None):
    out = {"wall_thickness": OUTER, "inner_wall_thickness": INNER,
           "rooms": rooms}
    if name:
        out["name"] = name
    return out


def _finish(spec, brick, furnished, style="Gable"):
    roof, joinery = BRICKS.get(brick, BRICKS["Red brick"])
    spec["walls"] = {"outside": brick, "inside": "Warm white",
                     "joinery": joinery}
    spec["roof"] = dict({"style": style, "color": roof, "overhang": 300,
                         "chimney": "auto"}, **spec.get("roof", {}))
    if style == "Flat":
        spec["roof"]["color"] = "Dark slate"
    if not furnished:                       # the shell keeps its stairs
        for floor in spec["floors"]:
            for room in floor["rooms"]:
                room["furniture"] = [f for f in room["furniture"]
                                     if "stairs" in f["part_id"]]
    return spec


# ------------------------------------------------------------ furniture
def _living(w, d, fireplace=True):
    out = [_at("home_sofa", w / 2.0, d * 0.62, 180.0),
           _at("home_coffee_table", w / 2.0, d * 0.42),
           _wall("home_sideboard", "S", w / 2.0, size="TV unit"),
           _at("room_tv", w / 2.0, 0.0, on_top=True, size="55"),
           _at("home_rug", w / 2.0, d * 0.45, size="2000"),
           _wall("home_floor_lamp", "N", 300.0)]
    if fireplace:
        out.append(_wall("home_fireplace", "W", d / 2.0))
    return out


def _tv_on_unit(room_furniture):
    """The TV stands on the unit: give it the unit's position."""
    unit = next(f for f in room_furniture if f["part_id"] == "home_sideboard")
    tv = next(f for f in room_furniture if f["part_id"] == "room_tv")
    tv.pop("x", None)
    tv.pop("y", None)
    tv["wall"], tv["along"] = unit["wall"], unit["along"]
    tv["gap"] = 80.0
    return room_furniture


def _kitchen(w, d, units_wall="N", along=None, table=True):
    out = [_wall("home_kitchen", units_wall, along,
                 size="4 units" if max(w, d) >= 3000 else "3 units"),
           _wall("home_fridge", "E", d - 500.0)]
    if table:
        out += [_at("home_round_table", w / 2.0, d * 0.35, size="4 seats")]
    return out


def _bedroom(w, d, bed="Double", bed_wall="E", wardrobe_wall="W"):
    along = d / 2.0 if bed_wall in ("E", "W") else w / 2.0
    out = [_wall("home_bed", bed_wall, along, size=bed),
           _wall("home_wardrobe", wardrobe_wall,
                 (d if wardrobe_wall in ("E", "W") else w) - 800.0,
                 size="2 doors")]
    if bed != "Single":
        side = 1000.0 if bed == "Double" else 1100.0
        out += [_wall("home_bedside_table", bed_wall, along - side),
                _wall("home_bedside_table", bed_wall, along + side)]
    return out


def _bathroom(w, d, shower=False):
    out = [_wall("home_toilet", "S", 450.0),
           _wall("home_washbasin", "S", 1200.0, size="600")]
    if w >= 1700.0 or d >= 1700.0:
        wall, along = ("N", w / 2.0) if w >= 1800.0 else ("W", d / 2.0)
        out.append(_wall("home_bath", wall, along, size="1700"))
    if shower and w >= 2400.0:
        out.append(_wall("home_shower", "E", d - 600.0, size="900"))
    return out


# ------------------------------------------------------------ bungalows
def bungalow(beds: int, brick="Red brick", furnished=True) -> dict:
    """A one-storey house: living room, hall and kitchen at the front,
    a corridor (part of the hall) and the bedrooms and bathroom behind."""
    beds = max(1, min(3, int(beds)))
    back = [3600.0] + [3000.0] * (beds - 1) + [2400.0]
    W = max(sum(back), 8400.0)
    back[0] += W - sum(back)
    front_d, corr, back_d = 4400.0, 1100.0, 3400.0
    lw = round((W - 1600.0) * 0.55 / 100.0) * 100.0
    kw = W - 1600.0 - lw
    rooms = [
        _room("Living room", 0, 0, lw, front_d,
              [_win("S", lw, 2000.0),
               _win("W", front_d, 1200.0, offset=2400.0)],
              _tv_on_unit(_living(lw, front_d, fireplace=False))
              + [_wall("home_fireplace", "W", 1000.0)]),
        _room("Hall", lw, 0, 1600, front_d,
              [_door("S", 300.0, 1000.0), _door("W", 2000.0),
               _door("E", 2000.0)],
              [_wall("home_coat_stand", "E", 600.0)]),
        _room("Kitchen", lw + 1600, 0, kw, front_d,
              [_win("S", kw, 1200.0), _win("E", front_d, 1000.0)],
              _kitchen(kw, front_d, units_wall="N")),
        _room("Hall", 0, front_d, W, corr, [_win("W", corr, 600.0,
                                                  offset=250.0)]),
    ]
    x = 0.0
    names = ["Main bedroom"] + [f"Bedroom {i + 2}" for i in range(beds - 1)]
    for i, width in enumerate(back[:-1]):
        side_win = [_win("W", back_d, 1200.0)] if i == 0 else []
        bed = "Double" if i < 2 else "Single"
        rooms.append(_room(names[i], x, front_d + corr, width, back_d,
                           [_door("S", 300.0), _win("N", width, 1500.0)]
                           + side_win,
                           _bedroom(width, back_d, bed, bed_wall="E",
                                    wardrobe_wall="W")))
        x += width
    rooms.append(_room("Bathroom", x, front_d + corr, back[-1], back_d,
                       [_door("S", 300.0, 750.0), _small("N", back[-1]),
                        _small("E", back_d)],
                       _bathroom(back[-1], back_d)))
    spec = {"name": f"Bungalow, {beds} bedroom", "floors": [_floor(rooms)]}
    return _finish(spec, brick, furnished, style="Hip" if beds == 3
                   else "Gable")


# ---------------------------------------------------- two-storey houses
def two_storey(beds: int, brick="Red brick", furnished=True) -> dict:
    """A two-storey house round a central hall: the stairs climb along
    its east wall to a landing that wraps the stairwell; a wing to the
    east for the third bedroom."""
    beds = max(1, min(3, int(beds)))
    wl, hall_w, D = 3800.0, 2200.0, 8200.0
    wr = 3200.0 if beds == 3 else 0.0
    hx = wl                                   # hall's west wall
    ex = hx + hall_w                          # hall's east wall
    front_d, back_d = 4400.0, D - 4400.0
    # along the hall's east wall (room-relative), climbing north
    stair = _at("home_stairs_straight", hall_w - OUTER / 2.0 - 520.0,
                2600.0, size="Straight")
    ground = [
        _room("Living room", 0, 0, wl, front_d,
              [_win("S", wl, 1800.0),
               _win("W", front_d, 1200.0, offset=2600.0),
               _door("E", 2800.0)],
              _tv_on_unit(_living(wl, front_d, fireplace=False))
              + [_wall("home_fireplace", "W", 1100.0)]),
        _room("Kitchen", 0, front_d, wl, back_d,
              [_win("N", wl, 1400.0), _win("W", back_d, 1000.0),
               _door("E", 50.0, 700.0)],
              _kitchen(wl, back_d, units_wall="N")),
        _room("Hall", hx, 0, hall_w, 5200,
              [_door("S", 250.0, 1000.0), _door("N", 250.0, 800.0)]
              + ([_door("E", 4480.0, 700.0)] if wr else []),
              [stair, _wall("home_console_table", "W", 1300.0)]),
        _room("Cloakroom", hx, 5200, hall_w, 3000,
              [_small("N", hall_w)],
              [_wall("home_toilet", "N", 600.0),
               _wall("home_washbasin", "E", 2000.0, size="600")]),
    ]
    upper = [
        _room("Main bedroom", 0, 0, wl, front_d,
              [_win("S", wl, 1800.0), _win("W", front_d, 1000.0),
               _door("E", 2800.0, 800.0)],
              _bedroom(wl, front_d, "King", bed_wall="W",
                       wardrobe_wall="N")),
        _room("Bedroom 2" if beds >= 2 else "Study", 0, front_d, wl, back_d,
              [_win("N", wl, 1500.0), _door("E", 50.0, 700.0)],
              _bedroom(wl, back_d, "Double", bed_wall="W",
                       wardrobe_wall="S") if beds >= 2 else
              [_wall("home_desk", "N", wl / 2.0),
               _at("home_office_chair", wl / 2.0, back_d - 1100.0, 180.0),
               _wall("home_bookcase", "W", 1500.0)]),
        _room("Landing", hx, 0, 1000, 5200,
              [_win("S", 1000.0, 700.0), _door("N", 100.0, 750.0)]),
        _room("Landing", hx + 1000, 0, 1200, 700),
        _room("Stairwell", hx + 1000, 700, 1200, 3700, surface="void"),
        _room("Landing", hx + 1000, 4400, 1200, 800,
              [_door("E", 100.0, 650.0)] if wr else []),
        _room("Bathroom", hx, 5200, hall_w, 3000,
              [_small("N", hall_w)], _bathroom(hall_w, 3000.0)),
    ]
    if wr:
        ground += [
            _room("Snug", ex, 0, wr, front_d,
                  [_win("S", wr, 1500.0), _win("E", front_d, 1200.0),
                   _door("N", 1200.0)],
                  [_wall("home_sofa", "N", wr / 2.0, size="2-seater"),
                   _wall("home_bookcase", "E", 3500.0)]),
            _room("Dining room", ex, front_d, wr, back_d,
                  [_win("N", wr, 1500.0), _win("E", back_d, 1000.0)],
                  [_at("home_dining_table", wr / 2.0, back_d / 2.0, 90.0,
                       size="4 seats"),
                   _wall("home_sideboard", "E", 3000.0,
                         size="Sideboard")]),
        ]
        upper += [
            _room("Bedroom 3", ex, front_d, wr, back_d,
                  [_win("N", wr, 1200.0), _door("S", 1200.0, 750.0)],
                  _bedroom(wr, back_d, "Single", bed_wall="E",
                           wardrobe_wall="N")),
            _room("En-suite", ex, 0, wr, front_d,
                  [_small("S", wr), _small("E", front_d)],
                  _bathroom(wr, front_d, shower=True)),
        ]
    spec = {"name": f"Two-storey house, {beds} bedroom",
            "floors": [_floor(ground, "Ground floor"),
                       _floor(upper, "First floor")]}
    return _finish(spec, brick, furnished, style="Gable")


# ----------------------------------------------------- block of flats
def _flat(x0, mirror, W, furnished=True):
    """One two-bedroom flat, 9 × 13 m, beside the core (east of it when
    *mirror*): living/kitchen at the front, bedrooms and bathroom behind
    an L-shaped hall."""
    FW = 9000.0

    def place(name, x, y, w, d, openings=(), furniture=()):
        ops = [dict(o) for o in openings]
        if mirror:
            x = W - x - w
            for o in ops:
                if o["side"] in ("E", "W"):
                    o["side"] = "W" if o["side"] == "E" else "E"
                else:
                    o["offset"] = w - o["offset"] - o["width"]
            fur = []
            for f in furniture:
                f = dict(f)
                if f.get("wall") in ("E", "W"):
                    f["wall"] = "W" if f["wall"] == "E" else "E"
                elif f.get("wall") in ("N", "S") and f.get("along") \
                        is not None:
                    f["along"] = w - f["along"]
                if "x" in f:
                    f["x"] = w - f["x"]
                    f["rz"] = -f.get("rz", 0.0)
                fur.append(f)
            furniture = fur
        return _room(name, x0 + x if not mirror else x, y, w, d, ops,
                     furniture if furnished else [])

    rooms = [
        place("Living room", 0, 0, 6000, 6900,
              [_win("S", 6000, 2400, offset=700.0),
               _win("S", 6000, 1200, offset=4000.0),
               _win("W", 6900, 1500), _door("E", 3500.0)],
              [_wall("home_kitchen", "N", 1600.0, size="4 units"),
               _at("home_sofa", 3000.0, 2800.0, 180.0, size="3-seater"),
               _at("home_coffee_table", 3000.0, 1700.0),
               _at("home_round_table", 4500.0, 4800.0, size="4 seats")]),
        place("Flat hall", 6000, 0, 3000, 6900,
              [_door("E", 1000.0, 950.0)]),
        place("Flat hall", 4000, 6900, 5000, 1300,
              [_door("W", 250.0, 800.0)]),
        place("Main bedroom", 0, 6900, 4000, 6100,
              [_win("N", 4000, 1500), _win("W", 6100, 1200)],
              _bedroom(4000, 6100, "Double", bed_wall="S",
                       wardrobe_wall="E")),
        place("Bathroom", 4000, 8200, 2200, 4800,
              [_door("S", 300.0, 750.0), _small("N", 2200)],
              _bathroom(2200, 4800)),
        place("Bedroom 2", 6200, 8200, 2800, 4800,
              [_door("S", 300.0, 800.0), _win("N", 2800, 1200)],
              _bedroom(2800, 4800, "Single", bed_wall="E",
                       wardrobe_wall="N")),
    ]
    return rooms


def apartment_block(floors: int = 10, brick="Red brick",
                    furnished=True) -> dict:
    """A block of *floors* storeys, two flats a floor round a central
    core: an entrance hall / landing, a lift shaft and switchback
    stairs (each floor's stairwell over the flight below)."""
    floors = max(2, min(20, int(floors)))
    W, D = 22000.0, 13000.0
    cx = 9000.0                                 # core from 9 m to 13 m
    col_a, col_b = (cx, 1300.0), (cx + 1300.0, 1300.0)
    out = []
    for k in range(floors):
        hall = "Entrance hall" if k == 0 else "Landing"
        core = [
            _room(hall, cx, 0, 4000, 6900,
                  [_door("S", 1300.0, 1400.0)] if k == 0 else
                  [_win("S", 4000, 1800)]),
            _room(hall, cx + 2600, 8900, 1400, 2000),
            _room(hall, cx, 10900, 4000, 2100, [_win("N", 4000, 1200)]),
            _room("Lift", cx + 2600, 6900, 1400, 2000,
                  [_door("S", 250.0, 900.0)], surface="void"),
        ]
        climbs = [] if k == floors - 1 else [
            _at("home_stairs_straight", 650.0, 2000.0,
                0.0 if k % 2 == 0 else 180.0, size="Straight")]
        for i, (x, w) in enumerate((col_a, col_b)):
            up = (k % 2 == 0) == (i == 0)       # this column climbs from k
            below = k > 0 and ((k - 1) % 2 == 0) == (i == 0)
            core.append(_room(
                "Stairwell" if below else hall, x, 6900, w, 4000,
                furniture=climbs if up and furnished is not None else [],
                surface="void" if below else "indoor"))
        flats = _flat(0.0, False, W, furnished) + \
            _flat(0.0, True, W, furnished)
        out.append(_floor(core + flats, "Ground floor" if k == 0
                          else f"Floor {k}"))
    spec = {"name": f"Block of flats, {floors} storeys", "floors": out,
            "roof": {"overhang": 0}}
    return _finish(spec, brick, furnished, style="Flat")


# ------------------------------------------------------------- catalogue
#: part id -> (label, builder(brick, furnished) -> spec)
DESIGNS = {
    "house_bungalow_1": ("Bungalow — 1 bedroom",
                         lambda b, f: bungalow(1, b, f)),
    "house_bungalow_2": ("Bungalow — 2 bedrooms",
                         lambda b, f: bungalow(2, b, f)),
    "house_bungalow_3": ("Bungalow — 3 bedrooms",
                         lambda b, f: bungalow(3, b, f)),
    "house_two_storey_1": ("Two-storey house — 1 bedroom",
                           lambda b, f: two_storey(1, b, f)),
    "house_two_storey_2": ("Two-storey house — 2 bedrooms",
                           lambda b, f: two_storey(2, b, f)),
    "house_two_storey_3": ("Two-storey house — 3 bedrooms",
                           lambda b, f: two_storey(3, b, f)),
    "house_flats_10": ("Block of flats — 10 storeys",
                       lambda b, f: apartment_block(10, b, f)),
}


def build_design(part_id, dims):
    """A design as ONE node: every floor stacked at its level."""
    from . import house
    from .model import CadNode
    label, make = DESIGNS[part_id]
    brick = (dims or {}).get("_color") or "Red brick"
    furnished = bool((dims or {}).get("furnished", 1))
    home = house.house_from_spec(make(brick, furnished))
    group = CadNode("union", label.replace(" — ", ", "), {})
    for floor in house.build_house_floors(home):
        group.add(floor)
    return group


def insert_design(part_id, model, dims):
    """Library insert: the design built by the House Builder itself —
    one Object per floor — beside any house already in the document,
    and made the one the House Builder edits."""
    from . import house
    _label, make = DESIGNS[part_id]
    brick = (dims or {}).get("_color") or "Red brick"
    furnished = bool((dims or {}).get("furnished", 1))
    home = house.house_from_spec(make(brick, furnished))
    short = _label.replace(" — ", ", ")
    for floor in home.floors:              # "Bungalow, 2 bedrooms · ..."
        floor.name = f"{short} · {floor.name}"
    return house.apply(model, home, replace=False)


def _sizes(part_id):
    furnished, empty = {"furnished": 1}, {"furnished": 0}
    if part_id == "house_flats_10":           # the one-click default: shell
        return {"Furnished": furnished, "Empty (shell)": empty}
    return {"Empty (shell)": empty, "Furnished": furnished}


PARTS = {
    pid: dict(label=label, category=CATEGORY, sizes=_sizes(pid), fields=[],
              colors=list(BRICKS),
              build=lambda dims, pid=pid: build_design(pid, dims),
              insert=lambda model, dims, pid=pid:
              insert_design(pid, model, dims))
    for pid, (label, _make) in DESIGNS.items()
}


def templates():
    """The designs as House Builder templates (red brick, furnished)."""
    return {label: (lambda make=make: make("Red brick", True))
            for label, make in DESIGNS.values()}
