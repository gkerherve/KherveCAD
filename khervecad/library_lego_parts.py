"""Every LEGO piece as its own Library item (the "Lego" category).

library_lego.py offers five customisable parts (brick, plate, tile,
slope, baseplate) whose size is picked in the Part Library dialog. This
module lists each real piece on its own — "Brick 2 × 4", "Slope 33°
3 × 2", "Arch 1 × 6", "Technic brick 1 × 8" — so the Library ▸ Lego
menu reads like a parts catalogue and one click drops the piece in.
`group_of` sorts the labels into the menu's submenus (`GROUP_ORDER`).

Beyond the rectangular parts there are the shapes that make a real set:
45°, 33°, 65°, inverted, curved and cheese slopes; round bricks, plates,
tiles and cones (one revolved profile each — hollow stud, open underside,
no boolean); arches (the side outline with the opening drawn into it);
windows (a frame with a 2D opening and a clear pane); Technic bricks
(the side profile extruded with its pin holes as 2D holes, exact in the
preview); jumpers, corner plates and a brick with a stud on its side.
Same grid, clearances and colours as library_lego: the origin is the
piece's corner on the 8 mm stud grid, front faces -Y.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from .library_lego import (BASEPLATE_H, BRICK_H, CATEGORY, COLORS, GAP,
                           PITCH, PLATE_H, STUD_BEVEL, STUD_H, STUD_R, TOP,
                           _stud, brick, colour)
from .model import CadNode

SEG = 32
#: a round piece's outer radius (1 x 1) and a Technic pin hole
ROUND_R = PITCH / 2 - GAP
HOLE_R = 2.45
HOLE_Z = 5.8
#: the hollow stud of a round piece
STUD_IN = 1.6

GROUP_ORDER = ["Bricks", "Plates", "Tiles", "Slopes", "Curved & cheese",
               "Round & cones", "Arches", "Windows", "Technic bricks",
               "Special", "Baseplates", "Any size (customise)"]


# ------------------------------------------------------------ geometry

def _poly(name, pts, holes=()):
    shape = CadNode("polygon", name, dict(x=0.0, y=0.0, points=pts))
    if not holes:
        return shape
    cut = CadNode("difference", name)
    cut.add(shape)
    for h in holes:
        cut.add(h)
    return cut


def _side_x(name, pts, depth, x=0.0, y=0.0, z=0.0, holes=()):
    """An outline drawn in (x, z) — along the piece and up — extruded
    *depth* towards +Y from the front face at y + GAP."""
    ext = CadNode("linear_extrude", name, dict(height=depth))
    ext.add(_poly(name, pts, holes))
    turn = CadNode("rotate", "Stand up", dict(x=90.0, y=0.0, z=0.0))
    turn.add(ext)
    place = CadNode("translate", "Position",
                    dict(x=x, y=y + GAP + depth, z=z))
    place.add(turn)
    return place


def _side_y(name, pts, width, x=0.0, y=0.0, z=0.0):
    """An outline drawn in (y, z) — front to back and up — extruded
    *width* along +X (a slope's side profile)."""
    ext = CadNode("linear_extrude", name, dict(height=width))
    ext.add(_poly(name, pts))
    turn = CadNode("rotate", "Stand up", dict(x=90.0, y=0.0, z=90.0))
    turn.add(ext)
    place = CadNode("translate", "Position", dict(x=x + GAP, y=y + GAP,
                                                  z=z))
    place.add(turn)
    return place


def _revolved(name, pts, cx, cy, z=0.0, seg=SEG):
    ring = CadNode("rotate_extrude", name, dict(angle=360.0, segments=seg))
    ring.add(_poly(name, pts))
    place = CadNode("translate", name, dict(x=cx, y=cy, z=z))
    place.add(ring)
    return place


def _studs(part, cells, z):
    for i, j in cells:
        part.add(_stud((i + 0.5) * PITCH, (j + 0.5) * PITCH, z, SEG, True))


def wedge(name, nx, depth, height, profile, stud_rows=0):
    """A slope-like piece *nx* studs wide: *profile(d, h)* gives its
    (y, z) outline over the true depth d and height h; the last
    *stud_rows* rows at the back carry studs."""
    d = depth * PITCH - 2 * GAP
    part = CadNode("union", name)
    part.add(_side_y("Body", profile(d, height), nx * PITCH - 2 * GAP))
    _studs(part, [(i, depth - 1 - r) for i in range(nx)
                  for r in range(stud_rows)], height)
    return part


def slope_profile(angle, lip_min=1.0, rows=1):
    """A roof slope at *angle*° running down to the front, flat for
    *rows* studs at the back."""
    def make(d, h):
        back = rows * PITCH - GAP
        run = d - back
        lip = max(lip_min, h - run * math.tan(math.radians(angle)))
        return [[0.0, 0.0], [d, 0.0], [d, h], [run, h], [0.0, lip]]
    return make


def inverted_profile(d, h):
    """45° inverted: full top, the underside rising to the front."""
    back = PITCH - GAP
    return [[0.0, h - 1.7], [d - back, 0.0], [d, 0.0], [d, h], [0.0, h]]


def curved_profile(lip=0.8, steps=12):
    def make(d, h):
        pts = [[0.0, 0.0], [d, 0.0], [d, h]]
        for s in range(steps, -1, -1):
            u = d * s / steps
            pts.append([u, lip + (h - lip) * math.sin(math.pi / 2 * s
                                                      / steps)])
        return pts
    return make


def cheese_profile(d, h):
    return [[0.0, 0.0], [d, 0.0], [d, h], [0.0, 0.4]]


def round_piece(name, height, studded=True, cone=False):
    """A 1 x 1 round brick / plate / tile / cone: one revolved outline
    with a hollow open stud and an open underside."""
    r, h, b = ROUND_R, height, STUD_BEVEL
    if cone:
        pts = [[3.1, 0.0], [r, 0.0], [r, 0.8], [STUD_R, h],
               [STUD_R, h + STUD_H - b], [STUD_R - b, h + STUD_H],
               [STUD_IN, h + STUD_H], [STUD_IN, 6.0], [3.1, 1.5]]
    elif studded:
        pts = [[2.45, 0.0], [r, 0.0], [r, h - 0.3], [r - 0.3, h],
               [STUD_R, h], [STUD_R, h + STUD_H - b],
               [STUD_R - b, h + STUD_H], [STUD_IN, h + STUD_H],
               [STUD_IN, h - TOP], [2.45, h - TOP]]
    else:
        pts = [[2.45, 0.0], [r, 0.0], [r, h - 0.3], [r - 0.3, h],
               [0.0, h], [0.0, h - TOP], [2.45, h - TOP]]
    part = CadNode("union", name)
    part.add(_revolved("Round body", pts, PITCH / 2, PITCH / 2))
    return part


def round_2x2(name, height, studded=True):
    """A 2 x 2 round brick / plate (axle hole, four studs) or tile."""
    r, h = PITCH - GAP, height
    if studded:
        pts = [[2.4, 0.0], [3.25, 0.0], [3.25, h - TOP], [r - 1.5, h - TOP],
               [r - 1.5, 0.0], [r, 0.0], [r, h - 0.35], [r - 0.35, h],
               [2.4, h]]
    else:
        pts = [[r - 1.5, 0.0], [r, 0.0], [r, h - 0.35], [r - 0.35, h],
               [0.0, h], [0.0, h - TOP], [r - 1.5, h - TOP]]
    part = CadNode("union", name)
    part.add(_revolved("Round body", pts, PITCH, PITCH, seg=48))
    if studded:
        _studs(part, [(0, 0), (1, 0), (0, 1), (1, 1)], h)
    return part


def arch(name, nx, bricks, span, rise, steps=16):
    """An arch 1 deep: the side outline with a half-ellipse opening
    *span* studs wide and *rise* mm high drawn into it."""
    w, h = nx * PITCH - 2 * GAP, bricks * BRICK_H
    a = span * PITCH / 2 - GAP
    c = nx * PITCH / 2 - GAP
    pts = [[0.0, 0.0], [c - a, 0.0]]
    for s in range(1, steps):
        t = math.pi * (1 - s / steps)
        pts.append([c + a * math.cos(t), rise * math.sin(t)])
    pts += [[c + a, 0.0], [w, 0.0], [w, h], [0.0, h]]
    part = CadNode("union", name)
    part.add(_side_x("Arch", pts, PITCH - 2 * GAP, x=GAP))
    _studs(part, [(i, 0) for i in range(nx)], h)
    return part


def window(name, nx, bricks):
    """A window frame 1 deep with a clear pane set in its middle."""
    w, h = nx * PITCH - 2 * GAP, bricks * BRICK_H
    f = 1.2
    sill = PLATE_H
    opening = CadNode("polygon", "Opening", dict(x=0.0, y=0.0, points=[
        [f, sill], [w - f, sill], [w - f, h - f], [f, h - f]]))
    part = CadNode("union", name)
    part.add(_side_x("Frame", [[0.0, 0.0], [w, 0.0], [w, h], [0.0, h]],
                     PITCH - 2 * GAP, x=GAP, holes=[opening]))
    pane = CadNode("cube", "Pane", dict(
        x=GAP + f, y=PITCH / 2 - 0.4, z=sill, width=w - 2 * f, depth=0.8,
        height=h - f - sill, center=False))
    part.add(colour(pane, "Trans-clear"))
    _studs(part, [(i, 0) for i in range(nx)], h)
    return part


def technic_brick(name, nx):
    """A 1 x *nx* Technic brick: pin holes through its side between the
    studs, drawn as 2D holes of the extruded side outline."""
    w = nx * PITCH - 2 * GAP
    holes = [CadNode("circle", "Pin hole", dict(
        x=i * PITCH - GAP, y=HOLE_Z, radius=HOLE_R, segments=24))
        for i in range(1, nx)]
    if nx == 1:
        holes = [CadNode("circle", "Pin hole", dict(
            x=PITCH / 2 - GAP, y=HOLE_Z, radius=HOLE_R, segments=24))]
    part = CadNode("union", name)
    part.add(_side_x("Body", [[0.0, 0.0], [w, 0.0], [w, BRICK_H],
                              [0.0, BRICK_H]], PITCH - 2 * GAP, x=GAP,
                     holes=holes))
    _studs(part, [(i, 0) for i in range(nx)], BRICK_H)
    return part


def jumper(name, nx, ny):
    """A plate with ONE stud in its middle (offsets by half a stud)."""
    part = brick(nx, ny, PLATE_H, studs=False, round_=True, name=name)
    part.add(_stud(nx * PITCH / 2, ny * PITCH / 2, PLATE_H, SEG, True))
    return part


def corner(name, height):
    """A 2 x 2 L-shaped corner brick or plate (the back-right cell
    missing): one extruded L outline and three studs."""
    a, b, g = GAP, 2 * PITCH - GAP, PITCH - GAP
    pts = [[a, a], [b, a], [b, g], [g, g], [g, b], [a, b]]
    part = CadNode("union", name)
    ext = CadNode("linear_extrude", "Body", dict(height=height))
    ext.add(_poly("L outline", pts))
    part.add(ext)
    _studs(part, [(0, 0), (1, 0), (0, 1)], height)
    return part


def side_stud_brick(name):
    """A 1 x 1 brick with a stud on its front face (studs not on top)."""
    part = brick(1, 1, round_=True, name=name)
    turn = CadNode("rotate", "Side stud", dict(x=90.0, y=0.0, z=0.0))
    turn.add(_stud(0.0, 0.0, 0.0, SEG, True))
    place = CadNode("translate", "Side stud",
                    dict(x=PITCH / 2, y=GAP, z=5.6))
    place.add(turn)
    part.add(place)
    return part


# ------------------------------------------------------------- catalogue

def _x(a, b):
    return f"{a} × {b}"


def _items():
    """(label, group, default colour, builder) for every piece."""
    out = []

    def add(label, group, build, col="Red"):
        out.append((label, group, col, build))

    for a, b in [(1, 1), (1, 2), (1, 3), (1, 4), (1, 6), (1, 8), (1, 10),
                 (1, 12), (1, 16), (2, 2), (2, 3), (2, 4), (2, 6), (2, 8),
                 (2, 10)]:
        add(f"Brick {_x(a, b)}", "Bricks",
            lambda a=a, b=b, n=None: brick(b, a, round_=True, name=n))
    for a, b in [(1, 1), (1, 2), (1, 3), (1, 4), (1, 6), (1, 8), (1, 10),
                 (1, 12), (2, 2), (2, 3), (2, 4), (2, 6), (2, 8), (2, 10),
                 (2, 12), (2, 16), (4, 4), (4, 6), (4, 8), (4, 10), (4, 12),
                 (6, 6), (6, 8), (6, 10), (6, 12), (8, 8), (8, 16)]:
        add(f"Plate {_x(a, b)}", "Plates",
            lambda a=a, b=b, n=None: brick(b, a, PLATE_H, round_=True,
                                           name=n), "Light bluish grey")
    for a, b in [(1, 1), (1, 2), (1, 3), (1, 4), (1, 6), (1, 8), (2, 2),
                 (2, 3), (2, 4), (2, 6)]:
        add(f"Tile {_x(a, b)}", "Tiles",
            lambda a=a, b=b, n=None: brick(b, a, PLATE_H, studs=False,
                                           round_=True, name=n), "White")
    for w in (1, 2, 3, 4):
        add(f"Slope 45° {_x(2, w)}", "Slopes",
            lambda w=w, n=None: wedge(n, w, 2, BRICK_H,
                                      slope_profile(45.0, 1.7), 1))
    for w in (1, 2, 4):
        add(f"Slope 33° {_x(3, w)}", "Slopes",
            lambda w=w, n=None: wedge(n, w, 3, BRICK_H,
                                      slope_profile(33.0, 1.0), 1))
    for w in (1, 2):
        add(f"Slope 65° {_x(2, w)} × 2", "Slopes",
            lambda w=w, n=None: wedge(n, w, 2, 2 * BRICK_H,
                                      slope_profile(65.0, 1.7), 1))
        add(f"Slope 45° inverted {_x(2, w)}", "Slopes",
            lambda w=w, n=None: wedge(n, w, 2, BRICK_H, inverted_profile,
                                      2))
    for w, d in ((1, 1), (2, 1)):
        add(f"Cheese slope {_x(d, w)}", "Curved & cheese",
            lambda w=w, n=None: wedge(n, w, 1, PLATE_H, cheese_profile),
            "Yellow")
    for d in (2, 3, 4):
        add(f"Curved slope {_x(d, 1)}", "Curved & cheese",
            lambda d=d, n=None: wedge(n, 1, d, 2 * PLATE_H,
                                      curved_profile()), "Yellow")
    add("Curved slope 2 × 2", "Curved & cheese",
        lambda n=None: wedge(n, 2, 2, 2 * PLATE_H, curved_profile()),
        "Yellow")
    add("Round brick 1 × 1", "Round & cones",
        lambda n=None: round_piece(n, BRICK_H), "Orange")
    add("Round plate 1 × 1", "Round & cones",
        lambda n=None: round_piece(n, PLATE_H), "Orange")
    add("Round tile 1 × 1", "Round & cones",
        lambda n=None: round_piece(n, PLATE_H, studded=False), "Orange")
    add("Cone 1 × 1", "Round & cones",
        lambda n=None: round_piece(n, BRICK_H, cone=True), "Orange")
    add("Round brick 2 × 2", "Round & cones",
        lambda n=None: round_2x2(n, BRICK_H), "Orange")
    add("Round plate 2 × 2", "Round & cones",
        lambda n=None: round_2x2(n, PLATE_H), "Orange")
    add("Round tile 2 × 2", "Round & cones",
        lambda n=None: round_2x2(n, PLATE_H, studded=False), "Orange")
    for label, nx, hi, span, rise in (("Arch 1 × 3", 3, 1, 1, 6.0),
                                      ("Arch 1 × 4", 4, 1, 2, 7.6),
                                      ("Arch 1 × 6", 6, 1, 4, 6.4),
                                      ("Arch 1 × 6 × 2", 6, 2, 4, 15.6),
                                      ("Arch 1 × 8 × 2", 8, 2, 6, 15.6)):
        add(label, "Arches",
            lambda nx=nx, hi=hi, span=span, rise=rise, n=None:
            arch(n, nx, hi, span, rise), "Tan")
    for nx, hi in ((2, 2), (2, 3), (4, 3)):
        add(f"Window {_x(1, nx)} × {hi}", "Windows",
            lambda nx=nx, hi=hi, n=None: window(n, nx, hi), "White")
    for nx in (1, 2, 4, 6, 8, 10, 12, 16):
        add(f"Technic brick {_x(1, nx)}", "Technic bricks",
            lambda nx=nx, n=None: technic_brick(n, nx), "Light bluish grey")
    add("Jumper plate 1 × 2", "Special",
        lambda n=None: jumper(n, 2, 1), "Light bluish grey")
    add("Jumper plate 2 × 2", "Special",
        lambda n=None: jumper(n, 2, 2), "Light bluish grey")
    add("Corner brick 2 × 2", "Special",
        lambda n=None: corner(n, BRICK_H))
    add("Corner plate 2 × 2", "Special",
        lambda n=None: corner(n, PLATE_H), "Light bluish grey")
    add("Brick 1 × 1 with side stud", "Special",
        lambda n=None: side_stud_brick(n), "White")
    for s in (8, 16, 24, 32):
        add(f"Baseplate {_x(s, s)}", "Baseplates",
            lambda s=s, n=None: brick(s, s, BASEPLATE_H, hollow=False,
                                      round_=True, seg=16, name=n),
            "Green")
    return out


ITEMS = _items()
_GROUPS = {label: group for label, group, _c, _b in ITEMS}


def group_of(label: str) -> str:
    """Which Lego submenu *label* belongs in (the customisable parts of
    library_lego go last)."""
    return _GROUPS.get(label, "Any size (customise)")


def _pid(label):
    s = label.lower().replace("×", "x").replace("°", "")
    return "lego_" + "_".join("".join(c if c.isalnum() else " "
                                      for c in s).split())


def _builder(label, default, make):
    def build(dims):
        name = dims.get("_color") or default
        node = make(n=label)
        node.name = label
        wrap = colour(node, name)
        wrap.name = f"{label}, {name}"
        return wrap
    return build


_COLORS = list(COLORS)

PARTS = {
    _pid(label): dict(label=label, category=CATEGORY, sizes={}, fields=[],
                      build=_builder(label, col, make),
                      colors=[col] + [c for c in _COLORS if c != col])
    for label, _group, col, make in ITEMS
}
