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


def test_city_menu_holds_builder_layouts_and_trees(window):
    library = _menu(window.menuBar(), "Library")
    city = _menu(library, "City")
    texts = _texts(city)
    assert texts[0] == "City Builder..."
    assert "New layout (random)" in texts
    trees = _texts(_menu(city, "Trees"))
    assert "Oak" in trees and "Weeping willow" in trees
    assert "Trees" not in _texts(library)
    buildings = _texts(_menu(city, "Buildings"))
    assert "Cottage" in buildings and "Office tower" in buildings
