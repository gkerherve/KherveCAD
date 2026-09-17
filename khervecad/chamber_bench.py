"""Benches and support frames for a UHV chamber (Qt-free), used by the
Chamber Designer.

A real system stands on a rectangular frame, not a ring: square-section
legs and rails with levelling feet or castors, an open top so the pumps
and bottom ports hang through, and brackets up to the chamber. Kinds:

- ``frame``   — welded box-section frame on levelling feet
- ``castors`` — the same frame on locking castors
- ``table``   — a breadboard table top with a cut-out and an electronics
  shelf below
- ``rack``    — the frame with a 19-inch electronics rack bay beside it
- ``tripod``  — three splayed legs with braces, for a small chamber
- ``none``

Everything is built in floor coordinates (the floor at z = 0), level
whatever the chamber's own orientation.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from .library import _cyl
from .library_uhv import between
from .library_vacuum import (_cube, _group, _move, _object, _paint, _turn,
                             _union)

KINDS = {"frame": "Frame on levelling feet", "castors": "Frame on castors",
         "table": "Table with breadboard top", "rack": "Frame with 19\" rack",
         "tripod": "Tripod", "none": "No bench"}

FRAME = "#5a6e8c"          # powder-coated steel
FEET = "#1d1f22"
RACK = "#2b2e33"
PANEL = "#c9ccd1"
TUBE = 50.0                # box section


def _box(name, x, y, z, w, d, h):
    return _cube(name, w, d, h, x=x, y=y, z=z)


def _leg_feet(kind, x, y):
    """(foot height, parts) under a leg at (x, y)."""
    if kind == "castors":
        return 110.0, [_box("Castor plate", x - 35, y - 35, 100.0, 70, 70,
                            10.0),
                       _box("Castor fork", x - 22, y - 15, 30.0, 44, 30,
                            70.0),
                       _move(_turn(_cyl("Wheel", 38.0, 32.0, segments=32),
                                   x=90.0), x, y + 16.0, 38.0),
                       _box("Brake pedal", x + 22, y - 8, 60.0, 30, 16, 6.0)]
    return 60.0, [_cyl("Levelling screw", 8.0, 60.0, x=x, y=y, z=10.0,
                       segments=16),
                  _cyl("Foot pad", 40.0, 10.0, x=x, y=y, segments=48),
                  _cyl("Lock nut", 14.0, 10.0, x=x, y=y, z=40.0,
                       segments=6)]


def _frame(kind, top, half_w, half_d, supports, cross_x=None):
    """A rectangular box-section frame whose top rails end at *top*."""
    metal, dark = [], []
    foot_h, _ = _leg_feet(kind, 0.0, 0.0)
    corners = [(sx * (half_w - TUBE / 2), sy * (half_d - TUBE / 2))
               for sx in (-1, 1) for sy in (-1, 1)]
    for x, y in corners:
        metal.append(_box("Leg", x - TUBE / 2, y - TUBE / 2, foot_h, TUBE,
                          TUBE, top - foot_h))
        _h, feet = _leg_feet(kind, x, y)
        dark += feet
    for z in (top - TUBE, foot_h + 150.0):
        for sy in (-1, 1):
            metal.append(_box("Rail X", -half_w, sy * (half_d - TUBE / 2)
                              - TUBE / 2, z, 2 * half_w, TUBE, TUBE))
        for sx in (-1, 1):
            metal.append(_box("Rail Y", sx * (half_w - TUBE / 2) - TUBE / 2,
                              -half_d, z, TUBE, 2 * half_d, TUBE))
    # cross members under the chamber carry the brackets
    cross_x = half_w * 0.45 if cross_x is None else cross_x
    for sx in (-1, 1):
        metal.append(_box("Cross member", sx * cross_x - TUBE / 2,
                          -half_d, top - TUBE, TUBE, 2 * half_d, TUBE))
    metal += supports(top)
    return metal, dark


SEAT = 0.85          # brackets meet the chamber at this fraction of R


def _brackets(seat_z, radius):
    """Four brackets from the frame's cross members up to saddles under
    the chamber at *seat_z*, SEAT of its radius out from the axis."""
    def make(top):
        parts = []
        for k in range(4):
            a = math.radians(45.0 + 90.0 * k)
            r = radius * SEAT
            x, y = r * math.cos(a), r * math.sin(a)
            z_top = max(seat_z, top + 30.0)
            parts += [between("Bracket post", 16.0, (x, y, top),
                              (x, y, z_top - 10.0), segments=24),
                      _box("Bracket pad", x - 30, y - 30, top, 60, 60, 12.0),
                      _cyl("Saddle", 28.0, 10.0, x=x, y=y, z=z_top - 10.0,
                           segments=32)]
        return parts
    return make


def build_bench(kind, chamber_z, bottom, radius, width=0.0, depth=0.0,
                seat_z=None):
    """The bench under a chamber whose centre is at *chamber_z* above the
    floor, its lowest body point at *bottom*, its body *radius* wide,
    resting on saddles at *seat_z* (default: its bottom). Returns a union
    of Objects, or None."""
    seat_z = bottom if seat_z is None else seat_z
    cross_x = radius * SEAT * math.cos(math.radians(45.0))
    if kind not in KINDS or kind == "none":
        return None
    half_w = max(width / 2.0, radius * 1.25 + 120.0, 350.0)
    half_d = max(depth / 2.0, radius * 1.25 + 120.0, 350.0)
    objects = []
    if kind == "tripod":
        legs = []
        for k in range(3):
            a = math.radians(90.0 + 120.0 * k)
            top = (radius * 0.6 * math.cos(a), radius * 0.6 * math.sin(a),
                   chamber_z - radius * 0.75)
            foot = (radius * 1.3 * math.cos(a), radius * 1.3 * math.sin(a),
                    40.0)
            legs += [between("Leg", 18.0, foot, top, segments=24),
                     _cyl("Foot", 45.0, 12.0, x=foot[0], y=foot[1],
                          segments=48),
                     _cyl("Levelling screw", 8.0, 40.0, x=foot[0], y=foot[1],
                          z=12.0, segments=16)]
        pts = []
        for k in range(3):
            a = math.radians(90.0 + 120.0 * k)
            f = 0.55
            pts.append((radius * (1.3 - 0.7 * f) * math.cos(a),
                        radius * (1.3 - 0.7 * f) * math.sin(a),
                        40.0 + (chamber_z - radius * 0.75 - 40.0) * f))
        legs += [between("Brace", 8.0, pts[k], pts[(k + 1) % 3], segments=16)
                 for k in range(3)]
        objects.append(_object("Tripod", _paint(_union("Tripod", *legs),
                                                FRAME, "Metal")))
        return _union("Bench", *objects)
    top = max(bottom - 40.0, 300.0)
    if kind == "table":
        metal, dark = _frame("frame", top - 30.0, half_w, half_d,
                             lambda _t: [])
        plate = _group("difference", "Breadboard",
                       _box("Breadboard top", -half_w - 20, -half_d - 20,
                            top - 30.0, 2 * half_w + 40, 2 * half_d + 40,
                            30.0),
                       _cyl("Chamber cut-out", radius * 0.78, 34.0,
                            z=top - 32.0, segments=96))
        holes = [_cyl("Tapped hole", 3.0, 2.0, x=x, y=y, z=top - 1.0,
                      segments=8)
                 for x in range(int(-half_w) + 50, int(half_w) - 25, 100)
                 for y in range(int(-half_d) + 50, int(half_d) - 25, 100)
                 if math.hypot(x, y) > radius * 1.05]
        shelf = _box("Electronics shelf", -half_w + TUBE, -half_d + TUBE,
                     260.0, 2 * half_w - 2 * TUBE, 2 * half_d - 2 * TUBE,
                     12.0)
        objects += [
            _object("Table frame", _paint(_union("Frame", *metal), FRAME,
                                          "Metal")),
            _object("Breadboard", _paint(_union("Top", plate, shelf), PANEL, "Metal")),
            _object("Tapped holes", _paint(_union("Holes", *holes), FEET,
                                           "Plastic")),
            _object("Feet", _paint(_union("Feet", *dark), FEET, "Rubber"))]
        support = _brackets(seat_z, radius)(top)
        objects.append(_object("Chamber supports", _paint(
            _union("Supports", *support), PANEL, "Metal")))
        return _union("Bench", *objects)
    frame_kind = "castors" if kind == "castors" else "frame"
    metal, dark = _frame(frame_kind, top, half_w, half_d,
                         _brackets(seat_z, radius), cross_x)
    objects += [_object("Frame", _paint(_union("Frame", *metal), FRAME,
                                        "Metal")),
                _object("Feet and castors", _paint(_union("Feet", *dark),
                                                   FEET, "Rubber"))]
    if kind == "rack":
        # the rack bay stands behind the bench (-Y), out of the way of
        # the analyser and the source, which take the horizontal ports
        y0 = -half_d - 640.0
        h = max(top + 200.0, 1400.0)
        units, leds = [], []
        for k in range(8):
            z = 250.0 + k * 133.0
            if z + 120 > h - 60:
                break
            units.append(_box("Rack unit", -290, y0 + 620.0, z, 580, 20,
                              120.0))
            leds.append(_box("Unit LED", -250, y0 + 638.0, z + 90.0, 8, 3,
                             8))
        objects += [
            _object("19-inch rack", _paint(_union(
                "Rack", _box("Rack cabinet", -300, y0, 0.0, 600, 620, h),
                _box("Rack plinth", -310, y0 - 10, 0.0, 620, 640, 80.0)),
                RACK, "Plastic")),
            _object("Rack units", _paint(_union("Units", *units), PANEL,
                                         "Metal")),
            _object("Status lights", _paint(_union("LEDs", *leds),
                                            "#43e06a", "Emissive"))]
    return _union("Bench", *objects)
