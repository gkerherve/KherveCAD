"""The Arab courtyard house (Qt-free): a `build_house` spec — the dar /
riad of the Arab world, in the House Builder.

What makes it that house, and what the House Builder gained for it:

- rooms turned INWARD round an open **courtyard** (a "paving" room with a
  fountain, planters and benches) — nearly blank walls to the street,
  every principal room opening onto the court;
- on the first floor a **gallery** round the court behind a balustrade
  (the courtyard is a "void" over it), so upstairs rooms open onto the
  gallery, and the gallery onto the sky;
- **round-headed windows and doors** (the `arch window` / `arch door`
  opening kinds: the wall filled round the head, an arched frame, a stone
  ring, a studded walnut door);
- a **flat terrace roof** with a crenellated **parapet** (`Roof.parapet`,
  `Roof.crenellated`) over the indoor rooms only, the court staying open;
- sand / ochre / terracotta / lime-washed **render**, walnut or turquoise
  joinery, a **majlis** (a room of cushioned seating along the walls) and
  a **diwan** (the reception room off the court).

The City Builder's "Arabic house" is the outside of such a house for a
street scene; this is the one you can walk into, edit room by room in the
House Builder, and furnish.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from .house_designs import OUTER, _at, _bedroom, _floor, _room, _wall

#: outside finish -> joinery colour (the Library part's colour combo)
STYLES = {"Sand render": "Walnut", "Ochre render": "Turquoise",
          "Lime-washed white": "Turquoise", "Terracotta render": "Walnut"}
DEFAULT_STYLE = "Sand render"

#: plan bands, mm: three columns and three rows round the courtyard
XS = (0.0, 4200.0, 9400.0, 13600.0)
YS = (0.0, 3800.0, 9200.0, 14000.0)
GALLERY = 1400.0                    # the first-floor gallery's width


def _arch_door(side, offset, width=1100.0, height=2500.0):
    return {"kind": "arch door", "side": side, "offset": offset,
            "width": width, "sill": 0.0, "height": height}


def _arch_win(side, length, width=1000.0, offset=None, sill=950.0,
              height=1600.0):
    if offset is None:
        offset = (length - width) / 2.0
    return {"kind": "arch window", "side": side, "offset": offset,
            "width": width, "sill": sill, "height": height}


def _centred(length, width=1300.0):
    return (length - width) / 2.0


def _majlis(w, d):
    """Seating all round the walls: sofas, a low table on a rug."""
    return [_wall("home_sofa", "N", w / 2.0, size="4-seater"),
            _wall("home_sofa", "W", d / 2.0, size="4-seater"),
            _wall("home_sofa", "E", d / 2.0, size="4-seater"),
            _at("home_rug", w / 2.0, d / 2.0, size="3000"),
            _at("home_coffee_table", w / 2.0, d / 2.0, size="Square"),
            _wall("home_floor_lamp", "S", 400.0)]


def courtyard_house(style=DEFAULT_STYLE, furnished=True) -> dict:
    """A two-storey courtyard house, 13.6 x 14 m: a majlis, entrance
    hall and dining room along the front, a family room and kitchen
    either side of the court, the diwan, a guest bedroom and the stair
    behind; upstairs four bedrooms and a sitting room round a gallery."""
    style = style if style in STYLES else DEFAULT_STYLE
    x0, x1, x2, x3 = XS
    y0, y1, y2, y3 = YS
    wA, wB, wC = x1 - x0, x2 - x1, x3 - x2
    dS, dM, dN = y1 - y0, y2 - y1, y3 - y2
    hall_w = 2400.0                          # the stair hall / landing
    ground = [
        _room("Majlis", x0, y0, wA, dS,
              [_arch_win("S", wA), _arch_win("W", dS),
               _arch_door("E", 1300.0, 1000.0)], _majlis(wA, dS)),
        _room("Entrance hall", x1, y0, wB, dS,
              [_arch_door("S", _centred(wB)),
               _arch_door("N", _centred(wB)),
               _arch_door("E", 1300.0, 1000.0)],
              [_wall("home_console_table", "W", dS / 2.0),
               _wall("home_wall_mirror", "W", dS / 2.0, z=1100.0),
               _at("home_plant", 500.0, 500.0, size="Tall"),
               _at("home_plant", wB - 500.0, 500.0, size="Tall")]),
        _room("Dining room", x2, y0, wC, dS,
              [_arch_win("S", wC), _arch_win("E", dS)],
              [_at("home_dining_table", wC / 2.0, dS / 2.0, 90.0,
                   size="6 seats"),
               _wall("home_sideboard", "N", wC / 2.0, size="Long")]),
        _room("Family room", x0, y1, wA, dM,
              [_arch_win("W", dM, 1000.0, 900.0),
               _arch_win("W", dM, 1000.0, 3500.0),
               _arch_door("E", _centred(dM))],
              [_wall("home_sofa", "W", dM / 2.0, size="3-seater"),
               _wall("home_armchair", "S", 800.0),
               _wall("home_sideboard", "N", wA / 2.0, size="TV unit"),
               _at("room_tv", wA / 2.0, dM - 250.0, on_top=True, size="55"),
               _at("home_rug", wA / 2.0, dM / 2.0, size="2000"),
               _at("home_coffee_table", wA / 2.0, dM / 2.0)]),
        _room("Courtyard", x1, y1, wB, dM, [],
              [_at("park_fountain", wB / 2.0, dM / 2.0, size="4 m",
                   dims={"d": 1800.0}),
               _at("home_planter", 900.0, 700.0),
               _at("home_planter", wB - 900.0, 700.0),
               _at("home_planter", 900.0, dM - 700.0),
               _at("home_planter", wB - 900.0, dM - 700.0),
               _at("home_garden_bench", wB / 2.0, 450.0, 180.0,
                   size="1500"),
               _at("home_garden_bench", wB / 2.0, dM - 450.0, 0.0,
                   size="1500")], surface="paving"),
        _room("Kitchen", x2, y1, wC, dM,
              [_arch_door("W", _centred(dM)),
               _arch_win("E", dM, 1000.0, 1200.0)],
              [_wall("home_kitchen", "N", None, size="4 units"),
               _wall("home_fridge", "E", dM - 500.0),
               _at("home_round_table", wC / 2.0, dM * 0.3,
                   size="4 seats")]),
        _room("Stair hall", x0, y2, hall_w, dN,
              [_arch_door("S", 700.0, 900.0), _arch_win("W", dN, 800.0)],
              [_at("home_stairs_straight", hall_w - OUTER / 2.0 - 520.0,
                   2500.0, size="Straight")]),
        _room("Cloakroom", hall_w, y2, wA - hall_w, 2000.0,
              [_arch_door("W", 300.0, 800.0)],
              [_wall("home_toilet", "N", 600.0),
               _wall("home_washbasin", "E", 1400.0, size="600")]),
        _room("Utility room", hall_w, y2 + 2000.0, wA - hall_w, dN - 2000.0,
              [_arch_door("W", 300.0, 800.0)], []),
        _room("Diwan", x1, y2, wB, dN,
              [_arch_door("S", _centred(wB)),
               _arch_win("N", wB, 1000.0, 900.0),
               _arch_win("N", wB, 1000.0, 3300.0)], _majlis(wB, dN)),
        _room("Guest bedroom", x2, y2, wC, dN,
              [_arch_door("W", 1800.0, 1000.0), _arch_win("N", wC),
               _arch_win("E", dN)],
              _bedroom(wC, dN, "Double", bed_wall="N", wardrobe_wall="S")),
    ]
    g0, g1 = x1 + GALLERY, x2 - GALLERY
    h0, h1 = y1 + GALLERY, y2 - GALLERY
    upper = [
        _room("Bedroom 1", x0, y0, wA, dS,
              [_arch_win("S", wA), _arch_win("W", dS),
               _arch_door("E", 1300.0, 1000.0)],
              _bedroom(wA, dS, "King", bed_wall="W", wardrobe_wall="N")),
        _room("Upper hall", x1, y0, wB, dS,
              [_arch_door("N", _centred(wB)),
               _arch_win("S", wB, 1200.0)],
              [_at("home_plant", 500.0, 500.0, size="Tall"),
               _wall("home_bench", "E", dS / 2.0, size="1800")]),
        _room("Bedroom 2", x2, y0, wC, dS,
              [_arch_win("S", wC), _arch_win("E", dS),
               _arch_door("W", 1300.0, 1000.0)],
              _bedroom(wC, dS, "Double", bed_wall="E", wardrobe_wall="N")),
        _room("Bedroom 3", x0, y1, wA, dM,
              [_arch_win("W", dM, 1000.0, 900.0),
               _arch_win("W", dM, 1000.0, 3500.0),
               _arch_door("E", 2100.0, 1000.0)],
              _bedroom(wA, dM, "Double", bed_wall="N", wardrobe_wall="S")),
        _room("Bedroom 4", x2, y1, wC, dM,
              [_arch_win("E", dM, 1000.0, 1200.0),
               _arch_door("W", 2100.0, 1000.0)],
              _bedroom(wC, dM, "Double", bed_wall="E", wardrobe_wall="S")),
        # the gallery: four rectangles of one name round the court
        _room("Gallery", x1, y1, wB, GALLERY),
        _room("Gallery", x1, h1, wB, GALLERY),
        _room("Gallery", x1, h0, GALLERY, h1 - h0),
        _room("Gallery", g1, h0, GALLERY, h1 - h0),
        _room("Gallery void", g0, h0, g1 - g0, h1 - h0, surface="void"),
        # the stairs from the ground floor, as in the two-storey houses
        _room("Landing", x0, y2, 1000.0, dN,
              [_arch_door("S", 100.0, 800.0)]),
        _room("Landing", x0 + 1000.0, y2, hall_w - 1000.0, 700.0),
        _room("Stairwell", x0 + 1000.0, y2 + 700.0, hall_w - 1000.0, 3700.0,
              surface="void"),
        _room("Landing", x0 + 1000.0, y2 + 4400.0, hall_w - 1000.0, 400.0),
        _room("Bathroom", hall_w, y2, wA - hall_w, 2400.0,
              [_arch_door("W", 20.0, 660.0)],
              [_wall("home_toilet", "N", 500.0),
               _wall("home_washbasin", "E", 1400.0, size="600")]),
        _room("Dressing room", hall_w, y2 + 2400.0, wA - hall_w, 2400.0,
              [_arch_door("S", 500.0, 700.0)],
              [_wall("home_wardrobe", "E", 1200.0, size="3 doors"),
               _wall("home_dressing_table", "N", 900.0)]),
        _room("Upper sitting room", x1, y2, wB, dN,
              [_arch_door("S", _centred(wB)),
               _arch_win("N", wB, 1000.0, 900.0),
               _arch_win("N", wB, 1000.0, 3300.0),
               _arch_door("E", 1800.0, 1000.0)], _majlis(wB, dN)),
        _room("Master bedroom", x2, y2, wC, dN,
              [_arch_win("N", wC), _arch_win("E", dN)],
              _bedroom(wC, dN, "King", bed_wall="N", wardrobe_wall="S")),
    ]
    joinery = STYLES[style]
    spec = {"name": "Arab courtyard house",
            "floors": [_floor(ground, "Ground floor"),
                       _floor(upper, "First floor")],
            "walls": {"outside": style, "inside": "Warm white",
                      "joinery": joinery},
            "roof": {"style": "Flat", "color": "Flat terrace",
                     "overhang": 0, "chimney": "none", "parapet": 1000.0,
                     "crenellated": True}}
    if not furnished:                       # the shell keeps its stairs
        for floor in spec["floors"]:
            for room in floor["rooms"]:
                room["furniture"] = [f for f in room["furniture"]
                                     if "stairs" in f["part_id"]]
    return spec
