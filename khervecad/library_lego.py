"""LEGO-compatible bricks for the parts library (the "Lego" category).

Bricks, plates, tiles, 45° slopes and baseplates at the system's real
dimensions — 8 mm stud pitch, 9.6 mm brick, 3.2 mm plate, Ø4.8 x 1.8 mm
studs, 1.5 mm walls and Ø6.51 mm underside tubes, each side 0.1 mm
short of the grid so neighbours never fuse — in the official LEGO
colours. The same numbers as the brick set already drawn by hand in
lego_bricks.kcad, so parts from either fit together.

Everything is boolean-free, so the built-in preview shows a part as it
is: the hollow underside is four walls and a top, the tubes are
revolved rings, a slope is an extruded side profile. A part's origin is
its corner on the stud grid (not its centre, as other library parts
have), so with the sketch grid at 8 mm bricks snap stud to stud.

`brick()` / `slope()` are also what examples_lego.py builds models
from, with `hollow=False` and a stud mask: a brick inside a wall has no
visible underside, and studs another brick covers are never drawn —
that keeps a few hundred bricks light enough for the 3D view.

Registered into ``library.PARTS`` via ``PARTS``; each entry carries a
``build`` callable and a ``colors`` list, the dialog's colour choice.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from .model import CadNode

CATEGORY = "Lego"

PITCH = 8.0            # stud to stud
BRICK_H = 9.6
PLATE_H = 3.2
BASEPLATE_H = 1.6
GAP = 0.1              # clearance on every side of a part
STUD_R = 2.4
STUD_H = 1.8
WALL = 1.5
TOP = 1.0
TUBE_R_OUT = 3.255
TUBE_R_IN = 2.4
PIN_R = 1.5
#: the moulded softness of a real part (``round_=True``): vertical
#: corners rounded to ROUND, the top edge bevelled by BEVEL, the stud
#: tops by STUD_BEVEL. Library parts have it; the brick-built models do
#: not (it would triple the triangles of a few hundred bricks)
ROUND = 0.5
BEVEL = 0.35
STUD_BEVEL = 0.25

#: official LEGO colour names -> hex (BrickLink / Rebrickable values)
COLORS = {
    "Red": "#C91A09", "Blue": "#0055BF", "Yellow": "#F2CD37",
    "Green": "#237841", "Bright green": "#4B9F4A", "Lime": "#BBE90B",
    "Orange": "#FE8A18", "White": "#F4F4F4", "Black": "#1B2A34",
    "Light bluish grey": "#A0A5A9", "Dark bluish grey": "#6C6E68",
    "Tan": "#E4CD9E", "Dark tan": "#958A73",
    "Reddish brown": "#582A12", "Dark brown": "#352100",
    "Dark red": "#720E0F", "Dark orange": "#A95500",
    "Medium azure": "#36AEBF", "Dark turquoise": "#008F9B",
    "Dark blue": "#0A3463", "Medium lavender": "#AC78BA",
    "Dark pink": "#C870A0", "Light nougat": "#F6D7B3",
    "Nougat": "#D09168", "Medium nougat": "#AA7D55",
    "Trans-clear": "#FCFCFC",
    "Trans-light blue": "#AEEFEC", "Trans-red": "#C91A09",
    "Trans-orange": "#F08F1C", "Trans-yellow": "#F5CD2F",
    "Trans-dark blue": "#0020A0", "Trans-green": "#84B68D",
}
#: colours cast in clear plastic: see-through in the preview
TRANSLUCENT = {name for name in COLORS if name.startswith("Trans-")}
#: the strongly tinted ones read washed-out at glass opacity (a flame
#: came out pastel pink over a white ground), so they are denser
VIVID = TRANSLUCENT - {"Trans-clear", "Trans-light blue"}


# ------------------------------------------------------------ geometry

def _cube(name, x, y, z, w, d, h):
    return CadNode("cube", name, dict(x=x, y=y, z=z, width=w, depth=d,
                                      height=h, center=False))


def _stud(x, y, z, seg, round_=False):
    if not round_:
        return CadNode("cylinder", "Stud", dict(
            x=x, y=y, z=z, height=STUD_H, radius_bottom=STUD_R,
            radius_top=STUD_R, segments=seg, center=False))
    stud = CadNode("union", "Stud")
    stud.add(CadNode("cylinder", "Stud side", dict(
        x=x, y=y, z=z, height=STUD_H - STUD_BEVEL, radius_bottom=STUD_R,
        radius_top=STUD_R, segments=seg, center=False)))
    stud.add(CadNode("cylinder", "Stud bevel", dict(
        x=x, y=y, z=z + STUD_H - STUD_BEVEL, height=STUD_BEVEL,
        radius_bottom=STUD_R, radius_top=STUD_R - STUD_BEVEL,
        segments=seg, center=False)))
    return stud


def rounded_rect(x, y, w, d, r, n=4):
    """Outline of a w x d rectangle with its corner at (x, y) and its
    corners rounded to *r*, counter-clockwise, *n* steps per corner."""
    pts = []
    for cx, cy, a0 in ((x + w - r, y + r, -90.0), (x + w - r, y + d - r, 0.0),
                       (x + r, y + d - r, 90.0), (x + r, y + r, 180.0)):
        for s in range(n + 1):
            a = math.radians(a0 + 90.0 * s / n)
            pts.append([cx + r * math.cos(a), cy + r * math.sin(a)])
    return pts


def _prism(name, pts, z, h):
    poly = CadNode("polygon", name, dict(x=0.0, y=0.0, points=pts))
    ext = CadNode("linear_extrude", name, dict(height=h))
    ext.add(poly)
    place = CadNode("translate", name, dict(x=0.0, y=0.0, z=z))
    place.add(ext)
    return place


def _slab(name, x0, y0, z, w, d, h):
    """A block with rounded vertical corners and a bevelled top edge:
    the hull of its rounded footprint and a thin top face set in by
    the bevel — convex, so the hull is exact in the preview too."""
    hull = CadNode("hull", name)
    hull.add(_prism("Sides", rounded_rect(x0, y0, w, d, ROUND), z,
                    h - BEVEL))
    b = BEVEL
    hull.add(_prism("Top face", rounded_rect(x0 + b, y0 + b, w - 2 * b,
                                             d - 2 * b, ROUND - b / 2),
                    z + h - 0.01, 0.01))
    return hull


def _corner(cx, cy, z, h, start):
    """A quarter round post filling one rounded outer corner."""
    quarter = CadNode("circle", "Corner", dict(
        x=cx, y=cy, radius=ROUND, angle=90.0, start_angle=start,
        segments=16))
    ext = CadNode("linear_extrude", "Corner", dict(height=h))
    ext.add(quarter)
    place = CadNode("translate", "Corner", dict(x=0.0, y=0.0, z=z))
    place.add(ext)
    return place


def _tube(x, y, z, h, seg):
    """An underside tube: a revolved ring, hollow without a boolean."""
    wall = CadNode("rect", "Tube wall", dict(
        x=TUBE_R_IN, y=0.0, width=TUBE_R_OUT - TUBE_R_IN, height=h))
    ring = CadNode("rotate_extrude", "Tube", dict(angle=360.0,
                                                   segments=seg))
    ring.add(wall)
    place = CadNode("translate", "Tube", dict(x=x, y=y, z=z))
    place.add(ring)
    return place


def _pin(x, y, z, h, seg):
    """The solid pin under a 1-wide brick."""
    return CadNode("cylinder", "Pin", dict(
        x=x, y=y, z=z, height=h, radius_bottom=PIN_R, radius_top=PIN_R,
        segments=seg, center=False))


def colour(node, name):
    """Wrap *node* in the LEGO colour *name* (or a hex string). Clear
    colours get the Glass material, so the preview sees through them."""
    hexcol = COLORS.get(name) or (name if str(name).startswith("#")
                                  else COLORS["Red"])
    glass = name in TRANSLUCENT
    alpha = 0.75 if name in VIVID else 0.55 if glass else 1.0
    wrap = CadNode("color", str(name), dict(
        color=hexcol, alpha=alpha,
        material="Glass" if glass else "Plastic"))
    wrap.add(node)
    return wrap


def _keep(studs, i, j):
    return studs is True or (studs and (i, j) in studs)


def brick(nx, ny, height=BRICK_H, studs=True, hollow=True, x=0.0,
          y=0.0, z=0.0, seg=32, name=None, round_=False):
    """A brick (or plate, or tile) *nx* x *ny* studs whose corner sits
    at (x, y, z) on the stud grid.

    *studs*: True for every stud, False for none (a tile), or a set of
    (i, j) to keep. *hollow* False makes the body one block — for a
    brick inside a build, whose underside nobody sees. *round_* gives
    it a real part's rounded corners and bevelled edges."""
    nx, ny = max(int(nx), 1), max(int(ny), 1)
    w, d = nx * PITCH - 2 * GAP, ny * PITCH - 2 * GAP
    x0, y0 = x + GAP, y + GAP
    part = CadNode("union", name or f"Brick {nx}x{ny}")
    if hollow and height > TOP + 0.5 and round_:
        inner = height - TOP
        r = ROUND
        part.add(_slab("Top", x0, y0, z + inner, w, d, TOP))
        part.add(_cube("Front wall", x0 + r, y0, z, w - 2 * r, WALL, inner))
        part.add(_cube("Back wall", x0 + r, y0 + d - WALL, z, w - 2 * r,
                       WALL, inner))
        part.add(_cube("Left wall", x0, y0 + r, z, WALL, d - 2 * r, inner))
        part.add(_cube("Right wall", x0 + w - WALL, y0 + r, z, WALL,
                       d - 2 * r, inner))
        for cx, cy, start in ((x0 + r, y0 + r, 180.0),
                              (x0 + w - r, y0 + r, 270.0),
                              (x0 + w - r, y0 + d - r, 0.0),
                              (x0 + r, y0 + d - r, 90.0)):
            part.add(_corner(cx, cy, z, inner, start))
    elif hollow and height > TOP + 0.5:
        inner = height - TOP
        part.add(_cube("Top", x0, y0, z + inner, w, d, TOP))
        part.add(_cube("Front wall", x0, y0, z, w, WALL, inner))
        part.add(_cube("Back wall", x0, y0 + d - WALL, z, w, WALL, inner))
        part.add(_cube("Left wall", x0, y0 + WALL, z, WALL,
                       d - 2 * WALL, inner))
        part.add(_cube("Right wall", x0 + w - WALL, y0 + WALL, z, WALL,
                       d - 2 * WALL, inner))
    if hollow and height > TOP + 0.5:
        inner = height - TOP
        if nx >= 2 and ny >= 2:
            for i in range(1, nx):
                for j in range(1, ny):
                    part.add(_tube(x + i * PITCH, y + j * PITCH, z, inner,
                                   seg))
        elif nx == 1:
            for j in range(1, ny):
                part.add(_pin(x + PITCH / 2, y + j * PITCH, z, inner, seg))
        else:
            for i in range(1, nx):
                part.add(_pin(x + i * PITCH, y + PITCH / 2, z, inner, seg))
    else:
        part.add(_slab("Body", x0, y0, z, w, d, height) if round_
                 else _cube("Body", x0, y0, z, w, d, height))
    for i in range(nx):
        for j in range(ny):
            if _keep(studs, i, j):
                part.add(_stud(x + (i + 0.5) * PITCH, y + (j + 0.5) * PITCH,
                               z + height, seg, round_))
    return part


def slope(nx, facing="-Y", studs=True, x=0.0, y=0.0, z=0.0, seg=32,
          name=None):
    """A 45° roof slope, 2 studs deep and *nx* wide: a row of studs at
    the back, the slope running down to a 1.7 mm lip at the front.
    *facing* is the side the low edge faces: "-Y"/"+Y" (the slope is
    *nx* along X) or "-X"/"+X" (*nx* along Y — four sides for a hipped
    roof or a spire). *studs* True, False, or a set of indices
    0..nx-1 along the stud row, counted from its low-coordinate end."""
    nx = max(int(nx), 1)
    if facing in ("-X", "+X"):
        # the Y-facing slope at the origin, turned a quarter to the
        # right ((x, y) -> (y, -x)) and slid back onto the grid; the
        # turn reverses the stud row, so the indices are mirrored
        if studs is not True and studs is not False:
            studs = {nx - 1 - i for i in studs}
        inner = slope(nx, "-Y" if facing == "-X" else "+Y", studs, seg=seg)
        turn = CadNode("rotate", "Turn", dict(x=0.0, y=0.0, z=-90.0))
        turn.add(inner)
        place = CadNode("translate", "Position",
                        dict(x=x, y=y + nx * PITCH, z=z))
        place.add(turn)
        part = CadNode("union", name or f"Slope 45° 2x{nx}")
        part.add(place)
        return part
    w, d = nx * PITCH - 2 * GAP, 2 * PITCH - 2 * GAP
    back = PITCH - GAP                 # where the flat stud row begins
    lip = BRICK_H - back               # 45°: the run equals the drop
    profile = [[0.0, 0.0], [d, 0.0], [d, BRICK_H], [back, BRICK_H],
               [0.0, lip]]
    row_y = y + 1.5 * PITCH
    if facing == "+Y":
        profile = [[d - u, v] for u, v in reversed(profile)]
        row_y = y + 0.5 * PITCH
    poly = CadNode("polygon", "Slope profile",
                   dict(x=0.0, y=0.0, points=profile))
    body = CadNode("linear_extrude", "Slope", dict(height=w))
    body.add(poly)
    # the profile is drawn across the depth (u) and up (v); turn it so
    # u runs along Y, v up Z and the extrusion along X
    turn = CadNode("rotate", "Stand up", dict(x=90.0, y=0.0, z=90.0))
    turn.add(body)
    place = CadNode("translate", "Position", dict(x=x + GAP, y=y + GAP,
                                                  z=z))
    place.add(turn)
    part = CadNode("union", name or f"Slope 45° 2x{nx}")
    part.add(place)
    for i in range(nx):
        if studs is True or (studs and i in studs):
            part.add(_stud(x + (i + 0.5) * PITCH, row_y, z + BRICK_H, seg))
    return part


# ------------------------------------------------------------- library

def _pick(dims, sizes):
    entry = sizes.get(dims.get("_size", ""), next(iter(sizes.values())))
    out = dict(entry)
    out.update({k: v for k, v in dims.items()
                if not k.startswith("_") and v is not None})
    return out


def _named(dims, node, default="Red"):
    name = dims.get("_color") or default
    wrap = colour(node, name)
    wrap.name = f"{node.name}, {name}"
    return wrap


def build_brick(dims):
    p = _pick(dims, BRICK_SIZES)
    return _named(dims, brick(p["nx"], p["ny"], round_=True,
                              name=f"{int(p['nx'])}x{int(p['ny'])} brick"))


def build_plate(dims):
    p = _pick(dims, PLATE_SIZES)
    return _named(dims, brick(p["nx"], p["ny"], PLATE_H, round_=True,
                              name=f"{int(p['nx'])}x{int(p['ny'])} plate"))


def build_tile(dims):
    p = _pick(dims, TILE_SIZES)
    return _named(dims, brick(p["nx"], p["ny"], PLATE_H, studs=False,
                              round_=True,
                              name=f"{int(p['nx'])}x{int(p['ny'])} tile"))


def build_slope(dims):
    p = _pick(dims, SLOPE_SIZES)
    return _named(dims, slope(p["nx"],
                              name=f"2x{int(p['nx'])} slope 45°"))


def build_baseplate(dims):
    p = _pick(dims, BASEPLATE_SIZES)
    n = int(p["nx"])
    return _named(dims, brick(n, int(p["ny"]), BASEPLATE_H, hollow=False,
                              round_=True,
                              seg=16, name=f"{n}x{int(p['ny'])} baseplate"),
                  default="Green")


def _sizes(pairs):
    return {f"{a}x{b}": dict(nx=a, ny=b) for a, b in pairs}


BRICK_SIZES = _sizes([(1, 1), (1, 2), (1, 3), (1, 4), (1, 6), (1, 8),
                      (2, 2), (2, 3), (2, 4), (2, 6), (2, 8)])
PLATE_SIZES = _sizes([(1, 1), (1, 2), (1, 3), (1, 4), (1, 6), (1, 8),
                      (2, 2), (2, 3), (2, 4), (2, 6), (2, 8),
                      (4, 4), (4, 6), (4, 8), (6, 6), (6, 8), (8, 8)])
TILE_SIZES = _sizes([(1, 1), (1, 2), (1, 4), (2, 2), (2, 4)])
SLOPE_SIZES = {f"2x{n}": dict(nx=n) for n in (1, 2, 3, 4)}
BASEPLATE_SIZES = _sizes([(8, 8), (16, 16), (24, 24)])

_GRID = [("nx", "Studs along X"), ("ny", "Studs along Y")]
_COLORS = list(COLORS)

PARTS = {
    "lego_brick": dict(label="Brick", category=CATEGORY,
                       sizes=BRICK_SIZES, build=build_brick,
                       fields=_GRID, colors=_COLORS),
    "lego_plate": dict(label="Plate (1/3 brick high)", category=CATEGORY,
                       sizes=PLATE_SIZES, build=build_plate,
                       fields=_GRID, colors=_COLORS),
    "lego_tile": dict(label="Tile (flat plate, no studs)",
                      category=CATEGORY, sizes=TILE_SIZES,
                      build=build_tile, fields=_GRID, colors=_COLORS),
    "lego_slope": dict(label="Slope 45° (roof)", category=CATEGORY,
                       sizes=SLOPE_SIZES, build=build_slope,
                       fields=[("nx", "Studs along X")], colors=_COLORS),
    "lego_baseplate": dict(label="Baseplate", category=CATEGORY,
                           sizes=BASEPLATE_SIZES, build=build_baseplate,
                           fields=_GRID, colors=_COLORS),
}

#: dialog fields that count studs (integer spin boxes, no "mm")
COUNT_FIELDS = {"nx", "ny"}
