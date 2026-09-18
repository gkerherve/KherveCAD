"""Carbon nanostructures in the Part Library: graphene (sheets, stacks,
twisted bilayers, nanoribbons, a quantum dot, defects) and the graphite
(0001) surface under Surfaces, nanotubes under Crystals, and the
fullerenes (C20, C60, C70, C80) under Molecules, in nanometres (the
crystals' `prepare` sets an empty document up). Sheets, stacks and
graphite are graphene_build's parametric loops; the rest are
carbon_nano's atoms drawn by the Compound Builder's writer.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import carbon_nano as cn
from .library_crystal import prepare

GRAPHENE = "Surfaces: Graphene & graphite"
NANOTUBES = "Crystals (nanotubes)"
FULLERENES = "Molecules: Fullerenes"
#: integer dialog fields (named apart from every other part's)
COUNT_FIELDS = {"tube_n", "tube_m", "tube_walls", "sheet_layers"}
_NM = " nm"


def _f(dims, key, default):
    try:
        return float(dims.get(key, default))
    except (TypeError, ValueError):
        return default


def _i(dims, key, default):
    return int(round(_f(dims, key, default)))


def _group(m, style):
    """The structure as one group (its Object inside)."""
    from . import molecule_build as mb
    from .library_molecule import _group as group
    try:                # the document drops to 12 segments anyway
        code, _stats = mb.molecule_program(m, style, fn=12)
    except mb.BuildError:
        code, _stats = mb.molecule_program(m, style, fn=8)
    return group(code, m.name)


def _part(label, category, build, sizes=None, fields=(), suffixes=None):
    """A part drawn with small balls (sheets and tubes), or ball and
    stick for the fullerene cages."""
    style = "ball_and_stick" if category == FULLERENES else "lattice"
    return dict(label=label, category=category, sizes=sizes or {},
                fields=list(fields), unit="nm", prepare=prepare,
                suffixes=suffixes or {}, build=lambda dims: _group(
                    build(dims), style))


_AREA = {"2 x 2 nm": dict(width=2.0, depth=2.0),
         "3 x 3 nm": dict(width=3.0, depth=3.0),
         "4 x 4 nm": dict(width=4.0, depth=4.0),
         "5 x 3 nm": dict(width=5.0, depth=3.0)}
_AREA_FIELDS = [("width", "Width"), ("depth", "Depth")]
_AREA_NM = {"width": _NM, "depth": _NM}


def _loop_part(label, sizes, fields, suffixes, **fixed):
    """A graphene / graphite part written as loops (graphene_build)."""
    def build(dims):
        from . import graphene_build as gb
        from .library_molecule import _group as group
        kw = dict(fixed)
        for key in ("width", "depth", "twist"):
            if key in dims:
                kw[key] = _f(dims, key, 3.0)
        if "sheet_layers" in dims:
            kw["layers"] = _i(dims, "sheet_layers", kw.get("layers", 1))
        code, stats = gb.program(**kw)
        return group(code, stats["name"])
    return dict(label=label, category=GRAPHENE, sizes=sizes,
                fields=list(fields), unit="nm", prepare=prepare,
                suffixes=suffixes, build=build)


def _sheet(label, layers, stacking):
    return _loop_part(label, _AREA, _AREA_FIELDS, _AREA_NM, layers=layers,
                      stacking=stacking)


PARTS = {
    "graphene_sheet": _sheet("Graphene (single layer)", 1, "AB"),
    "graphene_bilayer_ab": _sheet("Bilayer graphene (AB, Bernal)", 2, "AB"),
    "graphene_bilayer_aa": _sheet("Bilayer graphene (AA, eclipsed)", 2,
                                  "AA"),
    "graphene_trilayer_aba": _sheet("Trilayer graphene (ABA)", 3, "ABA"),
    "graphene_trilayer_abc": _sheet("Trilayer graphene (ABC, "
                                    "rhombohedral)", 3, "ABC"),
    "graphene_twisted": _loop_part(
        "Twisted bilayer graphene",
        {"21.8° (smallest moiré)": dict(width=3.0, depth=3.0, twist=21.79),
         "13.2°": dict(width=3.5, depth=3.5, twist=13.17),
         "9.4°": dict(width=4.0, depth=4.0, twist=9.43),
         "5.1°": dict(width=5.0, depth=5.0, twist=5.09)},
        _AREA_FIELDS + [("twist", "Twist")], dict(_AREA_NM, twist=" °"),
        layers=2),
    "graphene_ribbon_armchair": _part(
        "Armchair graphene nanoribbon", GRAPHENE,
        lambda d: cn.nanoribbon("armchair", _f(d, "width", 1.0),
                                _f(d, "length", 4.0)),
        {"1 x 4 nm": dict(width=1.0, length=4.0),
         "0.7 x 3 nm": dict(width=0.7, length=3.0),
         "1.5 x 6 nm": dict(width=1.5, length=6.0)},
        [("width", "Width"), ("length", "Length")],
        {"width": _NM, "length": _NM}),
    "graphene_ribbon_zigzag": _part(
        "Zigzag graphene nanoribbon", GRAPHENE,
        lambda d: cn.nanoribbon("zigzag", _f(d, "width", 1.0),
                                _f(d, "length", 4.0)),
        {"1 x 4 nm": dict(width=1.0, length=4.0),
         "0.7 x 3 nm": dict(width=0.7, length=3.0),
         "1.5 x 6 nm": dict(width=1.5, length=6.0)},
        [("width", "Width"), ("length", "Length")],
        {"width": _NM, "length": _NM}),
    "graphene_quantum_dot": _part(
        "Graphene quantum dot", GRAPHENE,
        lambda d: cn.quantum_dot(_f(d, "diameter", 2.0)),
        {"2 nm": dict(diameter=2.0), "1.2 nm": dict(diameter=1.2),
         "3 nm": dict(diameter=3.0)},
        [("diameter", "Diameter")], {"diameter": _NM}),
    "graphene_vacancy": _part(
        "Graphene with a vacancy", GRAPHENE,
        lambda d: cn.defect_sheet("vacancy", _f(d, "width", 3),
                                  _f(d, "depth", 3)),
        _AREA, _AREA_FIELDS, _AREA_NM),
    "graphene_n_doped": _part(
        "Nitrogen-doped graphene", GRAPHENE,
        lambda d: cn.defect_sheet("nitrogen", _f(d, "width", 3),
                                  _f(d, "depth", 3)),
        _AREA, _AREA_FIELDS, _AREA_NM),
    "graphite_surface": _loop_part(
        "Graphite (0001) surface (HOPG)",
        {"3 x 3 nm, 4 layers": dict(width=3.0, depth=3.0, sheet_layers=4),
         "2 x 2 nm, 3 layers": dict(width=2.0, depth=2.0, sheet_layers=3),
         "4 x 4 nm, 3 layers": dict(width=4.0, depth=4.0, sheet_layers=3)},
        _AREA_FIELDS + [("sheet_layers", "Layers")], _AREA_NM,
        kind="graphite", layers=4),
    "graphite_step": _loop_part(
        "Graphite (0001) surface with a step",
        {"3 x 3 nm, 4 layers": dict(width=3.0, depth=3.0, sheet_layers=4),
         "4 x 3 nm, 3 layers": dict(width=4.0, depth=3.0, sheet_layers=3)},
        _AREA_FIELDS + [("sheet_layers", "Layers")], _AREA_NM,
        kind="graphite", layers=4, step=True),
    "nanotube_armchair": _part(
        "Armchair nanotube (n, n)", NANOTUBES,
        lambda d: cn.nanotube(_i(d, "tube_n", 5), _i(d, "tube_n", 5),
                              _f(d, "length", 3)),
        {"(5, 5), 3 nm": dict(tube_n=5, length=3.0),
         "(6, 6), 3 nm": dict(tube_n=6, length=3.0),
         "(10, 10), 3 nm": dict(tube_n=10, length=3.0),
         "(5, 5), 6 nm": dict(tube_n=5, length=6.0)},
        [("tube_n", "n"), ("length", "Length")], {"length": _NM}),
    "nanotube_zigzag": _part(
        "Zigzag nanotube (n, 0)", NANOTUBES,
        lambda d: cn.nanotube(_i(d, "tube_n", 9), 0, _f(d, "length", 3)),
        {"(9, 0), 3 nm": dict(tube_n=9, length=3.0),
         "(10, 0), 3 nm": dict(tube_n=10, length=3.0),
         "(18, 0), 3 nm": dict(tube_n=18, length=3.0)},
        [("tube_n", "n"), ("length", "Length")], {"length": _NM}),
    "nanotube_chiral": _part(
        "Chiral nanotube (n, m)", NANOTUBES,
        lambda d: cn.nanotube(_i(d, "tube_n", 6), _i(d, "tube_m", 4),
                              _f(d, "length", 3)),
        {"(6, 4), 3 nm": dict(tube_n=6, tube_m=4, length=3.0),
         "(8, 4), 3 nm": dict(tube_n=8, tube_m=4, length=3.0),
         "(10, 5), 3 nm": dict(tube_n=10, tube_m=5, length=3.0),
         "(7, 2), 3 nm": dict(tube_n=7, tube_m=2, length=3.0)},
        [("tube_n", "n"), ("tube_m", "m"), ("length", "Length")],
        {"length": _NM}),
    "nanotube_multiwall": _part(
        "Multi-walled nanotube", NANOTUBES,
        lambda d: cn.nanotube(_i(d, "tube_n", 5), _i(d, "tube_n", 5),
                              _f(d, "length", 2), _i(d, "tube_walls", 3)),
        {"3 walls (5,5)@(10,10)@(15,15), 2 nm":
            dict(tube_n=5, tube_walls=3, length=2.0),
         "2 walls (5,5)@(10,10), 3 nm":
            dict(tube_n=5, tube_walls=2, length=3.0),
         "2 walls (8,8)@(13,13), 2 nm":
            dict(tube_n=8, tube_walls=2, length=2.0)},
        [("tube_n", "Inner n (armchair)"), ("tube_walls", "Walls"),
         ("length", "Length")], {"length": _NM}),
    "nanotube_capped": _part(
        "Capped nanotube (5, 5)", NANOTUBES,
        lambda d: cn.capped_nanotube(_f(d, "length", 3)),
        {"3 nm": dict(length=3.0), "2 nm": dict(length=2.0),
         "5 nm": dict(length=5.0)},
        [("length", "Length")], {"length": _NM}),
}

PARTS.update({
    f"fullerene_{key}": _part(name, FULLERENES,
                              lambda d, k=key: cn.fullerene(k))
    for key, (name, _cat, _build) in cn.STRUCTURES.items()
})
