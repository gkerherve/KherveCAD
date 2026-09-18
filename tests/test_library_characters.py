"""People & characters (library_characters.py): every figure builds,
the shipped colour maps match their rules, and they sit in the Library.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os

import pytest

from khervecad import library, library_groups
from khervecad import library_characters as C
from khervecad.model import validate


@pytest.mark.parametrize("pid", list(C.PARTS))
def test_every_character_builds_clean(pid):
    spec = library.PARTS[pid]
    for size in spec["sizes"]:
        node = spec["build"]({"_size": size})
        assert not validate(node), (pid, size)
        humans = [n for n in node.walk() if n.type == "human"]
        assert len(humans) == 1


@pytest.mark.parametrize("key", sorted(C.RULES))
def test_shipped_colour_maps_match_their_rules(key):
    size = (4, 4) if key == "skin" else ()
    with open(C.map_path(key), "rb") as fh:
        assert fh.read() == C.png_bytes(C.RULES[key], *size)


def test_paints_point_at_shipped_maps():
    for pid in C.PARTS:
        for n in library.PARTS[pid]["build"]({}).walk():
            if n.type == "paint":
                assert os.path.isfile(n.params["image"])


def test_heroes_are_muscled_and_people_are_not_hands_on_hips():
    hero = C.build_hero({})
    assert any(n.type == "sculpt" and len(n.params["strokes"]) > 10
               for n in hero.walk())
    man = next(n for n in C.build_man({}).walk() if n.type == "human")
    assert man.params["pose"] == C.ARMS_DOWN


def test_characters_have_their_own_library_menu():
    sub = {name: cats for section in library_groups.SECTIONS
           for name, _icon, cats in section[1]}
    assert sub["People & characters"] == ["Characters"]
