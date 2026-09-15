"""Crystals in the Part Library: every structure of the crystal library
as a ready UNIT CELL (its atoms, lattice box and coordination
polyhedra) and a SUPERCELL (2 x 2 x 2 to 6 x 6 x 6 cells), so the
Library menu, the Part Library dialog and an assistant's list_parts /
insert_part start from a real crystal instead of typing atoms.

Built by crystal_build with the counts written in (`inline`): a library
part lands inside an enclosing Object, and an OpenSCAD module cannot
see variables left beside it — the supercell would render nothing. In
nanometres; `prepare` (called by every insert path through
`library.prepare_document`) switches an empty document to nm first.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import crystal_build as cb
from .crystal_library import LIBRARY

UNIT_CELLS = "Crystals (unit cells)"
SUPERCELLS = "Crystals (supercells)"
#: dialog fields holding a count (integer spin box)
COUNT_FIELDS = {"cells"}
SIZES = {f"{n}x{n}x{n}": {"cells": n} for n in (2, 3, 4, 6)}
#: most cells per edge a library supercell takes (8^3 metal atoms
#: already cost ~250k triangles)
MAX_CELLS = 8


def build(key: str, supercell: bool, dims: dict):
    """The unit cell or supercell of library crystal *key*, as one group
    (its Object inside), in nm."""
    from .model import CadNode
    from .scadparse import parse_scad
    crystal = LIBRARY[key]
    n = max(1, min(int(round(float(dims.get("cells", 3)))), MAX_CELLS))
    spec = cb.Spec(crystal, build="supercell" if supercell else "unit_cell",
                   supercell=(n, n, n), inline=True)
    code, _stats = cb.program(spec)
    root, _warnings = parse_scad(code)
    name = f"{crystal.name} {'supercell' if supercell else 'unit cell'}"
    group = CadNode("union", name, {})
    for child in list(root.children):
        root.remove(child)
        group.add(child)
    return group


def prepare(model) -> str:
    """Before a crystal lands: an empty document becomes nanometres and
    round objects drop to 12 segments (atoms by the hundred). Returns
    what changed, or why a millimetre document will read it wrong."""
    notes = []
    if model.unit != "nm":
        if not model.root.children:
            model.set_unit("nm")
            notes.append("The document is now in nanometres, like crystal "
                         "parts.")
        else:
            notes.append(f"Crystal parts are in nanometres but this "
                         f"document is in {model.unit}: a 0.5 nm cell reads "
                         f"as 0.5 {model.unit}. Start a new document for "
                         "crystals.")
    if model.global_fn_on and model.global_fn > 12:
        model.set_global_fn(True, 12)
        notes.append("Round objects now use 12 segments, so atoms stay "
                     "light.")
    return " ".join(notes)


PARTS = {}
for _key, _crystal in LIBRARY.items():
    PARTS[f"crystal_{_key}"] = dict(
        label=_crystal.name, category=UNIT_CELLS, sizes={}, fields=[],
        unit="nm", prepare=prepare,
        build=lambda dims, k=_key: build(k, False, dims))
for _key, _crystal in LIBRARY.items():
    PARTS[f"supercell_{_key}"] = dict(
        label=_crystal.name, category=SUPERCELLS, sizes=SIZES,
        fields=[("cells", "Cells per edge")], unit="nm", prepare=prepare,
        build=lambda dims, k=_key: build(k, True, dims))
