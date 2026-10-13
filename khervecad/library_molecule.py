"""Compounds in the Part Library: every molecule of the compound library
as a ready part ("Molecules: <family>"), ball and stick, and every
preset peptide of the Protein Builder ("Molecules: Proteins & peptides",
a cartoon with its side chains), in nanometres, so the Library menu, the Part Library dialog and an assistant's
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
from .protein_build import PRESETS as PROTEIN_PRESETS

PREFIX = "Molecules: "


def _group(code, name):
    from .model import CadNode
    from .scadparse import parse_scad
    root, _warnings = parse_scad(code)
    group = CadNode("union", name, {})
    for child in list(root.children):
        root.remove(child)
        group.add(child)
    return group


def build(key: str, _dims: dict):
    """The library molecule *key* as one group (its Object inside)."""
    from . import molecule_build as mb
    m = get(key)
    code, _stats = mb.molecule_program(m)
    return _group(code, m.name)


def build_protein(key: str, _dims: dict):
    """The Protein Builder preset *key* as one group."""
    from . import protein_build as pb
    p = pb.preset(key)
    code, _stats = pb.protein_program(p, "cartoon_sticks")
    return _group(code, p.name)


PARTS = {
    f"molecule_{key}": dict(
        label=name, category=PREFIX + category, sizes={}, fields=[],
        unit="nm", prepare=prepare,
        build=lambda dims, k=key: build(k, dims))
    for key, (name, _smiles, category, _formula) in COMPOUNDS.items()
}

PROTEIN_CATEGORY = PREFIX + "Proteins & peptides"
PARTS.update({
    f"protein_{key}": dict(
        label=name, category=PROTEIN_CATEGORY, sizes={}, fields=[],
        unit="nm", prepare=prepare,
        build=lambda dims, k=key: build_protein(k, dims))
    for key, (name, *_rest) in PROTEIN_PRESETS.items()
})


# ------------------------------------------------------------ polymers
#: a polymer part's repeat-unit count is a whole number
COUNT_FIELDS = {"units"}
POLYMER_PREFIX = PREFIX + "Polymers: "


def build_polymer(key: str, dims: dict):
    """The polymer preset *key*, `units` repeat units, as one group."""
    from . import molecule_build as mb
    from . import polymers
    name, unit, n, _cat, (head, tail) = polymers.preset(key)
    n = max(1, int(round(float(dims.get("units", n)))))
    m = polymers.build_chain(unit, min(n, polymers.max_units(unit, head,
                                                             tail)),
                             head, tail)
    m.name = f"{name} ({n} units)"
    code, _stats = mb.molecule_program(m)
    return _group(code, m.name)


def _polymer_parts():
    from . import polymers
    out = {}
    for key, (name, _unit, n, cat, _caps) in polymers.PRESETS.items():
        # the preset's own length first: the first size is the default
        sizes = {f"{k} units": {"units": k}
                 for k in [n] + sorted({2, 4, 8} - {n})}
        out[f"polymer_{key}"] = dict(
            label=name, category=POLYMER_PREFIX + cat, sizes=sizes,
            fields=[("units", "Repeat units")],
            unit="nm", prepare=prepare,
            build=lambda dims, k=key: build_polymer(k, dims))
    return out


PARTS.update(_polymer_parts())
