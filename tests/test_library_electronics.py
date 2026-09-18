"""Electronics library (library_electronics.py): boards at their
published sizes, components, lab equipment and the Electronics lab.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest

from khervecad import house as H
from khervecad import house_designs as D
from khervecad import house_templates, library, library_groups, mesh
from khervecad import library_electronics as E
from khervecad.model import validate


@pytest.mark.parametrize("pid", list(E.PARTS))
def test_every_part_builds_clean_in_every_size(pid):
    spec = library.PARTS[pid]
    for size in spec["sizes"]:
        node = spec["build"]({"_size": size})
        assert not validate(node), (pid, size)
        assert mesh.tessellate(node), (pid, size)


# the PCB's outline (length, width) from the makers' drawings
BOARDS = {"elec_arduino_nano": (45.0, 18.0), "elec_arduino_mega": (101.6, 53.3),
          "elec_pi_pico": (51.0, 21.0), "elec_pi_zero2w": (65.0, 30.0),
          "elec_pi5": (85.0, 56.0), "elec_teensy40": (35.6, 17.8),
          "elec_microbit": (52.0, 42.0), "elec_esp32": (54.4, 27.9)}


@pytest.mark.parametrize("pid", list(BOARDS))
def test_boards_have_their_published_outline(pid):
    node = library.PARTS[pid]["build"]({})
    pcb = next(n for n in node.walk() if n.name == "PCB")
    xs = [p[0] for t in mesh.tessellate(pcb) for p in t]
    ys = [p[1] for t in mesh.tessellate(pcb) for p in t]
    assert max(xs) - min(xs) == pytest.approx(BOARDS[pid][0], abs=0.2)
    assert max(ys) - min(ys) == pytest.approx(BOARDS[pid][1], abs=0.2)


def test_resistor_colour_code():
    brown, black, red, orange, yellow, violet = (E.BAND[i]
                                                 for i in (1, 0, 2, 3, 4, 7))
    assert E.bands(1000)[:3] == [brown, black, red]
    assert E.bands(4700)[:3] == [yellow, violet, red]
    assert E.bands(220)[:3] == [red, red, brown]
    assert E.bands(10000)[:3] == [brown, black, orange]


def test_electronics_has_its_own_library_menu():
    sub = {name: cats for section in library_groups.SECTIONS
           for name, _icon, cats in section[1]}
    assert sub["Electronics"] == ["Electronics boards",
                                  "Electronic components",
                                  "Electronics lab"]


def test_electronics_lab_is_a_finished_lab_and_a_template():
    assert "Electronics lab" in house_templates.names()
    spec = library.PARTS["building_electronics_lab"]
    assert spec["category"] == D.LAB_CATEGORY
    home = H.house_from_spec(D.LABS["building_electronics_lab"][1]("", True))
    lab = next(r for r in home.floors[0].rooms if r.name == "Electronics lab")
    benches = [f for f in lab.furniture if f.part_id == "elec_esd_bench"]
    assert len(benches) >= 6
    for f in lab.furniture:                   # everything landed on a bench
        if library.PARTS[f.part_id].get("on_top"):
            assert f.z > 800, f.part_id
    assert not validate(D.build_design("building_electronics_lab",
                                       {"furnished": 1}))
