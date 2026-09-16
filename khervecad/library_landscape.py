"""The **Landscape** library: terrain from `terrain.py` — rolling hills,
a snow-capped mountain, a cliff (escarpment with rock strata), a river
valley, a desert mesa, an island in the sea, a canyon with its river,
sand dunes — and boulders and rock outcrops to dress them.

Each size sets the area and the relief; the Shape number grows a
different landscape of the same kind, Detail is the grid (cells a side).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import random

from . import terrain
from .city_buildings import _f, color, group
from .model import CadNode
from .treegen import Mesh

CATEGORY = "Landscape"
COUNT_FIELDS = {"seed", "cells"}

#: kind -> (label, relief as a fraction of the side)
KINDS = {
    "hills": ("Rolling hills", 0.12),
    "mountain": ("Mountain (snow-capped)", 0.45),
    "cliff": ("Cliff / escarpment", 0.22),
    "valley": ("River valley", 0.2),
    "mesa": ("Desert mesa", 0.18),
    "island": ("Island", 0.15),
    "canyon": ("Canyon with river", 0.25),
    "dunes": ("Sand dunes", 0.06),
}
AREAS = {"Small (100 m)": 100000.0, "Medium (250 m)": 250000.0,
         "Large (600 m)": 600000.0}


def _builder(kind):
    def build(dims):
        return terrain.build(kind, length=_f(dims.get("length"), 250000),
                             width=_f(dims.get("width"), 250000),
                             height=_f(dims.get("height"), 30000),
                             seed=int(_f(dims.get("seed"), 1)),
                             cells=int(_f(dims.get("cells"), 64)))
    return build


def _entry(kind):
    label, relief = KINDS[kind]
    sizes = {name: dict(length=side, width=side, height=round(side * relief),
                        seed=1, cells=64 if side < 500000 else 96)
             for name, side in AREAS.items()}
    return dict(label=label, category=CATEGORY, sizes=sizes,
                build=_builder(kind),
                fields=[("length", "Length"), ("width", "Width"),
                        ("height", "Relief"), ("seed", "Shape"),
                        ("cells", "Detail (cells)")])


def build_rocks(dims):
    """A boulder or an outcrop: irregular lumps in two stone tones."""
    size = _f(dims.get("size"), 2000)
    count = max(1, int(_f(dims.get("count"), 1)))
    rng = random.Random(int(_f(dims.get("seed"), 1)))
    light, dark = Mesh(), Mesh()
    for k in range(count):
        r = size / 2 * (1.0 if k == 0 else rng.uniform(0.3, 0.8))
        spread = size * 0.9 if count > 1 else 0.0
        c = (rng.uniform(-spread, spread), rng.uniform(-spread, spread),
             r * 0.55)
        (light if k % 2 == 0 else dark).clump(rng, c, r)
    parts = []
    for m, colour in ((light, "#8e867b"), (dark, "#6f675d")):
        if m.faces:
            parts.append(color(m.node("Rock"), colour, "Stone"))
    return group("Rock outcrop" if count > 1 else "Boulder", parts)


PARTS = {f"land_{k}": _entry(k) for k in KINDS}
PARTS["land_boulder"] = dict(
    label="Boulder", category=CATEGORY, build=build_rocks,
    sizes={"Small (0.8 m)": dict(size=800, count=1, seed=1),
           "Large (2.5 m)": dict(size=2500, count=1, seed=1)},
    fields=[("size", "Size"), ("seed", "Shape")])
PARTS["land_outcrop"] = dict(
    label="Rock outcrop", category=CATEGORY, build=build_rocks,
    sizes={"Small (4 m)": dict(size=2500, count=6, seed=2),
           "Large (10 m)": dict(size=6000, count=9, seed=2)},
    fields=[("size", "Size"), ("count", "Rocks"), ("seed", "Shape")])
COUNT_FIELDS |= {"count"}
