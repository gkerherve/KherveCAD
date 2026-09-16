"""The **Trees** library: every species `treegen` grows — oak, maple,
lime, silver birch, cherry blossom, apple, weeping willow, Lombardy
poplar, Scots pine, Norway spruce, Italian cypress, palm and a shrub —
with real branches and individual leaves, at three sizes, in any season
(deciduous trees turn spring-green, autumn-orange or bare in winter)
and with a Variation number that grows a different tree of the same
species.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import treegen

CATEGORY = "Trees"
COUNT_FIELDS = {"seed"}

#: size name -> fraction of the species' natural height
AGES = {"Young": 0.5, "Mature": 1.0, "Old / tall": 1.4}


def _builder(species):
    def build(dims):
        season = dims.get("_color") or "Summer"
        if season not in treegen.SEASONS:
            season = "Summer"
        node = treegen.build(species, height=float(dims.get("h", 0.0)),
                             season=season, detail="high",
                             seed=int(dims.get("seed", 1) or 1))
        return node
    return build


def _entry(species):
    sp = treegen.SPECIES[species]
    sizes = {f"{age} ({sp['height'] * k / 1000:.0f} m)":
             dict(h=round(sp["height"] * k), seed=1)
             for age, k in AGES.items()}
    entry = dict(label=sp["label"], category=CATEGORY, sizes=sizes,
                 build=_builder(species),
                 fields=[("h", "Height"), ("seed", "Variation")])
    if species not in treegen.EVERGREEN:
        entry["colors"] = list(treegen.SEASONS)
    return entry


PARTS = {f"tree_{k}": _entry(k) for k in treegen.SPECIES}
