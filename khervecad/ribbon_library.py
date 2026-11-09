"""The ribbon's LIBRARY tab (2026-11-09, the user: "I think we should
have a library tab, because this is really a big thing").

Nothing is built twice: every button IS a submenu of the Library menu
(its `menuAction`), so the tab and the menu always offer the same parts
— a subject added to `library_groups.SECTIONS` shows up here by itself.
One panel per section of the menu:

- `lib_parts` — Part Library (customise), My Library, OpenSCAD libraries;
- `lib_0` … — Engineering, Buildings & places, Science, Toys & models,
  Everyday things: one button per subject, opening its list;
- `lib_learn` — the example documents (Learn, Course projects, Showcase).

A click opens the subject's list; a click on a part adds it to the
document as one Object. Icons are painted per style (icons_cad_library).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import language
from .library_groups import SECTIONS

#: the tab's panels, in order
PANELS = ["lib_parts"] + ["lib_%d" % i for i in range(len(SECTIONS))] \
    + ["lib_learn"]

#: subject (as library_groups names it) -> painted icon key
ICONS = {
    "Fasteners & brackets": "lib_fasteners", "Hand tools": "lib_tools",
    "Vacuum & UHV": "lib_vacuum", "Mechanisms & motion": "lib_mechanisms",
    "Motion & motors": "lib_motors", "Electronics": "lib_electronics",
    "Air conditioning": "lib_aircon", "3D printing": "lib_printing",
    "Mechanical examples": "lib_mechanisms",
    "House & home": "lib_home", "City": "lib_city", "Sport": "lib_sport",
    "Nature & garden": "lib_nature",
    "Chemistry lab": "lib_chemistry", "Crystals": "lib_crystals",
    "Surfaces": "lib_surfaces", "Molecules": "lib_molecules",
    "Solar System": "lib_solar",
    "Lego": "lib_lego", "Lego Technic": "lib_technic",
    "Animals": "lib_animals", "Monsters": "lib_monsters",
    "People & characters": "lib_people", "Minecraft": "lib_minecraft",
    "Generative": "lib_generative", "Games": "lib_games",
    "Cars": "lib_cars", "Vehicles": "lib_vehicles",
    "Playing cards": "lib_cards",
    "Kitchen & tableware": "lib_kitchen",
    "Musical instruments": "lib_music", "Shoes": "lib_shoes",
    "Art": "lib_art", "Custom objects": "lib_custom",
    "My Library": "lib_mine",
    "Learn OpenSCAD, step by step": "lib_learn",
    "Course projects": "lib_learn", "Showcase models": "lib_showcase",
}
GENERIC = "lib_generic"
LEARN_NOTE = ("Example documents. One opens as a document, IN PLACE of "
              "yours — save your work first.")
PART_NOTE = ("Click to open the list, then a part to add it to the "
             "document. It lands as one Object you can move, colour, "
             "snap to others and open to edit.")


def _plain(text):
    return str(text).replace("&&", "\0").replace("&", "").replace("\0", "&")


def _names():
    """Menu title (translated, as shown) -> the subject's English name."""
    from .library_menu import EXAMPLE_PLACES
    names = [name for _t, entries in SECTIONS for name, _i, _s in entries]
    names += [title for _w, title, _i, _c in EXAMPLE_PLACES]
    names += ["My Library"]
    return {str(language.tr(n)): n for n in names}


def title_of(key):
    if key == "lib_parts":
        return language.tr("Parts")
    if key == "lib_learn":
        return language.tr("Learn")
    return language.tr(SECTIONS[int(key[4:])][0])


def panel(win, key):
    """(title, actions) of the Library tab's panel *key*."""
    menu = getattr(win, "_library_menu", None)
    if menu is None:
        return title_of(key), []
    names = _names()
    groups, header = {"lib_parts": []}, -1
    current = "lib_parts"
    for act in menu.actions():
        if act.isSeparator():
            continue
        if not act.isEnabled() and act.menu() is None:
            header += 1                    # a section's title line
            current = "lib_%d" % header if header < len(SECTIONS) \
                else "lib_learn"
            continue
        groups.setdefault(current, []).append(act)
    acts = groups.get(key, [])
    for act in acts:
        name = names.get(_plain(act.text()))
        if act.menu() is not None:
            if not act.property("kc_paint"):
                act.setProperty("kc_paint", ICONS.get(name, GENERIC))
            if "<" not in (act.toolTip() or ""):
                act.setToolTip("<b>%s</b><br>%s" % (
                    _plain(act.text()),
                    language.tr(LEARN_NOTE if key == "lib_learn"
                                else PART_NOTE)))
        elif not act.property("kc_paint") and not isinstance(act.data(),
                                                             str):
            # Part Library…, OpenSCAD Libraries…
            act.setProperty("kc_paint", "part_library" if "Part" in
                            act.text() else "lib_scad")
            if "<" not in (act.toolTip() or ""):
                act.setToolTip("<b>%s</b><br>%s" % (
                    _plain(act.text()).rstrip("."), language.tr(
                        "Every library part in one window: search, set "
                        "its sizes and colour, then Insert."
                        if "Part" in act.text() else
                        "BOSL2, MCAD, NopSCADlib and other OpenSCAD "
                        "libraries: install one, then use it from "
                        "OpenSCAD code.")))
    return title_of(key), acts
