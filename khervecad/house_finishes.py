"""What a House Builder house is finished with (Qt-free): the outside
walls, the walls between rooms, window and door joinery, a room's
tiling and its floor — and the choices made for a room nobody chose
for, from its name (a bathroom is tiled, a bedroom carpeted).

Every look is a (colour, material) pair, and the materials are the
shader's SURFACES (glrender): bricks, metro tiles, marble, floorboards
are drawn per pixel from world millimetres, so a whole tiled bathroom
costs no more triangles than a painted one.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import zlib

WALL_COLOR = "#f2efe9"

#: how the OUTSIDE of the house is finished: name -> (colour, material)
WALL_STYLES = {
    "Painted plaster": (WALL_COLOR, "Render"),
    "White render": ("#f5f3ee", "Render"),
    "Cream render": ("#e8dfc9", "Render"),
    "Grey render": ("#b9b9b4", "Render"),
    "Red brick": ("#9c5a45", "Brick"),
    "Buff brick": ("#c9a879", "Brick"),
    "Yellow stock brick": ("#c8a66a", "Brick"),
    "Brown brick": ("#7a4a35", "Brick"),
    "Blue engineering brick": ("#4d4e56", "Brick"),
    "Painted brick": ("#ece8df", "Brick"),
    "Grey stone": ("#a9a8a3", "Stone"),
    "Cotswold stone": ("#d2b77f", "Stone"),
    "Timber cladding": ("#a4794a", "Cladding"),
    "Grey cladding": ("#7d8488", "Cladding"),
    "White weatherboard": ("#eeeeea", "Cladding"),
    "Concrete": ("#bdbdb8", "Concrete"),
}
#: how the walls BETWEEN rooms (and the inside of the outer walls) are
#: finished
INNER_WALL_STYLES = {
    "Painted plaster": (WALL_COLOR, "Plaster"),
    "Warm white": ("#f6f1e7", "Plaster"),
    "Soft grey": ("#d9dbdd", "Plaster"),
    "Sage": ("#c7d2c0", "Plaster"),
    "Duck egg": ("#c9dcd8", "Plaster"),
    "Clay pink": ("#e3cfc4", "Plaster"),
    "Mustard": ("#d9b765", "Plaster"),
    "Navy": ("#3f4d63", "Plaster"),
    "Exposed brick": ("#9c5a45", "Brick"),
}

#: the details an outside finish comes with: the head over a window
#: ("stone" lintel, "brick" soldier course, "timber" trim, "none"), the
#: plinth at the foot of the wall and the window sills
OUTSIDE_DETAIL = {
    "brick": dict(head="brick", plinth=("#5a4a44", "Brick"),
                  sill=("#dcd7cb", "Render")),
    "stone": dict(head="stone", plinth=("#8f8d86", "Stone"),
                  sill=("#dcd7cb", "Render")),
    "render": dict(head="none", plinth=("#6f6f6c", "Render"),
                   sill=("#e2e0da", "Render")),
    "cladding": dict(head="timber", plinth=("#6f6f6c", "Render"),
                     sill=("#3b3f44", "Metal")),
    "concrete": dict(head="none", plinth=("#8c8c88", "Concrete"),
                     sill=("#9a9a96", "Render")),
}
_DETAIL_OF = {"Brick": "brick", "Stone": "stone", "Render": "render",
              "Cladding": "cladding", "Concrete": "concrete"}


def outside_detail(style: str) -> dict:
    """The head, plinth and sill that go with outside finish *style*."""
    material = WALL_STYLES.get(style, WALL_STYLES["Painted plaster"])[1]
    return OUTSIDE_DETAIL[_DETAIL_OF.get(material, "render")]


#: window frames and door linings: name -> (colour, material)
JOINERY = {
    "White": ("#f4f4f1", "Plastic"),
    "Anthracite grey": ("#3a3e43", "Plastic"),
    "Black": ("#232427", "Plastic"),
    "Oak": ("#9a6e3f", "Default"),
    "Sage green": ("#8b9c86", "Plastic"),
    "Cream": ("#ebe4d0", "Plastic"),
}
#: the joinery an outside finish looks right with, when none is chosen
_AUTO_JOINERY = {"brick": "White", "stone": "Sage green",
                 "render": "Anthracite grey", "cladding": "Black",
                 "concrete": "Anthracite grey"}


def joinery_for(choice: str, outside: str):
    """(colour, material) of the window frames: *choice* from JOINERY,
    or "" for the one that suits the *outside* finish."""
    if choice in JOINERY:
        return JOINERY[choice]
    material = WALL_STYLES.get(outside, WALL_STYLES["Painted plaster"])[1]
    return JOINERY[_AUTO_JOINERY.get(_DETAIL_OF.get(material), "White")]


#: front doors, picked per house so a street is not one colour
FRONT_DOORS = ("#2e4a3f", "#1f3550", "#7a2327", "#2a2b2e", "#56656d",
               "#8a6a3a", "#4b3a5a", "#e8e4da")
INTERIOR_DOOR = ("#f2f0ea", "Plastic")
GARAGE_DOORS = ("#d8dadd", "#3a3e43", "#8a6234", "#f2f1ec")
SKIRTING = ("#f3f2ee", "Plastic")
THRESHOLD = ("#9a7a52", "Default")

#: a room's own wall lining and the floor that goes with it:
#: name -> ((wall colour, material), (floor colour, material))
ROOM_FINISHES = {
    "White tiles": (("#eef1f2", "Wall tiles"), ("#c9c9c6", "Floor tiles")),
    "White metro tiles": (("#f3f3ef", "Metro tiles"),
                          ("#ebe8e0", "Checker tiles")),
    "Green metro tiles": (("#bcd6c2", "Metro tiles"),
                          ("#e9e6df", "Hex tiles")),
    "Black metro tiles": (("#2e3134", "Metro tiles"),
                          ("#efefec", "Hex tiles")),
    "Blue tiles": (("#bcd3e0", "Wall tiles"), ("#9fb9c8", "Floor tiles")),
    "Blue mosaic": (("#6a9ec2", "Mosaic"), ("#d9dcdc", "Floor tiles")),
    "Green zellige": (("#4f8a7a", "Zellige"), ("#e8e3da", "Terrazzo")),
    "Pink zellige": (("#e2b6a8", "Zellige"), ("#ece6dc", "Terrazzo")),
    "Hexagon tiles": (("#f2f2ef", "Wall tiles"), ("#efefec", "Hex tiles")),
    "Marble": (("#eceae4", "Marble"), ("#d8d4cc", "Marble")),
    "Grey porcelain": (("#bdbcb8", "Floor tiles"),
                       ("#a9a8a4", "Floor tiles")),
    "Terracotta tiles": (("#efe9dd", "Wall tiles"),
                         ("#b8674a", "Floor tiles")),
    "Wood panelling": (("#b98f5e", "Panelling"), ("#8a6234", "Floorboards")),
}
#: an explicit "no lining" choice (the empty string means automatic)
NO_FINISH = "None"

#: floor coverings: name -> (colour, material)
FLOORINGS = {
    "Oak floorboards": ("#b58a58", "Floorboards"),
    "Walnut floorboards": ("#6f4a2e", "Floorboards"),
    "Grey oak": ("#9d968c", "Floorboards"),
    "Oak parquet": ("#a87a4a", "Parquet"),
    "Grey carpet": ("#8e8b86", "Carpet"),
    "Beige carpet": ("#c2b39c", "Carpet"),
    "Blue carpet": ("#5d6f86", "Carpet"),
    "Grey porcelain": ("#a9a8a4", "Floor tiles"),
    "Stone tiles": ("#cbc3b2", "Floor tiles"),
    "Slate tiles": ("#4b5057", "Floor tiles"),
    "Terracotta": ("#b8674a", "Floor tiles"),
    "Checkerboard": ("#ebe8e0", "Checker tiles"),
    "Hexagon tiles": ("#efefec", "Hex tiles"),
    "Terrazzo": ("#e8e3da", "Terrazzo"),
    "Marble": ("#d8d4cc", "Marble"),
    "Polished concrete": ("#a7a6a1", "Render"),
    "Vinyl": ("#d4d0c6", "Plastic"),
}
#: the covering's depth over the slab, mm
FLOOR_THICKNESS = 20.0
#: a tile lining's depth off the plaster, mm
TILE_THICKNESS = 10.0

#: how far up the walls a room is tiled: "full" (floor to ceiling),
#: "half" (to HALF_TILE), "wet" (half, and full height behind a bath or
#: shower), "splash" (a band behind worktops and sinks)
HALF_TILE = 1200.0
SPLASH = (900.0, 1500.0)

_KINDS = (
    ("shower", ("shower", "wet room", "wetroom")),
    ("bath", ("bath", "en-suite", "ensuite", "en suite")),
    ("toilet", ("toilet", "wc", "cloak", "lavatory", "powder")),
    ("kitchen", ("kitchen", "kitchenette", "scullery")),
    ("utility", ("utility", "laundry", "boot room")),
    ("garage", ("garage", "workshop", "carport")),
    ("bedroom", ("bed", "nursery", "kids", "guest", "dressing")),
    ("hall", ("hall", "entrance", "porch", "lobby", "landing",
              "corridor", "stair", "reception")),
    ("living", ("living", "lounge", "sitting", "family", "snug", "dining",
                "study", "office", "library", "den", "playroom")),
    ("lab", ("lab", "server", "store", "plant", "meeting", "break")),
)


def room_kind(name: str) -> str:
    """What a room is used for, read from its *name*."""
    low = (name or "").lower()
    for kind, words in _KINDS:
        if any(w in low for w in words):
            return kind
    return "other"


def _pick(options, *key) -> str:
    """One of *options*, the same every time for the same *key*."""
    h = zlib.crc32(repr(key).encode())
    return options[h % len(options)]


_AUTO_FINISHES = {
    "bath": ("White metro tiles", "Marble", "Green metro tiles",
             "Blue mosaic", "Hexagon tiles", "Green zellige",
             "White tiles", "Black metro tiles"),
    "shower": ("White metro tiles", "Grey porcelain", "Blue mosaic",
               "Marble", "Black metro tiles"),
    "toilet": ("White tiles", "Green metro tiles", "Pink zellige",
               "White metro tiles"),
    "kitchen": ("White metro tiles", "Green zellige", "White tiles",
                "Black metro tiles", "Pink zellige", "Grey porcelain"),
    "utility": ("White tiles", "White metro tiles"),
}
_AUTO_FLOORS = {
    "kitchen": ("Grey porcelain", "Checkerboard", "Terracotta",
                "Stone tiles", "Oak floorboards", "Slate tiles"),
    "utility": ("Vinyl", "Grey porcelain", "Slate tiles"),
    "garage": ("Polished concrete",),
    "bedroom": ("Grey carpet", "Beige carpet", "Blue carpet",
                "Oak floorboards", "Grey oak"),
    "hall": ("Checkerboard", "Oak parquet", "Stone tiles",
             "Oak floorboards", "Terrazzo"),
    "living": ("Oak floorboards", "Oak parquet", "Walnut floorboards",
               "Grey oak", "Beige carpet"),
    "lab": ("Vinyl", "Polished concrete"),
    "other": ("Oak floorboards", "Grey oak"),
}
_COVERAGE = {"bath": "wet", "shower": "full", "toilet": "half",
             "kitchen": "splash", "utility": "splash"}


def finish_of(room) -> str | None:
    """The ROOM_FINISHES lining *room* gets: its own choice, else one
    that suits its name (a bathroom is tiled), or None."""
    if room.finish == NO_FINISH:
        return None
    if room.finish in ROOM_FINISHES:
        return room.finish
    options = _AUTO_FINISHES.get(room_kind(room.name))
    return _pick(options, room.name, room.x, room.y) if options else None


def coverage_of(room) -> str:
    """How far up *room*'s walls its lining goes (see HALF_TILE)."""
    kind = room_kind(room.name)
    if kind in _COVERAGE:
        return _COVERAGE[kind]
    if room.finish == "Wood panelling":
        return "half"
    return "full"


def flooring_of(room):
    """(colour, material) of *room*'s floor: its own flooring, else the
    floor of its finish when it chose one, else one suiting its name."""
    if room.flooring in FLOORINGS:
        return FLOORINGS[room.flooring]
    if room.finish in ROOM_FINISHES:
        return ROOM_FINISHES[room.finish][1]
    kind = room_kind(room.name)
    finish = finish_of(room)
    if finish is not None and kind in ("bath", "shower", "toilet"):
        return ROOM_FINISHES[finish][1]
    options = _AUTO_FLOORS.get(kind, _AUTO_FLOORS["other"])
    return FLOORINGS[_pick(options, "floor", room.name, room.x, room.y)]


def front_door(*key) -> str:
    return _pick(FRONT_DOORS, "door", *key)


#: part ids (substrings) a room is tiled behind: full height behind a
#: bath or a shower, a splashback behind worktops and sinks
WET_PARTS = ("bath", "shower")
SPLASH_PARTS = ("kitchen", "sink", "washbasin", "dishwasher",
                "washing_machine", "worktop", "cooker", "hob")
