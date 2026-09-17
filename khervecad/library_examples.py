"""Example models that are really parts: the flowers and the stylised
trees of the Examples menu as Library parts ("Flowers", "Stylised
trees"), so a rose or a palm drops into a design as one Object instead
of replacing the document. Like the Lego sets, each is built by its
example's own function (lazy import: examples imports the library), so
the two never drift apart.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from .model import CadNode

#: example category -> library category its models are listed under
CATEGORIES = {"Flowers": "Flowers", "Trees": "Stylised trees"}

#: part id -> (library category, Examples label)
MODELS = {
    "flower_layered": ("Flowers", "Flower (layered bloom)"),
    "flower_sunflower": ("Flowers", "Sunflower (phyllotaxis)"),
    "flower_tulip": ("Flowers", "Tulip"),
    "flower_rose": ("Flowers", "Rose"),
    "flower_daisy": ("Flowers", "Daisy"),
    "flower_lily": ("Flowers", "Lily"),
    "flower_daffodil": ("Flowers", "Daffodil"),
    "flower_calla": ("Flowers", "Calla lily"),
    "flower_poppy": ("Flowers", "Poppy"),
    "flower_hibiscus": ("Flowers", "Hibiscus"),
    "flower_orchid": ("Flowers", "Orchid"),
    "flower_cherry": ("Flowers", "Cherry blossom"),
    "stylised_pine": ("Stylised trees", "Pine / conifer"),
    "stylised_oak": ("Stylised trees", "Oak"),
    "stylised_palm": ("Stylised trees", "Palm"),
    "stylised_willow": ("Stylised trees", "Weeping willow"),
    "stylised_birch": ("Stylised trees", "Silver birch"),
    "stylised_cherry": ("Stylised trees", "Cherry blossom tree"),
}


def build_model(label, category):
    """The example *label*'s model as one node: its root's lone child,
    or all of them gathered into a group named after it."""
    from .examples import EXAMPLES
    source = next(c for c, lib in CATEGORIES.items() if lib == category)
    build = next(b for name, cat, b in EXAMPLES
                 if name == label and cat == source)
    root = build()
    children = list(root.children)
    for child in children:
        root.remove(child)
    if len(children) == 1:
        return children[0]
    group = CadNode("union", label, {})
    for child in children:
        group.add(child)
    return group


PARTS = {
    pid: dict(label=label, category=category, sizes={}, fields=[],
              build=lambda _dims, label=label, category=category:
              build_model(label, category))
    for pid, (category, label) in MODELS.items()
}
