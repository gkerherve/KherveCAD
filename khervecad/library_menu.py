"""The Library menu (built from `library_groups`).

Library = things you ADD to your design, in themed sections
(Engineering, Buildings & places, Science, Toys & models); each subject
menu carries its builder (House, City, Lego, Crystal, Surface, Compound)
on top.
The example documents — which REPLACE yours — live in it too, where
they belong (2026-09-17, the Examples menu merged in): the technique
demos under Engineering, the vacuum starter in Vacuum & UHV, the desk
setup in House & home, and the lessons, course projects and showcase
models in a closing LEARN section. Each example submenu says it opens as
a document.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import (icons, library_kcad, library_kitchen, library_lego_parts,
               library_music, library_surfaces)
from .library_groups import SECTIONS, entry_categories, short_name

#: category -> function(label) -> submenu name, for a category whose
#: parts split into a further level (Hand tools' 57 items read as one
#: unbroken flat list); GROUP_ORDER gives that submenu's own order.
GROUPED_CATEGORIES = {"Tools": library_kcad.tool_group,
                      "Lego": library_lego_parts.group_of,
                      library_music.CATEGORY: library_music.group_of,
                      library_kitchen.CATEGORY: library_kitchen.group_of}
GROUP_ORDER = {"Tools": library_kcad.TOOL_GROUP_ORDER,
               "Lego": library_lego_parts.GROUP_ORDER,
               library_music.CATEGORY: library_music.GROUP_ORDER,
               library_kitchen.CATEGORY: library_kitchen.GROUP_ORDER}
for _cat in library_surfaces.CATEGORIES:     # each crystal with its faces
    GROUPED_CATEGORIES[_cat] = library_surfaces.crystal_of
    GROUP_ORDER[_cat] = library_surfaces.CRYSTAL_ORDER

#: where the example documents go: (section, submenu title, icon,
#: example categories) — a submenu title already in that section gets
#: the examples at its end, else a new submenu is added
EXAMPLE_PLACES = [
    ("Engineering", "Mechanical examples", "mdi.cog-outline",
     ["Mechanical"]),
    ("Engineering", "Vacuum & UHV", "mdi.pipe", ["Vacuum"]),
    ("Buildings & places", "House & home", "mdi.home-city-outline",
     ["Room"]),
    ("Learn", "Learn OpenSCAD, step by step", "mdi.school-outline",
     ["Learn"]),
    ("Learn", "Course projects", "mdi.book-open-variant", ["Projects"]),
    ("Learn", "Showcase models", "mdi.star-outline", ["Showcase"]),
]

#: library categories House & home lists as a submenu each, after the
#: rooms (they are kinds of furniture, not pieces of one room)
HOME_CATEGORY_MENUS = ["Tables", "Bookshelves", "Doors", "Appliances",
                       "Ceiling lights"]

#: the note on top of an example submenu
EXAMPLE_NOTE = "Opens as a document, in place of yours"


def menu_text(text) -> str:
    """*text* as a Qt menu title: a lone "&" marks the shortcut letter."""
    return str(text).replace("&", "&&")


def _header(menu, text):
    """A section title: a greyed, unclickable line (menu sections lose
    their text in the macOS menu bar)."""
    menu.addSeparator()
    act = menu.addAction(menu_text(text.upper()))
    act.setEnabled(False)


def build_library_menu(window, menubar):
    from .library import PARTS
    menu = menubar.addMenu("&Library")
    menu.addAction(icons.icon("mdi.toy-brick-outline"),
                   "Part Library (customise)...", window.open_library,
                   "Ctrl+L")
    menu.addAction(icons.icon("mdi.bookshelf"),
                   "OpenSCAD Libraries (BOSL2, MCAD...)...",
                   window._open_scad_libraries)
    from .user_library_dialog import add_menu
    add_menu(window, menu)
    by_cat = {}
    for pid, spec in PARTS.items():
        by_cat.setdefault(spec.get("category", "Other"), []).append(pid)
    placed = set()
    sections = [title for title, _entries in SECTIONS]
    sections = list(dict.fromkeys(sections + [s for s, *_rest
                                              in EXAMPLE_PLACES]))
    entries_of = dict(SECTIONS)
    for title in sections:
        _header(menu, title)
        subs = {}
        for name, icon, spec in entries_of.get(title, []):
            special, cats = entry_categories(spec, list(by_cat))
            cats = [c for c in cats if c in by_cat]
            placed.update(cats)
            if not cats:
                continue
            if special == "home":
                subs[name] = _home_menu(window, menu, PARTS, cats)
                continue
            sub = subs[name] = menu.addMenu(icons.icon(icon),
                                            menu_text(name))
            if special:
                _BUILDERS[special](window, sub)
            if len(cats) == 1:            # straight into the menu
                _add_parts(window, sub, by_cat[cats[0]], PARTS,
                          category=cats[0])
                continue
            for cat in cats:
                _add_parts(window, sub.addMenu(menu_text(short_name(cat))),
                           by_cat[cat], PARTS, category=cat)
        _add_examples(window, menu, title, subs)
    # My Library has its own live submenu (user_library_dialog)
    rest = [c for c in by_cat if c not in placed
            and not c.startswith("My library")]
    if rest:
        _header(menu, "Other")
        for cat in rest:
            _add_parts(window, menu.addMenu(menu_text(cat)), by_cat[cat],
                       PARTS)
    return menu


def _add_parts(window, sub, ids, parts, category=None):
    grouper = GROUPED_CATEGORIES.get(category)
    if grouper is None:
        for pid in ids:
            sub.addAction(
                menu_text(parts[pid]["label"]),
                lambda _=False, p=pid: window._insert_library_part(p))
        return
    groups = {}
    for pid in ids:
        groups.setdefault(grouper(parts[pid]["label"]), []).append(pid)
    order = GROUP_ORDER.get(category, [])
    names = [n for n in order if n in groups] + \
        sorted(n for n in groups if n not in order)
    for name in names:
        target = sub.addMenu(menu_text(name))
        for pid in groups[name]:
            target.addAction(
                menu_text(parts[pid]["label"]),
                lambda _=False, p=pid: window._insert_library_part(p))


def _lego(window, sub):
    from . import lego_builder, lego_convert
    sub.addAction(icons.icon("mdi.toy-brick-outline"), "Lego Builder...",
                  lambda: lego_builder.open_builder(window))
    sub.addAction(icons.icon("mdi.toy-brick-plus-outline"),
                  "Convert Selection to Lego...",
                  lambda: lego_convert.convert_to_lego(window))
    sub.addAction(icons.icon("mdi.cube-outline"), "Fuse Lego into One Solid",
                  lambda: lego_convert.fuse_lego(window))
    sub.addSeparator()


def _city(window, sub):
    """The City Builder and quick random layouts; a build replaces the
    last one. Assistants use build_city."""
    from . import city, city_dialog
    sub.addAction(icons.icon("mdi.city-variant-outline"), "City Builder...",
                  lambda: city_dialog.open_builder(window))

    def build(layout):
        seed = getattr(window, "_city_seed", 0) + 1
        window._city_seed = seed
        city.apply(window.model, {"layout": layout, "seed": seed})
        window.view3d.fit()
        panel = getattr(window, "_city_builder", None)
        if panel is not None:
            panel.load_from_document()

    new = sub.addMenu("New layout (random)")
    for layout in ("village", "town", "city"):
        new.addAction(layout.capitalize(),
                      lambda _=False, lay=layout: build(lay))
    sub.addSeparator()


def _cars(window, sub):
    """The Car Builder (paint, wheels, tyres) on top; the cars
    themselves follow as one-click parts."""
    from . import car_dialog
    sub.addAction(icons.icon("mdi.car-sports"), "Car Builder...",
                  lambda: car_dialog.open_builder(window))
    sub.addSeparator()


def _people(window, sub):
    from . import human_dialog
    sub.addAction(icons.icon("mdi.human-edit"), "Human Builder...",
                  lambda: human_dialog.open_builder(window))
    sub.addSeparator()


def _crystals(window, sub):
    from . import crystal_dialog
    sub.addAction(icons.icon("mdi.molecule"), "Crystal Builder...",
                  lambda: crystal_dialog.open_builder(window))
    sub.addSeparator()


def _surfaces(window, sub):
    """The Surface Builder (any crystal, any (hkl)) on top; graphene,
    graphite and every crystal's usual faces follow as parts."""
    from . import crystal_surface_dialog
    sub.addAction(icons.icon("mdi.layers-outline"), "Surface Builder...",
                  lambda: crystal_surface_dialog.open_builder(window))
    sub.addSeparator()


def _molecules(window, sub):
    from . import molecule_dialog
    sub.addAction(icons.icon("mdi.atom"), "Compound Builder...",
                  lambda: molecule_dialog.open_builder(window))
    sub.addSeparator()


def _vacuum(window, sub):
    from . import chamber_dialog
    sub.addAction(icons.icon("mdi.pipe"), "Chamber Designer...",
                  lambda: chamber_dialog.open_designer(window))
    sub.addSeparator()


_BUILDERS = {"people": _people, "vacuum": _vacuum, "cars": _cars, "lego": _lego, "city": _city, "crystals": _crystals,
             "surfaces": _surfaces,
             "molecules": _molecules}


def _home_menu(window, menu, parts, categories):
    """House & home: the House Builder on top, then every home and room
    piece in a submenu per room — the House Builder's own catalogue, so
    the menu and the builder offer the same things — and whatever no
    room lists under Fixtures & other."""
    from . import house_dialog
    from .house import FURNITURE_CATALOG
    home = menu.addMenu(icons.icon("mdi.home-city-outline"), "House && home")
    home.addAction(icons.icon("mdi.home-city-outline"), "House Builder...",
                   lambda: house_dialog.open_builder(window))
    home.addSeparator()
    finished = [pid for pid, spec in parts.items()      # the built designs
                if spec.get("category") in ("Finished houses", "Houses")]
    if finished:
        _add_parts(window, home.addMenu(icons.icon("mdi.home-outline"),
                                        "Finished houses"), finished, parts)
        home.addSeparator()
    labs = [pid for pid, spec in parts.items()
            if spec.get("category") == "Finished labs"]
    if labs:
        _add_parts(window, home.addMenu(icons.icon("mdi.microscope"),
                                        "Finished labs"), labs, parts)
        home.addSeparator()
    commercial = [pid for pid, spec in parts.items()
                  if spec.get("category") == "Finished commercial"]
    if commercial:
        _add_parts(window, home.addMenu(icons.icon("mdi.storefront-outline"),
                                        "Finished commercial"),
                   commercial, parts)
        home.addSeparator()
    listed = set(finished) | set(labs) | set(commercial)
    for room, ids in FURNITURE_CATALOG.items():
        ids = [pid for pid in ids if pid in parts]
        if not ids:
            continue
        sub = home.addMenu(menu_text(room if room != "Other"
                                     else "Other pieces"))
        _add_parts(window, sub, ids, parts)
        listed.update(ids)
    for cat in HOME_CATEGORY_MENUS:            # the categories that are
        ids = [pid for pid, spec in parts.items()      # a menu of their own
               if spec.get("category") == cat and pid not in listed]
        if ids:
            _add_parts(window, home.addMenu(menu_text(cat)), ids, parts)
            listed.update(ids)
    rest = [pid for pid, spec in parts.items()
            if spec.get("category") in categories and pid not in listed]
    if rest:
        _add_parts(window, home.addMenu("Fixtures && other"), rest, parts)
    return home


def _add_examples(window, menu, section, subs):
    """The example documents placed in *section*: at the end of a submenu
    it already has, or in a submenu of their own."""
    from .examples import EXAMPLES
    for where, title, icon, cats in EXAMPLE_PLACES:
        if where != section:
            continue
        items = [(label, build) for label, cat, build in EXAMPLES
                 if cat in cats]
        if not items:
            continue
        sub = subs.get(title)
        if sub is None:
            sub = menu.addMenu(icons.icon(icon), menu_text(title))
        else:
            sub.addSeparator()
        note = sub.addAction(EXAMPLE_NOTE)
        note.setEnabled(False)
        for label, build in items:
            sub.addAction(menu_text(label),
                          lambda _=False, b=build: window._load_example(b))
