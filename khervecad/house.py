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
ARCH_WINDOW_SIZE = (900.0, 1600.0, 950.0)
ARCH_DOOR_SIZE = (1100.0, 2500.0, 0.0)
GARDEN_THICKNESS = 50.0
#: how far below the ground floor the ground lies (downpipes end there)
PLINTH_GROUND = 150.0
#: a floor plan is the floor cut this high above its slab and seen from
#: above — the 2D Top view draws a built floor that way, so its walls,
#: openings and furniture show instead of the roof over them
PLAN_CUT = 1200.0

SLAB_COLOR = "#c9c4ba"
ROOF_COLOR = "#6b4a3a"
GRASS_COLOR = "#5a9c4a"
PAVING_COLOR = "#b9b3a8"
#: the default thickness of a wall between rooms — a partition is
#: thinner than an outside cavity wall
INNER_WALL_THICKNESS = 100.0

from .house_finishes import (FLOORINGS, INNER_WALL_STYLES,  # noqa: E402
                             JOINERY, NO_FINISH, ROOM_FINISHES, WALL_COLOR,
                             WALL_STYLES)
from .house_walls import (DOOR_GLASS_ALPHA, GARAGE_DOOR_COLOR,  # noqa: E402
                          GARAGE_DOOR_THICKNESS, GLASS_ALPHA, GLASS_COLOR,
                          GLASS_THICKNESS, Look, opening_spans,
                          room_nodes, wall_segments)
from . import house_finishes as _F  # noqa: E402

#: thickness of a tile lining, mm
FINISH_THICKNESS = _F.TILE_THICKNESS

SIDES = ("N", "S", "E", "W")
OPENING_KINDS = ("door", "window", "garage door", "arch window",
                 "arch door")
#: the round-headed openings (an Arabic, Moorish or Mediterranean house)
ARCHED = ("arch window", "arch door")
#: what a room is: indoors (walls, slab, roof) or an outdoor area
SURFACES = ("indoor", "garden", "paving", "void")
SURFACE_COLORS = {"garden": GRASS_COLOR, "paving": PAVING_COLOR}

FLOOR_NAMES = ("Ground floor", "First floor", "Second floor",
               "Third floor", "Fourth floor", "Fifth floor")

#: roof shapes the House Builder offers
from .house_roof import (CHIMNEYS, ROOF_PITCH_RANGE,  # noqa: E402
                         ROOF_STYLES, RoofShape, chimneys as _chimneys)
#: the pitch each style reads right at, degrees (the builder's default)
ROOF_PITCH = {"Flat": 0.0, "Gable": 35.0, "Hip": 30.0, "Pyramid": 30.0,
              "Lean-to": 12.0}
#: roof coverings: name -> (colour, material)
ROOF_COLORS = {"Brown tiles": (ROOF_COLOR, "Roof tiles"),
               "Red clay": ("#a4492f", "Roof tiles"),
               "Terracotta pantiles": ("#b4613a", "Roof tiles"),
               "Grey tiles": ("#6e737a", "Roof tiles"),
               "Black pantiles": ("#3b3d40", "Roof tiles"),
               "Slate": ("#4b5057", "Slate"),
               "Dark slate": ("#3a3f45", "Slate"),
               "Cedar shingles": ("#8a6234", "Shingles"),
               "Thatch": ("#c9a45a", "Thatch"),
               "Green": ("#4f6b4a", "Standing seam"),
               "Green roof": ("#5f8f4f", "Leaves"),
               "Zinc": ("#8a9096", "Standing seam"),
               "Copper (verdigris)": ("#5f9a86", "Standing seam"),
               "Solar panels": ("#2b3a4a", "Solar panels"),
               "Flat terrace": ("#cfc8b8", "Concrete")}
#: which way the ridge runs: along the longer side, or along X / Y
ROOF_RIDGES = ("auto", "x", "y")
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
    "Entrance / porch": ["kcad_classical_porch", "kcad_craftsman_porch",
                         "kcad_victorian_porch", "kcad_rustic_porch",
                         "kcad_modern_porch",
                         "home_doormat", "home_coat_stand",
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
                          "home_garage_shelving", "hvac_indoor_unit"],
    "Garden / outdoor": ["home_tree_broadleaf", "home_tree_conifer",
                         "home_tree_birch", "home_shrub", "home_hedge",
                         "home_flower_bed", "home_planter",
                         "home_garden_bench", "home_patio_set", "home_bbq",
                         "home_lawn_mower", "home_car", "home_bicycle",
                         "home_wheelie_bin", "hvac_outdoor_unit"],
    "Chemistry lab": ["lab_bench", "lab_sink_bench", "lab_fume_hood",
                      "lab_safety_shower", "lab_safety_cabinet",
                      "lab_fridge", "lab_drying_oven", "lab_centrifuge",
                      "lab_rotavap", "lab_glassware", "chem_balance",
                      "chem_hotplate", "chem_stand", "chem_bunsen",
                      "chem_gas_cylinder", "lab_stool", "lab_whiteboard",
                      "lab_fire_extinguisher", "lab_first_aid",
                      "office_lockers"],
    "Physics lab": ["lab_optical_table", "lab_laser", "lab_optics",
                    "lab_oscilloscope", "lab_power_supply",
                    "lab_signal_generator", "lab_instrument_rack",
                    "lab_uhv_chamber", "lab_dewar", "lab_electronics_bench",
                    "chem_gas_cylinder", "lab_stool", "lab_whiteboard",
                    "room_workbench", "lab_fire_extinguisher",
                    "lab_first_aid"],
    "Electronics lab": ["elec_esd_bench", "elec_soldering_station",
                        "elec_hot_air", "elec_fume_extractor",
                        "elec_bench_multimeter", "elec_multimeter",
                        "elec_spectrum_analyser", "elec_electronic_load",
                        "elec_logic_analyser", "elec_microscope",
                        "elec_helping_hands", "elec_esd_mat",
                        "elec_component_drawers", "lab_oscilloscope",
                        "lab_power_supply", "lab_signal_generator",
                        "lab_electronics_bench", "lab_instrument_rack",
                        "elec_breadboard", "elec_arduino_mega",
                        "lab_stool", "lab_whiteboard",
                        "lab_fire_extinguisher", "lab_first_aid"],
    "Open-plan office": ["office_bench_desks", "office_cubicle",
                         "office_partition", "office_phone_booth",
                         "office_printer", "office_lockers", "home_desk",
                         "office_task_chair", "home_office_chair",
                         "room_monitor", "home_plant",
                         "home_filing_cabinet"],
    "Meeting room": ["office_meeting_table", "lab_whiteboard", "room_tv",
                     "home_sideboard", "office_coffee_machine", "home_plant"],
    "Server room": ["office_server_rack", "lab_instrument_rack",
                    "lab_fire_extinguisher", "office_task_chair",
                    "home_desk", "room_monitor", "office_lockers"],
    "Break room": ["home_kitchen", "home_fridge", "office_coffee_machine",
                   "office_vending_machine", "home_round_table",
                   "home_dining_chair", "home_sofa", "home_sideboard",
                   "home_microwave", "home_plant"],
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
    "Chemistry lab": (12000.0, 9000.0, "indoor"),
    "Physics lab": (10000.0, 8000.0, "indoor"),
    "Electronics lab": (12000.0, 9000.0, "indoor"),
    "Component store": (3000.0, 4000.0, "indoor"),
    "Chemical store": (4000.0, 3000.0, "indoor"),
    "Open-plan office": (12000.0, 10000.0, "indoor"),
    "Meeting room": (6000.0, 5000.0, "indoor"),
    "Manager's office": (5000.0, 4000.0, "indoor"),
    "Server room": (3000.0, 3000.0, "indoor"),
    "Break room": (6000.0, 4000.0, "indoor"),
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
    kind: str            # door | window | garage door | arch window | arch door
    side: str                          # "N" | "S" | "E" | "W"
    offset: float                      # from the side's start corner, mm
    width: float
    height: float
    sill: float = 0.0                  # height off the floor, mm


def opening_size(kind: str):
    """(width, height, sill) an opening of *kind* starts with."""
    return {"door": DOOR_SIZE, "window": WINDOW_SIZE,
            "garage door": GARAGE_DOOR_SIZE,
            "arch window": ARCH_WINDOW_SIZE,
            "arch door": ARCH_DOOR_SIZE}.get(kind, DOOR_SIZE)


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
    #: this room's wall lining (ROOM_FINISHES; "" = chosen from its
    #: name, NO_FINISH = none)
    finish: str = ""
    #: this room's floor (FLOORINGS; "" = chosen from its name/finish)
    flooring: str = ""

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
    #: walls between two rooms
    inner_wall_thickness: float = INNER_WALL_THICKNESS

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
    #: chimneys (CHIMNEYS): "auto" over every fireplace, "none", or
    #: "ridge" — one on the ridge even without a fireplace
    chimney: str = "auto"
    #: a flat roof's parapet: its height in mm round every outside wall
    #: (0 = none), and whether it is crenellated (merlons and gaps)
    parapet: float = 0.0
    crenellated: bool = False


@dataclass
class House:
    floors: list = field(default_factory=list)
    garden: Garden = None
    roof: Roof = field(default_factory=Roof)
    #: how the walls are finished: outside (WALL_STYLES) and between
    #: rooms (INNER_WALL_STYLES)
    outer_wall: str = "Painted plaster"
    inner_wall: str = "Painted plaster"
    #: window frames and door linings (JOINERY; "" = what suits the
    #: outside finish)
    joinery: str = ""

    def bounds(self):
        boxes = [f.bounds() for f in self.floors if f.bounds()]
        if not boxes:
            return None
        return (min(b[0] for b in boxes), min(b[1] for b in boxes),
                max(b[2] for b in boxes), max(b[3] for b in boxes))


# ------------------------------------------------------------ geometry
def collect_walls(floor: Floor):
    """Every distinct wall of *floor*'s indoor rooms: (p1, p2,
    openings, interior) — two rooms sharing an edge contribute to the
    SAME wall, which is *interior* (a partition, finished and sized
    differently from the outside of the house). See
    `house_walls.wall_segments` for the full story. Outdoor areas have
    no walls."""
    return [(sg.p1, sg.p2, sg.openings, sg.interior)
            for sg in wall_segments(floor) if not sg.rail]


#: kept for the plan editor
_opening_spans = opening_spans


def side_thickness(floor: Floor, room: Room, side: str) -> float:
    """The thickness of the wall on *room*'s *side* (the thinner one
    where it changes along the side)."""
    hor = side in ("N", "S")
    line = {"S": room.y, "N": room.y + room.d, "W": room.x,
            "E": room.x + room.w}[side]
    lo, hi = (room.x, room.x + room.w) if hor else (room.y, room.y + room.d)
    near = [sg.thickness for sg in wall_segments(floor)
            if sg.horizontal == hor and abs(sg.c - line) < 0.2
            and sg.b > lo + 1e-6 and sg.a < hi - 1e-6]
    return min(near) if near else floor.wall_thickness


def room_finish_nodes(room: Room, floor: Floor) -> list:
    """*room*'s floor covering, skirting and tiles (`house_walls.
    room_nodes`)."""
    return room_nodes(room, floor)


def floor_look(house: "House | None") -> Look:
    """How *house*'s walls, joinery and roof are finished."""
    house = house or House()
    outer = WALL_STYLES.get(house.outer_wall, WALL_STYLES["Painted plaster"])
    inner = INNER_WALL_STYLES.get(house.inner_wall,
                                  INNER_WALL_STYLES["Painted plaster"])
    roof = house.roof or Roof()
    return Look(outside=outer, inside=inner,
                detail=_F.outside_detail(house.outer_wall),
                joinery=_F.joinery_for(house.joinery, house.outer_wall),
                roof=ROOF_COLORS.get(roof.color, ROOF_COLORS["Brown tiles"]),
                key=f"{house.outer_wall}|{len(house.floors)}")


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
                roof: Roof | None = None, walls=None, wings=None,
                look: Look | None = None, index: int = 0,
                level: float = 0.0, extra=None) -> CadNode:
    """*floor*'s slabs, walls, joinery, room finishes and furniture as
    one group in the floor's own frame (z = 0 at its finished floor),
    with *roof* (flat by default) over it when it *is_top* and one over
    each of its *wings* — (bounds, attach side) of the parts nothing
    above covers, from `wing_roofs`. *walls* is (outside style,
    between-rooms style); *look* overrides everything they imply.
    *index* 0 is the ground floor (plinth, front steps); *level* is the
    floor's height, so downpipes reach the ground; *extra* are nodes
    built for it elsewhere (chimneys). Each piece of furniture is a
    nested Object (see `_furniture_object`)."""
    taken = set() if taken is None else taken
    if not floor.rooms:
        raise HouseError(f'"{floor.name}" has no rooms.')
    if look is None:
        outer, inner = walls or ("Painted plaster", "Painted plaster")
        look = floor_look(House(outer_wall=outer, inner_wall=inner,
                                roof=roof or Roof()))
    group = CadNode("union", floor.name, {})
    ft = _F.FLOOR_THICKNESS
    for room in floor.rooms:
        if room.surface == "void":
            continue                            # open to the floor below
        if room.indoor:
            group.add(_color(CadNode("cube", f"{room.name} slab", dict(
                x=room.x, y=room.y, z=-floor.slab_thickness, width=room.w,
                depth=room.d, height=floor.slab_thickness - ft,
                center=False)), SLAB_COLOR, "Concrete"))
        else:
            group.add(_color(CadNode("cube", room.name, dict(
                x=room.x, y=room.y, z=-GARDEN_THICKNESS, width=room.w,
                depth=room.d, height=GARDEN_THICKNESS, center=False)),
                SURFACE_COLORS[room.surface],
                "Leaves" if room.surface == "garden" else "Stone"))
    from .house_walls import build_walls
    for node in build_walls(floor, look, ground=(index == 0)):
        group.add(node)
    segments = wall_segments(floor)
    for room in floor.rooms:
        for node in room_nodes(room, floor, segments):
            group.add(node)
    roof = roof or Roof()
    ground_z = -level - PLINTH_GROUND
    from .house_roof import build_roof
    if is_top:
        for node in build_roof(roof, floor, wall_style=look.outside,
                               look=look, ground_z=ground_z):
            group.add(node)
    for bounds, attach in wings or []:
        style = None if roof.wings == "Same as main" else roof.wings
        for node in build_roof(roof, floor, bounds=bounds, style=style,
                               attach=attach, name="Wing roof",
                               wall_style=look.outside, look=look,
                               ground_z=ground_z):
            group.add(node)
    for node in extra or []:
        group.add(node)
    from . import library
    for room in floor.rooms:
        for f in room.furniture:
            node = library.build_part(f.part_id, dict(f.dims))
            group.add(_furniture_object(node, f, taken))
    return group


# ---------------------------------------------------------------- roof
def _roof_frame(roof: Roof, floor: Floor, bounds=None, attach=None):
    from .house_roof import roof_frame
    return roof_frame(roof, floor, bounds, attach)


def build_roof(roof: Roof, floor: Floor, bounds=None, style=None,
               attach=None, name="Roof", wall_style=None, look=None,
               ground_z=-400.0) -> list:
    """The roof over *bounds* — see `house_roof.build_roof`."""
    from . import house_roof
    return house_roof.build_roof(roof, floor, bounds, style, attach, name,
                                 wall_style, look, ground_z)


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
ON_TOP_PARTS = {"room_tv", "room_monitor", "chem_balance", "chem_hotplate",
                "chem_stand", "chem_rack", "chem_bunsen", "chem_beaker",
                "chem_erlenmeyer", "chem_round_flask", "chem_cylinder",
                "chem_wash_bottle", "chem_petri", "chem_tripod"}


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


def designs_in(model) -> list:
    """The House Builder designs the document holds: one per house built
    (each kept on its first Object, ``params["house"]``), the current
    one (``model.house``) first."""
    out = [model.house] if model.house else []
    for node in model.root.walk():
        spec = node.params.get("house") if node.type == "component" \
            else None
        if isinstance(spec, dict) and spec.get("objects") and \
                all(spec != o for o in out):
            out.append(spec)
    return out


def design_of(model, nodes) -> dict | None:
    """The design of the house any of *nodes* belongs to (a floor, the
    garden, anything inside them), or None."""
    names = set()
    for node in nodes:
        while node is not None:
            if node.type == "component":
                names.add(node.name)
            node = node.parent
    for spec in designs_in(model):
        if names & set(spec.get("objects") or []):
            return spec
    return None


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
    taken = {n.name for n in model.root.walk()}
    # Objects already at the top (another house's floors) keep their
    # names; this build's are made unique against them, or rebuilding
    # one house would take the other's "Ground floor" with it
    tops = {c.name for c in model.root.children}
    for i, content in enumerate(build_house_floors(house, taken)):
        model.root.add(content)
        comp = model.enclose_as_part(
            content, name=_unique(house.floors[i].name, tops))
        inserted.append(comp)
    if house.garden is not None:
        bounds = house.bounds()
        if bounds:
            g = build_garden(house.garden, bounds)
            model.root.add(g)
            inserted.append(model.enclose_as_part(
                g, name=_unique("Garden", tops)))
    for comp in inserted:
        comp.params.pop("house", None)
    model.house = dict(house_to_spec(house),
                       objects=[c.name for c in inserted])
    if inserted:                          # so another house can be picked
        inserted[0].params["house"] = model.house
    model.structure_changed.emit()
    return inserted


def floor_levels(house: House) -> list:
    """The height of each floor's finished floor, ground floor at 0."""
    levels, z = [], 0.0
    for i, floor in enumerate(house.floors):
        if i:
            z += floor.slab_thickness
        levels.append(z)
        z += floor.wall_height
    return levels


def build_house_floors(house: House, taken=None) -> list:
    """Every floor of *house* as a group placed at its level, chimneys
    included — what `apply` wraps into Objects."""
    taken = set() if taken is None else taken
    levels = floor_levels(house)
    look = floor_look(house)
    stacks = _chimneys(house, levels, [look] * len(house.floors))
    groups = []
    for i, floor in enumerate(house.floors):
        content = build_floor(floor, is_top=(i == len(house.floors) - 1),
                              taken=taken, roof=house.roof,
                              wings=wing_roofs(house, i), look=look,
                              index=i, level=levels[i],
                              extra=stacks.get(i))
        content.params["z"] = levels[i]
        groups.append(content)
    return groups


def house_to_spec(house: House) -> dict:
    """*house* as the JSON-shaped spec `house_from_spec` reads back —
    what the document saves. Furniture keeps its exact dims (size and
    colour already resolved) and its x/y relative to its room, so the
    two functions round-trip."""
    spec = {"floors": [{
        "name": floor.name, "wall_height": floor.wall_height,
        "wall_thickness": floor.wall_thickness,
        "inner_wall_thickness": floor.inner_wall_thickness,
        "slab_thickness": floor.slab_thickness,
        "rooms": [{
            "name": r.name, "x": r.x, "y": r.y, "w": r.w, "d": r.d,
            "surface": r.surface, "finish": r.finish,
            "flooring": r.flooring,
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
                    "color": r.color, "wings": r.wings,
                    "chimney": r.chimney, "parapet": r.parapet,
                    "crenellated": r.crenellated}
    spec["walls"] = {"outside": house.outer_wall,
                     "inside": house.inner_wall}
    if house.joinery:
        spec["walls"]["joinery"] = house.joinery
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
        wall = str(spec["wall"]).strip().upper()
        thick = side_thickness(floor, room, wall) if wall in SIDES \
            else floor.wall_thickness
        x, y, rz = against_wall(room, thick, part_id, dims,
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
    kind = {"garage": "garage door", "arched window": "arch window",
            "arched door": "arch door", "arch": "arch window",
            "arched": "arch window"}.get(kind, kind)
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
    chimney = str(spec.get("chimney", "auto")).strip().lower()
    if chimney not in CHIMNEYS:
        raise HouseError(f"Roof 'chimney' must be one of "
                         f"{', '.join(CHIMNEYS)}.")
    parapet = _num(spec, "parapet", 0.0)
    if parapet < 0:
        raise HouseError("Roof 'parapet' cannot be negative.")
    return Roof(style, pitch, overhang, ridge, color, wing, chimney,
                parapet, bool(spec.get("crenellated", False)))


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
    joinery = str(spec.get("joinery") or "").strip()
    if joinery:
        match = [j for j in JOINERY if j.lower() == joinery.lower()]
        if not match:
            raise HouseError(f"Joinery {joinery!r} is not one of "
                             f"{', '.join(JOINERY)}.")
        joinery = match[0]
    out.append(joinery)
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
                                          SLAB_THICKNESS),
                      inner_wall_thickness=_num(
                          fspec, "inner_wall_thickness",
                          INNER_WALL_THICKNESS))
        if floor.inner_wall_thickness <= 0 or floor.wall_thickness <= 0:
            raise HouseError("Wall thicknesses must be positive.")
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
                match = [f for f in list(ROOM_FINISHES) + [NO_FINISH]
                         if f.lower() == finish.lower()]
                if not match:
                    raise HouseError(
                        f"Room 'finish' must be one of "
                        f"{', '.join(ROOM_FINISHES)}, {NO_FINISH} — "
                        f"not {finish!r}.")
                finish = match[0]
            flooring = str(rspec.get("flooring") or "").strip()
            if flooring:
                match = [f for f in FLOORINGS
                         if f.lower() == flooring.lower()]
                if not match:
                    raise HouseError(
                        f"Room 'flooring' must be one of "
                        f"{', '.join(FLOORINGS)} — not {flooring!r}.")
                flooring = match[0]
            room = Room(str(rspec.get("name") or f"Room {j + 1}"),
                        _num(rspec, "x", 0.0), _num(rspec, "y", 0.0),
                        _num(rspec, "w"), _num(rspec, "d"),
                        surface=surface, finish=finish,
                        flooring=flooring)
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
    outer, inner, joinery = walls_from_spec(spec.get("walls"))
    return House(floors=floors, garden=garden or None,
                 roof=roof_from_spec(spec.get("roof")),
                 outer_wall=outer, inner_wall=inner, joinery=joinery)


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
