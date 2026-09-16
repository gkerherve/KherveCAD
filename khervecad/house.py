"""The House Builder's geometry (Qt-free): a house is FLOORS stacked on
top of each other, each floor a set of rectangular ROOMS with door/
window openings cut into their walls, plus a GARDEN beside the house
and a ROOF on the top floor.
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
turns a segment into solid pieces around its openings. Every wall
segment is axis-aligned (rooms are rectangles), so a wall is always
purely horizontal or purely vertical — no rotation is ever needed.

A room's `surface` says what it is: "indoor" (walls, a floor slab, under
the roof) or an outdoor area — "garden" (lawn) or "paving" (a porch,
patio or driveway) — which gets no walls and no roof, only its ground.

The roof (`Roof`, `build_roof`) is flat, gable, hip, pyramid or
lean-to over the top floor's indoor rooms, built from `hull()`s of thin
boxes — sloped boards and a wedge — so it has no boolean and previews
exactly.

Furniture is placed by calling the existing Part Library builders
(`library.build_part`) and wrapping whatever they return in its own
placed Object. `surface_below` finds how high a piece sits when set on
another (a TV on its stand, a microwave on the worktop).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from functools import lru_cache

from .model import CadNode

#: floor-plan defaults, millimetres
WALL_HEIGHT = 2400.0
WALL_THICKNESS = 200.0
SLAB_THICKNESS = 200.0
ROOF_THICKNESS = 200.0
ROOF_EAVE = 300.0
DOOR_SIZE = (900.0, 2000.0, 0.0)      # width, height, sill
WINDOW_SIZE = (1200.0, 1200.0, 900.0)
GARAGE_DOOR_SIZE = (2400.0, 2100.0, 0.0)
GARDEN_THICKNESS = 50.0
#: a floor plan is the floor cut this high above its slab and seen from
#: above — the 2D Top view draws a built floor that way, so its walls,
#: openings and furniture show instead of the roof over them
PLAN_CUT = 1200.0

SLAB_COLOR = "#c9c4ba"
WALL_COLOR = "#f2efe9"
ROOF_COLOR = "#6b4a3a"
GLASS_COLOR = "#bfe0e8"
GLASS_ALPHA = 0.3                     # see-through in preview and render
#: a door's leaf is clearer than a window: the Glass style lifts alpha
#: toward 0.45 with its highlight, and at 0.3 a near-white door pane read
#: as a solid frosted panel in 3D. 0.15 is glrender's floor.
DOOR_GLASS_ALPHA = 0.15
GLASS_THICKNESS = 6.0
GARAGE_DOOR_COLOR = "#d8dadd"
GARAGE_DOOR_THICKNESS = 40.0
GRASS_COLOR = "#5a9c4a"
PAVING_COLOR = "#b9b3a8"

#: how the OUTSIDE of the house is finished: name -> (colour, material)
WALL_STYLES = {"Painted plaster": (WALL_COLOR, "Default"),
               "White render": ("#f7f6f2", "Matte"),
               "Cream render": ("#e8dfc9", "Matte"),
               "Red brick": ("#9c5a45", "Matte"),
               "Buff brick": ("#c9a879", "Matte"),
               "Grey stone": ("#a9a8a3", "Matte"),
               "Timber cladding": ("#a4794a", "Default"),
               "Concrete": ("#bdbdb8", "Matte")}
#: how the walls BETWEEN rooms are finished (a wall two rooms share)
INNER_WALL_STYLES = {"Painted plaster": (WALL_COLOR, "Default"),
                     "Warm white": ("#f6f1e7", "Default"),
                     "Soft grey": ("#d9dbdd", "Default"),
                     "Sage": ("#c7d2c0", "Default"),
                     "Clay pink": ("#e3cfc4", "Default"),
                     "Exposed brick": ("#9c5a45", "Matte")}
#: a room's own finish: thin panels lining ITS side of every wall, and
#: its floor — bathroom and kitchen tiles, a panelled study
ROOM_FINISHES = {
    "White tiles": (("#eef1f2", "Default"), ("#dfe3e4", "Default")),
    "Blue tiles": (("#cfe0ea", "Default"), ("#9fb9c8", "Default")),
    "Green metro tiles": (("#cfe0d2", "Default"), ("#b7c9bb", "Default")),
    "Marble": (("#eceae4", "Default"), ("#d8d4cc", "Default")),
    "Terracotta tiles": (("#f2efe9", "Default"), ("#b8674a", "Clay")),
    "Wood panelling": (("#b98f5e", "Default"), ("#8a6234", "Default")),
}
#: thickness of that lining, mm
FINISH_THICKNESS = 15.0

SIDES = ("N", "S", "E", "W")
OPENING_KINDS = ("door", "window", "garage door")
#: what a room is: indoors (walls, slab, roof) or an outdoor area
SURFACES = ("indoor", "garden", "paving")
SURFACE_COLORS = {"garden": GRASS_COLOR, "paving": PAVING_COLOR}

FLOOR_NAMES = ("Ground floor", "First floor", "Second floor",
               "Third floor", "Fourth floor", "Fifth floor")

#: roof shapes the House Builder offers
ROOF_STYLES = ("Flat", "Gable", "Hip", "Pyramid", "Lean-to")
#: the pitch each style reads right at, degrees (the builder's default)
ROOF_PITCH = {"Flat": 0.0, "Gable": 35.0, "Hip": 30.0, "Pyramid": 30.0,
              "Lean-to": 12.0}
#: roof coverings: name -> (colour, material)
ROOF_COLORS = {"Brown tiles": (ROOF_COLOR, "Default"),
               "Red clay": ("#a4492f", "Clay"),
               "Terracotta pantiles": ("#b4613a", "Clay"),
               "Grey tiles": ("#6e737a", "Default"),
               "Slate": ("#4b5057", "Default"),
               "Dark slate": ("#3a3f45", "Default"),
               "Cedar shingles": ("#8a6234", "Matte"),
               "Thatch": ("#c9a45a", "Matte"),
               "Green": ("#4f6b4a", "Matte"),
               "Green roof": ("#5f8f4f", "Matte"),
               "Zinc": ("#8a9096", "Metal"),
               "Solar panels": ("#2b3a4a", "Metal")}
#: which way the ridge runs: along the longer side, or along X / Y
ROOF_RIDGES = ("auto", "x", "y")
ROOF_PITCH_RANGE = (5.0, 60.0)
#: the roof over a SIDE WING — a part of a floor with nothing above it,
#: like a garage beside a two-storey house. A lean-to leans on the
#: taller part; "Same as main" repeats the main roof's style.
WING_STYLES = ("Lean-to", "Gable", "Hip", "Flat", "Same as main")


def floor_default_name(index: int) -> str:
    return FLOOR_NAMES[index] if index < len(FLOOR_NAMES) \
        else f"Floor {index}"


#: furniture catalogue for the Add furniture picker, grouped by room
#: type — Part Library ids (library_room, library_home, library_home_more,
#: library_home_extra), minus the fixtures (door, wall panel) the House
#: Builder itself provides. A piece may sit in several rooms.
FURNITURE_CATALOG = {
    "Living room": ["home_sofa", "home_corner_sofa", "home_armchair",
                    "home_coffee_table", "home_side_table", "home_ottoman",
                    "home_sideboard", "room_tv", "home_bookcase",
                    "home_floor_lamp", "home_table_lamp", "home_rug",
                    "home_plant", "home_piano", "home_fireplace",
                    "home_wall_light"],
    "Dining room": ["home_dining_table", "home_round_table",
                    "home_dining_chair", "home_bench",
                    "home_display_cabinet", "home_sideboard",
                    "home_pendant", "home_rug", "home_plant"],
    "Kitchen": ["home_kitchen", "home_island", "home_fridge",
                "home_dishwasher", "home_microwave", "home_bar_stool",
                "home_round_table", "home_dining_chair", "home_pendant",
                "home_wheelie_bin"],
    "Bedroom": ["home_bed", "home_bedside_table", "home_wardrobe",
                "home_chest", "home_dressing_table", "home_ottoman",
                "home_table_lamp", "home_rug", "home_wall_mirror",
                "home_desk", "room_tv"],
    "Kids' room": ["home_bunk_bed", "home_cot", "home_toy_box", "home_desk",
                   "home_chest", "home_wardrobe", "home_rug",
                   "home_table_lamp"],
    "Bathroom": ["home_toilet", "home_washbasin", "home_bath",
                 "home_shower", "home_towel_radiator", "home_bath_cabinet",
                 "home_laundry_basket", "home_wall_mirror", "home_plant"],
    "Office / study": ["home_desk", "home_office_chair",
                       "home_filing_cabinet", "home_laptop", "room_monitor",
                       "home_bookcase", "home_wall_shelf", "room_table",
                       "room_chair", "home_plant", "home_table_lamp"],
    "Hallway / corridor": ["home_console_table", "home_coat_stand",
                           "home_shoe_cabinet", "home_rug", "home_plant",
                           "home_wall_light", "home_wall_mirror",
                           "home_umbrella_stand", "home_bench"],
    "Entrance / porch": ["home_doormat", "home_coat_stand",
                         "home_shoe_cabinet", "home_umbrella_stand",
                         "home_bench", "home_planter", "home_wall_light",
                         "home_garden_bench"],
    "Reception": ["home_reception_desk", "home_waiting_chairs",
                  "home_office_chair", "home_water_cooler",
                  "home_coffee_table", "home_plant", "home_rug",
                  "home_wall_light", "room_monitor", "home_laptop"],
    "Stairs": ["home_stairs_straight", "home_stairs_spiral"],
    "Garage": ["home_car", "home_bicycle", "home_garage_shelving",
               "room_workbench", "home_wheelie_bin", "home_lawn_mower",
               "home_tumble_dryer", "home_washing_machine"],
    "Utility / laundry": ["home_washing_machine", "home_tumble_dryer",
                          "home_laundry_basket", "home_wall_shelf",
                          "home_garage_shelving"],
    "Garden / outdoor": ["home_tree_broadleaf", "home_tree_conifer",
                         "home_tree_birch", "home_shrub", "home_hedge",
                         "home_flower_bed", "home_planter",
                         "home_garden_bench", "home_patio_set", "home_bbq",
                         "home_lawn_mower", "home_car", "home_bicycle",
                         "home_wheelie_bin"],
    "Other": ["room_carpet", "room_stool", "room_workbench"],
}

#: room presets for the builder's "+ Room" menu: name -> (w, d, surface)
ROOM_TYPES = {
    "Living room": (5000.0, 4000.0, "indoor"),
    "Kitchen": (3500.0, 3000.0, "indoor"),
    "Dining room": (3500.0, 3500.0, "indoor"),
    "Bedroom": (3500.0, 3500.0, "indoor"),
    "Kids' room": (3000.0, 3000.0, "indoor"),
    "Bathroom": (2500.0, 2000.0, "indoor"),
    "Toilet": (1500.0, 1200.0, "indoor"),
    "Office / study": (3000.0, 2500.0, "indoor"),
    "Hallway": (3000.0, 1500.0, "indoor"),
    "Corridor": (5000.0, 1200.0, "indoor"),
    "Entrance": (2000.0, 2000.0, "indoor"),
    "Reception": (4000.0, 3500.0, "indoor"),
    "Stairwell": (2400.0, 4000.0, "indoor"),
    "Utility room": (2000.0, 2000.0, "indoor"),
    "Garage": (3500.0, 6000.0, "indoor"),
    "Porch": (2500.0, 1500.0, "paving"),
    "Patio": (4000.0, 3000.0, "paving"),
    "Driveway": (3000.0, 6000.0, "paving"),
    "Garden": (8000.0, 6000.0, "garden"),
}


class HouseError(ValueError):
    """A house design this builder cannot compile — says why."""


# --------------------------------------------------------------- model
@dataclass
class Opening:
    """A door, window or garage door cut into one room's wall side."""
    kind: str                          # "door" | "window" | "garage door"
    side: str                          # "N" | "S" | "E" | "W"
    offset: float                      # from the side's start corner, mm
    width: float
    height: float
    sill: float = 0.0                  # height off the floor, mm


def opening_size(kind: str):
    """(width, height, sill) an opening of *kind* starts with."""
    return {"door": DOOR_SIZE, "window": WINDOW_SIZE,
            "garage door": GARAGE_DOOR_SIZE}.get(kind, DOOR_SIZE)


@dataclass
class Furniture:
    """One placed piece of furniture: a Part Library part id, its
    position in the floor's coordinates and a rotation about Z. *z*
    lifts it off the floor (a TV on its unit, a shelf on the wall);
    *name* names its Object (default: the part's own name)."""
    part_id: str
    x: float
    y: float
    rz: float = 0.0
    dims: dict = field(default_factory=dict)
    z: float = 0.0
    name: str = ""


@dataclass
class Room:
    """A rectangular room: footprint only — wall thickness and ceiling
    height are the floor's. *surface* "indoor" gets walls and a slab; a
    "garden" or "paving" area is outdoors: ground only."""
    name: str
    x: float
    y: float
    w: float
    d: float
    openings: list = field(default_factory=list)
    furniture: list = field(default_factory=list)
    surface: str = "indoor"
    #: this room's own finish (ROOM_FINISHES), "" for the house's
    finish: str = ""

    @property
    def indoor(self) -> bool:
        return self.surface not in SURFACE_COLORS

    def edges(self) -> dict:
        x, y, w, d = self.x, self.y, self.w, self.d
        return {"S": ((x, y), (x + w, y)),
                "N": ((x, y + d), (x + w, y + d)),
                "W": ((x, y), (x, y + d)),
                "E": ((x + w, y), (x + w, y + d))}


def _bounds_of(rooms):
    if not rooms:
        return None
    return (min(r.x for r in rooms), min(r.y for r in rooms),
            max(r.x + r.w for r in rooms), max(r.y + r.d for r in rooms))


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
        return _bounds_of(self.rooms)

    def indoor_bounds(self):
        """Like `bounds`, the indoor rooms only — what the roof covers."""
        return _bounds_of([r for r in self.rooms if r.indoor])


@dataclass
class Garden:
    width: float = 4000.0
    depth: float = 6000.0
    gap: float = 1500.0                # from the house's footprint, mm


@dataclass
class Roof:
    """The roof on the top floor: *style* (ROOF_STYLES), *pitch* in
    degrees, *overhang* past the walls (mm), which way the *ridge* runs
    ("auto" = along the longer side, "x", "y"; a lean-to rises across
    it) and its covering *color* (ROOF_COLORS)."""
    style: str = "Flat"
    pitch: float = 35.0
    overhang: float = ROOF_EAVE
    ridge: str = "auto"
    color: str = "Brown tiles"
    #: the roof over side wings (WING_STYLES) — parts of a floor with
    #: nothing above them, which would otherwise stand open
    wings: str = "Lean-to"


@dataclass
class House:
    floors: list = field(default_factory=list)
    garden: Garden = None
    roof: Roof = field(default_factory=Roof)
    #: how the walls are finished: outside (WALL_STYLES) and between
    #: rooms (INNER_WALL_STYLES)
    outer_wall: str = "Painted plaster"
    inner_wall: str = "Painted plaster"

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
    """Every distinct wall segment of *floor*'s indoor rooms: (p1, p2,
    openings, interior) with p1 -> p2 the segment's canonical direction
    and each opening's offset measured from p1 — two rooms sharing an
    edge contribute to the SAME segment instead of each getting their
    own wall, and that segment is *interior* (a wall between rooms,
    finished differently from the outside of the house). Outdoor areas
    have no walls."""
    walls = {}
    for room in floor.rooms:
        if not room.indoor:
            continue
        for side, (p1, p2) in room.edges().items():
            key = _canon(p1, p2)
            length = math.dist(p1, p2)
            reversed_ = _round_pt(p1) != key[0]
            entry = walls.setdefault(key, {"openings": [], "rooms": 0})
            entry["rooms"] += 1
            for op in room.openings:
                if op.side != side:
                    continue
                offset = (length - op.offset - op.width if reversed_
                          else op.offset)
                entry["openings"].append(
                    (offset, op.width, op.height, op.sill, op.kind))
    return [(p1, p2, e["openings"], e["rooms"] > 1)
            for (p1, p2), e in walls.items()]


def _opening_spans(openings, length, height):
    """*openings* clamped into a wall of *length* x *height* and made
    disjoint along it: sorted (start, end, sill, top, kind) spans — an
    opening overlapping the one before it starts where that one ends."""
    spans = []
    for offset, ow, oh, sill, kind in sorted(openings):
        ow = min(ow, length)
        start = max(0.0, min(offset, length - ow))
        end = start + ow
        if spans:
            start = max(start, spans[-1][1])
        sill = max(0.0, min(sill, height))
        top = min(sill + oh, height)
        if end - start > 1e-6 and top - sill > 1e-6:
            spans.append((start, end, sill, top, kind))
    return spans


def _wall_node(p1, p2, openings, thickness, height, name="Wall",
               style=None):
    """One wall segment, built from SOLID pieces — the full-height runs
    between openings, and a sill under / lintel over each opening —
    rather than a box minus cutters. With no boolean in it, the
    built-in preview shows the openings exactly (it only approximates a
    difference, drawing the uncut box) and OpenSCAD has nothing to cut.
    Each opening gets a transparent Glass pane at the wall's mid-plane
    (a window's glazing, a door's glazed leaf), a garage door a solid
    panel."""
    horizontal = abs(p1[1] - p2[1]) < 1e-6
    if horizontal:
        x0, x1 = sorted((p1[0], p2[0]))
        y0 = p1[1] - thickness / 2.0
        length = x1 - x0
    else:
        y0, y1 = sorted((p1[1], p2[1]))
        x0 = p1[0] - thickness / 2.0
        length = y1 - y0

    def piece(label, a, b, z0, z1, depth=thickness, inset=0.0):
        """A box spanning [a, b] along the wall and [z0, z1] up it."""
        if horizontal:
            box = dict(x=x0 + a, y=y0 + inset, width=b - a, depth=depth)
        else:
            box = dict(x=x0 + inset, y=y0 + a, width=depth, depth=b - a)
        return CadNode("cube", label, dict(z=z0, height=z1 - z0,
                                           center=False, **box))

    colour, material = style or (WALL_COLOR, "Default")
    spans = _opening_spans(openings, length, height)
    if not spans:
        return [_color(piece(name, 0.0, length, 0.0, height), colour,
                       material)]
    wall = CadNode("union", name, {})
    glazing = []
    cursor = 0.0
    for start, end, sill, top, kind in spans:
        if start - cursor > 1e-6:
            wall.add(piece("Pier", cursor, start, 0.0, height))
        if sill > 1e-6:
            wall.add(piece("Sill", start, end, 0.0, sill))
        if height - top > 1e-6:
            wall.add(piece("Lintel", start, end, top, height))
        if kind == "garage door":
            t = min(GARAGE_DOOR_THICKNESS, thickness)
            glazing.append(_color(piece("Garage door", start, end, sill,
                                        top, depth=t,
                                        inset=(thickness - t) / 2.0),
                                  GARAGE_DOOR_COLOR, material="Metal"))
        else:
            pane = piece("Door glass" if kind == "door" else "Glazing",
                         start, end, sill, top, depth=GLASS_THICKNESS,
                         inset=(thickness - GLASS_THICKNESS) / 2.0)
            alpha = DOOR_GLASS_ALPHA if kind == "door" else GLASS_ALPHA
            glazing.append(_color(pane, GLASS_COLOR, material="Glass",
                                  alpha=alpha))
        cursor = end
    if length - cursor > 1e-6:
        wall.add(piece("Pier", cursor, length, 0.0, height))
    return [_color(wall, colour, material)] + glazing


def _solid_runs(openings, length, height):
    """The stretches of a wall left solid between its *openings*."""
    runs, cursor = [], 0.0
    for start, end, *_rest in _opening_spans(openings, length, height):
        if start - cursor > 1e-6:
            runs.append((cursor, start))
        cursor = end
    if length - cursor > 1e-6:
        runs.append((cursor, length))
    return runs


def room_finish_nodes(room: Room, floor: Floor) -> list:
    """*room*'s own finish as thin panels lining ITS side of each of its
    walls — bathroom tiles, panelling — with the same gaps its doors and
    windows leave, plus its tiled floor. Empty when the room has no
    finish of its own."""
    look = ROOM_FINISHES.get(room.finish)
    if look is None or not room.indoor:
        return []
    (wall_colour, wall_material), (floor_colour, floor_material) = look
    half = floor.wall_thickness / 2.0
    t = FINISH_THICKNESS
    out = [_color(CadNode("cube", f"{room.name} floor tiles", dict(
        x=room.x + half, y=room.y + half, z=-t,
        width=room.w - 2 * half, depth=room.d - 2 * half, height=t,
        center=False)), floor_colour, floor_material)]
    for side in SIDES:
        length = room.w if side in ("N", "S") else room.d
        spans = [(o.offset, o.width, o.height, o.sill, o.kind)
                 for o in room.openings if o.side == side]
        for a, b in _solid_runs(spans, length, floor.wall_height):
            if side in ("N", "S"):
                y = (room.y + half if side == "S"
                     else room.y + room.d - half - t)
                box = dict(x=room.x + a, y=y, width=b - a, depth=t)
            else:
                x = (room.x + half if side == "W"
                     else room.x + room.w - half - t)
                box = dict(x=x, y=room.y + a, width=t, depth=b - a)
            out.append(_color(CadNode("cube", "Wall finish", dict(
                z=0.0, height=floor.wall_height, center=False, **box)),
                wall_colour, wall_material))
    return out


def _color(node, color, material="Default", alpha=1.0):
    c = CadNode("color", node.name, dict(color=color, alpha=alpha,
                                         material=material))
    c.add(node)
    return c


def _unique(base, taken):
    name = base
    for i in range(2, 10_000):
        if name not in taken:
            break
        name = f"{base} {i}"
    taken.add(name)
    return name


def _furniture_object(node, f: Furniture, taken) -> CadNode:
    """*node* (whatever type a library part returns) as its OWN Object,
    placed at (x, y, z) and turned *rz* degrees about Z — so the floor
    Object calls "Toilet", "Sofa", "Kitchen"... like any other Object
    (open one in the Object tab, hide it, move it) instead of holding
    anonymous geometry. Names are unique across the house (*taken*):
    two chairs become "Chair" and "Chair 2"."""
    comp = CadNode("component", _unique(f.name or node.name, taken),
                   dict(x=f.x, y=f.y, z=f.z, rz=f.rz))
    comp.add(node)
    return comp


def build_floor(floor: Floor, is_top: bool, taken=None,
                roof: Roof | None = None, walls=None, wings=None) -> CadNode:
    """*floor*'s slabs, walls, glazing and furniture as one group in
    the floor's own frame (z = 0 at the floor's own slab top), with
    *roof* (flat by default) over it when it *is_top* and one over each
    of its *wings* — (bounds, attach side) of the parts nothing above
    covers, from `wing_roofs`. *walls* is (outside style, between-rooms
    style) from WALL_STYLES / INNER_WALL_STYLES; each piece of furniture
    is a nested Object (see `_furniture_object`)."""
    taken = set() if taken is None else taken
    if not floor.rooms:
        raise HouseError(f'"{floor.name}" has no rooms.')
    group = CadNode("union", floor.name, {})
    for room in floor.rooms:
        if room.indoor:
            group.add(_color(CadNode("cube", f"{room.name} floor", dict(
                x=room.x, y=room.y, z=-floor.slab_thickness, width=room.w,
                depth=room.d, height=floor.slab_thickness, center=False)),
                SLAB_COLOR))
        else:
            group.add(_color(CadNode("cube", room.name, dict(
                x=room.x, y=room.y, z=-GARDEN_THICKNESS, width=room.w,
                depth=room.d, height=GARDEN_THICKNESS, center=False)),
                SURFACE_COLORS[room.surface], material="Matte"))
    outer, inner = walls or ("Painted plaster", "Painted plaster")
    outer = WALL_STYLES.get(outer, (WALL_COLOR, "Default"))
    inner = INNER_WALL_STYLES.get(inner, (WALL_COLOR, "Default"))
    for p1, p2, openings, interior in collect_walls(floor):
        for node in _wall_node(p1, p2, openings, floor.wall_thickness,
                               floor.wall_height,
                               name="Inner wall" if interior else "Wall",
                               style=inner if interior else outer):
            group.add(node)
    for room in floor.rooms:
        for node in room_finish_nodes(room, floor):
            group.add(node)
    roof = roof or Roof()
    if is_top:
        for node in build_roof(roof, floor, wall_style=outer):
            group.add(node)
    for bounds, attach in wings or []:
        style = None if roof.wings == "Same as main" else roof.wings
        for node in build_roof(roof, floor, bounds=bounds, style=style,
                               attach=attach, name="Wing roof",
                               wall_style=outer):
            group.add(node)
    from . import library
    for room in floor.rooms:
        for f in room.furniture:
            node = library.build_part(f.part_id, dict(f.dims))
            group.add(_furniture_object(node, f, taken))
    return group


# ---------------------------------------------------------------- roof
def _roof_frame(roof: Roof, floor: Floor, bounds=None, attach=None):
    """(along_x, (u0, u1, v0, v1), high_v0): the roof's own frame, u
    along the ridge and v across it, over *bounds* (the floor's indoor
    rooms by default; None if it has none). *attach* — the side where a
    taller part of the house stands — turns the ridge to run along that
    wall and says which way a lean-to rises (*high_v0*: towards the low
    v, so the roof leans on that wall)."""
    b = bounds if bounds is not None else floor.indoor_bounds()
    if b is None:
        return None
    x0, y0, x1, y1 = b
    if attach in ("E", "W"):
        along_x = False
    elif attach in ("N", "S"):
        along_x = True
    else:
        along_x = roof.ridge == "x" or (roof.ridge != "y"
                                        and x1 - x0 >= y1 - y0)
    frame = (x0, x1, y0, y1) if along_x else (y0, y1, x0, x1)
    return along_x, frame, attach in ("W", "S")


def _pitch_tan(roof: Roof) -> float:
    lo, hi = ROOF_PITCH_RANGE
    return math.tan(math.radians(min(max(float(roof.pitch), lo), hi)))


def build_roof(roof: Roof, floor: Floor, bounds=None, style=None,
               attach=None, name="Roof", wall_style=None) -> list:
    """The roof over *bounds* (the floor's indoor rooms by default) as
    coloured nodes: a flat slab, or sloped boards (`hull` of two thin
    bars: one at the eave, one at the ridge) over a wall-coloured gable
    / wedge infill, or one convex hull for a hip or pyramid roof. No
    booleans, so the preview shows it exactly. *style* overrides the
    roof's own; with *attach* — the side where a taller part of the
    house stands — a lean-to rises towards it and keeps its overhang
    out of it, which is what a side wing gets. Empty when there is
    nothing to cover."""
    frame = _roof_frame(roof, floor, bounds, attach)
    if frame is None:
        return []
    along_x, (u0, u1, v0, v1), high_v0 = frame
    H = floor.wall_height
    e = max(0.0, float(roof.overhang))
    t = ROOF_THICKNESS
    hw = floor.wall_thickness / 2.0
    color, material = ROOF_COLORS.get(roof.color, ROOF_COLORS["Brown tiles"])
    # the triangle of wall a gable closes, and the wedge under a lean-to,
    # are WALL — they wear the outside of the house, not a bare default
    wall_colour, wall_material = wall_style or (WALL_COLOR, "Default")
    style = style or roof.style
    style = style if style in ROOF_STYLES else "Flat"

    def cube(label, ua, va, z, du, dv, h):
        """A box in the roof's (u, v) frame."""
        box = (dict(x=ua, y=va, width=du, depth=dv) if along_x
               else dict(x=va, y=ua, width=dv, depth=du))
        return CadNode("cube", label, dict(z=z, height=h, center=False,
                                           **box))

    def hull(label, parts, colour=color, mat=material):
        node = CadNode("hull", label, {})
        for p in parts:
            node.add(p)
        return _color(node, colour, mat)

    L, span = u1 - u0, v1 - v0
    if style == "Flat":
        return [_color(cube(name, u0 - e, v0 - e, H, L + 2 * e,
                            span + 2 * e, t), color, material)]
    tan = _pitch_tan(roof)
    thin = 1.0
    vc = (v0 + v1) / 2.0
    ue, le = u0 - e, L + 2 * e             # eaves run past the gables too
    eave_z = H - e * tan
    wall_u, wall_l = u0 - hw, L + 2 * hw
    plate = cube("Wall plate", wall_u, v0 - hw, H, wall_l, span + 2 * hw,
                 thin)
    if style == "Gable":
        top = H + span / 2.0 * tan
        return [
            hull(f"{name} slope",
                 [cube("Eave", ue, v0 - e, eave_z, le, thin, t),
                  cube("Ridge", ue, vc - thin, top, le, thin, t)]),
            hull(f"{name} slope",
                 [cube("Eave", ue, v1 + e - thin, eave_z, le, thin, t),
                  cube("Ridge", ue, vc, top, le, thin, t)]),
            hull("Gable", [plate, cube("Apex", wall_u, vc - thin / 2.0,
                                       top - thin, wall_l, thin, thin)],
                 wall_colour, wall_material)]
    if style == "Lean-to":
        # it leans on the taller part: no overhang into that wall, and
        # the slope rises towards it (high_v0 when it stands at low v)
        he = 0.0 if attach else e
        if high_v0:
            lo_va, hi_va, wedge_va = v1 + e - thin, v0 - he, v0 - hw
        else:
            lo_va, hi_va, wedge_va = v0 - e, v1 + he - thin, v1 + hw - thin
        return [
            hull(f"{name} slope",
                 [cube("Low eave", ue, lo_va, eave_z, le, thin, t),
                  cube("High eave", ue, hi_va, H + (span + he) * tan, le,
                       thin, t)]),
            hull("Wedge", [plate, cube("High wall", wall_u, wedge_va,
                                       H + (span + hw) * tan - thin, wall_l,
                                       thin, thin)], wall_colour,
                 wall_material)]
    # hip and pyramid: one convex solid from the eaves to a ridge / apex
    rise = (min(L, span) if style == "Pyramid" else span) / 2.0 * tan
    rl = max(L - span, thin) if style == "Hip" else thin
    uc = (u0 + u1) / 2.0
    return [hull(name, [cube("Eaves", ue, v0 - e, eave_z, le, span + 2 * e,
                             t),
                        cube("Ridge", uc - rl / 2.0, vc - thin / 2.0,
                             H + rise, rl, thin, t)])]


def roof_outline(roof: Roof, floor: Floor, bounds=None, style=None,
                 attach=None):
    """The roof seen from above, for the plan: {"eave": (x0, y0, x1, y1),
    "lines": [((x, y), (x, y)), ...]} — ridge, hips, or the lean-to's
    fall line — or None when there is nothing to cover."""
    frame = _roof_frame(roof, floor, bounds, attach)
    if frame is None:
        return None
    along_x, (u0, u1, v0, v1), _high_v0 = frame
    e = max(0.0, float(roof.overhang))

    def xy(u, v):
        return (u, v) if along_x else (v, u)

    ea, eb = xy(u0 - e, v0 - e), xy(u1 + e, v1 + e)
    eave = (min(ea[0], eb[0]), min(ea[1], eb[1]),
            max(ea[0], eb[0]), max(ea[1], eb[1]))
    vc, uc = (v0 + v1) / 2.0, (u0 + u1) / 2.0
    L, span = u1 - u0, v1 - v0
    style = style or roof.style
    corners = [(u0 - e, v0 - e), (u1 + e, v0 - e), (u1 + e, v1 + e),
               (u0 - e, v1 + e)]
    lines = []
    if style == "Gable":
        lines = [(xy(u0 - e, vc), xy(u1 + e, vc))]
    elif style == "Hip":
        half = max(L - span, 0.0) / 2.0
        a, b = (uc - half, vc), (uc + half, vc)
        lines = [(xy(*a), xy(*b))]
        for cu, cv in corners:
            end = a if cu < uc else b
            lines.append((xy(cu, cv), xy(*end)))
    elif style == "Pyramid":
        lines = [(xy(cu, cv), xy(uc, vc)) for cu, cv in corners]
    elif style == "Lean-to":
        lines = [(xy(uc, v0 - e), xy(uc, v1 + e))]
    return {"eave": eave, "lines": lines}


def uncovered_rects(below, above):
    """The parts of the *below* rectangles that no *above* rectangle
    covers, merged back into rectangles — what a floor has standing open
    to the sky because nothing is built on top of it."""
    if not below:
        return []
    boxes = list(below) + list(above)
    xs = sorted({v for r in boxes for v in (r[0], r[2])})
    ys = sorted({v for r in boxes for v in (r[1], r[3])})

    def inside(rects, x, y):
        return any(r[0] < x < r[2] and r[1] < y < r[3] for r in rects)

    open_cells = set()
    for i in range(len(xs) - 1):
        cx = (xs[i] + xs[i + 1]) / 2.0
        for j in range(len(ys) - 1):
            cy = (ys[j] + ys[j + 1]) / 2.0
            if inside(below, cx, cy) and not inside(above, cx, cy):
                open_cells.add((i, j))
    strips = []
    for j in range(len(ys) - 1):
        i = 0
        while i < len(xs) - 1:
            if (i, j) not in open_cells:
                i += 1
                continue
            k = i
            while (k + 1, j) in open_cells:
                k += 1
            strips.append([xs[i], ys[j], xs[k + 1], ys[j + 1]])
            i = k + 1
    merged = []
    for s in strips:                       # join strips sitting on each other
        for m in merged:
            if m[0] == s[0] and m[2] == s[2] and abs(m[3] - s[1]) < 1e-6:
                m[3] = s[3]
                break
        else:
            merged.append(list(s))
    return [tuple(m) for m in merged]


def _touching(a, b, gap=1.0):
    return not (a[2] < b[0] - gap or b[2] < a[0] - gap
                or a[3] < b[1] - gap or b[3] < a[1] - gap)


def _clusters(rects):
    """*rects* grouped into the lumps that touch each other."""
    groups = []
    for r in rects:
        near = [g for g in groups if any(_touching(r, o) for o in g)]
        merged = [r]
        for g in near:
            merged += g
            groups.remove(g)
        groups.append(merged)
    return groups


def wing_roofs(house: House, index: int):
    """[(bounds, attach side or None)] for the parts of floor *index*
    with no floor above them — a garage or a single-storey wing beside a
    two-storey house, which would otherwise stand open. The attach side
    is where the taller part of the house is, so a lean-to leans on it."""
    floors = house.floors
    if not (0 <= index < len(floors) - 1):
        return []
    below = [(r.x, r.y, r.x + r.w, r.y + r.d)
             for r in floors[index].rooms if r.indoor]
    upper = [r for f in floors[index + 1:] for r in f.rooms]
    above = [(r.x, r.y, r.x + r.w, r.y + r.d) for r in upper]
    tall = _bounds_of(upper)
    out = []
    for group in _clusters(uncovered_rects(below, above)):
        b = (min(r[0] for r in group), min(r[1] for r in group),
             max(r[2] for r in group), max(r[3] for r in group))
        attach = None
        if tall is not None:
            if b[0] >= tall[2] - 1.0:
                attach = "W"
            elif b[2] <= tall[0] + 1.0:
                attach = "E"
            elif b[1] >= tall[3] - 1.0:
                attach = "S"
            elif b[3] <= tall[1] + 1.0:
                attach = "N"
        out.append((b, attach))
    return out


def build_garden(garden: Garden, house_bounds) -> CadNode:
    x0, y0, x1, y1 = house_bounds
    gx = x1 + garden.gap
    gy = y0
    box = CadNode("cube", "Garden", dict(
        x=gx, y=gy, z=-GARDEN_THICKNESS, width=garden.width,
        depth=garden.depth, height=GARDEN_THICKNESS, center=False))
    return _color(box, GRASS_COLOR, material="Matte")


# ---------------------------------------------------------- stacking
#: a piece set down on another stops at surfaces within reach — a
#: microwave goes on the worktop, not on the wall cupboards over it
STACK_REACH = 1800.0
#: parts from other modules that sit on what is under them
ON_TOP_PARTS = {"room_tv", "room_monitor"}


@lru_cache(maxsize=256)
def _part_tris(part_id, dims_key):
    from . import library, mesh
    return tuple(mesh.tessellate(
        library.build_part(part_id, json.loads(dims_key)), fn=12))


def part_tris(part_id, dims):
    """The part's own triangles (cached), in its own frame."""
    return _part_tris(part_id, json.dumps(dims or {}, sort_keys=True,
                                          default=str))


def part_rest_z(part_id) -> float:
    """How high a piece is put when added: 0 on the floor, more for one
    hung on a wall or a ceiling (the part's ``rest_z``)."""
    from . import library
    return float((library.PARTS.get(part_id) or {}).get("rest_z", 0.0))


def sits_on_top(part_id) -> bool:
    """Whether a piece is set down on whatever is under it (a lamp, a
    TV, a microwave) rather than on the floor."""
    from . import library
    return part_id in ON_TOP_PARTS or \
        bool((library.PARTS.get(part_id) or {}).get("on_top"))


def _hits(tris, x, y):
    """(z, facing up) of every face of *tris* straight above or below
    the point (x, y)."""
    out = []
    for a, b, c in tris:
        det = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(det) < 1e-9:
            continue                        # a vertical face
        l1 = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / det
        l2 = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / det
        l3 = 1.0 - l1 - l2
        if min(l1, l2, l3) < -1e-7:
            continue
        out.append((l1 * a[2] + l2 * b[2] + l3 * c[2], det > 0))
    return out


def surface_below(floor: Floor, f: Furniture,
                  reach: float = STACK_REACH) -> float:
    """How high *f* sits when set down on the furniture under its
    centre: the highest upward-facing surface of another piece there
    that is within *reach* and has room above it for *f* — so a TV lands
    on its stand and a microwave on the worktop, not on the wall
    cupboards — else 0, the floor. Pieces hung on a wall or a ceiling
    hold nothing."""
    own = part_tris(f.part_id, f.dims)
    height = max((p[2] for t in own for p in t), default=0.0)
    best = 0.0
    for room in floor.rooms:
        for g in room.furniture:
            if g is f or part_rest_z(g.part_id) > 0:
                continue
            a = math.radians(g.rz)
            dx, dy = f.x - g.x, f.y - g.y
            lx = dx * math.cos(a) + dy * math.sin(a)
            ly = -dx * math.sin(a) + dy * math.cos(a)
            hits = sorted(_hits(part_tris(g.part_id, g.dims), lx, ly))
            for i, (z, up) in enumerate(hits):
                top = g.z + z
                if not up or top > reach or top <= best:
                    continue
                above = [h for h, _u in hits[i + 1:] if h > z + 1.0]
                if above and above[0] - z < height:
                    continue                # no room for it there
                best = top
    return round(best, 1)


# --------------------------------------------------------------- apply
def remove_built(model) -> int:
    """Take out the top-level Objects the document's last House Builder
    build made (named in ``model.house["objects"]``); returns how many."""
    names = set((model.house or {}).get("objects") or [])
    gone = [c for c in list(model.root.children)
            if c.type == "component" and c.name in names]
    for comp in gone:
        model.root.remove(comp)
    return len(gone)


def apply(model, house: House, replace: bool = True) -> list:
    """Insert *house* into the document: one Object per floor (stacked
    in Z, so "Ground floor" sits at z=0 and "First floor" above it, the
    roof on the top one) and one "Garden" Object beside the house's
    footprint, and store the design as ``model.house`` so the House
    Builder reopens on it and it is saved with the document. With
    *replace* (the default) the house the last build made is swapped
    out, so editing and building again UPDATES the house instead of
    adding a second one. Returns the inserted component nodes, one call
    = one undo step."""
    if not house.floors:
        raise HouseError("Add at least one floor with a room.")
    for floor in house.floors:
        if not floor.rooms:
            raise HouseError(f'"{floor.name}" has no rooms.')
    if replace:
        remove_built(model)
    inserted = []
    z = 0.0
    taken = {n.name for n in model.root.walk()}
    for i, floor in enumerate(house.floors):
        content = build_floor(floor, is_top=(i == len(house.floors) - 1),
                              taken=taken, roof=house.roof,
                              walls=(house.outer_wall, house.inner_wall),
                              wings=wing_roofs(house, i))
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
    model.house = dict(house_to_spec(house),
                       objects=[c.name for c in inserted])
    model.structure_changed.emit()
    return inserted


def house_to_spec(house: House) -> dict:
    """*house* as the JSON-shaped spec `house_from_spec` reads back —
    what the document saves. Furniture keeps its exact dims (size and
    colour already resolved) and its x/y relative to its room, so the
    two functions round-trip."""
    spec = {"floors": [{
        "name": floor.name, "wall_height": floor.wall_height,
        "wall_thickness": floor.wall_thickness,
        "slab_thickness": floor.slab_thickness,
        "rooms": [{
            "name": r.name, "x": r.x, "y": r.y, "w": r.w, "d": r.d,
            "surface": r.surface, "finish": r.finish,
            "openings": [{"kind": o.kind, "side": o.side,
                          "offset": o.offset, "width": o.width,
                          "height": o.height, "sill": o.sill}
                         for o in r.openings],
            "furniture": [{"part_id": f.part_id, "x": f.x - r.x,
                           "y": f.y - r.y, "z": f.z, "rz": f.rz,
                           "dims": dict(f.dims), "name": f.name}
                          for f in r.furniture]}
            for r in floor.rooms]}
        for floor in house.floors]}
    if house.garden is not None:
        g = house.garden
        spec["garden"] = {"width": g.width, "depth": g.depth, "gap": g.gap}
    r = house.roof or Roof()
    spec["roof"] = {"style": r.style, "pitch": r.pitch,
                    "overhang": r.overhang, "ridge": r.ridge,
                    "color": r.color, "wings": r.wings}
    spec["walls"] = {"outside": house.outer_wall,
                     "inside": house.inner_wall}
    return spec


# ---------------------------------------------------- spec (MCP / JSON)
def _num(spec: dict, key: str, default=None) -> float:
    value = spec.get(key, default)
    if value is None:
        raise HouseError(f"'{key}' is required.")
    try:
        return float(value)
    except (TypeError, ValueError):
        raise HouseError(f"'{key}' must be a number, not {value!r}.")


def part_dims(part_id: str, size=None, color=None, overrides=None) -> dict:
    """The Part Library dims for *part_id* at *size* (a size name, or
    just its first word — '3-seater', '55'; default the first size),
    in *color* (one of the part's colour names), with *overrides*."""
    from . import library
    spec = library.PARTS.get(part_id)
    if spec is None:
        raise HouseError(f"No library part {part_id!r} — see list_parts "
                         "('Home furniture', 'Room & furniture').")
    sizes = spec.get("sizes") or {}
    dims = {}
    if sizes:
        key = next(iter(sizes))
        if size:
            want = str(size).strip().lower()
            match = [k for k in sizes if k.lower() == want] or \
                [k for k in sizes if k.lower().split(" ")[0] == want] or \
                [k for k in sizes if k.lower().startswith(want)]
            if not match:
                raise HouseError(f"{part_id} has no size {size!r}. It "
                                 f"offers: {', '.join(sizes)}.")
            key = match[0]
        dims = dict(sizes[key])
    if color:
        colors = spec.get("colors") or []
        match = [c for c in colors if c.lower() == str(color).lower()]
        if not match:
            raise HouseError(f"{part_id} has no colour {color!r}. It "
                             f"offers: {', '.join(colors) or 'none'}.")
        dims["_color"] = match[0]
    if overrides:
        if not isinstance(overrides, dict):
            raise HouseError("'dims' must be an object of mm values.")
        dims.update(overrides)
    return dims


#: which way a part is turned to put its back (+Y in the library's
#: convention: front faces -Y) against each wall
_WALL_RZ = {"N": 0.0, "S": 180.0, "E": -90.0, "W": 90.0}


def against_wall(room: Room, thickness: float, part_id: str, dims: dict,
                 wall: str, along=None, gap: float = 0.0):
    """(x, y, rz) that stands *part_id* with its back flush against the
    inside face of *room*'s *wall*, facing into the room. *along* is the
    distance of its centre from the room's W corner (N/S walls) or S
    corner (E/W walls), in the room's own centre-line frame like the
    room's x/y; None centres it. The depth comes from the built part
    itself, so any library part lands flush without a lookup."""
    wall = str(wall).strip().upper()
    if wall not in _WALL_RZ:
        raise HouseError(f"'wall' must be one of N, S, E, W — not "
                         f"{wall!r}.")
    tris = part_tris(part_id, dims)
    back = max((p[1] for tri in tris for p in tri), default=0.0)
    inner = thickness / 2.0 + gap + back
    rz = _WALL_RZ[wall]
    if wall in ("N", "S"):
        x = room.x + (room.w / 2.0 if along is None else float(along))
        y = room.y + room.d - inner if wall == "N" else room.y + inner
    else:
        y = room.y + (room.d / 2.0 if along is None else float(along))
        x = room.x + room.w - inner if wall == "E" else room.x + inner
    return x, y, rz


def _furniture_from_spec(spec: dict, room: Room, floor: Floor) -> Furniture:
    if not isinstance(spec, dict):
        raise HouseError("Each furniture entry must be an object.")
    part_id = str(spec.get("part_id", "")).strip()
    if "dims" in spec and not spec.get("size") and not spec.get("color"):
        part_dims(part_id)                   # checks the part exists
        dims = dict(spec["dims"] or {})      # saved dims, used as they are
    else:
        dims = part_dims(part_id, spec.get("size"), spec.get("color"),
                         spec.get("dims"))
    if spec.get("wall"):
        x, y, rz = against_wall(room, floor.wall_thickness, part_id, dims,
                                spec["wall"], spec.get("along"),
                                _num(spec, "gap", 0.0))
        rz = _num(spec, "rz", rz)
    else:
        x = room.x + _num(spec, "x", room.w / 2.0)
        y = room.y + _num(spec, "y", room.d / 2.0)
        rz = _num(spec, "rz", 0.0)
    return Furniture(part_id, x, y, rz, dims,
                     z=_num(spec, "z", part_rest_z(part_id)),
                     name=str(spec.get("name") or ""))


def _opening_from_spec(spec: dict) -> Opening:
    if not isinstance(spec, dict):
        raise HouseError("Each opening must be an object.")
    kind = str(spec.get("kind", "door")).strip().lower()
    if kind == "garage":
        kind = "garage door"
    if kind not in OPENING_KINDS:
        raise HouseError(f"Opening 'kind' must be one of "
                         f"{', '.join(OPENING_KINDS)} — not {kind!r}.")
    side = str(spec.get("side", "S")).strip().upper()
    if side not in SIDES:
        raise HouseError(f"Opening 'side' must be one of N, S, E, W — "
                         f"not {side!r}.")
    w, h, sill = opening_size(kind)
    return Opening(kind, side, _num(spec, "offset", 0.0),
                   _num(spec, "width", w), _num(spec, "height", h),
                   _num(spec, "sill", sill))


def roof_from_spec(spec) -> Roof:
    """A `Roof` from the spec's "roof" entry; none means the flat roof
    every house had before roofs could be chosen."""
    if not spec:
        return Roof()
    if not isinstance(spec, dict):
        raise HouseError("'roof' must be an object.")
    names = {s.lower(): s for s in ROOF_STYLES}
    names.update({"shed": "Lean-to", "lean to": "Lean-to",
                  "hipped": "Hip", "pitched": "Gable"})
    style = names.get(str(spec.get("style", "Gable")).strip().lower())
    if style is None:
        raise HouseError(f"Roof 'style' must be one of "
                         f"{', '.join(ROOF_STYLES)}.")
    ridge = str(spec.get("ridge", "auto")).strip().lower()
    if ridge not in ROOF_RIDGES:
        raise HouseError("Roof 'ridge' must be auto, x or y.")
    colors = {c.lower(): c for c in ROOF_COLORS}
    color = colors.get(str(spec.get("color", "Brown tiles")).strip().lower())
    if color is None:
        raise HouseError(f"Roof 'color' must be one of "
                         f"{', '.join(ROOF_COLORS)}.")
    pitch = _num(spec, "pitch", ROOF_PITCH[style] or 35.0)
    if style != "Flat" and not (ROOF_PITCH_RANGE[0] <= pitch
                                <= ROOF_PITCH_RANGE[1]):
        raise HouseError(f"Roof 'pitch' must be between "
                         f"{ROOF_PITCH_RANGE[0]:g} and "
                         f"{ROOF_PITCH_RANGE[1]:g} degrees.")
    overhang = _num(spec, "overhang", ROOF_EAVE)
    if overhang < 0:
        raise HouseError("Roof 'overhang' cannot be negative.")
    wings = {w.lower(): w for w in WING_STYLES}
    wings.update({"shed": "Lean-to", "same": "Same as main"})
    wing = wings.get(str(spec.get("wings", "Lean-to")).strip().lower())
    if wing is None:
        raise HouseError(f"Roof 'wings' must be one of "
                         f"{', '.join(WING_STYLES)}.")
    return Roof(style, pitch, overhang, ridge, color, wing)


def walls_from_spec(spec):
    """(outside style, between-rooms style) from the spec's "walls"."""
    spec = spec or {}
    if not isinstance(spec, dict):
        raise HouseError("'walls' must be an object.")
    out = []
    for key, table, default in (("outside", WALL_STYLES, "Painted plaster"),
                                ("inside", INNER_WALL_STYLES,
                                 "Painted plaster")):
        name = str(spec.get(key, default)).strip()
        match = [s for s in table if s.lower() == name.lower()]
        if not match:
            raise HouseError(f"Wall style {name!r} is not one of "
                             f"{', '.join(table)}.")
        out.append(match[0])
    return tuple(out)


def house_from_spec(spec: dict) -> House:
    """A `House` from a JSON-shaped *spec* (the build_house tool's
    input): floors -> rooms -> openings / furniture, plus an optional
    garden and roof. Furniture x/y are measured from its room's (x, y)
    corner, or resolved by `against_wall` when it names a `wall`; one
    marked `on_top` is set down on what is under it (`surface_below`)."""
    floors_in = spec.get("floors")
    if not isinstance(floors_in, list) or not floors_in:
        raise HouseError("Give 'floors': a list with at least one floor "
                         "of rooms.")
    floors = []
    for i, fspec in enumerate(floors_in):
        if not isinstance(fspec, dict):
            raise HouseError("Each floor must be an object.")
        floor = Floor(str(fspec.get("name") or floor_default_name(i)),
                      wall_height=_num(fspec, "wall_height", WALL_HEIGHT),
                      wall_thickness=_num(fspec, "wall_thickness",
                                          WALL_THICKNESS),
                      slab_thickness=_num(fspec, "slab_thickness",
                                          SLAB_THICKNESS))
        rooms_in = fspec.get("rooms") or []
        for j, rspec in enumerate(rooms_in):
            if not isinstance(rspec, dict):
                raise HouseError("Each room must be an object.")
            surface = str(rspec.get("surface", "indoor")).strip().lower()
            if surface not in SURFACES:
                raise HouseError(f"Room 'surface' must be one of "
                                 f"{', '.join(SURFACES)}.")
            finish = str(rspec.get("finish") or "").strip()
            if finish:
                match = [f for f in ROOM_FINISHES
                         if f.lower() == finish.lower()]
                if not match:
                    raise HouseError(
                        f"Room 'finish' must be one of "
                        f"{', '.join(ROOM_FINISHES)} — not {finish!r}.")
                finish = match[0]
            room = Room(str(rspec.get("name") or f"Room {j + 1}"),
                        _num(rspec, "x", 0.0), _num(rspec, "y", 0.0),
                        _num(rspec, "w"), _num(rspec, "d"),
                        surface=surface, finish=finish)
            if room.w <= 0 or room.d <= 0:
                raise HouseError(f'Room "{room.name}" needs a positive '
                                 "w and d.")
            room.openings = [_opening_from_spec(o)
                             for o in rspec.get("openings") or []]
            floor.rooms.append(room)
        stacked = []
        for room, rspec in zip(floor.rooms, rooms_in):
            room.furniture = []
            for fs in rspec.get("furniture") or []:
                f = _furniture_from_spec(fs, room, floor)
                room.furniture.append(f)
                if isinstance(fs, dict) and fs.get("on_top"):
                    stacked.append(f)
        for f in stacked:                   # once everything else stands
            f.z = surface_below(floor, f)
        floors.append(floor)
    garden = spec.get("garden")
    if garden:
        garden = Garden(width=_num(garden, "width", Garden.width),
                        depth=_num(garden, "depth", Garden.depth),
                        gap=_num(garden, "gap", Garden.gap))
    outer, inner = walls_from_spec(spec.get("walls"))
    return House(floors=floors, garden=garden or None,
                 roof=roof_from_spec(spec.get("roof")),
                 outer_wall=outer, inner_wall=inner)


def build_house(window, params: dict) -> dict:
    """The build_house MCP tool: `house_from_spec` then `apply`, with
    every resolved placement reported back so the caller can check it
    without a render."""
    house = house_from_spec(params or {})
    floors = []
    for index, floor in enumerate(house.floors):
        if not floor.rooms:
            raise HouseError(f'"{floor.name}" has no rooms.')
        floors.append({
            "name": floor.name,
            "walls": len(collect_walls(floor)),
            "wing_roofs": len(wing_roofs(house, index)),
            "rooms": [{"name": r.name, "x": r.x, "y": r.y, "w": r.w,
                       "d": r.d, "surface": r.surface,
                       "openings": len(r.openings),
                       "furniture": [{"part_id": f.part_id,
                                      "x": round(f.x, 1),
                                      "y": round(f.y, 1),
                                      "z": f.z, "rz": f.rz}
                                     for f in r.furniture]}
                      for r in floor.rooms]})
    roof = {"style": house.roof.style, "pitch": house.roof.pitch,
            "wings": house.roof.wings}
    if params.get("dry_run"):
        return {"dry_run": True, "floors": floors, "roof": roof}
    inserted = apply(window.model, house)
    window.view3d.fit()
    panel = getattr(window, "_house_builder", None)
    if panel is not None:                 # an open builder shows it now
        panel.load_from_document(force=True)
    return {"objects": [{"id": c.id, "name": c.name,
                         "contains": [n.name for n in c.walk()
                                      if n.type == "component"
                                      and n is not c]}
                        for c in inserted],
            "floors": floors, "roof": roof}
