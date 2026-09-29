"""Monsters for PlanetCraft in the parts library (2026-09-29) — Library ▸
Toys & models ▸ Monsters: every preset of creature_build at real size,
already jointed for the game. Insert one, change it however you like
(keeping each piece inside its part's group), then File ▸ Send to
PlanetCraft; it remembers what it is, how fast and how strong.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from . import creature_build

CATEGORY = "Monsters"


def build(name, dims=None):
    """The preset *name* as one node, jointed for PlanetCraft."""
    node, _spec, _parts = creature_build.node_of({"preset": name})
    return node


def _slug(name):
    return "monster_" + "".join(c if c.isalnum() else "_"
                                for c in name.lower()).strip("_")


PARTS = {_slug(name): dict(
    label=f"{name} ({p['blurb']})", category=CATEGORY,
    sizes={f"Real size ({p['height'] / 1000:.1f} m)": {}}, fields=[],
    build=lambda dims, n=name: build(n, dims))
    for name, p in creature_build.PRESETS.items()}
