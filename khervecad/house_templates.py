"""Whole-building templates for the House Builder (Qt-free): a
chemistry lab, a physics lab and a company office, each a `build_house`
spec — rooms sharing walls, doors between them, windows, and every
room furnished from the Part Library (`library_lab` for the labs and
offices, `library_home*` for the rest). Loaded from the builder's
Template menu (then edited like any house) or with build_house
``template``; a spec's own ``floors`` win over the template's.

Furniture is written room-relative: ``wall`` + ``along`` for pieces
against a wall, x / y from the room's SW corner for islands, and the
instruments, glassware and coffee machines ``on_top`` so they land on
the bench under them.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import copy


def _door(side, offset, width=None):
    out = {"kind": "door", "side": side, "offset": offset}
    if width:
        out["width"] = width
    return out


def _window(side, offset, width=1800.0):
    return {"kind": "window", "side": side, "offset": offset,
            "width": width}


def _wall(part, wall, along=None, **kw):
    out = {"part_id": part, "wall": wall}
    if along is not None:
        out["along"] = along
    out.update(kw)
    return out


def _at(part, x, y, rz=0.0, **kw):
    return dict(part_id=part, x=x, y=y, rz=rz, **kw)


def _top(part, x, y, rz=0.0, **kw):
    return _at(part, x, y, rz, on_top=True, **kw)


# ------------------------------------------------------------ chemistry
def chemistry_lab() -> dict:
    bench_y = (3400.0, 6600.0)
    lab_furniture = []
    for y in bench_y:
        lab_furniture.append(_at("lab_bench", 6500, y))
        for x in (5500.0, 6500.0, 7500.0):
            for side in (-1, 1):
                lab_furniture.append(_at("lab_stool", x, y + side * 1050))
    lab_furniture += [
        _top("lab_glassware", 5600, 3100), _top("lab_glassware", 7300, 6900),
        _top("lab_rotavap", 7400, 3050), _top("chem_balance", 5200, 6900),
        _top("chem_hotplate", 5900, 6250), _top("lab_centrifuge", 7700, 6250,
                                                180.0),
        _top("chem_stand", 6000, 3700, 180.0),
    ]
    for along in (2500.0, 5000.0, 7500.0, 10000.0):
        lab_furniture.append(_wall("lab_fume_hood", "N", along))
    lab_furniture += [
        _wall("lab_sink_bench", "E", 5000.0),
        _wall("lab_safety_shower", "W", 1200.0),
        _wall("lab_whiteboard", "W", 7000.0, size="2.4 × 1.2 m"),
        _wall("lab_fire_extinguisher", "S", 13000.0),
        _wall("lab_first_aid", "E", 8500.0),
        _top("lab_drying_oven", 13550, 4300, -90.0),
        _wall("lab_fridge", "S", 12600.0, size="Under-bench"),
    ]
    return {
        "name": "Chemistry lab",
        "floors": [{"name": "Ground floor", "wall_height": 3000.0,
                    "rooms": [
            {"name": "Entrance", "x": 0, "y": 0, "w": 4000, "d": 4000,
             "finish": "",
             "openings": [_door("S", 1500), _door("E", 1500),
                          _door("N", 1200)],
             "furniture": [_wall("office_lockers", "W", 2000,
                                 size="6 columns"),
                           _wall("lab_first_aid", "E", 3000),
                           _wall("lab_fire_extinguisher", "S", 3200)]},
            {"name": "Chemistry lab", "x": 4000, "y": 0, "w": 14000,
             "d": 10000, "finish": "White tiles",
             "openings": [_window("S", 3000), _window("S", 6500),
                          _window("S", 10000), _window("E", 1500, 1500),
                          _door("W", 8000)],
             "furniture": lab_furniture},
            {"name": "Chemical store", "x": 0, "y": 4000, "w": 4000,
             "d": 3000,
             "furniture": [_wall("lab_safety_cabinet", "W", 1500,
                                 color="Flammables (yellow)"),
                           _wall("lab_safety_cabinet", "N", 1000,
                                 color="Acids (blue)"),
                           _wall("lab_fridge", "N", 2700),
                           _wall("office_lockers", "E", 1500, size="4 columns"),
                           _wall("chem_gas_cylinder", "S", 3300)]},
            {"name": "Lab office", "x": 0, "y": 7000, "w": 4000, "d": 3000,
             "openings": [_window("W", 800, 1400)],
             "furniture": [_wall("home_desk", "N", 1500),
                           _at("office_task_chair", 1500, 1900, 180.0),
                           _wall("home_bookcase", "S", 1200),
                           _top("home_laptop", 1500, 2550)]},
        ]}]}


# -------------------------------------------------------------- physics
def physics_lab() -> dict:
    laser = [
        _at("lab_optical_table", 5000, 3000),
        _top("lab_laser", 4100, 2700), _top("lab_optics", 5200, 2700),
        _top("lab_optics", 5000, 3400, 90.0, size="3 optics"),
        _top("lab_oscilloscope", 5700, 3450),
        _wall("lab_electronics_bench", "N", 3000),
        _wall("lab_instrument_rack", "N", 6000, size="42 U"),
        _wall("lab_instrument_rack", "N", 6700, size="42 U"),
        _wall("lab_whiteboard", "E", 4000),
        _wall("lab_fire_extinguisher", "W", 1000),
        _at("lab_stool", 3000, 5900), _at("lab_stool", 5000, 1600),
    ]
    vacuum = [
        _at("lab_uhv_chamber", 2500, 3500),
        _at("lab_uhv_chamber", 5800, 3500, 0.0,
            size="Ø600 on a 1 m frame"),
        _wall("lab_instrument_rack", "N", 1600, size="42 U"),
        _wall("lab_instrument_rack", "N", 2300, size="42 U"),
        _wall("lab_electronics_bench", "N", 5500),
        _wall("lab_dewar", "E", 1200, size="100 L"),
        _wall("chem_gas_cylinder", "E", 2000),
        _wall("chem_gas_cylinder", "E", 2400),
        _wall("lab_safety_cabinet", "S", 6500, size="Under-bench"),
        _wall("lab_first_aid", "W", 6500),
        _at("lab_stool", 4200, 5800),
    ]
    return {
        "name": "Physics lab",
        "floors": [{"name": "Ground floor", "wall_height": 3200.0,
                    "rooms": [
            {"name": "Corridor", "x": 0, "y": 0, "w": 3000, "d": 8000,
             "openings": [_door("S", 1000), _door("E", 2000),
                          _door("N", 1000)],
             "furniture": [_wall("office_lockers", "W", 5000),
                           _wall("lab_fire_extinguisher", "E", 6500),
                           _wall("lab_first_aid", "W", 2200)]},
            {"name": "Laser lab", "x": 3000, "y": 0, "w": 10000, "d": 8000,
             "openings": [_door("E", 1500), _window("S", 5000, 2400)],
             "furniture": laser},
            {"name": "Vacuum lab", "x": 13000, "y": 0, "w": 8000, "d": 8000,
             "openings": [_window("S", 4000, 2400), _window("E", 4000)],
             "furniture": vacuum},
            {"name": "Physics office", "x": 0, "y": 8000, "w": 8000,
             "d": 4000,
             "openings": [_window("N", 2000), _window("N", 6000),
                          _window("W", 2000, 1200)],
             "furniture": [_at("office_bench_desks", 3000, 2000,
                               size="4 seats"),
                           _wall("lab_whiteboard", "E", 2000),
                           _wall("home_bookcase", "S", 6500)]},
        ]}]}


# -------------------------------------------------------------- company
def company_office() -> dict:
    open_plan = [
        _at("office_bench_desks", 3200, 3100, size="6 seats"),
        _at("office_bench_desks", 8700, 3100, size="6 seats"),
        _at("office_bench_desks", 3200, 7300, size="6 seats"),
        _at("office_bench_desks", 8700, 7300, size="6 seats"),
        _wall("office_printer", "E", 5200),
        _wall("office_partition", "E", 6300),
        _at("office_phone_booth", 11000, 9000, 180.0),
        _at("office_phone_booth", 11000, 1000),
        _wall("office_lockers", "W", 8300),
        _at("home_plant", 6000, 5200), _at("home_plant", 600, 5200),
    ]
    return {
        "name": "Company office",
        "floors": [{"name": "Ground floor", "wall_height": 3000.0,
                    "rooms": [
            {"name": "Reception", "x": 0, "y": 0, "w": 6000, "d": 6000,
             "openings": [_door("S", 3000, 1600), _window("S", 1000, 1400),
                          _door("E", 3000), _door("N", 1500)],
             "furniture": [_at("home_reception_desk", 3000, 3800),
                           _at("office_task_chair", 3000, 4700, 180.0),
                           _wall("home_waiting_chairs", "W", 2500),
                           _wall("home_water_cooler", "W", 4500),
                           _at("home_plant", 5400, 600),
                           _at("home_rug", 3000, 1600)]},
            {"name": "Open-plan office", "x": 6000, "y": 0, "w": 12000,
             "d": 10000,
             "openings": [_window("S", 2000, 2400), _window("S", 6000, 2400),
                          _window("S", 10000, 2400),
                          _window("N", 2000, 2400), _window("N", 6000, 2400),
                          _door("E", 2500), _door("E", 7500)],
             "furniture": open_plan},
            {"name": "Meeting room", "x": 18000, "y": 0, "w": 6000,
             "d": 5000,
             "openings": [_window("S", 3000, 2400), _window("E", 2500)],
             "furniture": [_at("office_meeting_table", 3000, 2500,
                               size="8 seats"),
                           _wall("lab_whiteboard", "N", 3000),
                           _wall("room_tv", "W", 2500, z=1100.0)]},
            {"name": "Manager's office", "x": 18000, "y": 5000, "w": 6000,
             "d": 5000,
             "openings": [_window("N", 3000, 2400), _window("E", 2500)],
             "furniture": [_at("home_desk", 3000, 3000, 180.0),
                           _at("office_task_chair", 3000, 3800, 180.0),
                           _top("room_monitor", 3000, 2850, 180.0),
                           _wall("home_bookcase", "N", 1200),
                           _wall("home_armchair", "S", 1200),
                           _wall("home_plant", "S", 5300)]},
            {"name": "Break room", "x": 0, "y": 6000, "w": 6000, "d": 4000,
             "finish": "White tiles",
             "openings": [_window("W", 2000, 1600)],
             "furniture": [_wall("home_kitchen", "N", 2500),
                           _wall("home_fridge", "N", 5300),
                           _wall("office_vending_machine", "E", 1200),
                           _at("home_round_table", 2500, 1700),
                           _at("office_task_chair", 2500, 1000),
                           _at("office_task_chair", 2500, 2400, 180.0),
                           _wall("home_sideboard", "S", 4300),
                           _top("office_coffee_machine", 4300, 250, 180.0)]},
            {"name": "Server room", "x": 0, "y": 10000, "w": 3000,
             "d": 3000,
             "openings": [_door("E", 1500)],
             "furniture": [_wall("office_server_rack", "N", 900),
                           _wall("office_server_rack", "N", 1550),
                           _wall("office_server_rack", "N", 2200),
                           _wall("lab_fire_extinguisher", "W", 700)]},
            {"name": "Toilets", "x": 3000, "y": 10000, "w": 3000, "d": 3000,
             "finish": "White tiles",
             "openings": [_door("S", 2300)],
             "furniture": [_wall("home_toilet", "N", 700),
                           _wall("home_toilet", "N", 1700),
                           _wall("home_washbasin", "E", 1000)]},
            {"name": "Corridor", "x": 6000, "y": 10000, "w": 18000,
             "d": 2000,
             "openings": [_door("S", 3000), _door("W", 1000),
                          _door("E", 1000, 1600)],
             "furniture": [_wall("home_plant", "N", 9000)]},
        ]}]}


TEMPLATES = {"Chemistry lab": chemistry_lab, "Physics lab": physics_lab,
             "Company office": company_office}
# the finished houses (house_designs): bungalows, two-storey houses and
# a block of flats, opened in the builder to edit
from .house_designs import templates as _designs  # noqa: E402

TEMPLATES.update(_designs())


def names():
    return list(TEMPLATES)


def spec(name: str) -> dict:
    """The template *name* (any case) as a fresh build_house spec."""
    for key, build in TEMPLATES.items():
        if key.lower() == str(name).strip().lower():
            return copy.deepcopy(build())
    raise KeyError(f"No template {name!r} — choices: "
                   f"{', '.join(TEMPLATES)}.")


def expand(params: dict) -> dict:
    """build_house arguments with ``template`` filled in: the template's
    floors unless the call brings its own, its other keys as defaults."""
    name = (params or {}).get("template")
    if not name:
        return params
    out = spec(name)
    out.pop("name", None)
    out.update({k: v for k, v in params.items() if k != "template"})
    return out
