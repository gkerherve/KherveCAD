"""The modern house with pool (Qt-free): a `build_house` spec — a flat-
roofed two-storey house 15 × 11 m in dark render with anthracite
joinery, full-height glazing to the street and a sliding glass wall onto
the terrace, a double garage, the stairs climbing in the hall to a
landing round the stairwell, and outside a terrace, a pool deck with the
pool and loungers, a driveway and gardens planted with the Trees library
(maple, Norway spruce, Scots pine, lime, birch, shrubs).

It is a Finished house in the Library and a House Builder template, so
it can be opened in the builder and edited room by room.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from .house_designs import (OUTER, _at, _bathroom, _bedroom, _door,
                            _floor, _kitchen, _room, _small, _wall, _win)

W, D = 15000.0, 11000.0          # the house
FRONT = 6000.0                   # depth of the front rooms
HALL_X, HALL_W = 5900.0, 3300.0
GARAGE_X = HALL_X + HALL_W


def _tree(species, x, y, h, seed=1):
    return _at(f"tree_{species}", x, y, dims={"h": h, "seed": seed})


def modern_house(furnished=True) -> dict:
    gw = W - GARAGE_X
    stair = _at("home_stairs_straight", HALL_W - OUTER / 2.0 - 520.0,
                2600.0, size="Straight")
    ground = [
        _room("Living room", 0, 0, HALL_X, FRONT,
              [_win("S", HALL_X, 3500.0, offset=2400.0, sill=200.0,
                    height=3000.0),
               _win("W", FRONT, 2000.0, offset=3000.0, height=1700.0),
               _door("E", 3500.0, 900.0)],
              [_at("home_sofa", HALL_X / 2.0, FRONT * 0.62, 180.0),
               _at("home_coffee_table", HALL_X / 2.0, FRONT * 0.42),
               _at("home_rug", HALL_X / 2.0, FRONT * 0.45, size="2000"),
               _wall("home_floor_lamp", "N", 400.0)]),
        _room("Hall", HALL_X, 0, HALL_W, FRONT,
              [_door("S", 600.0, 1200.0), _door("N", 400.0, 900.0),
               _door("E", 4800.0, 900.0)],
              [stair, _wall("home_coat_stand", "W", 900.0)]),
        _room("Garage", GARAGE_X, 0, gw, FRONT,
              [{"kind": "garage door", "side": "S", "offset": 250.0,
                "width": 2450.0},
               {"kind": "garage door", "side": "S", "offset": 3050.0,
                "width": 2450.0}],
              [_at("home_car", gw / 2.0, FRONT / 2.0, 90.0)]),
        _room("Kitchen / dining", 0, FRONT, W, D - FRONT,
              [_win("N", W, 10200.0, offset=800.0, sill=200.0,
                    height=3000.0),
               _win("W", D - FRONT, 1500.0)],
              _kitchen(W, D - FRONT, units_wall="E", table=False)
              + [_at("home_dining_table", 4000.0, 2400.0, 0.0,
                     size="6 seats")]),
    ]
    back_d = D - FRONT
    upper = [
        _room("Main bedroom", 0, 0, HALL_X, FRONT,
              [_win("S", HALL_X, 3500.0, offset=2400.0, sill=250.0,
                    height=2800.0),
               _win("W", FRONT, 2000.0, offset=3500.0, sill=750.0,
                    height=1300.0),
               _door("E", 4300.0, 800.0), _door("N", 1500.0, 750.0)],
              _bedroom(HALL_X, FRONT, "King", bed_wall="W",
                       wardrobe_wall="N")),
        _room("Landing", HALL_X, 0, 2100, FRONT,
              [_win("S", 2100.0, 1800.0, offset=150.0, sill=450.0,
                    height=2100.0),
               _door("N", 1000.0, 800.0)]),
        _room("Landing", HALL_X + 2100, 0, 1200, 700),
        _room("Stairwell", HALL_X + 2100, 700, 1200, 3700, surface="void"),
        _room("Landing", HALL_X + 2100, 4400, 1200, 1600,
              [_door("N", 200.0, 800.0), _door("E", 400.0, 800.0)]),
        _room("Bedroom 2", GARAGE_X, 0, gw, FRONT,
              [_win("S", gw, 5000.0, sill=100.0, height=2550.0),
               _win("E", FRONT, 2000.0, offset=4000.0, sill=800.0,
                    height=1300.0)],
              _bedroom(gw, FRONT, "Double", bed_wall="E",
                       wardrobe_wall="N")),
        _room("Bathroom", 0, FRONT, 3500, back_d,
              [_small("N", 3500.0)], _bathroom(3500.0, back_d,
                                              shower=True)),
        _room("Study", 3500, FRONT, 4100, back_d,
              [_win("N", 4100.0, 2700.0, sill=700.0, height=1800.0)],
              [_wall("home_desk", "N", 2050.0),
               _at("home_office_chair", 2050.0, back_d - 1100.0, 180.0),
               _wall("home_bookcase", "W", 2500.0)]),
        _room("Bedroom 3", 7600, FRONT, W - 7600, back_d,
              [_win("N", W - 7600, 3000.0, sill=700.0, height=1800.0)],
              _bedroom(W - 7600, back_d, "Double", bed_wall="E",
                       wardrobe_wall="W")),
    ]
    # outside, on the ground floor: front garden and drive, terrace, pool
    ground += [
        _room("Front garden", 0, -6000, GARAGE_X, 6000, surface="garden",
              furniture=[_tree("maple", 2500, 2800, 6000),
                         _tree("shrub", 7200, 3300, 800, 1),
                         _tree("shrub", 8400, 4500, 1200, 2),
                         _tree("shrub", 7000, 5200, 1200, 3)]),
        _room("Driveway", GARAGE_X, -6000, gw, 6000, surface="paving"),
        _room("Terrace", 0, D, W, 4000, surface="paving",
              furniture=[_at("home_patio_set", 9500, 2000)]),
        _room("Pool deck", 0, D + 4000, 2500, 6000, surface="paving",
              furniture=[_at("kcad_sun_lounger", 800, 3000, 90.0),
                         _at("kcad_sun_lounger", 1800, 3000, 90.0)]),
        _room("Pool deck", 2500, D + 4000, 10000, 600, surface="paving"),
        _room("Pool", 2500, D + 4600, 10000, 4000, surface="void",
              furniture=[_at("kcad_garden_swimming_pool_10x4_m", 5000,
                             2000)]),
        _room("Pool deck", 2500, D + 8600, 10000, 1400, surface="paving"),
        _room("Pool deck", 12500, D + 4000, 2500, 6000, surface="paving"),
        _room("Back garden", 0, D + 10000, W, 8000, surface="garden",
              furniture=[_tree("spruce", 13500, 2000, 8000, 1),
                         _tree("pine", 14000, 6000, 9000, 2),
                         _tree("birch", 1000, 2000, 6000, 1),
                         _tree("lime", 2000, 6000, 6000, 3)]),
    ]
    spec = {"name": "Modern house with pool",
            "floors": [dict(_floor(ground, "Ground floor"),
                            wall_height=3300.0),
                       dict(_floor(upper, "First floor"),
                            wall_height=3000.0)],
            "walls": {"outside": "Grey render", "inside": "Warm white",
                      "joinery": "Anthracite grey"},
            "roof": {"style": "Flat", "color": "Zinc", "overhang": 900.0,
                     "chimney": "none"}}
    if not furnished:                       # the shell keeps its stairs
        for floor in spec["floors"]:
            for room in floor["rooms"]:
                room["furniture"] = [f for f in room["furniture"]
                                     if "stairs" in f["part_id"]]
    return spec
