"""Surfaces in the Part Library: every crystal of the crystal library
cut along its usual low-index faces — cubic (100) (110) (111),
hexagonal and trigonal (0001) (10-10) (11-20), tetragonal (001) (100)
(110) (101) — as ready slabs (Library ▸ Surfaces, one part per face,
grouped by family), built by crystal_surface with the counts written
in (`inline`). Graphite is the exception: its surface, and graphene,
are library_carbon's bonded loops in "Surfaces: Graphene & graphite".

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import crystal_build as cb
from . import crystal_surface as cs
from .crystal_library import LIBRARY
from .library_crystal import prepare

PREFIX = "Surfaces: "
#: integer dialog fields
COUNT_FIELDS = {"surf_repeat", "surf_layers"}
SIZES = {"6 x 6 cells, 3 layers": dict(surf_repeat=6, surf_layers=3),
         "4 x 4 cells, 2 layers": dict(surf_repeat=4, surf_layers=2),
         "10 x 10 cells, 3 layers": dict(surf_repeat=10, surf_layers=3)}
FIELDS = [("surf_repeat", "Cells each way"), ("surf_layers", "Layers")]
#: crystals whose surface lives elsewhere
SKIP = {"graphite"}


def faces(crystal):
    """The usual low-index faces of *crystal*, as Miller strings."""
    system = crystal.system.lower()
    if system.startswith(("hex", "trig")):
        return ("0001", "10-10", "11-20")
    if system.startswith("tetra"):
        return ("001", "100", "110", "101")
    return ("100", "110", "111")


def build(key: str, miller: str, dims: dict):
    """The (hkl) slab of library crystal *key*, as one group; a size
    past the budget is cut down (fewer cells) rather than refused."""
    from .model import CadNode
    from .scadparse import parse_scad
    try:
        repeat = int(round(float(dims.get("surf_repeat", 6))))
        layers = int(round(float(dims.get("surf_layers", 3))))
    except (TypeError, ValueError):
        repeat, layers = 6, 3
    repeat = max(1, min(repeat, cs.MAX_REPEAT))
    layers = max(1, min(layers, 60))
    while True:
        spec = cs.SurfaceSpec(crystal=LIBRARY[key],
                              miller=cs.parse_miller(miller),
                              repeat=(repeat, repeat), layers=layers,
                              inline=True)
        try:
            code, stats = cs.program(spec)
            break
        except cb.BuildError:
            if repeat == 1 and layers == 1:
                raise
            if repeat > 1:
                repeat -= 1
            else:
                layers -= 1
    root, _warnings = parse_scad(code)
    group = CadNode("union", stats["surface"], {})
    for child in list(root.children):
        root.remove(child)
        group.add(child)
    return group


def crystal_of(label: str) -> str:
    """The Library submenu of a face: its crystal ("Copper (111)" ->
    "Copper"), so a family lists crystals, each with its faces."""
    return label.rsplit(" (", 1)[0]


#: submenu order: the crystal library's own
CRYSTAL_ORDER = [c.name for c in LIBRARY.values()]


def _label(crystal, miller):
    return cs.label(crystal, cs.parse_miller(miller))


PARTS = {}
for _key, _crystal in LIBRARY.items():
    if _key in SKIP:
        continue
    for _miller in faces(_crystal):
        PARTS[f"surface_{_key}_{_miller.replace('-', 'm')}"] = dict(
            label=_label(_crystal, _miller),
            category=PREFIX + _crystal.category,
            sizes=SIZES, fields=FIELDS, unit="nm", prepare=prepare,
            build=lambda dims, k=_key, m=_miller: build(k, m, dims))

CATEGORIES = sorted({spec["category"] for spec in PARTS.values()})
