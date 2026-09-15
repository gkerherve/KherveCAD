"""The House Builder's geometry (Qt-free): a house is FLOORS stacked on
top of each other, each floor a set of rectangular ROOMS with door/
window openings cut into their walls, plus a GARDEN beside the house.
`house_dialog.py` is the 2D floor-plan editor that builds this data
model; `apply()` compiles it into the document as real Objects, one
per floor (so "Ground floor", "First floor", ... are each an ordinary
Object, editable afterwards like any other) plus one "Garden" Object.

A room is defined only by its footprint (x, y, width, depth) in the
floor's own millimetre-flat coordinates — wall thickness and ceiling
height are floor-wide, matching how a real floor plan works and
keeping two rooms that share an edge from getting a double-thickness
wall between them. `collect_walls()` finds every distinct wall segment
of a floor (two rooms sharing an edge produce ONE wall, not two) and
gathers the door/window openings that belong to it; `_wall_node()`
turns a segment into a plain box, or a `difference()` of the box minus
each opening when there are any. Every wall segment is axis-aligned
(rooms are rectangles), so a wall is always purely horizontal (its
length along X) or purely vertical (its length along Y) — no rotation
is ever needed, only two symmetric branches.

Furniture is placed by calling the existing Part Library builders
(`library.build_part`) and wrapping whatever they return in a small
placement group — some library parts return a plain "union" node
(which already accepts x/y/rz directly) and some return a "color"-
wrapped node (which does not), so wrapping uniformly is what makes
placement work for either kind without needing to special-case parts.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .model import CadNode

#: floor-plan defaults, millimetres
WALL_HEIGHT = 2400.0
WALL_THICKNESS = 200.0
SLAB_THICKNESS = 200.0
ROOF_THICKNESS = 200.0
ROOF_EAVE = 300.0
DOOR_SIZE = (900.0, 2000.0, 0.0)      # width, height, sill
WINDOW_SIZE = (1200.0, 1200.0, 900.0)
GARDEN_THICKNESS = 50.0

SLAB_COLOR = "#c9c4ba"
WALL_COLOR = "#f2efe9"
ROOF_COLOR = "#6b4a3a"
GLASS_COLOR = "#bfe0e8"
GRASS_COLOR = "#5a9c4a"

SIDES = ("N", "S", "E", "W")

#: furniture catalogue for the Add furniture picker, grouped by room
#: type — part ids from library_room.PARTS / library_home.PARTS, minus
#: the fixtures (door, wall panel) the House Builder itself provides.
FURNITURE_CATALOG = {
    "Living room": ["home_sofa", "home_armchair", "home_coffee_table",
                    "home_sideboard", "home_bookcase", "home_floor_lamp",
                    "room_tv"],
    "Dining room": ["home_dining_table", "home_dining_chair"],
    "Bedroom": ["home_bed", "home_bedside_table", "home_wardrobe",
                "home_chest"],
    "Kitchen": ["home_kitchen", "home_fridge"],
    "Bathroom": ["home_toilet", "home_washbasin", "home_bath",
                "home_shower"],
    "Office / study": ["room_table", "room_chair", "room_monitor",
                       "home_bookcase"],
    "Other": ["room_carpet", "room_stool", "room_workbench"],
}


class HouseError(ValueError):
    """A house design this builder cannot compile — says why."""


# --------------------------------------------------------------- model
@dataclass
class Opening:
    """A door or window cut into one room's wall side."""
    kind: str                          # "door" | "window"
    side: str                          # "N" | "S" | "E" | "W"
    offset: float                      # from the side's start corner, mm
    width: float
    height: float
    sill: float = 0.0                  # height off the floor, mm


@dataclass
class Furniture:
    """One placed piece of furniture: a Part Library part id, its
    position in the floor's coordinates and a rotation about Z."""
    part_id: str
    x: float
    y: float
    rz: float = 0.0
    dims: dict = field(default_factory=dict)


@dataclass
class Room:
    """A rectangular room: footprint only — wall thickness and ceiling
    height are the floor's."""
    name: str
    x: float
    y: float
    w: float
    d: float
    openings: list = field(default_factory=list)
    furniture: list = field(default_factory=list)

    def edges(self) -> dict:
        x, y, w, d = self.x, self.y, self.w, self.d
        return {"S": ((x, y), (x + w, y)),
                "N": ((x, y + d), (x + w, y + d)),
                "W": ((x, y), (x, y + d)),
                "E": ((x + w, y), (x + w, y + d))}


@dataclass
class Floor:
    """One storey: uniform wall height/thickness, any number of rooms."""
    name: str
    wall_height: float = WALL_HEIGHT
    wall_thickness: float = WALL_THICKNESS
    slab_thickness: float = SLAB_THICKNESS
    rooms: list = field(default_factory=list)

    def bounds(self):
        """(x0, y0, x1, y1) of every room's footprint, or None."""
        if not self.rooms:
            return None
        x0 = min(r.x for r in self.rooms)
        y0 = min(r.y for r in self.rooms)
        x1 = max(r.x + r.w for r in self.rooms)
        y1 = max(r.y + r.d for r in self.rooms)
        return x0, y0, x1, y1


@dataclass
class Garden:
    width: float = 4000.0
    depth: float = 6000.0
    gap: float = 1500.0                # from the house's footprint, mm


@dataclass
class House:
    floors: list = field(default_factory=list)
    garden: Garden = None

    def bounds(self):
        boxes = [f.bounds() for f in self.floors if f.bounds()]
        if not boxes:
            return None
        return (min(b[0] for b in boxes), min(b[1] for b in boxes),
               max(b[2] for b in boxes), max(b[3] for b in boxes))


# ------------------------------------------------------------ geometry
def _round_pt(p):
    return round(p[0], 1), round(p[1], 1)


def _canon(p1, p2):
    a, b = _round_pt(p1), _round_pt(p2)
    return (a, b) if a <= b else (b, a)


def collect_walls(floor: Floor):
    """Every distinct wall segment of *floor*: (p1, p2, openings) with
    p1 -> p2 the segment's canonical direction and each opening's
    offset measured from p1 — two rooms sharing an edge contribute to
    the SAME segment instead of each getting their own wall."""
    walls = {}
    for room in floor.rooms:
        for side, (p1, p2) in room.edges().items():
            key = _canon(p1, p2)
            length = math.dist(p1, p2)
            reversed_ = _round_pt(p1) != key[0]
            entry = walls.setdefault(key, {"openings": []})
            for op in room.openings:
                if op.side != side:
                    continue
                offset = (length - op.offset - op.width if reversed_
                          else op.offset)
                entry["openings"].append(
                    (offset, op.width, op.height, op.sill, op.kind))
    return [(p1, p2, e["openings"]) for (p1, p2), e in walls.items()]


def _wall_node(p1, p2, openings, thickness, height, name="Wall"):
    horizontal = abs(p1[1] - p2[1]) < 1e-6
    if horizontal:
        x0, x1 = sorted((p1[0], p2[0]))
        y0 = p1[1] - thickness / 2.0
        w, d = x1 - x0, thickness
    else:
        y0, y1 = sorted((p1[1], p2[1]))
        x0 = p1[0] - thickness / 2.0
        w, d = thickness, y1 - y0
    length = w if horizontal else d
    outer = CadNode("cube", name, dict(x=x0, y=y0, z=0.0, width=w,
                                       depth=d, height=height,
                                       center=False))
    glazing = []
    cuts = []
    for offset, ow, oh, sill, kind in openings:
        offset = max(0.0, min(offset, length - ow))
        ow = min(ow, length)
        if horizontal:
            ox, oy = x0 + offset, y0 - 5.0
            cw, cd = ow, thickness + 10.0
        else:
            ox, oy = x0 - 5.0, y0 + offset
            cw, cd = thickness + 10.0, ow
        cuts.append(CadNode("cube", kind.capitalize(), dict(
            x=ox, y=oy, z=sill, width=cw, depth=cd, height=oh,
            center=False)))
        if kind == "window":
            gx, gy = (x0 + offset, y0 + thickness / 2.0 - 3.0) \
                if horizontal else (x0 + thickness / 2.0 - 3.0,
                                    y0 + offset)
            gw, gd = (ow, 6.0) if horizontal else (6.0, ow)
            glazing.append(CadNode("cube", "Glazing", dict(
                x=gx, y=gy, z=sill, width=gw, depth=gd, height=oh,
                center=False)))
    if not cuts:
        return [_color(outer, WALL_COLOR)]
    node = CadNode("difference", name, {})
    node.add(outer)
    for cut in cuts:
        node.add(cut)
    result = [_color(node, WALL_COLOR)]
    result += [_color(g, GLASS_COLOR, material="Glass", alpha=0.35)
              for g in glazing]
    return result


def _color(node, color, material="Default", alpha=1.0):
    c = CadNode("color", node.name, dict(color=color, alpha=alpha,
                                         material=material))
    c.add(node)
    return c


def _place(node, x, y, rz=0.0):
    """Wrap *node* (whatever type a library part returns) in a group
    placed at (x, y) and turned *rz* degrees about Z."""
    wrap = CadNode("union", node.name, dict(x=x, y=y, z=0.0, rz=rz))
    wrap.add(node)
    return wrap


def build_floor(floor: Floor, is_top: bool) -> CadNode:
    """*floor*'s slabs, walls, glazing and furniture as one group in
    the floor's own frame (z = 0 at the floor's own slab top)."""
    if not floor.rooms:
        raise HouseError(f'"{floor.name}" has no rooms.')
    group = CadNode("union", floor.name, {})
    for room in floor.rooms:
        group.add(_color(CadNode("cube", f"{room.name} floor", dict(
            x=room.x, y=room.y, z=-floor.slab_thickness, width=room.w,
            depth=room.d, height=floor.slab_thickness, center=False)),
            SLAB_COLOR))
    for p1, p2, openings in collect_walls(floor):
        for node in _wall_node(p1, p2, openings, floor.wall_thickness,
                               floor.wall_height):
            group.add(node)
    if is_top:
        x0, y0, x1, y1 = floor.bounds()
        group.add(_color(CadNode("cube", "Roof", dict(
            x=x0 - ROOF_EAVE, y=y0 - ROOF_EAVE, z=floor.wall_height,
            width=(x1 - x0) + 2 * ROOF_EAVE,
            depth=(y1 - y0) + 2 * ROOF_EAVE, height=ROOF_THICKNESS,
            center=False)), ROOF_COLOR))
    from . import library
    for room in floor.rooms:
        for f in room.furniture:
            node = library.build_part(f.part_id, dict(f.dims))
            group.add(_place(node, f.x, f.y, f.rz))
    return group


def build_garden(garden: Garden, house_bounds) -> CadNode:
    x0, y0, x1, y1 = house_bounds
    gx = x1 + garden.gap
    gy = y0
    box = CadNode("cube", "Garden", dict(
        x=gx, y=gy, z=-GARDEN_THICKNESS, width=garden.width,
        depth=garden.depth, height=GARDEN_THICKNESS, center=False))
    return _color(box, GRASS_COLOR, material="Matte")


# --------------------------------------------------------------- apply
def apply(model, house: House) -> list:
    """Insert *house* into the document: one Object per floor (stacked
    in Z, so "Ground floor" sits at z=0 and "First floor" above it) and
    one "Garden" Object beside the house's footprint. Returns the
    inserted component nodes, one call = one undo step."""
    if not house.floors:
        raise HouseError("Add at least one floor with a room.")
    inserted = []
    z = 0.0
    for i, floor in enumerate(house.floors):
        content = build_floor(floor, is_top=(i == len(house.floors) - 1))
        content.params["z"] = z
        model.root.add(content)
        comp = model.enclose_as_part(content, name=floor.name)
        inserted.append(comp)
        z += floor.wall_height + floor.slab_thickness
    if house.garden is not None:
        bounds = house.bounds()
        if bounds:
            g = build_garden(house.garden, bounds)
            model.root.add(g)
            inserted.append(model.enclose_as_part(g, name="Garden"))
    model.structure_changed.emit()
    return inserted
