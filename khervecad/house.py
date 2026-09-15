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
GLASS_ALPHA = 0.3                     # see-through in preview and render
GLASS_THICKNESS = 6.0
GRASS_COLOR = "#5a9c4a"

SIDES = ("N", "S", "E", "W")

FLOOR_NAMES = ("Ground floor", "First floor", "Second floor",
               "Third floor", "Fourth floor", "Fifth floor")


def floor_default_name(index: int) -> str:
    return FLOOR_NAMES[index] if index < len(FLOOR_NAMES) \
        else f"Floor {index}"

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
    position in the floor's coordinates and a rotation about Z. *z*
    lifts it off the floor (a TV on its unit); *name* names its Object
    (default: the part's own name)."""
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


def _wall_node(p1, p2, openings, thickness, height, name="Wall"):
    """One wall segment, built from SOLID pieces — the full-height runs
    between openings, and a sill under / lintel over each opening —
    rather than a box minus cutters. With no boolean in it, the
    built-in preview shows the openings exactly (it only approximates a
    difference, drawing the uncut box) and OpenSCAD has nothing to cut.
    Each opening gets a transparent Glass pane at the wall's mid-plane:
    a window's glazing, or a door's glazed leaf."""
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

    spans = _opening_spans(openings, length, height)
    if not spans:
        return [_color(piece(name, 0.0, length, 0.0, height), WALL_COLOR)]
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
        pane = piece("Door glass" if kind == "door" else "Glazing",
                     start, end, sill, top, depth=GLASS_THICKNESS,
                     inset=(thickness - GLASS_THICKNESS) / 2.0)
        glazing.append(_color(pane, GLASS_COLOR, material="Glass",
                              alpha=GLASS_ALPHA))
        cursor = end
    if length - cursor > 1e-6:
        wall.add(piece("Pier", cursor, length, 0.0, height))
    return [_color(wall, WALL_COLOR)] + glazing


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


def build_floor(floor: Floor, is_top: bool, taken=None) -> CadNode:
    """*floor*'s slabs, walls, glazing and furniture as one group in
    the floor's own frame (z = 0 at the floor's own slab top); each
    piece of furniture is a nested Object (see `_furniture_object`)."""
    taken = set() if taken is None else taken
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
            group.add(_furniture_object(node, f, taken))
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
    taken = {n.name for n in model.root.walk()}
    for i, floor in enumerate(house.floors):
        content = build_floor(floor, is_top=(i == len(house.floors) - 1),
                              taken=taken)
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
    from . import library, mesh
    wall = str(wall).strip().upper()
    if wall not in _WALL_RZ:
        raise HouseError(f"'wall' must be one of N, S, E, W — not "
                         f"{wall!r}.")
    tris = mesh.tessellate(library.build_part(part_id, dict(dims)), fn=8)
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
    return Furniture(part_id, x, y, rz, dims, z=_num(spec, "z", 0.0),
                     name=str(spec.get("name") or ""))


def _opening_from_spec(spec: dict) -> Opening:
    if not isinstance(spec, dict):
        raise HouseError("Each opening must be an object.")
    kind = str(spec.get("kind", "door")).strip().lower()
    if kind not in ("door", "window"):
        raise HouseError(f"Opening 'kind' must be door or window, not "
                         f"{kind!r}.")
    side = str(spec.get("side", "S")).strip().upper()
    if side not in SIDES:
        raise HouseError(f"Opening 'side' must be one of N, S, E, W — "
                         f"not {side!r}.")
    w, h, sill = DOOR_SIZE if kind == "door" else WINDOW_SIZE
    return Opening(kind, side, _num(spec, "offset", 0.0),
                   _num(spec, "width", w), _num(spec, "height", h),
                   _num(spec, "sill", sill))


def house_from_spec(spec: dict) -> House:
    """A `House` from a JSON-shaped *spec* (the build_house tool's
    input): floors -> rooms -> openings / furniture, plus an optional
    garden. Furniture x/y are measured from its room's (x, y) corner,
    or resolved by `against_wall` when it names a `wall`."""
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
            room = Room(str(rspec.get("name") or f"Room {j + 1}"),
                        _num(rspec, "x", 0.0), _num(rspec, "y", 0.0),
                        _num(rspec, "w"), _num(rspec, "d"))
            if room.w <= 0 or room.d <= 0:
                raise HouseError(f'Room "{room.name}" needs a positive '
                                 "w and d.")
            room.openings = [_opening_from_spec(o)
                             for o in rspec.get("openings") or []]
            floor.rooms.append(room)
        for room, rspec in zip(floor.rooms, rooms_in):
            room.furniture = [_furniture_from_spec(f, room, floor)
                              for f in rspec.get("furniture") or []]
        floors.append(floor)
    garden = spec.get("garden")
    if garden:
        garden = Garden(width=_num(garden, "width", Garden.width),
                        depth=_num(garden, "depth", Garden.depth),
                        gap=_num(garden, "gap", Garden.gap))
    return House(floors=floors, garden=garden or None)


def build_house(window, params: dict) -> dict:
    """The build_house MCP tool: `house_from_spec` then `apply`, with
    every resolved placement reported back so the caller can check it
    without a render."""
    house = house_from_spec(params or {})
    floors = []
    for floor in house.floors:
        if not floor.rooms:
            raise HouseError(f'"{floor.name}" has no rooms.')
        floors.append({
            "name": floor.name,
            "walls": len(collect_walls(floor)),
            "rooms": [{"name": r.name, "x": r.x, "y": r.y, "w": r.w,
                       "d": r.d, "openings": len(r.openings),
                       "furniture": [{"part_id": f.part_id,
                                      "x": round(f.x, 1),
                                      "y": round(f.y, 1),
                                      "z": f.z, "rz": f.rz}
                                     for f in r.furniture]}
                      for r in floor.rooms]})
    if params.get("dry_run"):
        return {"dry_run": True, "floors": floors}
    inserted = apply(window.model, house)
    window.view3d.fit()
    return {"objects": [{"id": c.id, "name": c.name,
                         "contains": [n.name for n in c.walk()
                                      if n.type == "component"
                                      and n is not c]}
                        for c in inserted],
            "floors": floors}
