"""The **Stones** library (Nature & garden, beside Trees and Leaves):
pebbles, river cobbles, flat skipping stones, broken rocks, boulders,
standing stones and flagstones at true size, a pebble scatter, a gravel
patch and a cairn — `stonegen`'s star-shaped closed polyhedra, sitting
on the ground, in a choice of rock (granite, sandstone, limestone,
basalt, slate, marble, red sandstone, mossy) or a river mix where every
stone has its own tone.

Each part has three standard sizes and a Shape number that grows a
different stone of the same kind.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import random

from . import stonegen
from .city_buildings import _f, color, group
from .treegen import Mesh

CATEGORY = "Stones"
COUNT_FIELDS = {"seed", "count"}
COLOR_NAMES = list(stonegen.COLOURS)

#: kind -> (size name, longest dimension mm) x 3
SIZES = {
    "pebble": (("Small (25 mm)", 25), ("Medium (50 mm)", 50),
               ("Large (90 mm)", 90)),
    "cobble": (("Small (12 cm)", 120), ("Medium (20 cm)", 200),
               ("Large (30 cm)", 300)),
    "skipping": (("Small (6 cm)", 60), ("Medium (9 cm)", 90),
                 ("Large (12 cm)", 120)),
    "angular": (("Small (30 cm)", 300), ("Medium (80 cm)", 800),
                ("Large (1.5 m)", 1500)),
    "boulder": (("Small (60 cm)", 600), ("Medium (1.2 m)", 1200),
                ("Large (2.5 m)", 2500)),
    "menhir": (("Low (1.5 m)", 1500), ("Standard (3 m)", 3000),
               ("Tall (5 m)", 5000)),
    "flagstone": (("Small (40 cm)", 400), ("Medium (60 cm)", 600),
                  ("Large (1 m)", 1000)),
}


def _tone(hexcol, factor):
    r, g, b = (int(hexcol[i:i + 2], 16) for i in (1, 3, 5))
    r, g, b = (max(0, min(255, int(c * factor))) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def _material(name):
    return "Marble" if name == "Marble" else "Stone"


def _tones(name, rng, n=3):
    """*n* colours for one part: shades of the rock, or the river mix."""
    if name == "River mix":
        return [rng.choice(stonegen.RIVER_MIX) for _ in range(n)]
    base = stonegen.COLOURS.get(name, stonegen.COLOURS["Granite grey"])
    return [_tone(base, f) for f in (0.92, 1.0, 1.08)[:n]]


def _single(kind):
    def build(dims):
        rng = random.Random(int(_f(dims.get("seed"), 1)))
        name = dims.get("_color") or COLOR_NAMES[0]
        mesh = Mesh()
        stonegen.stone(mesh, rng, kind, _f(dims.get("size"),
                                           SIZES[kind][1][1]))
        label = stonegen.KINDS[kind]["label"].split(" (")[0]
        return group(label, [color(mesh.node("Stone"),
                                   _tones(name, rng, 1)[0],
                                   _material(name), name="Stone")])
    return build


def _scatter(kind, default_count, sizes, level):
    """Many stones over a disc: a pebble beach, gravel, a rock garden."""
    def build(dims):
        rng = random.Random(int(_f(dims.get("seed"), 1)))
        name = dims.get("_color") or COLOR_NAMES[0]
        area = _f(dims.get("size"), 600.0)
        count = max(1, int(_f(dims.get("count"), default_count)))
        meshes = [Mesh(), Mesh(), Mesh()]
        kinds = ("pebble", "cobble") if kind != "rocks" else (
            "angular", "boulder", "cobble")
        low, high = sizes(area)
        stonegen.scatter(lambda i: meshes[i % 3], rng, count, area,
                         (low, high), kinds, level=level)
        parts = [color(m.node("Stones"), c, _material(name), name="Stones")
                 for m, c in zip(meshes, _tones(name, rng)) if m.faces]
        return group({"pebbles": "Pebble scatter", "gravel": "Gravel patch",
                      "rocks": "Rock garden"}[kind], parts)
    return build


def _cairn(dims):
    rng = random.Random(int(_f(dims.get("seed"), 1)))
    name = dims.get("_color") or COLOR_NAMES[0]
    mesh = Mesh()
    stonegen.cairn(mesh, rng, _f(dims.get("size"), 600.0),
                   max(2, int(_f(dims.get("count"), 6))))
    return group("Cairn", [color(mesh.node("Stones"),
                                 _tones(name, rng, 1)[0], _material(name),
                                 name="Stones")])


PARTS = {}
for _kind, _sizes in SIZES.items():
    _rec = stonegen.KINDS[_kind]
    PARTS[f"stone_{_kind}"] = dict(
        label=_rec["label"], category=CATEGORY,
        sizes={n: dict(size=s, seed=1) for n, s in _sizes},
        fields=[("size", "Longest side"), ("seed", "Shape")],
        colors=COLOR_NAMES, build=_single(_kind))

PARTS["stone_pebbles"] = dict(
    label="Pebble scatter", category=CATEGORY, colors=COLOR_NAMES,
    sizes={"Small patch (60 cm)": dict(size=600, count=30, seed=1),
           "Medium patch (1.5 m)": dict(size=1500, count=90, seed=1),
           "Large patch (4 m)": dict(size=4000, count=240, seed=1)},
    fields=[("size", "Diameter"), ("count", "Stones"), ("seed", "Shape")],
    build=_scatter("pebbles", 60, lambda a: (max(a * 0.02, 20.0),
                                             max(a * 0.09, 60.0)), 2))
PARTS["stone_gravel"] = dict(
    label="Gravel patch", category=CATEGORY, colors=COLOR_NAMES,
    sizes={"Small patch (60 cm)": dict(size=600, count=90, seed=1),
           "Medium patch (1.5 m)": dict(size=1500, count=220, seed=1),
           "Large patch (4 m)": dict(size=4000, count=420, seed=1)},
    fields=[("size", "Diameter"), ("count", "Stones"), ("seed", "Shape")],
    build=_scatter("gravel", 120, lambda a: (max(a * 0.008, 8.0),
                                             max(a * 0.022, 24.0)), 1))
PARTS["stone_rocks"] = dict(
    label="Rock garden (mixed rocks)", category=CATEGORY,
    colors=COLOR_NAMES,
    sizes={"Small (2 m)": dict(size=2000, count=8, seed=1),
           "Medium (5 m)": dict(size=5000, count=14, seed=1),
           "Large (12 m)": dict(size=12000, count=24, seed=1)},
    fields=[("size", "Diameter"), ("count", "Rocks"), ("seed", "Shape")],
    build=_scatter("rocks", 14, lambda a: (max(a * 0.05, 200.0),
                                           max(a * 0.24, 700.0)), 3))
PARTS["stone_cairn"] = dict(
    label="Cairn (balanced stack)", category=CATEGORY, colors=COLOR_NAMES,
    sizes={"Small (30 cm)": dict(size=300, count=5, seed=1),
           "Medium (60 cm)": dict(size=600, count=6, seed=1),
           "Large (1.2 m)": dict(size=1200, count=8, seed=1)},
    fields=[("size", "Base stone"), ("count", "Stones"), ("seed", "Shape")],
    build=_cairn)
