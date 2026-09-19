"""The **Leaves** library (Library ▸ Buildings & places ▸ Nature &
garden ▸ Leaves): one real leaf of each species from `leafgen`, at true
size, in its summer, autumn or spring colour — simple blades, palmate
and compound leaves, needles, scale sprays and a palm frond.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import copy
from functools import lru_cache

from . import leafgen
from .city_buildings import _f

CATEGORY = "Leaves"


@lru_cache(maxsize=128)
def _cached(species, season, size, detail):
    return leafgen.build(species, season, size, detail)


def _builder(species):
    def build(dims):
        size = _f(dims.get("size"), 0.0)
        detail = "low" if _f(dims.get("detail"), 2) < 1 else (
            "medium" if _f(dims.get("detail"), 2) < 2 else "high")
        return copy.deepcopy(_cached(species, dims.get("_color") or "Summer",
                                     size, detail))
    return build


def _size_field(sp):
    if sp["kind"] == "palm":
        return sp["R"]
    return sp.get("L", 0.0)


def _sizes(sp):
    base = _size_field(sp)
    if sp["kind"] in ("strip", "palm"):
        return {"Typical": dict(size=base, detail=2),
                "Large": dict(size=round(base * 1.4), detail=2),
                "Small": dict(size=round(base * 0.7), detail=2)}
    return {"Typical": dict(size=base, detail=2)}


PARTS = {}
for _key, _sp in leafgen.SPECIES.items():
    _fields = [("detail", "Detail (0 low, 1 medium, 2 high)")]
    if _sp["kind"] in ("strip", "palm"):
        _fields.insert(0, ("size", "Length" if _sp["kind"] == "strip"
                           else "Radius"))
    _evergreen = len(set(_sp["colours"][:2])) == 1
    PARTS[f"leaf_{_key}"] = dict(
        label=f"{_sp['name']} leaf" if _sp["kind"] not in (
            "fascicle", "shoot", "spur", "scales", "frond") else
        {"fascicle": f"{_sp['name']} needles", "shoot":
         f"{_sp['name']} shoot", "spur": f"{_sp['name']} needle tuft",
         "scales": f"{_sp['name']} spray", "frond": _sp["name"]}[
            _sp["kind"]],
        category=CATEGORY, sizes=_sizes(_sp), fields=_fields,
        colors=(["Summer", "Spring"] if _evergreen
                else list(leafgen.SEASONS)),
        build=_builder(_key))

COUNT_FIELDS = {"detail"}
