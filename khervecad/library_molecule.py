"""Compounds in the Part Library: every molecule of the compound library
as a ready part ("Molecules: <family>"), ball and stick, in nanometres,
so the Library menu, the Part Library dialog and an assistant's
list_parts / insert_part start from a real molecule. The document
set-up is the crystals' (`library_crystal.prepare`): an empty document
becomes nanometres, round objects drop to 12 segments.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from .library_crystal import prepare
from .molecule_library import COMPOUNDS, get

PREFIX = "Molecules: "


def build(key: str, _dims: dict):
    """The library molecule *key* as one group (its Object inside)."""
    from . import molecule_build as mb
    from .model import CadNode
    from .scadparse import parse_scad
    m = get(key)
    code, _stats = mb.molecule_program(m)
    root, _warnings = parse_scad(code)
    group = CadNode("union", m.name, {})
    for child in list(root.children):
        root.remove(child)
        group.add(child)
    return group


PARTS = {
    f"molecule_{key}": dict(
        label=name, category=PREFIX + category, sizes={}, fields=[],
        unit="nm", prepare=prepare,
        build=lambda dims, k=key: build(k, dims))
    for key, (name, _smiles, category, _formula) in COMPOUNDS.items()
}
