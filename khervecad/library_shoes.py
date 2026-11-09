"""Library ▸ Everyday things ▸ **Shoes**: every `shoe_design` preset as
a Part Library part — pumps, boots, sandals, loafers, Oxfords and
original sneakers — sized by EU size, coloured by the colour combo
(the upper's colour). The Shoe Builder (`shoe_dialog`) makes any other.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

CATEGORY = "Shoes"

WOMEN_SIZES = {f"EU {n}": {"size": n} for n in range(35, 43)}
MEN_SIZES = {f"EU {n}": {"size": n} for n in range(39, 48)}


def _build(name, dims):
    from . import shoe_design
    spec = {"preset": name}
    size = dims.get("size")
    if size:
        spec["size"] = size
    col = dims.get("_color")
    if col and col in shoe_design.COLOURS:
        spec["upper_colour"] = col
    return shoe_design.build(spec)


def _slug(name):
    return "shoe_" + "".join(c if c.isalnum() else "_"
                             for c in name.lower()).strip("_")


def _parts():
    from . import shoe_design
    parts = {}
    for name, preset in shoe_design.PRESETS.items():
        men = preset.get("gender") == "Men"
        sizes = MEN_SIZES if men else WOMEN_SIZES
        default = "EU 43" if men else "EU 38"
        ordered = {default: sizes[default]}
        ordered.update(sizes)
        colours = [preset.get("upper_colour", "Black")] + [
            c for c in shoe_design.COLOURS
            if c != preset.get("upper_colour")]
        parts[_slug(name)] = dict(
            label=name, category=CATEGORY,
            build=lambda dims, n=name: _build(n, dims),
            sizes=ordered, fields=[], colors=colours)
    return parts


PARTS = _parts()
