"""The Library menu: every Lego thing under one Lego menu, and the House
Builder with every home and room piece under one House & home menu, by
room.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication


@pytest.fixture(scope="session")
def app():
    # kept referenced for the session: an unreferenced QApplication is
    # collected and the next widget aborts the process
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    return MainWindow()


def _plain(text):
    """A Qt menu title as it reads: "&&" is an "&", a lone "&" marks
    the shortcut letter."""
    return text.replace("&&", "\0").replace("&", "").replace("\0", "&")


def _menu(parent, text):
    for act in parent.actions():
        if act.menu() is not None and _plain(act.text()) == text:
            return act.menu()
    raise AssertionError(f"no {text!r} menu in "
                         f"{[_plain(a.text()) for a in parent.actions()]}")


def _texts(menu):
    return [_plain(a.text()) for a in menu.actions() if not a.isSeparator()]


def test_lego_tools_bricks_and_sets_share_one_menu(window):
    library = _menu(window.menuBar(), "Library")
    lego = _menu(library, "Lego")
    assert _texts(lego)[:3] == ["Lego Builder...",
                                "Convert Selection to Lego...",
                                "Fuse Lego into One Solid"]
    assert _texts(_menu(lego, "Bricks & plates"))
    assert _texts(_menu(lego, "Lego sets"))
    top = _texts(library)
    for gone in ("Lego sets", "Lego Builder...", "House Builder...",
                 "Home furniture", "Room & furniture"):
        assert gone not in top, gone


def test_house_and_home_has_the_builder_on_top_and_a_menu_per_room(window):
    from khervecad import library
    from khervecad.house import FURNITURE_CATALOG
    home = _menu(_menu(window.menuBar(), "Library"), "House & home")
    assert _texts(home)[0] == "House Builder..."
    for room in ("Living room", "Kitchen", "Bedroom", "Garage",
                 "Garden / outdoor", "Stairs"):
        assert _texts(_menu(home, room)), room
    # every home and room piece is reachable somewhere in it
    labels = set()
    for act in home.actions():
        if act.menu() is not None:
            labels.update(_texts(act.menu()))
    for pid, spec in library.PARTS.items():
        if spec["category"] in ("Home furniture", "Room & furniture"):
            assert spec["label"] in labels, pid
    assert len(FURNITURE_CATALOG) >= 10


def test_city_menu_holds_builder_layouts_and_buildings(window):
    library = _menu(window.menuBar(), "Library")
    city = _menu(library, "City")
    texts = _texts(city)
    assert texts[0] == "City Builder..."
    assert "New layout (random)" in texts
    buildings = _texts(_menu(city, "Buildings"))
    assert "Cottage" in buildings and "Office tower" in buildings
    nature = _menu(library, "Nature & garden")
    trees = _texts(_menu(nature, "Grown trees"))
    assert "Oak" in trees and "Weeping willow" in trees
    assert "Rose" in _texts(_menu(nature, "Flowers"))
    assert "Trees" not in _texts(library)


def test_library_is_sections_and_every_category_is_placed_once():
    from khervecad import library
    from khervecad.library_groups import SECTIONS, entry_categories
    cats = {spec["category"] for spec in library.PARTS.values()}
    placed = []
    for _title, entries in SECTIONS:
        for _name, _icon, spec in entries:
            placed += [c for c in entry_categories(spec, sorted(cats))[1]
                       if c in cats]
    assert sorted(placed) == sorted(cats)       # all, and none twice


def test_library_menu_reads_in_sections(window):
    top = _texts(_menu(window.menuBar(), "Library"))
    heads = [t for t in top if t.isupper()]
    assert heads == ["ENGINEERING", "BUILDINGS & PLACES", "SCIENCE",
                     "TOYS & MODELS", "LEARN"]
    assert top.index("House & home") > top.index("BUILDINGS & PLACES")
    assert top.index("Lego") > top.index("TOYS & MODELS")


def test_examples_live_in_the_library_and_open_as_documents(window):
    from khervecad.examples import EXAMPLES
    from khervecad.library_menu import EXAMPLE_NOTE
    bar = _texts(window.menuBar())
    assert "Examples" not in bar
    library = _menu(window.menuBar(), "Library")
    found = {}

    def walk(menu):
        texts = _texts(menu)
        if EXAMPLE_NOTE in texts:
            for t in texts[texts.index(EXAMPLE_NOTE) + 1:]:
                found[t] = found.get(t, 0) + 1
        for act in menu.actions():
            if act.menu() is not None:
                walk(act.menu())
    walk(library)
    for label, cat, _build in EXAMPLES:
        if cat in ("Learn", "Mechanical", "Projects", "Showcase", "Vacuum",
                   "Room"):
            assert found.get(label) == 1, label
    for gone in ("Rose", "Palm", "Dragon", "Minecraft tower"):
        assert gone not in found
    engineering = _menu(library, "Mechanical examples")
    assert "Meshing gear pair" in _texts(engineering)
    assert "Vacuum starter (CF tee + turbo)" in _texts(
        _menu(library, "Vacuum & UHV"))


def test_hand_tools_are_split_into_submenus(window):
    from khervecad import library
    from khervecad.library_kcad import TOOL_GROUP_ORDER
    tools = _menu(_menu(window.menuBar(), "Library"), "Hand tools")
    top = _texts(tools)
    # a flat list of 57 tools was unreadable — every action here is a
    # submenu, never a tool inserted straight into "Hand tools"
    assert all(act.menu() is not None for act in tools.actions())
    labels = set()
    for group in top:
        assert group in TOOL_GROUP_ORDER, group
        labels.update(_texts(_menu(tools, group)))
    for pid, spec in library.PARTS.items():
        if spec["category"] == "Tools":
            assert spec["label"] in labels, pid


def test_flowers_and_stylised_trees_insert_as_parts():
    from khervecad import library, mesh
    from khervecad.model import validate
    for pid in ("flower_rose", "stylised_palm"):
        node = library.default_part(pid)
        assert not validate(node)
        assert mesh.tessellate(node, fn=12)
