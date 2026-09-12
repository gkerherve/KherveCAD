"""The Lego sets: the brick-built models of examples_lego as parts of
the library (the "Lego sets" category), so a finished set drops into an
assembly as one Object — next to a flange or another set — instead of
replacing the document the way an example does.

A set is built by the same function as its example and lifted out of
that example's document root, so the two never drift apart. The import
of examples is lazy: examples imports the library (fasteners), and the
library imports this module.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

CATEGORY = "Lego sets"

#: part id -> the Examples-menu label of the model it builds
SETS = {
    "lego_set_tower": "Minecraft tower",
    "lego_set_house": "House",
    "lego_set_church": "Church",
    "lego_set_building": "Apartment building",
    "lego_set_dragon": "Dragon",
    "lego_set_man": "Man (Minecraft style)",
    "lego_set_woman": "Woman (Minecraft style)",
    "lego_set_man_small": "Man (Minecraft style, small)",
    "lego_set_woman_small": "Woman (Minecraft style, small)",
}


def build_set(label):
    """The model the example *label* builds, lifted out of its root."""
    from .examples import EXAMPLES
    build = next(b for name, _cat, b in EXAMPLES if name == label)
    root = build()
    model = root.children[0]
    root.remove(model)
    return model


PARTS = {
    pid: dict(label=label, category=CATEGORY, sizes={}, fields=[],
              build=lambda _dims, label=label: build_set(label))
    for pid, label in SETS.items()
}
