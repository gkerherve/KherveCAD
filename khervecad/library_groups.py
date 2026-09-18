"""How the Library is organised (Qt-free): every part category placed
in a themed section, so the Library menu and the Part Library dialog
read the same way instead of listing categories in the order modules
happened to register them.

A section is (title, [(menu title, icon, categories or special)]): a
menu with one category lists its parts directly, several get a submenu
each; a special ("home", "city", "lego", "crystals", "surfaces",
"molecules", "vacuum") also
carries its builder on top. `test_library_menu` checks every category
of `library.PARTS` is placed exactly once.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

SECTIONS = [
    ("Engineering", [
        ("Fasteners & brackets", "mdi.screw-machine-flat-top",
         ["Fasteners", "Brackets"]),
        ("Hand tools", "mdi.hammer-wrench", ["Tools"]),
        ("Vacuum & UHV", "mdi.pipe", ("vacuum", ["Vacuum"])),
        ("Mechanisms & motion", "mdi.cogs", ["Mechanisms & motion"]),
        ("Motion & electronics", "mdi.cog-transfer-outline",
         ["Motion & motors", "Electronics boards"]),
        ("3D printing", "mdi.printer-3d",
         ["Printed joints & hinges", "Printed organisers", "Enclosures",
          "Prusa"]),
    ]),
    ("Buildings & places", [
        ("House & home", "mdi.home-city-outline",
         ("home", ["Finished houses", "Finished labs",
                   "Home furniture",
                   "Room & furniture"])),
        ("City", "mdi.city-variant-outline",
         ("city", ["Buildings", "Landmarks", "Skyscrapers", "Bridges",
                   "Park & sport", "Lighting & signals"])),
        ("Nature & garden", "mdi.flower-outline",
         ["Trees", "Stylised trees", "Flowers", "Landscape", "Pots"]),
    ]),
    ("Science", [
        ("Chemistry lab", "mdi.flask-outline", ["Chemistry"]),
        ("Crystals", "mdi.atom", ("crystals", [
            "Crystals (unit cells)", "Crystals (supercells)",
            "Crystals (nanotubes)"])),
        ("Surfaces", "mdi.layers-outline", ("surfaces", "Surfaces: ")),
        ("Molecules", "mdi.molecule", ("molecules", "Molecules: ")),
        ("Solar System", "mdi.orbit",
         ["Solar System models", "Planets", "Moons"]),
    ]),
    ("Toys & models", [
        ("Lego", "mdi.toy-brick-outline", ("lego", ["Lego", "Lego sets"])),
        ("Lego Technic", "mdi.cog-outline", ["Lego Technic"]),
        ("Minecraft", "mdi.cube-outline", ["Minecraft"]),
        ("Generative", "mdi.chart-bubble", ["Generative"]),
        ("Cars", "mdi.car-sports", ("cars", ["Cars (from blueprints)",
                                            "Cars"])),
        ("Playing cards", "mdi.cards-playing-outline", ["Playing cards"]),
    ]),
    ("Everyday things", [
        ("Kitchen & tableware", "mdi.silverware-fork-knife",
         ["Kitchen & tableware"]),
        ("Musical instruments", "mdi.music", ["Musical instruments"]),
    ]),
]

#: how a category reads inside its menu when the menu title already
#: says what it is
SHORT_NAMES = {"Lego": "Bricks & plates",
               "Crystals (unit cells)": "Unit cells",
               "Crystals (supercells)": "Supercells",
               "Crystals (nanotubes)": "Carbon nanotubes",
               "Stylised trees": "Stylised trees",
               "Trees": "Grown trees"}


def entry_categories(spec, all_categories):
    """(special or None, [categories]) of one menu entry's *spec*."""
    if isinstance(spec, tuple):
        special, cats = spec
        if isinstance(cats, str):               # a prefix
            cats = [c for c in all_categories if c.startswith(cats)]
        return special, list(cats)
    return None, list(spec)


def category_order(all_categories):
    """Every category in Library order (unplaced ones last)."""
    order = []
    for _title, entries in SECTIONS:
        for _name, _icon, spec in entries:
            for cat in entry_categories(spec, all_categories)[1]:
                if cat in all_categories and cat not in order:
                    order.append(cat)
    return order + [c for c in all_categories if c not in order]


def short_name(category: str) -> str:
    for prefix in ("Molecules: ", "Surfaces: "):
        if category.startswith(prefix):
            return category[len(prefix):]
    return SHORT_NAMES.get(category, category)
